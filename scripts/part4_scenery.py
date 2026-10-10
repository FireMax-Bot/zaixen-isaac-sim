# PART 4 -- scenery. Idempotent (rebuilds /World/Junction/Scenery). Decoration only: no colliders, no physics.
#
# Everything is a UsdGeom.PointInstancer with a handful of tiny prototypes, so the whole scene costs a few
# thousand instanced low-poly shapes and no textures or lights.
#   trees   : extra round + pine trees on the lawns (existing Greenery/Tree_* are kept and avoided)
#   bushes  : round shrubs at tree bases and scattered
#   hedges  : a low hedge following the ring's inner sidewalk in every quadrant
#   fences  : white garden fence strips parallel to the arm sidewalks
#   benches : benches (+ bins) on the lawn next to the arm sidewalks, facing the road
#   flowers : small red / yellow / white / pink patches
#   tufts   : grass tufts (two greens)
# Lawn = quadrant interiors (inside the ring) + the outer ring (beyond the outer sidewalk).
import math
import random
import omni.usd
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt

stage = omni.usd.get_context().get_stage()
ROOT = "/World/Junction/Scenery"
if stage.GetPrimAtPath(ROOT).IsValid():
    stage.RemovePrim(ROOT)
UsdGeom.Scope.Define(stage, ROOT)
rng = random.Random(2026)

# ---------------- layout constants (match part2_ring_roads.py) ----------------
ROAD_HALF_W, SW_W, RING_R, CURB_R = 1.0, 0.6, 15.0, 0.8
ARM_EDGE = ROAD_HALF_W + SW_W                        # 1.6  outer edge of the arm sidewalks
RING_IN_SW = RING_R - ROAD_HALF_W - SW_W             # 13.4 inner edge of the ring's inner sidewalk
RING_OUT_SW = RING_R + ROAD_HALF_W + SW_W            # 16.6 outer edge of the ring's outer sidewalk
GROUND_HALF = 20.0
FILLET_C = []                                        # curb-return centres (pavement wraps round them)
_yc = math.sqrt((RING_R - ROAD_HALF_W - CURB_R) ** 2 - (ROAD_HALF_W + CURB_R) ** 2)
for sx in (1, -1):
    for sy in (1, -1):
        FILLET_C += [(sx * (ROAD_HALF_W + CURB_R), sy * _yc), (sx * _yc, sy * (ROAD_HALF_W + CURB_R))]

# ---------------- obstacles already in the scene ----------------
placed = []                                          # (x, y, radius) of every big thing we (or the scene) put down
for c in stage.GetPrimAtPath("/World/Junction/Greenery").GetChildren():
    if c.GetName().startswith("Tree_"):
        t = UsdGeom.Xformable(c.GetChild("Trunk")).GetOrderedXformOps()[0].Get()
        placed.append((t[0], t[1], UsdGeom.Sphere(c.GetChild("Canopy")).GetRadiusAttr().Get() + 0.25))
    elif c.GetName().startswith("Lamp_"):                # lamp poles: keep canopies and props clear of them
        t = UsdGeom.Xformable(c.GetChild("Pole")).GetOrderedXformOps()[0].Get()
        placed.append((t[0], t[1], 0.15))

def lawn_ok(x, y, m=0.3):
    if abs(x) > GROUND_HALF - 0.3 or abs(y) > GROUND_HALF - 0.3:
        return False
    if abs(x) < ARM_EDGE + m or abs(y) < ARM_EDGE + m:
        return False                                  # arms, sidewalks, junction plaza
    r = math.hypot(x, y)
    if r < RING_IN_SW - m:
        return all(math.hypot(x - fx, y - fy) > 1.3 for fx, fy in FILLET_C)
    return r > RING_OUT_SW + m

def free(x, y, rad):
    return all(math.hypot(x - px, y - py) > rad + pr for px, py, pr in placed)

def sample_lawn(rad, tries=400, edge=0.3):
    for _ in range(tries):
        if rng.random() < 0.8:                        # quadrant interiors dominate
            x, y = rng.choice((1, -1)) * rng.uniform(2.0, 12.6), rng.choice((1, -1)) * rng.uniform(2.0, 12.6)
        else:                                         # outer ring corners
            x, y = rng.uniform(-19.5, 19.5), rng.uniform(-19.5, 19.5)
        if lawn_ok(x, y, edge) and free(x, y, rad):
            return x, y
    return None

# ---------------- materials + primitive helpers ----------------
def mat(name, color, rough=0.85):
    path = f"/World/Looks/{name}"
    if stage.GetPrimAtPath(path).IsValid():
        return UsdShade.Material(stage.GetPrimAtPath(path))
    m = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, path + "/Shader")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(rough)
    m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    return m

M = {k: mat(k, v) for k, v in {
    "PineGreen": (0.05, 0.27, 0.12), "HedgeGreen": (0.07, 0.31, 0.09), "BushA": (0.12, 0.42, 0.10),
    "BushB": (0.17, 0.50, 0.15), "FenceWhite": (0.92, 0.92, 0.89), "BenchWood": (0.48, 0.30, 0.13),
    "BenchMetal": (0.12, 0.12, 0.13), "BinGreen": (0.10, 0.30, 0.18), "TuftLight": (0.32, 0.66, 0.20),
    "TuftDark": (0.14, 0.42, 0.10), "FlowerRed": (0.85, 0.10, 0.12), "FlowerYellow": (0.96, 0.80, 0.10),
    "FlowerWhite": (0.96, 0.96, 0.92), "FlowerPink": (0.92, 0.36, 0.62), "StemGreen": (0.10, 0.36, 0.08)}.items()}
for k in ("TreeTrunk", "TreeCanopyA", "TreeCanopyB", "TreeCanopyC"):
    M[k] = UsdShade.Material(stage.GetPrimAtPath(f"/World/Looks/{k}"))

def _bind(prim, m):
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(m)

def box(path, size, t, m, rot=None):
    g = UsdGeom.Cube.Define(stage, path); g.CreateSizeAttr(1.0)
    x = UsdGeom.Xformable(g); x.ClearXformOpOrder()
    x.AddTranslateOp().Set(Gf.Vec3d(*t))
    if rot: x.AddRotateXYZOp().Set(Gf.Vec3f(*rot))
    x.AddScaleOp().Set(Gf.Vec3f(*size)); _bind(g.GetPrim(), m)

def cyl(path, r, h, t, m):
    g = UsdGeom.Cylinder.Define(stage, path); g.CreateRadiusAttr(r); g.CreateHeightAttr(h); g.CreateAxisAttr("Z")
    UsdGeom.Xformable(g).AddTranslateOp().Set(Gf.Vec3d(*t)); _bind(g.GetPrim(), m)

def sph(path, r, t, m, scale=None):
    g = UsdGeom.Sphere.Define(stage, path); g.CreateRadiusAttr(r)
    x = UsdGeom.Xformable(g); x.AddTranslateOp().Set(Gf.Vec3d(*t))
    if scale: x.AddScaleOp().Set(Gf.Vec3f(*scale))
    _bind(g.GetPrim(), m)

def cone(path, r, h, t, m, rot=None):
    g = UsdGeom.Cone.Define(stage, path); g.CreateRadiusAttr(r); g.CreateHeightAttr(h); g.CreateAxisAttr("Z")
    x = UsdGeom.Xformable(g); x.AddTranslateOp().Set(Gf.Vec3d(*t))
    if rot: x.AddRotateXYZOp().Set(Gf.Vec3f(*rot))
    _bind(g.GetPrim(), m)

# ---------------- instancer plumbing ----------------
class Inst:
    def __init__(self, name, protos):
        self.prim = UsdGeom.PointInstancer.Define(stage, f"{ROOT}/{name}")
        self.protos = []
        for pname, builder in protos:
            p = f"{ROOT}/{name}/Protos/{pname}" if self.protos else f"{ROOT}/{name}/Protos/{pname}"
            if not stage.GetPrimAtPath(f"{ROOT}/{name}/Protos").IsValid():
                UsdGeom.Scope.Define(stage, f"{ROOT}/{name}/Protos")
            UsdGeom.Xform.Define(stage, p)
            builder(p)
            self.prim.GetPrototypesRel().AddTarget(p)
            self.protos.append(pname)
        self.items = []

    def add(self, proto, x, y, yaw=0.0, s=1.0, sz=None, z=0.0):
        self.items.append((self.protos.index(proto) if isinstance(proto, str) else proto, x, y, z, yaw, s, s if sz is None else sz))

    def finish(self):
        idx, pos, ori, scl = [], [], [], []
        for pi, x, y, z, yaw, s, sz in self.items:
            h = math.radians(yaw) / 2.0
            idx.append(pi); pos.append(Gf.Vec3f(x, y, z)); scl.append(Gf.Vec3f(s, s, sz))
            ori.append(Gf.Quath(math.cos(h), 0.0, 0.0, math.sin(h)))
        self.prim.CreateProtoIndicesAttr(Vt.IntArray(idx))
        self.prim.CreatePositionsAttr(Vt.Vec3fArray(pos))
        self.prim.CreateOrientationsAttr(Vt.QuathArray(ori))
        self.prim.CreateScalesAttr(Vt.Vec3fArray(scl))
        return len(idx)

counts = {}

# ---------------- benches + bins beside the arm sidewalks ----------------
def bench(p):
    box(p + "/Seat", (0.42, 0.62, 0.03), (0, 0, 0.21), M["BenchWood"])
    box(p + "/Back", (0.03, 0.62, 0.17), (-0.20, 0, 0.32), M["BenchWood"], rot=(0, -12, 0))
    box(p + "/LegL", (0.36, 0.03, 0.20), (0, 0.27, 0.10), M["BenchMetal"])
    box(p + "/LegR", (0.36, 0.03, 0.20), (0, -0.27, 0.10), M["BenchMetal"])
def bin_(p):
    cyl(p + "/Body", 0.09, 0.30, (0, 0, 0.15), M["BinGreen"])
    cyl(p + "/Lid", 0.10, 0.03, (0, 0, 0.315), M["BenchMetal"])
benches = Inst("Benches", [("Bench", bench)])
bins = Inst("Bins", [("Bin", bin_)])
bench_spots = []
for sx in (1, -1):
    for sy in (1, -1):
        for along_x in (True, False):
            s_pos = 7.0 + rng.uniform(-0.2, 0.2)                # between lamp stations (5.5 and 8.5)
            off = ARM_EDGE + 0.28
            if along_x:                                          # beside the X arm sidewalk, facing -sy
                x, y, face = sx * s_pos, sy * off, (0.0, -sy)
                bx, by = x + sx * 0.75, y
            else:                                                # beside the Y arm sidewalk, facing -sx
                x, y, face = sx * off, sy * s_pos, (-sx, 0.0)
                bx, by = x, y + sy * 0.75
            yaw = math.degrees(math.atan2(face[1], face[0]))
            benches.add("Bench", x, y, yaw)
            bins.add("Bin", bx, by, 0.0)
            placed.append((x, y, 0.55)); placed.append((bx, by, 0.2))
            bench_spots.append((x, y))
counts["benches"] = benches.finish()
counts["bins"] = bins.finish()

# ---------------- trees ----------------
def tree_round(canopy_mat, r):
    def b(p):
        cyl(p + "/Trunk", 0.05, 0.75, (0, 0, 0.375), M["TreeTrunk"])
        sph(p + "/Canopy", r, (0, 0, 0.75 + r * 0.75), canopy_mat, scale=(1.0, 1.0, 1.15))
    return b
def tree_pine(p):
    cyl(p + "/Trunk", 0.04, 0.45, (0, 0, 0.225), M["TreeTrunk"])
    cone(p + "/Tier0", 0.46, 0.55, (0, 0, 0.62), M["PineGreen"])
    cone(p + "/Tier1", 0.36, 0.48, (0, 0, 0.95), M["PineGreen"])
    cone(p + "/Tier2", 0.25, 0.42, (0, 0, 1.24), M["PineGreen"])
trees = Inst("Trees", [("RoundA", tree_round(M["TreeCanopyA"], 0.5)), ("RoundB", tree_round(M["TreeCanopyB"], 0.46)),
                       ("RoundC", tree_round(M["TreeCanopyC"], 0.52)), ("Pine", tree_pine)])
n_trees = 0
for i in range(26):
    k = rng.choice(("RoundA", "RoundB", "RoundC", "Pine", "Pine"))
    s = rng.uniform(0.8, 1.25)
    spot = sample_lawn(0.55 * s + 0.35)
    if spot:
        trees.add(k, spot[0], spot[1], rng.uniform(0, 360), s)
        placed.append((spot[0], spot[1], 0.55 * s + 0.2))
        n_trees += 1
counts["trees"] = trees.finish()

# ---------------- bushes (at tree bases + scattered) ----------------
def bush(m, r):
    return lambda p: sph(p + "/Body", r, (0, 0, r * 0.7), m, scale=(1.0, 1.0, 0.75))
bushes = Inst("Bushes", [("BushA", bush(M["BushA"], 0.22)), ("BushB", bush(M["BushB"], 0.19))])
for (px, py, pr) in list(placed):
    for _ in range(2):
        a = rng.uniform(0, 2 * math.pi); d = pr + rng.uniform(0.05, 0.3)
        x, y = px + d * math.cos(a), py + d * math.sin(a)
        if lawn_ok(x, y, 0.25) and free(x, y, 0.2):
            bushes.add(rng.choice(("BushA", "BushB")), x, y, rng.uniform(0, 360), rng.uniform(0.7, 1.3))
            placed.append((x, y, 0.25))
for _ in range(34):
    spot = sample_lawn(0.3, edge=0.35)
    if spot:
        bushes.add(rng.choice(("BushA", "BushB")), spot[0], spot[1], rng.uniform(0, 360), rng.uniform(0.7, 1.5))
        placed.append((spot[0], spot[1], 0.3))
counts["bushes"] = bushes.finish()

# ---------------- hedges along the ring's inner sidewalk ----------------
hedges = Inst("Hedges", [("Seg", lambda p: box(p + "/Body", (0.82, 0.30, 0.34), (0, 0, 0.17), M["HedgeGreen"]))])
R_H = RING_IN_SW - 0.42
seg_ang = 0.80 / R_H
for q in range(4):
    a = math.radians(11.0)
    while a < math.radians(79.0):
        ang = a + seg_ang / 2
        x, y = R_H * math.cos(ang + q * math.pi / 2), R_H * math.sin(ang + q * math.pi / 2)
        if lawn_ok(x, y, 0.15):
            hedges.add("Seg", x, y, math.degrees(ang + q * math.pi / 2) + 90.0)
        a += seg_ang
counts["hedges"] = hedges.finish()

# ---------------- fences parallel to the arm sidewalks ----------------
def fence(p):
    for sx in (-0.5, 0.5):
        box(p + f"/Post{'A' if sx < 0 else 'B'}", (0.05, 0.05, 0.42), (sx, 0, 0.21), M["FenceWhite"])
    box(p + "/RailTop", (1.0, 0.022, 0.04), (0, 0, 0.36), M["FenceWhite"])
    box(p + "/RailLow", (1.0, 0.022, 0.04), (0, 0, 0.18), M["FenceWhite"])
fences = Inst("Fences", [("Section", fence)])
F_OFF = ARM_EDGE + 1.45
for sx in (1, -1):
    for sy in (1, -1):
        for j in range(9):                                      # 9 sections, 3.4 m .. 12.4 m
            s_pos = 3.9 + j * 1.0
            for along_x in (True, False):
                x, y = (sx * s_pos, sy * F_OFF) if along_x else (sx * F_OFF, sy * s_pos)
                if lawn_ok(x, y, 0.1):
                    fences.add("Section", x, y, 0.0 if along_x else 90.0)
counts["fences"] = fences.finish()
for sx in (1, -1):
    for sy in (1, -1):
        placed.append((sx * F_OFF, sy * 8.0, 0.0))

# ---------------- flower patches ----------------
def flower(head_mat):
    def b(p):
        cyl(p + "/Stem", 0.006, 0.15, (0, 0, 0.075), M["StemGreen"])
        sph(p + "/Head", 0.032, (0, 0, 0.165), head_mat)
    return b
flowers = Inst("Flowers", [("Red", flower(M["FlowerRed"])), ("Yellow", flower(M["FlowerYellow"])),
                           ("White", flower(M["FlowerWhite"])), ("Pink", flower(M["FlowerPink"]))])
patches = 0
for _ in range(20):
    spot = sample_lawn(0.7, edge=0.6)
    if not spot:
        continue
    patches += 1
    placed.append((spot[0], spot[1], 0.6))
    cols = rng.sample(("Red", "Yellow", "White", "Pink"), 2)
    for _f in range(rng.randint(10, 15)):
        a, d = rng.uniform(0, 2 * math.pi), abs(rng.gauss(0, 0.28))
        flowers.add(rng.choice(cols), spot[0] + d * math.cos(a), spot[1] + d * math.sin(a), 0.0, rng.uniform(0.8, 1.3))
counts["flowers"] = flowers.finish()

# ---------------- grass tufts ----------------
def tuft(m):
    def b(p):
        for i, (dx, dy, rx, ry) in enumerate(((0.0, 0.0, 0, 0), (0.025, 0.0, 0, 14), (-0.02, 0.02, -12, -6), (0.0, -0.025, 12, 4))):
            cone(p + f"/Blade{i}", 0.018, 0.13, (dx, dy, 0.065), m, rot=(rx, ry, 0))
    return b
tufts = Inst("Tufts", [("Light", tuft(M["TuftLight"])), ("Dark", tuft(M["TuftDark"]))])
n_t = 0
attempts = 0
while n_t < 1500 and attempts < 6000:
    attempts += 1
    if rng.random() < 0.85:
        x, y = rng.choice((1, -1)) * rng.uniform(1.9, 13.0), rng.choice((1, -1)) * rng.uniform(1.9, 13.0)
    else:
        x, y = rng.uniform(-19.7, 19.7), rng.uniform(-19.7, 19.7)
    if lawn_ok(x, y, 0.12) and free(x, y, 0.02):
        tufts.add(rng.choice(("Light", "Dark", "Light")), x, y, rng.uniform(0, 360), rng.uniform(0.7, 1.5), rng.uniform(0.7, 1.8))
        n_t += 1
counts["tufts"] = tufts.finish()

junction = stage.GetPrimAtPath("/World/Junction")
junction.CreateAttribute("zaixen:sceneryInstances", Sdf.ValueTypeNames.Int, custom=True).Set(sum(counts.values()))
print("PART4 OK -", counts, "flower patches:", patches, "| total instances:", sum(counts.values()))
