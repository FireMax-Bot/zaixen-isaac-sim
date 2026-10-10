import time
import omni.usd
import omni.kit.app
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

ctx = omni.usd.get_context()
stage = ctx.get_stage()

# clean up any previous run (unsubscribe old timer first)
try:
    if TRAFFIC_LIGHT_SUB is not None:  # noqa: F821
        TRAFFIC_LIGHT_SUB.unsubscribe()  # noqa: F821
except NameError:
    pass
TRAFFIC_LIGHT_SUB = None

if stage.GetPrimAtPath("/World/Junction/TrafficLights").IsValid():
    stage.RemovePrim("/World/Junction/TrafficLights")

def make_material(path, color, roughness=0.5, emissive=None):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    if emissive is not None:
        shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*emissive))
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat

def make_box(path, size, translate, material=None):
    geo = UsdGeom.Cube.Define(stage, path)
    geo.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geo.GetPrim()).Bind(material)
    return geo

def make_cylinder(path, radius, height, translate, material=None):
    geo = UsdGeom.Cylinder.Define(stage, path)
    geo.CreateRadiusAttr(radius)
    geo.CreateHeightAttr(height)
    geo.CreateAxisAttr("Z")
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geo.GetPrim()).Bind(material)
    return geo

def make_sphere(path, radius, translate, material=None):
    geo = UsdGeom.Sphere.Define(stage, path)
    geo.CreateRadiusAttr(radius)
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geo.GetPrim()).Bind(material)
    return geo

mat_scope = "/World/Looks"
pole_mat = make_material(mat_scope + "/PoleMetal", (0.12, 0.12, 0.13), roughness=0.4)

OFF = (0.03, 0.03, 0.03)
sig_mats = {}
for axis in ("X", "Y"):
    sig_mats[(axis, "red")] = make_material(f"{mat_scope}/Signal_{axis}_Red", (0.3, 0.0, 0.0), emissive=OFF)
    sig_mats[(axis, "amber")] = make_material(f"{mat_scope}/Signal_{axis}_Amber", (0.3, 0.2, 0.0), emissive=OFF)
    sig_mats[(axis, "green")] = make_material(f"{mat_scope}/Signal_{axis}_Green", (0.0, 0.3, 0.0), emissive=OFF)

POLE_HEIGHT = 1.2
POLE_R = 0.03
HEAD_SIZE = (0.14, 0.10, 0.32)

# diagonal corners: Y-axis road (N/S arms) controlled by NE+SW poles,
# X-axis road (E/W arms) controlled by NW+SE poles
POLES = [
    ("Y1", "Y", (1.3, 1.3)),
    ("Y2", "Y", (-1.3, -1.3)),
    ("X1", "X", (-1.3, 1.3)),
    ("X2", "X", (1.3, -1.3)),
]

TRAFFIC_LIGHT_PATHS = {"X": {"red": [], "amber": [], "green": []}, "Y": {"red": [], "amber": [], "green": []}}

import math

for name, axis, (px, py) in POLES:
    base = f"/World/Junction/TrafficLights/Pole_{name}"
    make_cylinder(base + "/PoleBody", POLE_R, POLE_HEIGHT, (px, py, POLE_HEIGHT / 2.0), pole_mat)
    head_z = POLE_HEIGHT + HEAD_SIZE[2] / 2.0
    make_box(base + "/Head", HEAD_SIZE, (px, py, head_z), pole_mat)
    light_r = 0.045
    z_top = POLE_HEIGHT + HEAD_SIZE[2] - light_r - 0.02
    z_mid = POLE_HEIGHT + HEAD_SIZE[2] / 2.0
    z_bot = POLE_HEIGHT + light_r + 0.02
    # protrude lights out of the head's junction-facing side so they aren't buried in solid geometry
    d = math.hypot(px, py)
    dx, dy = (-px / d, -py / d) if d > 1e-6 else (0.0, 0.0)
    offset = HEAD_SIZE[1] / 2.0 + light_r * 0.6
    lx, ly = px + dx * offset, py + dy * offset
    red_path = base + "/Light_Red"
    amber_path = base + "/Light_Amber"
    green_path = base + "/Light_Green"
    make_sphere(red_path, light_r, (lx, ly, z_top), sig_mats[(axis, "red")])
    make_sphere(amber_path, light_r, (lx, ly, z_mid), sig_mats[(axis, "amber")])
    make_sphere(green_path, light_r, (lx, ly, z_bot), sig_mats[(axis, "green")])
    TRAFFIC_LIGHT_PATHS[axis]["red"].append(red_path)
    TRAFFIC_LIGHT_PATHS[axis]["amber"].append(amber_path)
    TRAFFIC_LIGHT_PATHS[axis]["green"].append(green_path)

# ---------- timer-driven phase cycle ----------
COLOR_EMISSIVE = {
    "red": Gf.Vec3f(18.0, 0.0, 0.0),
    "amber": Gf.Vec3f(18.0, 10.0, 0.0),
    "green": Gf.Vec3f(0.0, 18.0, 0.0),
}
OFF_EMISSIVE = Gf.Vec3f(*OFF)

def phase_for(t):
    if t < 8.0:
        return "GREEN"
    elif t < 10.0:
        return "YELLOW"
    else:
        return "RED"

PHASE_TO_COLOR = {"GREEN": "green", "YELLOW": "amber", "RED": "red"}

def set_axis_phase(axis, phase):
    active_color = PHASE_TO_COLOR[phase]
    for color in ("red", "amber", "green"):
        mat_path = f"{mat_scope}/Signal_{axis}_{color.capitalize()}"
        shader = UsdShade.Shader(stage.GetPrimAtPath(mat_path + "/Shader"))
        val = COLOR_EMISSIVE[color] if color == active_color else OFF_EMISSIVE
        shader.GetInput("emissiveColor").Set(val)

TRAFFIC_STATE = {"X": None, "Y": None, "t": 0.0, "cycle_len": 20.0}

_traffic_start_time = time.time()

def _traffic_light_on_update(e):
    t = (time.time() - _traffic_start_time) % 20.0
    y_phase = phase_for(t)
    x_phase = phase_for((t + 10.0) % 20.0)
    if TRAFFIC_STATE["Y"] != y_phase:
        set_axis_phase("Y", y_phase)
        TRAFFIC_STATE["Y"] = y_phase
    if TRAFFIC_STATE["X"] != x_phase:
        set_axis_phase("X", x_phase)
        TRAFFIC_STATE["X"] = x_phase
    TRAFFIC_STATE["t"] = t

# initialize once immediately (t=0 -> Y GREEN, X RED)
set_axis_phase("Y", "GREEN")
set_axis_phase("X", "RED")
TRAFFIC_STATE["Y"] = "GREEN"
TRAFFIC_STATE["X"] = "RED"

_update_stream = omni.kit.app.get_app().get_update_event_stream()
TRAFFIC_LIGHT_SUB = _update_stream.create_subscription_to_pop(_traffic_light_on_update, name="traffic_light_timer")

print("STEP3 OK - traffic lights created, timer subscription active")
print("TRAFFIC_STATE:", TRAFFIC_STATE)
print("Pole prims:")
for p in stage.Traverse():
    if str(p.GetPath()).startswith("/World/Junction/TrafficLights"):
        print(" ", p.GetPath())
