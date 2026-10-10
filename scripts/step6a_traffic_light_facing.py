import math
import omni.usd
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

stage = omni.usd.get_context().get_stage()

if stage.GetPrimAtPath("/World/Junction/TrafficLights").IsValid():
    stage.RemovePrim("/World/Junction/TrafficLights")

def make_material(path, color, roughness=0.5, emissive=None):
    if stage.GetPrimAtPath(path).IsValid():
        return UsdShade.Material(stage.GetPrimAtPath(path))
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    if emissive is not None:
        shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*emissive))
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat

mat_scope = "/World/Looks"
pole_mat = UsdShade.Material(stage.GetPrimAtPath(mat_scope + "/PoleMetal")) \
    if stage.GetPrimAtPath(mat_scope + "/PoleMetal").IsValid() \
    else make_material(mat_scope + "/PoleMetal", (0.12, 0.12, 0.13), roughness=0.4)

OFF = (0.03, 0.03, 0.03)
sig_mats = {}
for axis in ("X", "Y"):
    sig_mats[(axis, "red")] = make_material(f"{mat_scope}/Signal_{axis}_Red", (0.3, 0.0, 0.0), emissive=OFF)
    sig_mats[(axis, "amber")] = make_material(f"{mat_scope}/Signal_{axis}_Amber", (0.3, 0.2, 0.0), emissive=OFF)
    sig_mats[(axis, "green")] = make_material(f"{mat_scope}/Signal_{axis}_Green", (0.0, 0.3, 0.0), emissive=OFF)

POLE_HEIGHT = 1.2
POLE_R = 0.03
HEAD_W, HEAD_D, HEAD_H = 0.14, 0.10, 0.32  # width(local X), depth/face-axis(local Y), height

# each pole sits at a corner and its head FACES the oncoming traffic it controls
# (face vector = world direction the lens points, i.e. back toward the approaching cars)
POLES = [
    ("Y1", "Y", (1.3, 1.3), (0.0, -1.0)),    # NE corner, controls northbound approach -> faces south
    ("Y2", "Y", (-1.3, -1.3), (0.0, 1.0)),   # SW corner, controls southbound approach -> faces north
    ("X1", "X", (-1.3, 1.3), (1.0, 0.0)),    # NW corner, controls westbound approach -> faces east
    ("X2", "X", (1.3, -1.3), (-1.0, 0.0)),   # SE corner, controls eastbound approach -> faces west
]

def rotate_z_for_face(fx, fy):
    # local +Y (the face/lens axis) rotated by theta about Z -> (-sin(theta), cos(theta))
    # solve theta so that (-sin(theta), cos(theta)) == (fx, fy)
    return math.degrees(math.atan2(-fx, fy))

def make_cylinder(path, radius, height, translate, material=None, axis="Z"):
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

def make_box_rotated(path, size, translate, rotate_z_deg, material=None):
    geo = UsdGeom.Cube.Define(stage, path)
    geo.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xf.AddRotateZOp().Set(rotate_z_deg)
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
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

TRAFFIC_LIGHT_PATHS = {"X": {"red": [], "amber": [], "green": []}, "Y": {"red": [], "amber": [], "green": []}}

for name, axis, (px, py), (fx, fy) in POLES:
    base = f"/World/Junction/TrafficLights/Pole_{name}"
    make_cylinder(base + "/PoleBody", POLE_R, POLE_HEIGHT, (px, py, POLE_HEIGHT / 2.0), pole_mat)

    rot_deg = rotate_z_for_face(fx, fy)
    head_z = POLE_HEIGHT + HEAD_H / 2.0
    make_box_rotated(base + "/Head", (HEAD_W, HEAD_D, HEAD_H), (px, py, head_z), rot_deg, pole_mat)

    light_r = 0.045
    z_top = POLE_HEIGHT + HEAD_H - light_r - 0.02
    z_mid = POLE_HEIGHT + HEAD_H / 2.0
    z_bot = POLE_HEIGHT + light_r + 0.02
    offset = HEAD_D / 2.0 + light_r * 0.6
    lx, ly = px + fx * offset, py + fy * offset

    red_path = base + "/Light_Red"
    amber_path = base + "/Light_Amber"
    green_path = base + "/Light_Green"
    make_sphere(red_path, light_r, (lx, ly, z_top), sig_mats[(axis, "red")])
    make_sphere(amber_path, light_r, (lx, ly, z_mid), sig_mats[(axis, "amber")])
    make_sphere(green_path, light_r, (lx, ly, z_bot), sig_mats[(axis, "green")])
    TRAFFIC_LIGHT_PATHS[axis]["red"].append(red_path)
    TRAFFIC_LIGHT_PATHS[axis]["amber"].append(amber_path)
    TRAFFIC_LIGHT_PATHS[axis]["green"].append(green_path)

# re-apply the currently active phase colors so the rebuilt lights immediately show the right state
COLOR_EMISSIVE = {
    "red": Gf.Vec3f(18.0, 0.0, 0.0),
    "amber": Gf.Vec3f(18.0, 10.0, 0.0),
    "green": Gf.Vec3f(0.0, 18.0, 0.0),
}
OFF_EMISSIVE = Gf.Vec3f(*OFF)
PHASE_TO_COLOR = {"GREEN": "green", "YELLOW": "amber", "RED": "red"}

def set_axis_phase(axis, phase):
    active_color = PHASE_TO_COLOR[phase]
    for color in ("red", "amber", "green"):
        mat_path = f"{mat_scope}/Signal_{axis}_{color.capitalize()}"
        shader = UsdShade.Shader(stage.GetPrimAtPath(mat_path + "/Shader"))
        val = COLOR_EMISSIVE[color] if color == active_color else OFF_EMISSIVE
        shader.GetInput("emissiveColor").Set(val)

try:
    set_axis_phase("X", TRAFFIC_STATE["X"])  # noqa: F821
    set_axis_phase("Y", TRAFFIC_STATE["Y"])  # noqa: F821
except NameError:
    set_axis_phase("X", "RED")
    set_axis_phase("Y", "GREEN")

print("STEP6A OK - traffic lights rebuilt with correct facing")
