import random
import omni.usd
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

stage = omni.usd.get_context().get_stage()

if stage.GetPrimAtPath("/World/Junction/Greenery").IsValid():
    stage.RemovePrim("/World/Junction/Greenery")

def make_material(path, color, roughness=0.7):
    if stage.GetPrimAtPath(path).IsValid():
        return UsdShade.Material(stage.GetPrimAtPath(path))
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat

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

def make_sphere(path, radius, translate, material=None, scale=None):
    geo = UsdGeom.Sphere.Define(stage, path)
    geo.CreateRadiusAttr(radius)
    xf = UsdGeom.Xformable(geo)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if scale is not None:
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geo.GetPrim()).Bind(material)
    return geo

def make_cone(path, radius, height, translate, material=None, axis="Z"):
    geo = UsdGeom.Cone.Define(stage, path)
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
trunk_mat = make_material(mat_scope + "/TreeTrunk", (0.30, 0.18, 0.08), roughness=0.9)
canopy_mats = [
    make_material(mat_scope + "/TreeCanopyA", (0.10, 0.40, 0.10), roughness=0.85),
    make_material(mat_scope + "/TreeCanopyB", (0.15, 0.50, 0.15), roughness=0.85),
    make_material(mat_scope + "/TreeCanopyC", (0.08, 0.35, 0.18), roughness=0.85),
]
lamp_pole_mat = make_material(mat_scope + "/LampPole", (0.15, 0.15, 0.16), roughness=0.4)
lamp_glow_mat = make_material(mat_scope + "/LampGlow", (0.95, 0.92, 0.75), roughness=0.3)

scope = UsdGeom.Scope.Define(stage, "/World/Junction/Greenery")

# ---------- trees scattered across the 4 grass quadrants ----------
ROAD_HALF_W = 1.0
JUNC_HALF = ROAD_HALF_W
SW_OUTER = JUNC_HALF + 0.6  # sidewalk outer edge
GROUND_HALF = 20.0
TREE_MARGIN = 1.5  # keep trees off the very edge of the ground

rng = random.Random(42)

QUADRANTS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
TREES_PER_QUADRANT = 8

tree_idx = 0
for qx, qy in QUADRANTS:
    placed = 0
    attempts = 0
    while placed < TREES_PER_QUADRANT and attempts < 200:
        attempts += 1
        x = qx * rng.uniform(SW_OUTER + 1.0, GROUND_HALF - TREE_MARGIN)
        y = qy * rng.uniform(SW_OUTER + 1.0, GROUND_HALF - TREE_MARGIN)
        # keep clear of the road corridors themselves (defensive; quadrant sampling already avoids them)
        if abs(x) < SW_OUTER or abs(y) < SW_OUTER:
            continue
        trunk_h = rng.uniform(0.6, 0.9)
        canopy_r = rng.uniform(0.35, 0.55)
        path = f"/World/Junction/Greenery/Tree_{tree_idx:03d}"
        make_cylinder(path + "/Trunk", 0.05, trunk_h, (x, y, trunk_h / 2.0), trunk_mat)
        canopy_mat = canopy_mats[tree_idx % len(canopy_mats)]
        make_sphere(path + "/Canopy", canopy_r, (x, y, trunk_h + canopy_r * 0.75), canopy_mat,
                    scale=(1.0, 1.0, 1.15))
        tree_idx += 1
        placed += 1

# ---------- lamp poles along every sidewalk arm ----------
ARM_LEN = 15.0
LAMP_POLE_H = 1.5
LAMP_POLE_R = 0.025
LAMP_SPACING = 3.0
LAMP_OFFSET = SW_OUTER + 0.05  # just outside the sidewalk, on the grass edge

arm_ranges = {
    "E": ("X", 1),
    "W": ("X", -1),
    "N": ("Y", 1),
    "S": ("Y", -1),
}

lamp_idx = 0
for arm, (axis, sign) in arm_ranges.items():
    s = JUNC_HALF + 1.5
    while s < ARM_LEN - 0.5:
        for side in (1, -1):
            if axis == "X":
                x, y = sign * s, side * LAMP_OFFSET
            else:
                x, y = side * LAMP_OFFSET, sign * s
            path = f"/World/Junction/Greenery/Lamp_{arm}_{lamp_idx:03d}_{'A' if side > 0 else 'B'}"
            make_cylinder(path + "/Pole", LAMP_POLE_R, LAMP_POLE_H, (x, y, LAMP_POLE_H / 2.0), lamp_pole_mat)
            make_sphere(path + "/Globe", 0.06, (x, y, LAMP_POLE_H + 0.03), lamp_glow_mat)
        lamp_idx += 1
        s += LAMP_SPACING

print("STEP6C OK - trees:", tree_idx, " lamp stations:", lamp_idx * 2)
