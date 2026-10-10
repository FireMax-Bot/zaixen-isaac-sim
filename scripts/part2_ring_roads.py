# PART 2 -- ring road + plus roads (v2: rounded curb returns, continuous ring line, give-way lines).
# Idempotent; stop the timeline first.
# Run order:  part1_drivable_surface.py  ->  step2_markings.py  ->  part2_ring_roads.py
#
# Layout (m, Z-up, right-hand traffic, lane = 1 m)
#   plus  : Road_X / Road_Y, 2 m wide (one lane each way), x/y in [-15, 15]   (unchanged)
#   ring  : circle, centreline R = 15 through the four arm ends, 2 m wide -> r in [14, 16]
#           dashed yellow centre line at r = 15 (continuous across the arm mouths)
#           inner lane r = 14.5 (clockwise), outer lane r = 15.5 (counter-clockwise)
#   walks : 0.6 m sidewalks. Outer ring r in [16, 16.6]. Inside the ring: four continuous
#           bands (one per quadrant) that run along both arms and round the ring's inner
#           edge, with a CURB_R rounded curb return at every arm mouth.
#   fill  : each curb return leaves a small corner that is paved with road-height asphalt
#   paint : give-way line across the exit lane of every arm, right before the ring
#   height: every drivable top == /World/Junction.zaixen:roadSurfaceZ (Part 1 rule)
import math
import omni.usd
import omni.timeline
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Vt

assert not omni.timeline.get_timeline_interface().is_playing(), "stop the timeline first"
stage = omni.usd.get_context().get_stage()

junction = stage.GetPrimAtPath("/World/Junction")
ROAD_TOP = junction.GetAttribute("zaixen:roadSurfaceZ").Get()
assert ROAD_TOP is not None, "run part1_drivable_surface.py first"

RING_R = 15.0
ROAD_HALF_W = 1.0
LANE_W = 1.0
R_IN, R_OUT = RING_R - ROAD_HALF_W, RING_R + ROAD_HALF_W          # 14 .. 16
SW_W = 0.6
SW_TOP = 0.03
SLAB_DEPTH = 0.10      # colliders/visuals extend this far below their top (hidden inside Ground)
CURB_R = 0.8           # rounded curb-return radius at every arm mouth
SEG_DEG = 1.0          # arc sampling
GIVEWAY_D = 13.3       # give-way line distance from centre along each arm

# ---------------- clean previous run ----------------
for p in ("/World/Junction/Ring", "/World/Junction/Sidewalks"):
    if stage.GetPrimAtPath(p).IsValid():
        stage.RemovePrim(p)
for c in list(junction.GetChildren()):
    if c.GetName().startswith("Sidewalk_"):           # v1 arm-sidewalk boxes
        stage.RemovePrim(c.GetPath())
markings = stage.GetPrimAtPath("/World/Junction/Markings")
assert markings.IsValid(), "run step2_markings.py first"
for c in list(markings.GetChildren()):
    if c.GetName().startswith(("RingDash_", "GiveWay_")):
        stage.RemovePrim(c.GetPath())

def mat(path):
    m = UsdShade.Material(stage.GetPrimAtPath(path))
    assert m.GetPrim().IsValid(), f"missing material {path}"
    return m
road_mat, sidewalk_mat = mat("/World/Looks/Road"), mat("/World/Looks/Sidewalk")
yellow_mat, white_mat = mat("/World/Looks/PaintYellow"), mat("/World/Looks/PaintWhite")
asphalt, pavement = mat("/World/PhysicsMaterials/Asphalt"), mat("/World/PhysicsMaterials/Pavement")

# ---------------- mesh helpers ----------------
def finish_mesh(path, pts, idx, counts, visual_mat, phys_mat):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(counts))
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateExtentAttr(Vt.Vec3fArray(UsdGeom.PointBased.ComputeExtent(mesh.GetPointsAttr().Get())))
    prim = mesh.GetPrim()
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(visual_mat)
    UsdPhysics.CollisionAPI.Apply(prim)
    UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr("none")   # static triangle mesh
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(phys_mat, UsdShade.Tokens.weakerThanDescendants, "physics")
    return mesh

def make_arc_slab(path, r0, r1, z_top, visual_mat, phys_mat):
    """Full annulus r0..r1, top at z_top, extruded down SLAB_DEPTH."""
    n = int(round(360.0 / SEG_DEG))
    z_bot = z_top - SLAB_DEPTH
    pts = []
    for i in range(n):
        a = 2.0 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        pts += [(r0 * c, r0 * s, z_top), (r1 * c, r1 * s, z_top), (r0 * c, r0 * s, z_bot), (r1 * c, r1 * s, z_bot)]
    IT, OT, IB, OB = 0, 1, 2, 3
    v = lambda i, k: (i % n) * 4 + k
    idx = []
    for i in range(n):
        j = i + 1
        idx += [v(i, IT), v(i, OT), v(j, OT), v(j, IT)]        # top
        idx += [v(i, IB), v(j, IB), v(j, OB), v(i, OB)]        # bottom
        idx += [v(i, OB), v(j, OB), v(j, OT), v(i, OT)]        # outer wall
        idx += [v(i, IB), v(i, IT), v(j, IT), v(j, IB)]        # inner wall
    return finish_mesh(path, pts, idx, [4] * (len(idx) // 4), visual_mat, phys_mat)

def signed_area(loop):
    return 0.5 * sum(loop[i][0] * loop[(i + 1) % len(loop)][1] - loop[(i + 1) % len(loop)][0] * loop[i][1]
                     for i in range(len(loop)))

def make_strip_slab(path, outer, inner, z_top, visual_mat, phys_mat):
    """Closed strip between two index-paired loops (outer encloses inner). Duplicate inner
    points (mitred corners) collapse the quad to a triangle."""
    if signed_area(outer) < 0:                       # want CCW
        outer, inner = outer[::-1], inner[::-1]
    n = len(outer)
    z_bot = z_top - SLAB_DEPTH
    pts = [(p[0], p[1], z_top) for p in outer] + [(p[0], p[1], z_top) for p in inner] \
        + [(p[0], p[1], z_bot) for p in outer] + [(p[0], p[1], z_bot) for p in inner]
    OT, IT, OB, IB = 0, n, 2 * n, 3 * n
    idx, cnt = [], []
    def add(face):
        seen = []
        for f in face:                               # drop coincident consecutive vertices
            if not seen or pts[f][:2] != pts[seen[-1]][:2] or pts[f][2] != pts[seen[-1]][2]:
                seen.append(f)
        if len(seen) > 1 and pts[seen[0]] == pts[seen[-1]]:
            seen.pop()
        if len(seen) >= 3:
            idx.extend(seen); cnt.append(len(seen))
    for i in range(n):
        j = (i + 1) % n
        add([OT + i, OT + j, IT + j, IT + i])        # top (+z)
        add([OB + i, IB + i, IB + j, OB + j])        # bottom (-z)
        add([OB + i, OB + j, OT + j, OT + i])        # outer wall (outward)
        add([IB + i, IT + i, IT + j, IB + j])        # inner wall (towards the grass)
    return finish_mesh(path, pts, idx, cnt, visual_mat, phys_mat)

def make_fan_prism(path, apex, arc, z_top, visual_mat, phys_mat):
    """Corner fill: triangle fan from `apex` over the sampled `arc` (2D points), extruded down."""
    tris = [(apex, arc[i], arc[i + 1]) for i in range(len(arc) - 1)]
    tris = [t if (t[1][0]-t[0][0])*(t[2][1]-t[0][1]) - (t[1][1]-t[0][1])*(t[2][0]-t[0][0]) > 0 else (t[0], t[2], t[1])
            for t in tris]
    z_bot = z_top - SLAB_DEPTH
    pts, idx = [], []
    for a, b, c in tris:
        base = len(pts)
        pts += [(a[0], a[1], z_top), (b[0], b[1], z_top), (c[0], c[1], z_top),
                (a[0], a[1], z_bot), (b[0], b[1], z_bot), (c[0], c[1], z_bot)]
        idx += [base, base + 1, base + 2]                      # top
        idx += [base + 3, base + 5, base + 4]                  # bottom
        for (p, q) in ((0, 1), (1, 2), (2, 0)):                # side walls (double-sided: winding is not critical)
            idx += [base + p, base + q, base + 3 + q, base + 3 + p]
    counts = []
    i = 0
    for _ in tris:
        counts += [3, 3, 4, 4, 4]
    return finish_mesh(path, pts, idx, counts, visual_mat, phys_mat)

def rot90(p, k):
    x, y = p
    for _ in range(k % 4):
        x, y = -y, x
    return (x, y)

def arc_pts(cx, cy, r, a0, a1):
    n = max(2, int(math.ceil(abs(a1 - a0) / SEG_DEG)))
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

# ---------------- ring road + outer sidewalk ----------------
UsdGeom.Scope.Define(stage, "/World/Junction/Ring")
make_arc_slab("/World/Junction/Ring/RoadSlab", R_IN, R_OUT, ROAD_TOP, road_mat, asphalt)
make_arc_slab("/World/Junction/Ring/Sidewalk_Outer", R_OUT, R_OUT + SW_W, SW_TOP, sidewalk_mat, pavement)

# ---------------- curb-return geometry (north-arm, east side; every other mouth is a rotation/mirror) ----------------
XC = ROAD_HALF_W + CURB_R                          # fillet centre x
RC = R_IN - CURB_R                                 # fillet centre distance from origin
YC = math.sqrt(RC * RC - XC * XC)                  # fillet centre y
A_B = math.degrees(math.atan2(YC, XC))             # angle of the tangent point on the ring (~82 deg)
K = (ROAD_HALF_W, math.sqrt(R_IN * R_IN - ROAD_HALF_W ** 2))   # sharp corner the fillet replaces

# ---------------- four quadrant sidewalk bands ----------------
UsdGeom.Scope.Define(stage, "/World/Junction/Sidewalks")
w = SW_W
def half_loops():
    """(outer, inner) index-paired points from the junction corner to the 45-degree axis of the NE quadrant."""
    outer = [(ROAD_HALF_W, ROAD_HALF_W)]
    inner = [(ROAD_HALF_W + w, ROAD_HALF_W + w)]
    n = 20
    for i in range(n + 1):                                            # straight along the arm edge
        y = (ROAD_HALF_W + w) + (YC - (ROAD_HALF_W + w)) * i / n
        outer.append((ROAD_HALF_W, y)); inner.append((ROAD_HALF_W + w, y))
    o = arc_pts(XC, YC, CURB_R, 180.0, A_B)                           # curb return
    i_ = arc_pts(XC, YC, CURB_R - w, 180.0, A_B)
    outer += o[1:]; inner += i_[1:]
    o = arc_pts(0, 0, R_IN, A_B, 45.0)                                # ring inner edge to the 45-degree axis
    i_ = arc_pts(0, 0, R_IN - w, A_B, 45.0)
    outer += o[1:]; inner += i_[1:]
    return outer, inner
ho, hi = half_loops()
mir = lambda p: (p[1], p[0])
full_o = ho + [mir(p) for p in reversed(ho[1:-1])]
full_i = hi + [mir(p) for p in reversed(hi[1:-1])]
for k in range(4):
    o = [rot90(p, k) for p in full_o]
    i_ = [rot90(p, k) for p in full_i]
    make_strip_slab(f"/World/Junction/Sidewalks/Quad_{k}", o, i_, SW_TOP, sidewalk_mat, pavement)

# ---------------- asphalt fill for each curb-return corner (8 mouths x sides) ----------------
mouth = 0
fillets = []
A_pt = (ROAD_HALF_W, YC)
arc = arc_pts(XC, YC, CURB_R, 180.0, A_B)          # A .. B along the fillet
ring_seg = arc_pts(0, 0, R_IN, A_B, 45.0)
for k in range(4):
    for mirrored in (False, True):
        f = (lambda p: mir(p)) if mirrored else (lambda p: p)
        fan_arc = [rot90(f(p), k) for p in arc]
        fan_apex = rot90(f(K), k)
        make_fan_prism(f"/World/Junction/Ring/MouthFill_{mouth}", fan_apex, fan_arc, ROAD_TOP, road_mat, asphalt)
        mouth += 1
# the fan only covers the wedge between apex->A and apex->B lines; add the wedge between K, B and the ring edge
mouth = 0
for k in range(4):
    for mirrored in (False, True):
        f = (lambda p: mir(p)) if mirrored else (lambda p: p)
        B = arc[-1]
        ring_wedge = arc_pts(0, 0, R_IN, A_B, math.degrees(math.atan2(K[1], K[0])))[1:]   # B (excluded) .. K along r=14
        wedge_pts = [rot90(f(p), k) for p in ring_wedge]
        make_fan_prism(f"/World/Junction/Ring/MouthFillB_{mouth}", rot90(f(B), k), wedge_pts, ROAD_TOP, road_mat, asphalt)
        mouth += 1

# ---------------- paint: continuous ring dashed centre line ----------------
DASH_LEN, DASH_GAP, DASH_W, MARK_Z = 0.5, 0.5, 0.08, 0.021
n_dash = int((2.0 * math.pi * RING_R) // (DASH_LEN + DASH_GAP))
for i in range(n_dash):
    a = 2.0 * math.pi * i / n_dash
    cube = UsdGeom.Cube.Define(stage, f"/World/Junction/Markings/RingDash_{i:03d}")
    cube.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(cube)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(RING_R * math.cos(a), RING_R * math.sin(a), MARK_Z))
    xf.AddRotateZOp().Set(math.degrees(a) + 90.0)                 # long axis tangent to the ring
    xf.AddScaleOp().Set(Gf.Vec3f(DASH_LEN, DASH_W, 0.005))
    UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(yellow_mat)

# ---------------- paint: give-way line across each arm's EXIT lane (dashed white) ----------------
# prototype: north arm, north-bound lane (x in [0, 1]) at y = GIVEWAY_D; rotate by -90 deg * k for the others
GW_SEG, GW_GAP, GW_T = 0.20, 0.0667, 0.10
n_gw = 4
for k in range(4):
    for j in range(n_gw):
        x0 = (GW_SEG + GW_GAP) * j + GW_SEG / 2.0
        px, py = rot90((x0, GIVEWAY_D), -k)
        cube = UsdGeom.Cube.Define(stage, f"/World/Junction/Markings/GiveWay_{k}_{j}")
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(px, py, MARK_Z))
        xf.AddRotateZOp().Set(-90.0 * k)
        xf.AddScaleOp().Set(Gf.Vec3f(GW_SEG, GW_T, 0.005))
        UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(white_mat)

# ---------------- record the layout for later parts ----------------
def setd(name, val):
    junction.CreateAttribute(name, Sdf.ValueTypeNames.Double, custom=True).Set(val)
setd("zaixen:ringRadius", RING_R); setd("zaixen:laneWidth", LANE_W)
setd("zaixen:roadHalfWidth", ROAD_HALF_W); setd("zaixen:armLength", 15.0)
setd("zaixen:curbReturnRadius", CURB_R); setd("zaixen:giveWayDistance", GIVEWAY_D)

print(f"ring r=[{R_IN},{R_OUT}] top z={ROAD_TOP}; curb return R={CURB_R} (fillet centre y={YC:.3f}, tangent at {A_B:.2f} deg); "
      f"ring dashes {n_dash}")
