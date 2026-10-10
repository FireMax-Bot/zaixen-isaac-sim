# Run this once after opening zaixen_scene.usd to bring the whole live simulation back to life.
#
# It re-arms EVERY runtime callback (they are behaviour, not USD data, so they must be re-armed after each stage load):
#   zaixen_runtime  the fixed 60 Hz simulation clock (physics-step driven; resets everything on Stop)
#   zaixen_traffic  traffic lights (X and Y) + NPC traffic on the plus roads and the ring + "NPC Traffic" window
#   zaixen_ego      the autonomous ego driver (decides + drives through the real vehicle controls)
#   zaixen_log      the CSV recorder (registered but OFF until you switch it on)
#
# HOW TO RUN THIS IN ISAAC SIM:
#   Window > Script Editor  ->  open this file (or paste its contents)  ->  press Run (Ctrl+Enter)
#   Then press Play. Nothing moves until Play; Stop resets everything to the same start, so runs repeat exactly.
#
# Change the NPC count any time: the slider in the "NPC Traffic" window, or  zaixen_traffic.set_npc_count(14)
# Log to CSV:     zaixen_log.enable()  /  zaixen_log.disable()   (or tick "Log to CSV" in the window)
# Ego on/off:     zaixen_ego.disarm()  gives the ego back (e.g. to ROS);  zaixen_ego.arm()  takes it again
import os
import sys
import importlib
import omni.usd

_url = omni.usd.get_context().get_stage_url() or ""
_scripts = os.path.join(os.path.dirname(_url.replace("file:/", "").replace("file:", "")), "scripts")
if not os.path.isdir(_scripts):
    _scripts = "D:/Robotics/Projects/Zaixen_simulation/scripts"
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

# Isaac's Python may trust cached .pyc files without checking the source (edited scripts would silently not load).
# So: never write bytecode for our modules, delete any that exist, and drop the modules so they import fresh.
import glob
sys.dont_write_bytecode = True
for _pyc in glob.glob(os.path.join(_scripts, "__pycache__", "zaixen_*.pyc")):
    try:
        os.remove(_pyc)
    except OSError:
        pass
importlib.invalidate_caches()                                                     # pick up modules added since Isaac started
for _name in ("zaixen_log", "zaixen_ego", "zaixen_traffic", "zaixen_runtime"):     # stop anything already running first
    _old = sys.modules.get(_name)
    if _old is not None:
        try:
            _old.disarm()
        except Exception as _e:
            print(f"(note) could not disarm previous {_name}: {_e}")
for _name in ("zaixen_log", "zaixen_ego", "zaixen_traffic", "zaixen_runtime"):
    sys.modules.pop(_name, None)                                                  # import from the source files, fresh
import zaixen_runtime, zaixen_traffic, zaixen_ego, zaixen_log

zaixen_runtime.arm()          # the clock: physics-step + contact reports + Stop-resets
zaixen_traffic.arm()          # lights + NPCs (count from /World/Junction.zaixen:npcCount, default 10)
zaixen_ego.arm()              # autonomous ego (switches the ROS Ackermann graph off while it drives)
zaixen_log.arm()              # recorder registered, OFF
zaixen_runtime.reset()        # everything to its seeded t=0 state
print("Simulation armed. Press Play. (Stop resets to the same start; NPC count slider + 'Log to CSV' are in the NPC Traffic window.)")
