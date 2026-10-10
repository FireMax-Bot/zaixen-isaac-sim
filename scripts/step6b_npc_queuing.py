import time
import omni.kit.app
from pxr import Gf

# unsubscribe the old (non-queuing) mover
try:
    if NPC_MOVER_SUB is not None:  # noqa: F821
        NPC_MOVER_SUB.unsubscribe()  # noqa: F821
except NameError:
    pass
NPC_MOVER_SUB = None

CW_BAND = 0.6            # crosswalk width, painted flush against the junction edge
STOP_BOUNDARY = JUNC_HALF + CW_BAND  # noqa: F821 -- stop line sits just behind the crosswalk
CAR_HALF_LEN = 0.4        # half of the NPC car body length (see step5_npc_cars.py CAR_LEN)
STOP_MARGIN = 0.03
NPC_SPEED = 1.2   # m/s, free-flow speed
NPC_GAP = 1.4      # m, minimum following gap (center-to-center); ~0.6 m bumper-to-bumper

def _npc_stop_limit(axis, direction, s):
    """Return the max progress (s*direction) allowed by the stop line, or None if unconstrained."""
    approaching = (s * direction) < -1e-6
    if not approaching:
        return None
    if abs(s) < STOP_BOUNDARY:
        return None  # already past the stop boundary -- committed, let it clear
    phase = TRAFFIC_STATE.get(axis)  # noqa: F821
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
    for car in NPC_CARS:  # noqa: F821
        key = (car["axis"], car["dir"])
        lanes.setdefault(key, []).append(car)

    for (axis, direction), cars in lanes.items():
        # sort rear -> front by progress along the direction of travel
        cars.sort(key=lambda c: c["s"] * direction)

        leader_max = None  # progress ceiling imposed by the car ahead (set while iterating front->rear)
        for car in reversed(cars):  # frontmost first
            s = car["s"]
            progress = s * direction
            target = progress + NPC_SPEED * dt

            stop_limit = _npc_stop_limit(axis, direction, s)
            if stop_limit is not None:
                target = min(target, stop_limit)

            if leader_max is not None:
                target = min(target, leader_max - NPC_GAP)

            target = max(target, progress)  # never move backward
            leader_max = target

            new_s = target * direction
            if new_s > ARM_LEN:  # noqa: F821
                new_s -= 2 * ARM_LEN  # noqa: F821
            elif new_s < -ARM_LEN:  # noqa: F821
                new_s += 2 * ARM_LEN  # noqa: F821

            car["s"] = new_s
            x, y = (new_s, car["offset"]) if axis == "X" else (car["offset"], new_s)
            car["t_op"].Set(Gf.Vec3d(x, y, 0.0))

_update_stream = omni.kit.app.get_app().get_update_event_stream()
NPC_MOVER_SUB = _update_stream.create_subscription_to_pop(_npc_mover_on_update, name="npc_car_mover")

print("STEP6B OK - NPC queuing mover armed")
