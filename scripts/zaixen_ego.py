# zaixen_ego.py -- autonomous ego (in-sim, no ROS, ground-truth perception for now).
#
# The ego drives its fixed E-W route forever:
#     east along the eastbound lane (y=-0.5) -> across the junction -> U-turn at the east arm end ->
#     west along the westbound lane (y=+0.5) -> across the junction -> U-turn at the west arm end -> repeat
#
# It DECIDES every physics step (it does not replay a path):
#     * reads the X-axis traffic light and STOPS at its stop line on red / yellow, goes on green
#     * slows / stops for any car close ahead on its path (NPC ground-truth positions for now)
#     * is driven through the vehicle's real controls (Ackermann steering + wheel speeds via the joint drives),
#       so it moves under physics: real dynamics, real collisions.
#
# ===== PART A: pure decision logic (no omni/USD imports) =====================================
# One clear function. This exact function can later move into a ROS node unchanged:
#
#     cmd, plan = ego_decide(light, obstacle_dist, pose, plan)
#
#   light          "GREEN" | "YELLOW" | "RED"   the ego's (X-axis) signal
#   obstacle_dist  metres from the ego's front bumper to the nearest car ahead on its path, or None
#   pose           EgoPose(x, y, yaw, v)        chassis centre (mid-wheelbase), heading, forward speed
#   plan           Plan (progress along the route); pass back what the previous call returned
#   -> cmd         Command(go, speed, steer, reason)   go: False = stopping/holding; speed: target m/s;
#                  steer: front steering angle in rad (+ = left); reason: "go" | "red" | "yellow" | "obstacle"
#
# ego_perceive() is the stand-in "sensor": ground-truth NPC positions -> obstacle_dist.
import math

# ---------------------------------------------------------------- vehicle + route constants
WHEELBASE, TRACK, WHEEL_R = 0.32, 0.24, 0.052       # Leatherback (from its own Ackermann controller node)
REAR_AXLE = 0.16                                     # chassis centre -> rear axle (chassis origin = mid-wheelbase)
FRONT_X = 0.26                                       # chassis centre -> front bumper
STEER_MAX = 0.62                                     # rad: keeps the INNER front wheel at ~44 deg (the asset's own limit is 45)
LANE_E, LANE_W = -0.5, 0.5                           # eastbound / westbound lane centres (right-hand traffic)
X_TURN = 11.0                                        # centre x of the U-turn at each arm end
R_TURN = 0.5                                         # U-turn radius: half the lane spacing
STOP_FRONT = 1.75                                    # front bumper stops here (same as the NPCs)
STOP_MARGIN = 0.05
V_CRUISE, V_TURN = 0.9, 0.5                          # m/s
A_STOP = 1.0                                         # comfortable deceleration used for every stop profile
GAP = 0.25                                           # bumper-to-bumper gap kept behind a car ahead
HIT_R = 0.5                                          # a car within this of the ego's path is "in the way"
HIT_R_TURN = 0.95                                    # ... around a U-turn arc that the ego has not started yet (swept area)
PATH_DS = 0.04


def _build_path():
    def line(x0, y0, x1, y1):
        n = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / PATH_DS)))
        return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]

    def arc(cx, cy, r, a0, a1):
        n = max(2, int(math.ceil(abs(math.radians(a1 - a0)) * r / PATH_DS)))
        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n)]

    legs = [("E", line(-X_TURN, LANE_E, X_TURN, LANE_E)),
            ("UE", arc(X_TURN, 0.0, R_TURN, -90.0, 90.0)),            # left U-turn: east lane -> west lane
            ("W", line(X_TURN, LANE_W, -X_TURN, LANE_W)),
            ("UW", arc(-X_TURN, 0.0, R_TURN, 90.0, 270.0))]           # left U-turn: west lane -> east lane
    pts, leg = [], []
    for name, seg in legs:
        pts += seg
        leg += [name] * len(seg)
    n = len(pts)
    ph = [math.atan2(pts[(i + 1) % n][1] - pts[i - 1][1], pts[(i + 1) % n][0] - pts[i - 1][0]) for i in range(n)]
    return [p[0] for p in pts], [p[1] for p in pts], ph, leg


PX, PY, PH, LEG = _build_path()
N = len(PX)
TURN_STARTS = [i for i in range(N) if LEG[i] in ("UE", "UW") and LEG[i - 1] not in ("UE", "UW")]


class EgoPose:
    __slots__ = ("x", "y", "yaw", "v")

    def __init__(self, x, y, yaw, v=0.0):
        self.x, self.y, self.yaw, self.v = x, y, yaw, v


class Plan:
    """Where the ego is on its route. The only state the decision function carries between calls."""
    __slots__ = ("idx",)

    def __init__(self, idx=0):
        self.idx = idx


class Command:
    __slots__ = ("go", "speed", "steer", "reason", "leg")

    def __init__(self, go, speed, steer, reason, leg):
        self.go, self.speed, self.steer, self.reason, self.leg = go, speed, steer, reason, leg


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _progress(idx, rx, ry):
    """Where the rear axle is on the route. Strictly forward-only search from the current index: looking backwards
    lets the ego lock onto the END of the loop when it starts behind the route's first point (both are equally near)."""
    best, bi = 1e9, idx
    for k in range(0, 70):
        i = (idx + k) % N
        d = (PX[i] - rx) ** 2 + (PY[i] - ry) ** 2
        if d < best:
            best, bi = d, i
    return bi


def ego_decide(light, obstacle_dist, pose, plan=None):
    """The ego's whole decision: (light, obstacle distance, pose) -> (stop/go + speed, steering). See the header."""
    plan = plan or Plan()
    c, s = math.cos(pose.yaw), math.sin(pose.yaw)
    rx, ry = pose.x - REAR_AXLE * c, pose.y - REAR_AXLE * s          # rear axle: the bicycle model's reference point
    idx = _progress(plan.idx, rx, ry)
    leg = LEG[idx]
    turning = leg in ("UE", "UW")

    # --- steering: pure pursuit on the route
    ld = 0.45 if turning else max(0.55, 0.3 + 0.7 * abs(pose.v))
    gi = (idx + int(ld / PATH_DS)) % N
    alpha = _wrap(math.atan2(PY[gi] - ry, PX[gi] - rx) - pose.yaw)
    steer = max(-STEER_MAX, min(STEER_MAX, math.atan2(2.0 * WHEELBASE * math.sin(alpha), ld)))

    # --- speed: cruise, slower through the U-turns, and slow down BEFORE reaching one
    v_target = V_TURN if turning else V_CRUISE
    if not turning:
        ahead = min(((i - idx) % N) * PATH_DS for i in TURN_STARTS)
        v_target = min(v_target, math.sqrt(V_TURN ** 2 + 2.0 * A_STOP * ahead))
    reason = "go"

    # --- traffic light: stop at the line on red / yellow (unless too close to stop), go on green
    if leg in ("E", "W") and light != "GREEN":
        front = pose.x + FRONT_X * c
        d_line = (-STOP_FRONT - front) if leg == "E" else (front - STOP_FRONT)   # distance still to go to the line
        if -0.05 <= d_line < 30.0 or (light == "RED" and pose.v < 0.15 and -0.5 < d_line < 30.0):
            need = pose.v * pose.v / (2.0 * (3.0 if light == "RED" else 1.5))
            if d_line >= need - 0.05 or (light == "RED" and pose.v < 0.15):
                v_stop = math.sqrt(2.0 * A_STOP * max(d_line - STOP_MARGIN, 0.0))
                if v_stop < v_target:
                    v_target, reason = v_stop, light.lower()

    # --- car ahead: slow down and stop behind it. Inside a U-turn the ego is committed (the NPCs yield to it),
    #     so only a car that is practically touching stops it.
    if obstacle_dist is not None:
        if turning:
            if obstacle_dist < 0.20:
                v_target, reason = 0.0, "obstacle"
        else:
            v_obs = math.sqrt(2.0 * A_STOP * max(obstacle_dist - GAP, 0.0))
            if v_obs < v_target:
                v_target, reason = v_obs, "obstacle"

    plan.idx = idx
    holding = reason != "go" and v_target < 0.05
    return Command(not holding, max(v_target, 0.0), steer, reason, leg), plan


def ego_perceive(npcs, pose, plan, look=3.0):
    """Stand-in sensor: distance (m, front bumper -> nearest car) to any NPC on the ego's path ahead, else None.
    npcs: iterable of (x, y, yaw) ground-truth NPC poses. Replace with real perception later; same output.
    Before a U-turn the corridor is wider around the turn arc (its swept area is much wider than the lane), so the
    ego holds at the turn start until a car in that area has gone; once it is turning it is committed."""
    idx = plan.idx if plan is not None else 0
    turning_now = LEG[idx] in ("UE", "UW")
    best = None
    for k in range(int(look / 0.1) + 1):
        i = (idx + int(k * 0.1 / PATH_DS)) % N
        cx, cy = PX[i] + REAR_AXLE * math.cos(PH[i]), PY[i] + REAR_AXLE * math.sin(PH[i])   # ego centre at that point
        on_arc = LEG[i] in ("UE", "UW") and not turning_now
        r = HIT_R_TURN if on_arc else HIT_R
        for nx, ny, _yaw in npcs:
            if (nx - cx) ** 2 + (ny - cy) ** 2 < r * r:
                best = k * 0.1
                if on_arc:                          # a car in the turn's swept area: hold BEFORE the arc starts
                    to_arc = min(((j - idx) % N) * PATH_DS for j in TURN_STARTS)
                    best = max(0.0, to_arc - (REAR_AXLE + FRONT_X))     # (bumper distance to the arc start)
                break
        if best is not None:
            break
    return best


# ===== PART B: vehicle control (Ackermann geometry) ===========================================
def wheel_commands(v, steer):
    """Rear-axle speed v (m/s, + forward) and front steering angle (rad, + left) ->
    (steer_left_deg, steer_right_deg, {wheel: deg/s}). Ideal Ackermann: inner wheel turns more, slower on the inside."""
    if abs(steer) < 1e-4:
        w = math.degrees(v / WHEEL_R)
        return 0.0, 0.0, {"RL": w, "RR": w, "FL": w, "FR": w}
    R = WHEELBASE / math.tan(steer)                      # signed turn radius of the rear-axle centre (+ = left)
    dl = math.atan(WHEELBASE / (R - TRACK / 2.0))        # left front wheel   (atan, NOT atan2: R is negative for right turns
    dr = math.atan(WHEELBASE / (R + TRACK / 2.0))        # right front wheel   and atan2 would flip the wheel ~180 degrees)
    yaw_rate = v / R
    sp = lambda lat, lon: math.degrees(math.copysign(math.hypot(lat, lon) * abs(yaw_rate), v) / WHEEL_R)
    return math.degrees(dl), math.degrees(dr), {
        "RL": sp(R - TRACK / 2.0, 0.0), "RR": sp(R + TRACK / 2.0, 0.0),
        "FL": sp(R - TRACK / 2.0, WHEELBASE), "FR": sp(R + TRACK / 2.0, WHEELBASE)}


# ===== PART C: Isaac Sim glue (drives the joints every physics step) ==========================
JOINTS = {"RL": "Wheel__Upright__Rear_Left", "RR": "Wheel__Upright__Rear_Right",
          "FL": "Wheel__Knuckle__Front_Left", "FR": "Wheel__Knuckle__Front_Right",
          "SL": "Knuckle__Upright__Front_Left", "SR": "Knuckle__Upright__Front_Right"}
JOINT_ROOT = "/World/Ego/leatherback/Joints/"
ROS_DRIVE_GRAPH = "/World/Ego/leatherback/ROS_Ackermann_Drive"
A_ACC, A_DEC, STEER_RATE = 0.6, 2.5, 2.5                # m/s^2, m/s^2, rad/s

STATUS = {"leg": "", "reason": "", "cmd_speed": 0.0, "steer": 0.0, "obstacle": None, "speed": 0.0}
_S = {}


def _set_targets(steer_l_deg=0.0, steer_r_deg=0.0, wheels=None):
    wheels = wheels or {}
    for key, attr, val in (("SL", "pos", steer_l_deg), ("SR", "pos", steer_r_deg), ("RL", "vel", wheels.get("RL", 0.0)),
                           ("RR", "vel", wheels.get("RR", 0.0)), ("FL", "vel", wheels.get("FL", 0.0)),
                           ("FR", "vel", wheels.get("FR", 0.0))):
        _S["drv"][key][attr].Set(float(val))


def _on_reset():
    _S["plan"], _S["v_cmd"], _S["steer_cmd"], _S["blind"] = Plan(), 0.0, 0.0, 0
    STATUS.update(leg="", reason="", cmd_speed=0.0, steer=0.0, obstacle=None, speed=0.0)
    if "drv" in _S:
        _set_targets()


def _on_step(dt, t):
    import zaixen_runtime as rt
    import zaixen_traffic as zt
    snap = rt.ego()
    if snap is None:
        _S["blind"] = _S.get("blind", 0) + 1
        if _S["blind"] == 120:                            # 2 s without a valid ego pose: the ego is gone / corrupted
            import omni.timeline
            _set_targets()
            omni.timeline.get_timeline_interface().stop()
            print("[zaixen_ego] FAILSAFE: no valid ego pose for 2 s -> drives zeroed, timeline stopped")
        return
    _S["blind"] = 0
    if not all(math.isfinite(q) for q in (snap.x, snap.y, snap.yaw)) or abs(snap.x) > 60.0 or abs(snap.y) > 60.0:
        import omni.timeline                              # physics has gone wrong (e.g. the ego was flung off the map)
        _set_targets()
        omni.timeline.get_timeline_interface().stop()
        print(f"[zaixen_ego] FAILSAFE: ego pose invalid ({snap.x}, {snap.y}) -> drives zeroed, timeline stopped")
        return
    v = snap.vx * math.cos(snap.yaw) + snap.vy * math.sin(snap.yaw)
    pose = EgoPose(snap.x, snap.y, snap.yaw, v)
    sim = zt._S.get("sim")
    npcs = [(c.x, c.y, c.h) for c in sim.cars if c.active] if sim is not None else []
    obstacle = ego_perceive(npcs, pose, _S["plan"])
    cmd, _S["plan"] = ego_decide(zt.TRAFFIC_STATE["X"], obstacle, pose, _S["plan"])
    if zt.collision_flag(60):                             # touched a car in the last second: cut the drive, do not push on
        _S["v_cmd"] = 0.0
        cmd = Command(False, 0.0, cmd.steer, "collision", cmd.leg)
    # ramp the commanded speed / steering so the physics sees smooth demands
    dv = cmd.speed - _S["v_cmd"]
    _S["v_cmd"] += max(-A_DEC * dt, min(A_ACC * dt, dv))
    ds = cmd.steer - _S["steer_cmd"]
    _S["steer_cmd"] += max(-STEER_RATE * dt, min(STEER_RATE * dt, ds))
    sl, sr, wh = wheel_commands(_S["v_cmd"], _S["steer_cmd"])
    _set_targets(sl, sr, wh)
    STATUS.update(leg=cmd.leg, reason=cmd.reason, cmd_speed=_S["v_cmd"], steer=_S["steer_cmd"], obstacle=obstacle, speed=v)


def arm():
    """Take over the ego's drive joints (the ROS Ackermann graph is switched off meanwhile) and register with the runtime."""
    import omni.usd
    import omni.graph.core as og
    from pxr import UsdPhysics
    import zaixen_runtime as rt
    disarm()
    stage = omni.usd.get_context().get_stage()
    _S["drv"] = {}
    for key, name in JOINTS.items():
        d = UsdPhysics.DriveAPI.Get(stage.GetPrimAtPath(JOINT_ROOT + name), "angular")
        _S["drv"][key] = {"pos": d.GetTargetPositionAttr(), "vel": d.GetTargetVelocityAttr()}
    g = og.Controller.graph(ROS_DRIVE_GRAPH)
    _S["graph_was_disabled"] = g.is_disabled()
    g.set_disabled(True)                                  # otherwise it rewrites the same joint targets with zeros every tick
    _on_reset()
    rt.register("ego", on_reset=_on_reset, on_step=_on_step, order=30)


def disarm():
    """Give the ego back: zero the drives and re-enable the ROS drive graph (so ROS control works again)."""
    import zaixen_runtime as rt
    rt.unregister("ego")
    if "drv" in _S:
        _set_targets()
    if "graph_was_disabled" in _S:
        import omni.graph.core as og
        _S.pop("graph_was_disabled")
        # The asset ships with this graph ENABLED. Always give it back that way (do not "restore" what we saw at arm time:
        # after an interrupted session that could be a leftover disabled state).
        og.Controller.graph(ROS_DRIVE_GRAPH).set_disabled(False)
    _S.pop("drv", None)
