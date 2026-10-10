import omni.usd
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

ctx = omni.usd.get_context()
stage = ctx.get_stage()

for p in ("/World/Junction/Markings",):
    prim = stage.GetPrimAtPath(p)
    if prim.IsValid():
        stage.RemovePrim(p)

def make_material(path, color, roughness=0.6):
    if stage.GetPrimAtPath(path).IsValid():
        return UsdShade.Material(stage.GetPrimAtPath(path))
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat

def make_box(path, size, translate, material=None):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(cube)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(material)
    return cube

mat_scope = "/World/Looks"
yellow_mat = make_material(mat_scope + "/PaintYellow", (1.0, 0.82, 0.0), roughness=0.5)
white_mat = make_material(mat_scope + "/PaintWhite", (0.92, 0.92, 0.9), roughness=0.5)

scope = UsdGeom.Scope.Define(stage, "/World/Junction/Markings")

ROAD_HALF_W = 1.0
JUNC_HALF = ROAD_HALF_W
ARM_LEN = 15.0
MARK_Z = 0.021  # just above road surface (road top = 0.02)

DASH_LEN = 0.5
DASH_GAP = 0.5
DASH_W = 0.08

STOP_THICK = 0.12
STOP_W = ROAD_HALF_W * 2.0  # spans full road width

CW_BAND = 0.6           # crosswalk band width (along travel axis)
CW_SPAN = 1.6            # crosswalk half-span across the road (covers road + verge to sidewalk edge)
CW_STRIPE_LEN = CW_BAND  # stripe length along travel axis
CW_STRIPE_W = 0.35
CW_STRIPE_GAP = 0.25

ARMS = [
    ("E", "X", 1),   # East arm: travel axis X, positive direction
    ("W", "X", -1),  # West arm: travel axis X, negative direction
    ("N", "Y", 1),   # North arm: travel axis Y, positive direction
    ("S", "Y", -1),  # South arm: travel axis Y, negative direction
]

# ---------- dashed yellow center lines (split the 2 lanes on every arm) ----------
# start past the crosswalk + stop line zone so the first dash doesn't render through them
DASH_START = JUNC_HALF + CW_BAND + STOP_THICK
# arms end at the ring; centre dashes stop before the give-way line (part2_ring_roads.py)
ARM_PAINT_END = 13.0   # dashes stop short of the give-way line at 13.3
n_dashes = int((ARM_PAINT_END - DASH_START + DASH_GAP) // (DASH_LEN + DASH_GAP))
for arm, axis, sign in ARMS:
    for i in range(n_dashes):
        start = DASH_START + i * (DASH_LEN + DASH_GAP)
        center = sign * (start + DASH_LEN / 2.0)
        if axis == "X":
            pos = (center, 0.0, MARK_Z)
            size = (DASH_LEN, DASH_W, 0.005)
        else:
            pos = (0.0, center, MARK_Z)
            size = (DASH_W, DASH_LEN, 0.005)
        make_box(f"/World/Junction/Markings/CenterDash_{arm}_{i:02d}", size, pos, yellow_mat)

# ---------- zebra crosswalks (flush against the junction edge, at all 4 approaches) ----------
# real-world order outward from the junction: junction -> crosswalk -> stop line -> open road.
# (cars must stop BEHIND the crosswalk, not have the crosswalk painted behind the stop line.)
n_stripes = int((2 * CW_SPAN) // (CW_STRIPE_W + CW_STRIPE_GAP))
for arm, axis, sign in ARMS:
    band_center = sign * (JUNC_HALF + CW_BAND / 2.0)
    total_span = n_stripes * CW_STRIPE_W + (n_stripes - 1) * CW_STRIPE_GAP
    start_off = -total_span / 2.0
    for i in range(n_stripes):
        s_center = start_off + i * (CW_STRIPE_W + CW_STRIPE_GAP) + CW_STRIPE_W / 2.0
        if axis == "X":
            pos = (band_center, s_center, MARK_Z)
            size = (CW_STRIPE_LEN, CW_STRIPE_W, 0.005)
        else:
            pos = (s_center, band_center, MARK_Z)
            size = (CW_STRIPE_W, CW_STRIPE_LEN, 0.005)
        make_box(f"/World/Junction/Markings/Crosswalk_{arm}_{i:02d}", size, pos, white_mat)

# ---------- solid white stop lines (one per approach, just behind the crosswalk) ----------
for arm, axis, sign in ARMS:
    center = sign * (JUNC_HALF + CW_BAND + STOP_THICK / 2.0)
    if axis == "X":
        pos = (center, 0.0, MARK_Z)
        size = (STOP_THICK, STOP_W, 0.006)
    else:
        pos = (0.0, center, MARK_Z)
        size = (STOP_W, STOP_THICK, 0.006)
    make_box(f"/World/Junction/Markings/StopLine_{arm}", size, pos, white_mat)

print("STEP2 OK")
count = 0
for p in stage.Traverse():
    if str(p.GetPath()).startswith("/World/Junction/Markings"):
        count += 1
print("marking prims:", count)
