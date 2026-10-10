# SUPERSEDED by zaixen_traffic.py (run_simulation.py arms it). Do not run this together with it: two drivers would fight over the same cars/lights.
import time
import omni.usd
import omni.kit.app
from pxr import UsdGeom, Gf

stage = omni.usd.get_context().get_stage()

try:
    if NPC_MOVER_SUB is not None:  # noqa: F821
        NPC_MOVER_SUB.unsubscribe()  # noqa: F821
except NameError:
    pass
NPC_MOVER_SUB = None

ROAD_HALF_W = 1.0
ROAD_TOP = stage.GetPrimAtPath("/World/Junction").GetAttribute("zaixen:roadSurfaceZ").Get()  # single road-height source (part1_drivable_surface.py)
JUNC_HALF = ROAD_HALF_W
CW_BAND = 0.6          # crosswalk width, painted flush against the junction edge
STOP_BOUNDARY = JUNC_HALF + CW_BAND  # stop line sits just behind the crosswalk, not in front of it
CAR_HALF_LEN = 0.4      # half of the NPC car body length (see step5_npc_cars.py CAR_LEN)
STOP_MARGIN = 0.03
ARM_LEN = 15.0
NPC_SPEED = 1.2   # m/s free-flow speed
NPC_GAP = 1.4      # m minimum following gap (center-to-center; leaves ~0.6 m bumper-to-bumper)

def classify_heading(rot_deg):
    r = round(rot_deg) % 360
    if r == 0:
        return ("X", 1)
    if r == 180:
        return ("X", -1)
    if r == 90:
        return ("Y", 1)
    if r == 270:
        return ("Y", -1)
    raise ValueError(f"unexpected car heading {rot_deg}")

# rediscover the NPC cars from the already-saved geometry (translate + rotateZ encode
# lane axis/direction/offset/progress, so no separate car-state needs to be persisted)
NPC_CARS = []
cars_scope = stage.GetPrimAtPath("/World/Junction/NPCCars")
for child in cars_scope.GetChildren():
    if not child.GetName().startswith("Car_"):
        continue
    xf = UsdGeom.Xformable(child)
    t_op = None
    r_op = None
    for op in xf.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            t_op = op
        elif op.GetOpType() == UsdGeom.XformOp.TypeRotateZ:
            r_op = op
    translate = t_op.Get()
    heading = r_op.Get() if r_op is not None else 0.0
    axis, direction = classify_heading(heading)
    s = translate[0] if axis == "X" else translate[1]
    offset = translate[1] if axis == "X" else translate[0]
    NPC_CARS.append({
        "path": str(child.GetPath()), "t_op": t_op,
        "axis": axis, "dir": direction, "offset": offset, "s": s,
    })

print(f"discovered {len(NPC_CARS)} NPC cars")

def _npc_stop_limit(axis, direction, s):
    approaching = (s * direction) < -1e-6
    if not approaching:
        return None
    if abs(s) < STOP_BOUNDARY:
        return None  # already past the stop boundary -- committed, let it clear
    phase = TRAFFIC_STATE.get(axis)  # noqa: F821 (from rearm_traffic_lights.py, run first)
    if phase in ("RED", "YELLOW"):
        # clamp the CAR CENTER so its FRONT BUMPER (center + CAR_HALF_LEN) stops just
        # behind STOP_BOUNDARY -- clamping the center directly at STOP_BOUNDARY let the
        # front bumper overshoot onto the crosswalk/into the junction by CAR_HALF_LEN
        return -(STOP_BOUNDARY + CAR_HALF_LEN + STOP_MARGIN)
    return None

_npc_last_time = time.time()

def _npc_mover_on_update(e):
    global _npc_last_time
    now = time.time()
    dt = now - _npc_last_time
    _npc_last_time = now
    if dt <= 0 or dt > 0.5:
        return

    lanes = {}
    for car in NPC_CARS:
        key = (car["axis"], car["dir"])
        lanes.setdefault(key, []).append(car)

    for (axis, direction), cars in lanes.items():
        cars.sort(key=lambda c: c["s"] * direction)
        leader_max = None
        for car in reversed(cars):  # frontmost first
            s = car["s"]
            progress = s * direction
            target = progress + NPC_SPEED * dt

            stop_limit = _npc_stop_limit(axis, direction, s)
            if stop_limit is not None:
                target = min(target, stop_limit)
            if leader_max is not None:
                target = min(target, leader_max - NPC_GAP)
            target = max(target, progress)
            leader_max = target

            new_s = target * direction
            if new_s > ARM_LEN:
                new_s -= 2 * ARM_LEN
            elif new_s < -ARM_LEN:
                new_s += 2 * ARM_LEN

            car["s"] = new_s
            x, y = (new_s, car["offset"]) if axis == "X" else (car["offset"], new_s)
            car["t_op"].Set(Gf.Vec3d(x, y, ROAD_TOP))

_update_stream = omni.kit.app.get_app().get_update_event_stream()
NPC_MOVER_SUB = _update_stream.create_subscription_to_pop(_npc_mover_on_update, name="npc_car_mover")

print("NPC queuing mover re-armed")
