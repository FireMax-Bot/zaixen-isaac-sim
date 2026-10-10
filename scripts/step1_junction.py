import omni.usd
from pxr import Usd, UsdGeom, UsdShade, UsdLux, UsdPhysics, Sdf, Gf

ctx = omni.usd.get_context()
stage = ctx.get_stage()

for p in ("/World/Junction", "/World/Looks", "/World/Lights"):
    prim = stage.GetPrimAtPath(p)
    if prim.IsValid():
        stage.RemovePrim(p)

# ---------- helpers ----------
def make_material(path, color, roughness=0.8, metallic=0.0):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat

def make_box(path, size, translate, material=None, color=None):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(cube)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(material)
    return cube

# ---------- scope ----------
scope = UsdGeom.Scope.Define(stage, "/World/Junction")

# ---------- materials ----------
mat_scope = "/World/Looks"
grass_mat = make_material(mat_scope + "/Grass", (0.10, 0.45, 0.12), roughness=0.95)
road_mat = make_material(mat_scope + "/Road", (0.08, 0.08, 0.09), roughness=0.7)
sidewalk_mat = make_material(mat_scope + "/Sidewalk", (0.75, 0.75, 0.72), roughness=0.85)

# ---------- lighting ----------
dome = UsdLux.DomeLight.Define(stage, "/World/Lights/DomeLight")
dome.CreateIntensityAttr(400.0)
dome.CreateColorAttr(Gf.Vec3f(0.95, 0.97, 1.0))

distant = UsdLux.DistantLight.Define(stage, "/World/Lights/SunLight")
distant.CreateIntensityAttr(800.0)
distant.CreateColorAttr(Gf.Vec3f(1.0, 0.98, 0.92))
distant.CreateAngleAttr(1.0)
UsdGeom.Xformable(distant).AddRotateXYZOp().Set(Gf.Vec3f(-55.0, 20.0, 0.0))

# ---------- ground ----------
ground = make_box("/World/Junction/Ground", (40.0, 40.0, 0.1), (0.0, 0.0, -0.05), grass_mat)
UsdPhysics.CollisionAPI.Apply(ground.GetPrim())  # so rigid bodies (ego) rest on it instead of free-falling

# ---------- roads (2 lanes each, 1.0 m/lane -> 2.0 m wide, 30 m arm-to-arm) ----------
ROAD_HALF_W = 1.0     # half width of road (2 lanes x 1.0 m)
ARM_LEN = 15.0         # each arm extends 15 m from center
ROAD_Z = 0.01

make_box("/World/Junction/Road_X", (ARM_LEN * 2.0, ROAD_HALF_W * 2.0, 0.02), (0.0, 0.0, ROAD_Z), road_mat)
make_box("/World/Junction/Road_Y", (ROAD_HALF_W * 2.0, ARM_LEN * 2.0, 0.02), (0.0, 0.0, ROAD_Z), road_mat)

# ---------- sidewalks (0.6 m strips flanking each arm, leaving the junction square clear) ----------
SW_W = 0.6
JUNC_HALF = ROAD_HALF_W  # 1.0 m half-extent of the crossing square
SW_LEN = ARM_LEN - JUNC_HALF  # 14 m
SW_CENTER_OFFSET = JUNC_HALF + SW_W / 2.0  # 1.3 m from road centerline
SW_ARM_CENTER = JUNC_HALF + SW_LEN / 2.0   # 8 m from origin along the arm

# Arms along X (roads running east-west): sidewalks run along X, offset in Y
for side, sy in (("N", 1), ("S", -1)):
    for arm, sx in (("E", 1), ("W", -1)):
        make_box(
            f"/World/Junction/Sidewalk_X_{arm}_{side}",
            (SW_LEN, SW_W, 0.03),
            (sx * SW_ARM_CENTER, sy * SW_CENTER_OFFSET, ROAD_Z + 0.005),
            sidewalk_mat,
        )

# Arms along Y (roads running north-south): sidewalks run along Y, offset in X
for side, sx in (("E", 1), ("W", -1)):
    for arm, sy in (("N", 1), ("S", -1)):
        make_box(
            f"/World/Junction/Sidewalk_Y_{arm}_{side}",
            (SW_W, SW_LEN, 0.03),
            (sx * SW_CENTER_OFFSET, sy * SW_ARM_CENTER, ROAD_Z + 0.005),
            sidewalk_mat,
        )

print("STEP1 OK - prims under /World/Junction and /World/Looks created")
for p in stage.Traverse():
    print(p.GetPath())
