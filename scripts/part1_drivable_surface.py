# PART 1 -- drivable surface. Idempotent; safe to re-run (stop the timeline first).
#
# Single source of truth for the road height is the stage attribute
#   /World/Junction.zaixen:roadSurfaceZ
# NPC placement (rearm_npc_movers.py) and the ego wheel-contact seat both read it.
#
# What this does
#   1. asserts the visual road slabs' top == ROAD_TOP
#   2. adds static colliders to every drivable / walkable slab (roads, sidewalks)
#   3. creates physics materials (asphalt grip, pavement, grass) and binds them
#      with the "physics" purpose so the visual materials are untouched
#   4. puts every NPC car's tyres at ROAD_TOP
#   5. re-seats the ego so its lowest wheel bottom is a hair above ROAD_TOP
import omni.usd
import omni.timeline
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema, Sdf, Gf

assert not omni.timeline.get_timeline_interface().is_playing(), "stop the timeline first"
stage = omni.usd.get_context().get_stage()

ROAD_TOP = 0.02          # <- the ONE height value (m)
SEAT_CLEARANCE = 0.003   # ego wheels start this far above the road, then settle

junction = stage.GetPrimAtPath("/World/Junction")
attr = junction.CreateAttribute("zaixen:roadSurfaceZ", Sdf.ValueTypeNames.Double, custom=True)
attr.Set(ROAD_TOP)

# ---- 1. visual road top must equal ROAD_TOP -------------------------------
bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
def top_z(path):
    return bbox.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange().GetMax()[2]
for road in ("Road_X", "Road_Y"):
    z = top_z(f"/World/Junction/{road}")
    assert abs(z - ROAD_TOP) < 1e-6, f"{road} visual top {z} != ROAD_TOP {ROAD_TOP}"

# ---- 3. physics materials --------------------------------------------------
UsdGeom.Scope.Define(stage, "/World/PhysicsMaterials")
def make_phys_material(name, static, dynamic, restitution, fric_mode, rest_mode):
    path = f"/World/PhysicsMaterials/{name}"
    mat = UsdShade.Material.Define(stage, path)
    prim = mat.GetPrim()
    api = UsdPhysics.MaterialAPI.Apply(prim)
    api.CreateStaticFrictionAttr(static)
    api.CreateDynamicFrictionAttr(dynamic)
    api.CreateRestitutionAttr(restitution)
    px = PhysxSchema.PhysxMaterialAPI.Apply(prim)
    px.CreateFrictionCombineModeAttr(fric_mode)
    px.CreateRestitutionCombineModeAttr(rest_mode)
    return mat

# "max" friction: the higher of road/tyre wins (tyre asset is 0.9/0.8) -> deterministic grip.
# "min" restitution: the tyre asset ships restitution 0.7; min() with 0 stops it bouncing.
asphalt = make_phys_material("Asphalt", 1.0, 0.9, 0.0, "max", "min")
pavement = make_phys_material("Pavement", 0.9, 0.8, 0.0, "max", "min")
grass = make_phys_material("Grass", 0.8, 0.7, 0.0, "average", "min")

def bind_physics(prim, mat):
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat, UsdShade.Tokens.weakerThanDescendants, "physics")

# ---- 2 + 3. colliders + binding -------------------------------------------
n = 0
for child in stage.GetPrimAtPath("/World/Junction").GetChildren():
    name = child.GetName()
    if name in ("Ground",):
        mat = grass
    elif name.startswith("Road_"):
        mat = asphalt
    elif name.startswith("Sidewalk_"):
        mat = pavement
    else:
        continue
    UsdPhysics.CollisionAPI.Apply(child)     # static: no RigidBodyAPI
    bind_physics(child, mat)
    n += 1
print(f"colliders on {n} slabs; road top z = {ROAD_TOP}")

# ---- 4. NPC tyre height -----------------------------------------------------
for car in stage.GetPrimAtPath("/World/Junction/NPCCars").GetChildren():
    for op in UsdGeom.Xformable(car).GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            t = op.Get()
            op.Set(Gf.Vec3d(t[0], t[1], ROAD_TOP))

# ---- 5. re-seat ego ---------------------------------------------------------
# Only ever done ONCE per ego (flag zaixen:seated). Re-running it is NOT idempotent: the wheel meshes' bounding
# boxes do not equal their collision shapes, so seating from the bboxes again drives the ego into the road.
# step4_ego.py rebuilds /World/Ego, which drops the flag and lets this seat the fresh ego once.
ego = stage.GetPrimAtPath("/World/Ego")
if ego.GetAttribute("zaixen:seated").IsValid():
    print("ego already seated -- left untouched")
else:
    rb = stage.GetPrimAtPath("/World/Ego/leatherback/Rigid_Bodies")
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    wheel_bottoms = [bbox.ComputeWorldBound(rb.GetChild(w)).ComputeAlignedRange().GetMin()[2]
                     for w in ("Wheel_Rear_Right", "Wheel_Rear_Left", "Wheel_Front_Right", "Wheel_Front_Left")]
    ego_xf = UsdGeom.Xformable(ego)
    t_op = [o for o in ego_xf.GetOrderedXformOps() if o.GetOpType() == UsdGeom.XformOp.TypeTranslate][0]
    t = t_op.Get()
    new_z = t[2] + (ROAD_TOP + SEAT_CLEARANCE) - min(wheel_bottoms)
    t_op.Set(Gf.Vec3d(t[0], t[1], new_z))
    ego.CreateAttribute("zaixen:seated", Sdf.ValueTypeNames.Bool, custom=True).Set(True)
    print(f"ego root z {t[2]:.4f} -> {new_z:.4f}  (lowest wheel bottom was {min(wheel_bottoms):.4f})")
