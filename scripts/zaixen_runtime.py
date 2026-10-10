# zaixen_runtime.py -- the one simulation clock everything hangs off.
#
# Determinism: lights, NPC traffic, the ego controller and the CSV logger are all driven from the
# PhysX step callback, i.e. from FIXED 1/60 s steps, never from wall-clock time. So:
#   * nothing moves while the timeline is stopped or paused,
#   * pressing Stop resets every module to the same seeded starting state, so every Play is identical.
#
# Modules register hooks:
#   register("traffic", on_reset=fn(), on_step=fn(dt, t), on_contact=fn(pairs), order=20)
# Per physics step: the ego snapshot is refreshed first, then on_step hooks run in `order`.
# Contact reports (pairs of prim-path strings) are forwarded to on_contact hooks.
import math

DT = 1.0 / 60.0
EGO_CHASSIS = "/World/Ego/leatherback/Rigid_Bodies/Chassis"

_S = {"time": 0.0, "step": 0, "run": 0, "hooks": {}, "ego": None, "subs": {}, "armed": False}


class EgoSnapshot:
    """Ego chassis pose + velocity in the world frame (chassis origin = mid-wheelbase)."""
    __slots__ = ("x", "y", "yaw", "vx", "vy", "wz")

    def __init__(self, x, y, yaw, vx=0.0, vy=0.0, wz=0.0):
        self.x, self.y, self.yaw, self.vx, self.vy, self.wz = x, y, yaw, vx, vy, wz


def register(name, on_reset=None, on_step=None, on_contact=None, order=50):
    _S["hooks"][name] = dict(reset=on_reset, step=on_step, contact=on_contact, order=order)


def unregister(name):
    _S["hooks"].pop(name, None)


def sim_time():
    return _S["time"]


def step_count():
    return _S["step"]


def run_id():
    return _S["run"]


def ego():
    return _S["ego"]


def _ordered():
    return sorted(_S["hooks"].values(), key=lambda h: h["order"])


def _read_ego(dt):
    import omni.usd
    from pxr import Gf, UsdGeom
    prim = omni.usd.get_context().get_stage().GetPrimAtPath(EGO_CHASSIS)
    if not prim.IsValid():
        return None
    m = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    p = m.ExtractTranslation()
    d = m.TransformDir(Gf.Vec3d(1, 0, 0))
    if not (math.isfinite(p[0]) and math.isfinite(p[1]) and abs(p[0]) < 100.0 and abs(p[1]) < 100.0):
        return None                                   # a corrupt / stale pose: better no data than wrong data
    prev = _S["ego"]
    yaw = math.atan2(d[1], d[0])
    vx = vy = wz = 0.0
    if prev is not None and dt > 1e-6:
        vx, vy = (p[0] - prev.x) / dt, (p[1] - prev.y) / dt
        wz = ((yaw - prev.yaw + math.pi) % (2 * math.pi) - math.pi) / dt
        if math.hypot(vx, vy) > 3.0:                  # a reset / teleport, not a real velocity
            vx = vy = wz = 0.0
        vx, vy = 0.5 * prev.vx + 0.5 * vx, 0.5 * prev.vy + 0.5 * vy
        wz = 0.7 * prev.wz + 0.3 * wz
    return EgoSnapshot(p[0], p[1], yaw, vx, vy, wz)


def reset():
    """Back to t = 0 with every module in its seeded start state (called on Stop and on arm)."""
    _S["time"], _S["step"] = 0.0, 0
    _S["run"] += 1
    _S["ego"] = None      # on Stop the physics has not restored the start pose yet: the first step supplies a fresh one
    for h in _ordered():
        if h["reset"]:
            h["reset"]()


def _on_step(dt):
    try:
        _S["ego"] = _read_ego(dt)
        t = _S["time"]
        for h in _ordered():
            if h["step"]:
                h["step"](dt, t)
        _S["step"] += 1
        _S["time"] = _S["step"] * DT
    except Exception as exc:                          # never spam every step: report once and disarm
        import traceback
        print("[zaixen_runtime] step failed, disarming:", exc)
        traceback.print_exc()
        disarm()


def _on_contact(headers, _data):
    try:
        from pxr import PhysicsSchemaTools
        from omni.physx.bindings._physx import ContactEventType
        pairs = []
        for h in headers:
            if h.type == ContactEventType.CONTACT_LOST:
                continue
            pairs.append((str(PhysicsSchemaTools.intToSdfPath(h.actor0)), str(PhysicsSchemaTools.intToSdfPath(h.actor1))))
        if pairs:
            for hk in _ordered():
                if hk["contact"]:
                    hk["contact"](pairs)
    except Exception as exc:
        print("[zaixen_runtime] contact callback failed:", exc)


def _on_timeline(event):
    import omni.timeline
    if event.type == int(omni.timeline.TimelineEventType.STOP):
        reset()


def arm():
    """Start listening to the physics step / contact reports / timeline Stop. Safe to call again."""
    import omni.physx
    import omni.timeline
    disarm()
    _S["subs"]["step"] = omni.physx.get_physx_interface().subscribe_physics_step_events(_on_step)
    _S["subs"]["contact"] = omni.physx.get_physx_simulation_interface().subscribe_contact_report_events(_on_contact)
    _S["subs"]["timeline"] = omni.timeline.get_timeline_interface().get_timeline_event_stream().create_subscription_to_pop(
        _on_timeline, name="zaixen_runtime")
    _S["armed"] = True


def disarm():
    for k in list(_S["subs"]):
        sub = _S["subs"].pop(k)
        try:
            sub.unsubscribe()
        except AttributeError:
            pass
    _S["armed"] = False
