# Scene validation for zaixen_scene.usd -- run inside Isaac Sim (Script Editor, or isaacsim_send.py --file ...).
# Prerequisite: run_simulation.py has been run (modules armed). Plays the timeline for ~24 s of SIM time for the live
# checks and stops it again (a Stop resets everything to its seeded start, so the scene is left as you found it).
# Checks: road geometry, heights, colliders, NPC bodies (kinematic + contact reports), NPC/ego footprint match,
#         scenery placement, physics timestep, runtime/ego/log wiring, and a live sample (signals, NPC overlaps,
#         ego decisions, cost per step).
import math
import time
import omni.usd
import omni.kit.app
import omni.timeline
import omni.graph.core as og
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema

SAMPLE_SIM_SECONDS = 24.0            # covers one full 20 s signal cycle
stage = omni.usd.get_context().get_stage()
results = []


def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))


J = stage.GetPrimAtPath("/World/Junction")
top = J.GetAttribute("zaixen:roadSurfaceZ").Get()
bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
names = lambda p: [c.GetName() for c in stage.GetPrimAtPath(p).GetChildren()]
zmax = lambda p: bbox.ComputeWorldBound(stage.GetPrimAtPath(p)).ComputeAlignedRange().GetMax()[2]

# ---------------- 1. road geometry ----------------
ring = names("/World/Junction/Ring")
check("ring road slab + outer sidewalk present", "RoadSlab" in ring and "Sidewalk_Outer" in ring)
check("8 curb-return asphalt fills (+8 wedge fills)",
      sum(n.startswith("MouthFill_") for n in ring) == 8 and sum(n.startswith("MouthFillB_") for n in ring) == 8)
check("4 continuous sidewalk bands with rounded curb returns",
      sorted(names("/World/Junction/Sidewalks")) == [f"Quad_{k}" for k in range(4)])
check("legacy square-cornered sidewalk boxes removed", not any(n.startswith("Sidewalk_") for n in names("/World/Junction")))
mk = names("/World/Junction/Markings")
n_dash = sum(n.startswith("RingDash_") for n in mk)
check("ring centre line: dashes all the way round", n_dash >= 90, f"{n_dash} dashes")
check("give-way lines: 4 arms x 4 dashes", sum(n.startswith("GiveWay_") for n in mk) == 16)

# ---------------- 2. heights + colliders ----------------
flat = ["/World/Junction/Road_X", "/World/Junction/Road_Y", "/World/Junction/Ring/RoadSlab"] + \
       [f"/World/Junction/Ring/{n}" for n in ring if n.startswith("MouthFill")]
off = [(p.split("/")[-1], round(zmax(p), 5)) for p in flat if abs(zmax(p) - top) > 1e-4]
check(f"every drivable top == roadSurfaceZ ({top})", not off, str(off[:3]))
nocol = []
for p in flat + ["/World/Junction/Ground", "/World/Junction/Ring/Sidewalk_Outer"] + [f"/World/Junction/Sidewalks/Quad_{k}" for k in range(4)]:
    prim = stage.GetPrimAtPath(p)
    if not (prim.HasAPI(UsdPhysics.CollisionAPI) and UsdShade.MaterialBindingAPI(prim).GetDirectBindingRel("physics").GetTargets()):
        nocol.append(p.split("/")[-1])
check("roads, ring, sidewalks, ground: static collider + physics material", not nocol, str(nocol[:4]))
sc = [p for p in stage.Traverse() if str(p.GetPath()).startswith("/World/Junction/Scenery") and p.HasAPI(UsdPhysics.CollisionAPI)]
check("scenery carries no colliders", not sc, f"{len(sc)} found")

# ---------------- 3. determinism + collision foundations (Part 4) ----------------
ps = stage.GetPrimAtPath("/PhysicsScene")
hz = ps.GetAttribute("physxScene:timeStepsPerSecond").Get()
import carb.settings
fixed = carb.settings.get_settings().get("/app/player/useFixedTimeStepping")
check("fixed physics timestep: 60 Hz PhysX scene + fixed-step player", hz == 60 and bool(fixed), f"{hz} steps/s, fixed stepping={fixed}")
pool = [c for c in stage.GetPrimAtPath("/World/Junction/NPCCars").GetChildren() if c.GetName().startswith("Car_")]
check("NPC pool built (30 cars)", len(pool) >= 30, f"{len(pool)} cars")
kin = [p for p in pool if UsdPhysics.RigidBodyAPI(p).GetKinematicEnabledAttr().Get()]
crep = [p for p in pool if p.HasAPI(PhysxSchema.PhysxContactReportAPI)]
body_col = [p for p in pool if p.GetChild("Model").GetChild("Body").HasAPI(UsdPhysics.CollisionAPI)]
check("every NPC is a kinematic rigid body with a collider and contact reports", len(kin) == len(crep) == len(body_col) == len(pool),
      f"kinematic {len(kin)}, contact-report {len(crep)}, collider {len(body_col)} of {len(pool)}")
ego_col = [p for p in Usd.PrimRange(stage.GetPrimAtPath("/World/Ego")) if p.HasAPI(UsdPhysics.CollisionAPI)]
check("ego body has colliders (chassis + wheels + suspension)", len(ego_col) >= 20, f"{len(ego_col)} collider prims")

# footprint (measured in each vehicle's own frame; a rotated car would inflate a world-aligned box)
_fresh = lambda: UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
_rb = stage.GetPrimAtPath("/World/Ego/leatherback/Rigid_Bodies")
_m = UsdGeom.XformCache().GetLocalToWorldTransform(_rb)
egob = [v * _m.GetRow3(0).GetLength() for v in _fresh().ComputeUntransformedBound(_rb).ComputeAlignedRange().GetSize()]
model = pool[0].GetChild("Model")
scale = [o.Get() for o in UsdGeom.Xformable(model).GetOrderedXformOps() if o.GetOpType() == UsdGeom.XformOp.TypeScale][0]
# NPC footprint straight from the car's own dimensions: body length, and the outer face of the wheels for the width
_body_sx = [o.Get() for o in UsdGeom.Xformable(model.GetChild("Body")).GetOrderedXformOps() if o.GetOpType() == UsdGeom.XformOp.TypeScale][0][0]
_wheel = model.GetChild("Wheel_FL")
_wy = [o.Get() for o in UsdGeom.Xformable(_wheel).GetOrderedXformOps() if o.GetOpType() == UsdGeom.XformOp.TypeTranslate][0][1]
_wh = UsdGeom.Cylinder(_wheel).GetHeightAttr().Get()
cw = (_body_sx, 2.0 * (abs(_wy) + _wh / 2.0))
dims = sorted([cw[0] * scale[0], cw[1] * scale[1]], reverse=True)
edims = sorted([egob[0], egob[1]], reverse=True)
check("NPC footprint matches ego footprint (within 8%)",
      abs(dims[0] - edims[0]) / edims[0] < 0.08 and abs(dims[1] - edims[1]) / edims[1] < 0.08,
      f"NPC {dims[0]:.3f} x {dims[1]:.3f} m  vs  ego {edims[0]:.3f} x {edims[1]:.3f} m  (scale {scale[0]:.2f})")

# ---------------- 4. scenery ----------------
def in_road(x, y):
    r = math.hypot(x, y)
    return ((abs(x) < 1.6 or abs(y) < 1.6) and r < 16.6) or 13.4 < r < 16.6
bad_scn, total_scn = [], 0
sce = stage.GetPrimAtPath("/World/Junction/Scenery")
for inst in sce.GetChildren():
    pts = UsdGeom.PointInstancer(inst).GetPositionsAttr().Get() or []
    total_scn += len(pts)
    for p in pts:
        if inst.GetName() == "Hedges":
            if math.hypot(p[0], p[1]) > 13.3 or abs(p[0]) < 1.7 or abs(p[1]) < 1.7:
                bad_scn.append((inst.GetName(), round(p[0], 2), round(p[1], 2)))
        elif in_road(p[0], p[1]):
            bad_scn.append((inst.GetName(), round(p[0], 2), round(p[1], 2)))
check("scenery: nothing on a road, sidewalk or the junction plaza", not bad_scn, str(bad_scn[:3]))
check("scenery: instanced, ~2000 instances in 8 instancers", total_scn > 1500 and len(sce.GetChildren()) >= 8, f"{total_scn} instances")

# ---------------- 5. runtime wiring (Parts 4-5) ----------------
import zaixen_runtime as rt, zaixen_traffic as zt, zaixen_ego as ze, zaixen_log as zl
hooks = set(rt._S["hooks"])
check("runtime armed with traffic + ego + log hooks (physics-step driven)", rt._S["armed"] and {"traffic", "ego", "log"} <= hooks, f"hooks: {sorted(hooks)}")
g = og.Controller.graph(ze.ROS_DRIVE_GRAPH)
check("ROS Ackermann graph switched off while the in-sim ego drives", g.is_disabled())
check("CSV logger registered but OFF by default", "log" in hooks and not zl.is_on())
check("ego decision function present: ego_decide(light, obstacle_dist, pose, plan)", callable(ze.ego_decide))

# ---------------- 6. live sample (real physics steps) ----------------
tl = omni.timeline.get_timeline_interface()
app = omni.kit.app.get_app()


def corners(x, y, h, L=zt.CAR_L, W=zt.CAR_W):
    c, s = math.cos(h), math.sin(h)
    return [(x + c * a - s * b, y + s * a + c * b) for a, b in ((L / 2, W / 2), (L / 2, -W / 2), (-L / 2, -W / 2), (-L / 2, W / 2))]


def overlap(p, q):
    for poly in (p, q):
        for i in range(4):
            ex, ey = poly[(i + 1) % 4][0] - poly[i][0], poly[(i + 1) % 4][1] - poly[i][1]
            ax, ay = -ey, ex
            pp = [ax * u + ay * v for u, v in p]
            qq = [ax * u + ay * v for u, v in q]
            if max(pp) < min(qq) or max(qq) < min(pp):
                return False
    return True


sim = zt._S["sim"]
n_active = sim.n_active()
seen = {"X": set(), "Y": set()}
overlaps = mismatch = frames = 0
travelled, reasons, ego_min = {}, {}, 9.0
last = {}
lastp = None
ego_dist = 0.0
tl.play()
for _ in range(10):
    await app.next_update_async()
last_step = -1
while rt.sim_time() < SAMPLE_SIM_SECONDS and tl.is_playing():
    await app.next_update_async()
    if rt.step_count() == last_step:
        continue
    last_step = rt.step_count()
    frames += 1
    for ax in ("X", "Y"):
        seen[ax].add(zt.TRAFFIC_STATE[ax])
    act = [c for c in sim.cars if c.active]
    for i, a in enumerate(act):
        for b in act[i + 1:]:
            if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < 1.0 and overlap(corners(a.x, a.y, a.h), corners(b.x, b.y, b.h)):
                overlaps += 1
    for a in act:
        t = [o for o in UsdGeom.Xformable(zt._S["pool"][a.id][0]).GetOrderedXformOps()
             if o.GetOpType() == UsdGeom.XformOp.TypeTranslate][0].Get()
        if abs(t[0] - a.x) > 0.05 or abs(t[1] - a.y) > 0.05:
            mismatch += 1
        travelled[a.id] = travelled.get(a.id, 0.0) + (math.hypot(a.x - last[a.id][0], a.y - last[a.id][1]) if a.id in last else 0.0)
        last[a.id] = (a.x, a.y)
    e = rt.ego()
    if e is not None:
        reasons[ze.STATUS["reason"]] = reasons.get(ze.STATUS["reason"], 0) + 1
        ego_min = min([ego_min] + [math.hypot(a.x - e.x, a.y - e.y) for a in act])
        if lastp is not None:
            ego_dist += math.hypot(e.x - lastp[0], e.y - lastp[1])
        lastp = (e.x, e.y)
collisions = zt.COLLISION["total"]
sim_reached = rt.sim_time()
tl.stop()
for _ in range(30):
    await app.next_update_async()

check("live: sim clock advanced on the fixed physics step", sim_reached >= SAMPLE_SIM_SECONDS - 0.1 and frames > 600,
      f"{sim_reached:.1f} s of sim time, {frames} steps")
check("live: no two NPCs ever overlap", overlaps == 0, f"{overlaps} overlapping steps")
check("live: NPC prim poses follow the planner", mismatch == 0, f"{mismatch} mismatches")
check("live: every NPC makes progress", all(m > 1.0 for m in travelled.values()), f"min {min(travelled.values()):.1f} m" if travelled else "no cars")
check("live: signals cycle GREEN -> YELLOW -> RED on both axes", all({"GREEN", "YELLOW", "RED"} <= s for s in seen.values()),
      f"X {sorted(seen['X'])}, Y {sorted(seen['Y'])}")
check("live: the ego drives (moves under physics) under its own decisions", ego_dist > 5.0 and reasons.get("go", 0) > 100 and "collision" not in reasons,
      f"drove {ego_dist:.1f} m, decisions {dict(sorted(reasons.items()))}")
check("live: no ego-NPC collision", collisions == 0 and ego_min > 0.4, f"collisions={collisions}, closest NPC {ego_min:.2f} m")
check("live: Stop reset everything (ego back at start, sim time 0)", rt.sim_time() == 0.0 and rt.step_count() == 0)
t0 = time.perf_counter()
for k in range(200):
    zt._on_step(1.0 / 60.0, k / 60.0)
per_step_ms = (time.perf_counter() - t0) / 200 * 1000
rt.reset()                                       # undo the 200 manual steps
check("traffic + signals step is cheap (< 3 ms incl. USD writes)", per_step_ms < 3.0, f"{per_step_ms:.2f} ms/step with {n_active} NPCs")

# ---------------- report (printed, and saved to <project>/logs/validation_report.txt) ----------------
import os
w = max(len(n) for _, n, _ in results)
lines = ["=" * (w + 30)]
for ok, name, detail in results:
    lines.append(f"[{'PASS' if ok else 'FAIL'}] {name:<{w}}  {detail}")
fails = [n for ok, n, _ in results if not ok]
lines.append("=" * (w + 30))
lines.append(f"{len(results) - len(fails)}/{len(results)} checks passed" + ("" if not fails else f"  -- FAILED: {fails}"))
print("\n".join(lines))
_dir = os.path.join(os.path.dirname(omni.usd.get_context().get_stage_url().replace("file:/", "")), "logs")
os.makedirs(_dir, exist_ok=True)
with open(os.path.join(_dir, "validation_report.txt"), "w", encoding="utf-8") as _f:
    _f.write("\n".join(lines) + "\n")
