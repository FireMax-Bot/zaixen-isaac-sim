# zaixen_log.py -- lightweight per-step CSV recorder for metrics. OFF by default.
#
#   import zaixen_log
#   zaixen_log.enable()            # start logging (new file logs/sim_log_<timestamp>.csv in the project folder)
#   zaixen_log.disable()           # stop + flush          zaixen_log.toggle()   zaixen_log.status()
#   zaixen_log.enable(every=6)     # log every 6th physics step (10 Hz) instead of every step (60 Hz)
# or tick "Log to CSV" in the "NPC Traffic" window.
#
# It records on the fixed 60 Hz physics step (so only while the timeline is Playing). One file can hold many
# runs: the `run` column increments on every Stop/Play reset and `sim_time` restarts at 0.
#
# Columns: run, step, sim_time, ego_x, ego_y, ego_yaw, ego_speed, ego_leg, ego_reason, ego_cmd_speed, ego_steer,
#          ego_obstacle_dist, light_X, light_Y, collision (1 while the ego touches an NPC), collisions_total,
#          n_npc, then for every NPC slot i: npc{i}_x, npc{i}_y, npc{i}_yaw, npc{i}_v (empty when that car is inactive).
import os
import time

LOG_DIR = "D:/Robotics/Projects/Zaixen_simulation/logs"
FLUSH_EVERY = 120                                   # rows

_S = {"on": False, "fh": None, "path": None, "every": 1, "buf": [], "rows": 0, "n": 0}


def _header(n_npc):
    cols = ["run", "step", "sim_time", "ego_x", "ego_y", "ego_yaw", "ego_speed", "ego_leg", "ego_reason",
            "ego_cmd_speed", "ego_steer", "ego_obstacle_dist", "light_X", "light_Y", "collision", "collisions_total", "n_npc"]
    for i in range(n_npc):
        cols += [f"npc{i}_x", f"npc{i}_y", f"npc{i}_yaw", f"npc{i}_v"]
    return ",".join(cols)


def _flush():
    if _S["fh"] is not None and _S["buf"]:
        _S["fh"].write("\n".join(_S["buf"]) + "\n")
        _S["fh"].flush()
        _S["buf"].clear()


def enable(path=None, every=1):
    """Start logging. Default file: <project>/logs/sim_log_<timestamp>.csv. Returns the file path."""
    import zaixen_traffic as zt
    disable()
    if path is None:
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, time.strftime("sim_log_%Y%m%d_%H%M%S.csv"))
    _S.update(fh=open(path, "w", encoding="utf-8", newline="\n"), path=path, every=max(1, int(every)), rows=0,
              n=zt.MAX_NPCS, on=True)
    _S["fh"].write(_header(_S["n"]) + "\n")
    print(f"[zaixen_log] logging ON -> {path}  (rows are written while the timeline is playing)")
    return path


def disable():
    if _S["fh"] is not None:
        _flush()
        _S["fh"].close()
        print(f"[zaixen_log] logging OFF ({_S['rows']} rows written to {_S['path']})")
    _S.update(fh=None, on=False)


def toggle():
    return disable() if _S["on"] else enable()


def is_on():
    return _S["on"]


def status():
    return {"on": _S["on"], "path": _S["path"], "rows": _S["rows"], "every": _S["every"]}


def _fmt(v, nd=4):
    return "" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def _on_step(dt, t):
    if not _S["on"]:
        return
    import zaixen_runtime as rt
    import zaixen_traffic as zt
    step = rt.step_count()
    if step % _S["every"]:
        return
    e = rt.ego()
    try:
        import zaixen_ego as ze
        st = ze.STATUS
    except Exception:
        st = {"leg": "", "reason": "", "cmd_speed": 0.0, "steer": 0.0, "obstacle": None, "speed": 0.0}
    ts = zt.TRAFFIC_STATE
    sim = zt._S.get("sim")
    row = [str(rt.run_id()), str(step), _fmt(t, 4),
           _fmt(e.x if e else None), _fmt(e.y if e else None), _fmt(e.yaw if e else None), _fmt(st["speed"], 3),
           st["leg"], st["reason"], _fmt(float(st["cmd_speed"]), 3), _fmt(float(st["steer"]), 3), _fmt(st["obstacle"], 2),
           ts["X"], ts["Y"], str(zt.collision_flag()), str(zt.COLLISION["total"]), str(sim.n_active() if sim else 0)]
    cars = sim.cars if sim else []
    for i in range(_S["n"]):
        if i < len(cars) and cars[i].active:
            c = cars[i]
            row += [_fmt(c.x), _fmt(c.y), _fmt(c.h), _fmt(c.v, 3)]
        else:
            row += ["", "", "", ""]
    _S["buf"].append(",".join(row))
    _S["rows"] += 1
    if len(_S["buf"]) >= FLUSH_EVERY:
        _flush()


def _on_reset():
    _flush()                                         # a Stop ends the run: make sure everything is on disk


def arm():
    """Register with the runtime. Registering does NOT start logging; call enable() (or tick the checkbox) for that."""
    import zaixen_runtime as rt
    rt.register("log", on_step=_on_step, on_reset=_on_reset, order=90)


def disarm():
    import zaixen_runtime as rt
    disable()
    rt.unregister("log")
