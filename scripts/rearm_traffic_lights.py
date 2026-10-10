# SUPERSEDED by zaixen_traffic.py (run_simulation.py arms it). Do not run this together with it: two drivers would fight over the same cars/lights.
import time
import omni.usd
import omni.kit.app
from pxr import UsdShade, Gf

stage = omni.usd.get_context().get_stage()
mat_scope = "/World/Looks"

try:
    if TRAFFIC_LIGHT_SUB is not None:  # noqa: F821
        TRAFFIC_LIGHT_SUB.unsubscribe()  # noqa: F821
except NameError:
    pass
TRAFFIC_LIGHT_SUB = None

COLOR_EMISSIVE = {"red": Gf.Vec3f(18.0, 0.0, 0.0), "amber": Gf.Vec3f(18.0, 10.0, 0.0), "green": Gf.Vec3f(0.0, 18.0, 0.0)}
OFF_EMISSIVE = Gf.Vec3f(0.03, 0.03, 0.03)
PHASE_TO_COLOR = {"GREEN": "green", "YELLOW": "amber", "RED": "red"}

def phase_for(t):
    if t < 8.0:
        return "GREEN"
    elif t < 10.0:
        return "YELLOW"
    else:
        return "RED"

def set_axis_phase(axis, phase):
    active_color = PHASE_TO_COLOR[phase]
    for color in ("red", "amber", "green"):
        mat_path = f"{mat_scope}/Signal_{axis}_{color.capitalize()}"
        shader = UsdShade.Shader(stage.GetPrimAtPath(mat_path + "/Shader"))
        val = COLOR_EMISSIVE[color] if color == active_color else OFF_EMISSIVE
        shader.GetInput("emissiveColor").Set(val)

TRAFFIC_STATE = {"X": None, "Y": None, "t": 0.0, "cycle_len": 20.0}
_traffic_start_time = time.time()

def _traffic_light_on_update(e):
    t = (time.time() - _traffic_start_time) % 20.0
    y_phase = phase_for(t)
    x_phase = phase_for((t + 10.0) % 20.0)
    if TRAFFIC_STATE["Y"] != y_phase:
        set_axis_phase("Y", y_phase)
        TRAFFIC_STATE["Y"] = y_phase
    if TRAFFIC_STATE["X"] != x_phase:
        set_axis_phase("X", x_phase)
        TRAFFIC_STATE["X"] = x_phase
    TRAFFIC_STATE["t"] = t

set_axis_phase("Y", "GREEN")
set_axis_phase("X", "RED")
TRAFFIC_STATE["Y"] = "GREEN"
TRAFFIC_STATE["X"] = "RED"

_update_stream = omni.kit.app.get_app().get_update_event_stream()
TRAFFIC_LIGHT_SUB = _update_stream.create_subscription_to_pop(_traffic_light_on_update, name="traffic_light_timer")

print("Traffic light timer re-armed. TRAFFIC_STATE:", TRAFFIC_STATE)
