# SUPERSEDED by zaixen_traffic.py (run_simulation.py arms it). Do not run this together with it: two drivers would fight over the same cars/lights.
import time
import math
import omni.usd
import omni.kit.app
from pxr import Usd, UsdGeom, UsdShade, UsdPhysics, Sdf, Gf

ctx = omni.usd.get_context()
stage = ctx.get_stage()

# clean up any previous run (unsubscribe old mover timer first)
try:
    if NPC_MOVER_SUB is not None:  # noqa: F821
        NPC_MOVER_SUB.unsubscribe()  # noqa: F821
except NameError:
    pass
NPC_MOVER_SUB = None

if stage.GetPrimAtPath("/World/Junction/NPCCars").IsValid():
    stage.RemovePrim("/World/Junction/NPCCars")

def make_material(path, color, roughness=0.4):
    if stage.GetPrimAtPath(path).IsValid():
        return UsdShade.Material(stage.GetPrimAtPath(path))
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat

def make_box(path, size, translate, material=None, collision=False):
    geo = UsdGeom.Cube.Define(stage, path)
    geo.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geo.GetPrim()).Bind(material)
    if collision:
        UsdPhysics.CollisionAPI.Apply(geo.GetPrim())
    return geo

def make_cylinder(path, radius, height, translate, material=None, axis="Y"):
    geo = UsdGeom.Cylinder.Define(stage, path)
    geo.CreateRadiusAttr(radius)
    geo.CreateHeightAttr(height)
    geo.CreateAxisAttr(axis)
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geo.GetPrim()).Bind(material)
    return geo

mat_scope = "/World/Looks"
wheel_mat = make_material(mat_scope + "/WheelRubber", (0.03, 0.03, 0.03), roughness=0.9)
window_mat = make_material(mat_scope + "/CarWindow", (0.05, 0.08, 0.12), roughness=0.15)

CAR_COLORS = [
    ("Red", (0.75, 0.08, 0.08)),
    ("Blue", (0.08, 0.20, 0.75)),
    ("Yellow", (0.85, 0.70, 0.05)),
    ("Orange", (0.85, 0.40, 0.05)),
    ("Purple", (0.45, 0.10, 0.65)),
    ("Teal", (0.05, 0.55, 0.55)),
    ("White", (0.85, 0.85, 0.85)),
    ("Lime", (0.45, 0.75, 0.10)),
]

CAR_LEN, CAR_W, CAR_H = 0.8, 0.4, 0.35
CABIN_LEN, CABIN_W, CABIN_H = 0.42, 0.30, 0.16
WHEEL_R, WHEEL_THICK = 0.09, 0.06

ROAD_HALF_W = 1.0
JUNC_HALF = ROAD_HALF_W
ARM_LEN = 15.0
LANE_OFFSET = 0.5  # right-hand lane centerline offset from road centerline

scope = UsdGeom.Scope.Define(stage, "/World/Junction/NPCCars")

# lane definitions: axis of travel, direction sign, perpendicular lane offset, heading (deg, 0 = +X local forward)
LANES = {
    ("X", 1): {"offset": -LANE_OFFSET, "heading": 0.0},     # eastbound
    ("X", -1): {"offset": LANE_OFFSET, "heading": 180.0},   # westbound
    ("Y", 1): {"offset": LANE_OFFSET, "heading": 90.0},      # northbound
    ("Y", -1): {"offset": -LANE_OFFSET, "heading": -90.0},   # southbound
}

# (axis, dir, start_s) for each of the 8 NPC cars
CAR_SPECS = [
    ("X", 1, -10.0),
    ("X", 1, 2.0),
    ("X", -1, 10.0),
    ("X", -1, -5.0),
    ("Y", 1, -10.0),
    ("Y", 1, 3.0),
    ("Y", -1, 10.0),
    ("Y", -1, -4.0),
]

def build_car(index, axis, direction, s0, color_name, color):
    path = f"/World/Junction/NPCCars/Car_{index:02d}_{color_name}"
    car_xf = UsdGeom.Xform.Define(stage, path)
    lane = LANES[(axis, direction)]
    offset = lane["offset"]
    heading = lane["heading"]
    x, y = (s0, offset) if axis == "X" else (offset, s0)

    xf = UsdGeom.Xformable(car_xf)
    xf.ClearXformOpOrder()
    t_op = xf.AddTranslateOp()
    t_op.Set(Gf.Vec3d(x, y, 0.0))
    r_op = xf.AddRotateZOp()
    r_op.Set(heading)

    body_mat = make_material(f"{mat_scope}/Car_{color_name}", color)

    make_box(path + "/Body", (CAR_LEN, CAR_W, CAR_H), (0.0, 0.0, CAR_H / 2.0), body_mat, collision=True)
    cabin_z = CAR_H + CABIN_H / 2.0
    make_box(path + "/Cabin", (CABIN_LEN, CABIN_W, CABIN_H), (-0.05, 0.0, cabin_z), body_mat)
    # simple window faces (front + rear glass plates on the cabin)
    make_box(path + "/WindowFront", (0.02, CABIN_W * 0.92, CABIN_H * 0.75),
             (-0.05 + CABIN_LEN / 2.0 - 0.01, 0.0, cabin_z), window_mat)
    make_box(path + "/WindowRear", (0.02, CABIN_W * 0.92, CABIN_H * 0.75),
             (-0.05 - CABIN_LEN / 2.0 + 0.01, 0.0, cabin_z), window_mat)

    wx = CAR_LEN / 2.0 - WHEEL_R - 0.06
    wy = CAR_W / 2.0 + WHEEL_THICK / 2.0 - 0.01
    for wname, (sx, sy) in (
        ("FL", (wx, wy)), ("FR", (wx, -wy)), ("RL", (-wx, wy)), ("RR", (-wx, -wy))
    ):
        make_cylinder(path + f"/Wheel_{wname}", WHEEL_R, WHEEL_THICK, (sx, sy, WHEEL_R), wheel_mat, axis="Y")

    return path, t_op, offset

NPC_CARS = []
for i, (axis, direction, s0) in enumerate(CAR_SPECS):
    color_name, color = CAR_COLORS[i % len(CAR_COLORS)]
    path, t_op, offset = build_car(i, axis, direction, s0, color_name, color)
    NPC_CARS.append({
        "path": path,
        "t_op": t_op,
        "axis": axis,
        "dir": direction,
        "offset": offset,
        "s": s0,
    })

# ---------- kinematic mover ----------
NPC_SPEED = 1.2  # m/s

def _npc_is_stopped(axis, direction, s):
    approaching = (s * direction) < -1e-6  # moving toward the origin
    if not approaching:
        return False
    if abs(s) <= JUNC_HALF:
        return False  # already at/within the junction, let it clear
    phase = TRAFFIC_STATE.get(axis)  # noqa: F821 (defined by traffic light script in this context)
    return phase in ("RED", "YELLOW")

_npc_last_time = time.time()

def _npc_mover_on_update(e):
    global _npc_last_time
    now = time.time()
    dt = now - _npc_last_time
    _npc_last_time = now
    if dt <= 0 or dt > 0.5:
        return
    for car in NPC_CARS:
        axis, direction, s = car["axis"], car["dir"], car["s"]
        if not _npc_is_stopped(axis, direction, s):
            s += direction * NPC_SPEED * dt
            if s > ARM_LEN:
                s = -ARM_LEN
            elif s < -ARM_LEN:
                s = ARM_LEN
            car["s"] = s
            x, y = (s, car["offset"]) if axis == "X" else (car["offset"], s)
            car["t_op"].Set(Gf.Vec3d(x, y, 0.0))

_update_stream = omni.kit.app.get_app().get_update_event_stream()
NPC_MOVER_SUB = _update_stream.create_subscription_to_pop(_npc_mover_on_update, name="npc_car_mover")

print("STEP5 OK - NPC cars created:", len(NPC_CARS))
for c in NPC_CARS:
    print(" ", c["path"], "axis", c["axis"], "dir", c["dir"], "s0", c["s"])
