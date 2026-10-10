# Zaixen Ring-Road Simulation — Full Report

Project folder: `D:\Robotics\Projects\Zaixen_simulation`  
Scene file: `zaixen_scene.usd` (saved, verified by re-opening it from disk)  
Report date: 2026-09-20  
Companion document: `docs/Beginner_Guide_Zaixen_Simulation.pdf` (how to build and explain a scene like this)

---

## 1. The 60-second summary

We have an Isaac Sim scene made of:

- a **plus-shaped road** (two 2 m wide roads crossing at a signalised junction) whose four arms end on a
- **ring road** (radius 15 m, one lane clockwise on the inside, one lane counter-clockwise on the outside),
- with rounded curb corners, lane paint, give-way lines, traffic lights, lamps, and about **2,000 scenery props** (trees, bushes, hedges, fences, benches, bins, flowers, grass),
- **up to 30 NPC cars** (default 10) that drive fixed lane paths on **all four arms and the ring**, obey the lights, keep a gap, take turns at merges and crossings, and always yield to the ego,
- one **autonomous ego vehicle** (the Leatherback) that **decides for itself**: it drives its E–W route, U-turns at each arm end, **stops at its stop line on red/yellow, goes on green, and slows/stops for cars ahead**, driven through its real steering and wheel controls under physics,
- a **fixed 60 Hz simulation clock**, so every Play repeats exactly,
- **real collisions** (the ego physically hits cars; the contact is reported, logged, and the NPC stops),
- an optional **CSV recorder** (off by default), and
- a new **chase camera locked to the ego chassis** that can see the traffic lights all the way to the stop line.

Everything was tested three ways: off-line (plain Python, about 44 simulated hours of soak runs), in the running app (29 automated checks) and by deliberate crash tests. Result: **zero collisions, zero red-light runs, no deadlocks** in the final code.

---

## 2. The three things you asked for at the end (quick answers)

### 2.1 Re-arm commands for every runtime callback

Lights, NPC traffic, ego controller and logger are *behaviour*, not stored in the `.usd`, so they must be re-armed after every time you open the scene.

**Easiest — one script for everything:** open `zaixen_scene.usd`, then in Isaac Sim  
`Window > Script Editor` → open `scripts\run_simulation.py` → **Run (Ctrl+Enter)** → press **Play**.

| Callback | Module | Individual command |
|---|---|---|
| Simulation clock (fixed 60 Hz physics step, contact reports, Stop-reset) | `zaixen_runtime` | `zaixen_runtime.arm()` |
| Traffic lights + NPC traffic + slider window | `zaixen_traffic` | `zaixen_traffic.arm()` |
| Ego controller (autonomous driver) | `zaixen_ego` | `zaixen_ego.arm()` |
| CSV recorder (registered, **off**) | `zaixen_log` | `zaixen_log.arm()` |

Undo commands: `zaixen_log.disarm()`, `zaixen_ego.disarm()` (also gives the ego back to ROS), `zaixen_traffic.disarm()`, `zaixen_runtime.disarm()`.

Useful live commands: `zaixen_traffic.set_npc_count(14)` (0–30), or drag the slider in the **NPC Traffic** window.

### 2.2 CSV log: path and how to switch it on

- Folder: `D:\Robotics\Projects\Zaixen_simulation\logs\`
- File name: `sim_log_<YYYYMMDD_HHMMSS>.csv`, a new file each time you enable logging. A real example is kept as `logs\example_sim_log.csv`.
- **Off by default.** Switch on: `import zaixen_log; zaixen_log.enable()` — or tick **"Log to CSV"** in the NPC Traffic window. Off: `zaixen_log.disable()` (or untick).
- `zaixen_log.enable(every=6)` logs every 6th physics step (10 Hz) instead of every step (60 Hz).
- It only records while the timeline is **Playing**. One file can hold several runs: the `run` column goes up by one at every Stop, and `sim_time` restarts at 0.
- Columns (137): `run, step, sim_time, ego_x, ego_y, ego_yaw, ego_speed, ego_leg, ego_reason, ego_cmd_speed, ego_steer, ego_obstacle_dist, light_X, light_Y, collision, collisions_total, n_npc`, then for each of the 30 NPC slots `npcN_x, npcN_y, npcN_yaw, npcN_v` (empty when that car is inactive).

### 2.3 Name of the ego decision function

**`ego_decide(light, obstacle_dist, pose, plan)`** in `scripts\zaixen_ego.py` — returns `(cmd, plan)` where `cmd = Command(go, speed, steer, reason, leg)`.
It is pure Python (no Isaac imports), so it can move into a ROS node unchanged. Its stand-in "sensor" is `ego_perceive(npcs, pose, plan)`.

### 2.4 How to run the project (open the scene and press Play?)

**No — opening the `.usd` and pressing Play is not enough.** The scene file stores the *things* (roads, cars, lights, cameras, the ego). The *behaviour* — signal timing, NPC driving, the autonomous ego, the collision handling, the logger and the slider panel — is Python code, and code cannot be stored in a `.usd`. Without the script, Play runs physics only: the lights stay as they were, the cars stand still and the ego does nothing.

Every time you open the scene (or restart Isaac Sim):

1. `File > Open` → `zaixen_scene.usd`
2. `Window > Script Editor` → `File > Open` → `scripts\run_simulation.py` → **Run** (Ctrl+Enter). Wait for "Simulation armed" and for the **NPC Traffic** panel (bottom right, next to Property).
3. Press **Play**. Press **Stop** to reset to the identical start (no need to run the script again after Stop).

What `run_simulation.py` does: finds the `scripts` folder, disarms any older copy, deletes stale cached `.pyc` files and imports the four modules fresh, then arms the fixed-step clock, the traffic, the ego driver and the (off) logger, and resets everything to t = 0. Making this automatic (Isaac `--exec` launch flag, or a small Kit extension) is possible but was not done; the manual step is simple and easy to debug. The guide explains all of this in topic 3.6.

---

## 3. What we did, in order

### 3.0 Recovering the unfinished work
The earlier session ended mid-way. I read the project (`D:\Robotics\Projects\Zaixen_simulation`, not the NVIDIA repo), connected to the running Isaac Sim through its python server (`127.0.0.1:8226`), and found that the rewritten road geometry had **never been applied** to the live scene. I backed up the scene (`zaixen_scene_backup_v1.usd`) and continued.

### 3.1 The five bugs / requests you listed before Part 3

| # | Your request | What was done | Result |
|---|---|---|---|
| 1 | "Corner at the end of each straight road looks chipped" | Replaced the square sidewalk boxes with four **continuous sidewalk bands** with a **0.8 m rounded curb return** at every arm mouth, and filled the corner behind each curb with road-height asphalt (`part2_ring_roads.py`) | Smooth rounded corners; car paths keep ≥ 0.35 m from every curb |
| 2 | NPCs should use the ring with fixed, car-like logic, different timings/positions, controllable count | Four fixed closed loops on the N–S arms + ring (later four more on E–W arms), smooth arc turns, speed limits from curvature, lights, following gap, conflict zones; **slider 0–30, default 10** | No collisions, no deadlocks (see §5) |
| 3 | Yellow lines incomplete at the T-junctions | Ring centre line now runs **unbroken** across all arm mouths (94 dashes); every arm gets a dashed **give-way line** | Visible in the top view |
| 4 | Ego and NPC the same size | NPC prims scaled ×0.6 → **0.480 × 0.300 m** vs ego **0.476 × 0.305 m** | Within 1–2 % |
| 5 | Make it look better, cheaply | `PointInstancer` scenery: extra round + pine trees, bushes, hedges, fences, benches, bins, flowers, grass tufts (**~2,000 instances, no colliders**) | Cheap to render, physics untouched |

Questions I asked and your answers for this stage: NPCs form **one unified pool**; ego on **E–W arms**; save with **backup first**.

### 3.2 Part 4 — foundations

- **Determinism.** The PhysX scene was already 60 steps/s. The real fix was moving cars, lights, ego and logger from wall-clock time to the **fixed physics step** (`zaixen_runtime`). Nothing moves while stopped; **Stop resets everything to the same seeded start**. Proof: two Plays differ by **0.000 mm** in ego position and 0 in NPC state, lights and decisions identical (even with logging on).
- **Collisions.** Each NPC is now a **kinematic rigid body** (moved by the traffic logic, cannot be pushed) with a collider and a **contact-report API**. The ego already has colliders (chassis, wheels, suspension: 27 prims). Deliberate crash test: ego (made blind on purpose) drove into a parked car → contact detected at t = 4.77 s, collision flag = 1, NPC held still, ego stopped, no bounce or instability.
- **Logging hook.** `zaixen_log` (see §2.2). Off by default; tested (137 columns, 305 rows for 30 s at 10 Hz).

### 3.3 Part 5 — autonomous ego (in-sim, no ROS, no sensors)

- Route: east along the eastbound lane → across the junction → **U-turn** at the east end → west along the westbound lane → across the junction → U-turn → repeat.
- **It decides, it does not replay.** Every physics step it reads `TRAFFIC_STATE["X"]` and the distance to the nearest car ahead (ground-truth NPC positions for now) and calls `ego_decide`.
- **Driven through real vehicle controls**: Ackermann front-wheel angles (position drives) and four wheel speeds (velocity drives) written to the asset's own joint drives every step. No teleporting. The asset's ROS Ackermann graph is switched off while the in-sim driver runs, and **switched back on by `zaixen_ego.disarm()`**.
- Behaviours: stop at the line on red/yellow (yellow: only if it can stop comfortably), go on green, follow/stop behind cars, wait before a U-turn if a car is in the turn's swept area, cut drive immediately if it touches a car, failsafe that stops the timeline if the ego's pose ever becomes invalid.
- **The U-turn.** You chose a back-and-forth turn *because I claimed the ego could not turn in one sweep*. That was my mistake: the vehicle's own controller allows 45° steering with a 0.32 m wheelbase, so a smooth **0.5 m-radius semicircle** fits easily inside the 2 m road. I built the smooth U-turn; you confirmed you are happy with it.

### 3.4 NPCs on the ego's road
You asked that NPCs may also enter the ego's road. The four loops were **turned 90°** to make four more loops on the E–W arms (obeying the X signal). Because the ego and NPCs now share lanes, the ego gets real cars ahead of it. Wherever two loops cross or merge (junction, ring mouths) a precomputed **conflict zone** lets the first car through and makes the other stop short of it. A car stopped by a red light, or stuck behind another car, never holds a claim on a zone (this rule removed several deadlocks).

### 3.5 The new camera
- **`Camera_Chase` cannot be removed.** It is *defined* inside the ego's referenced asset (`leatherback.usd`); the scene file only overrides its pose. `RemovePrim` returns False and the prim stays (tested safely in the throw-away session layer). Per your instruction I **left it exactly as it was**.
- **New camera:** `/World/Ego/leatherback/Rigid_Bodies/Chassis/Camera_ChassisView`. It is a **child of the chassis**, so it is locked to the ego. Compared with your chase view (1.0 m behind, 0.56 m up, 15.8° down, 60° wide) it is 1.3 m behind, 0.92 m up, **6.8° down, 70° wide**, so the top of the frame is 21° above the horizon: the signal heads (1.5 m tall) stay visible from the start all the way to the stop line. Proof images: `docs\images\camera_view_start.png` and `docs\images\camera_view_stopline.png`.
- The viewport has been switched to it (camera menu → choose another to switch back).

### 3.6 Part 6 — save and report
- Backup taken; all runtime hooks disarmed (drives zeroed, ROS graph re-enabled); scene **saved to `zaixen_scene.usd`**.
- Proof: the file was **re-opened from disk**, `run_simulation.py` run, and the full validator gave **29/29 checks passed** (`logs\validation_report.txt`).

### 3.7 Follow-up: the NPC Traffic panel text overlap (fixed)
- **Symptom:** in the docked **NPC Traffic** panel the label ("10 NPC cars driving (max 30)") was drawn on top of another copy of itself and the slider showed a wrong value.
- **Cause:** every run of `run_simulation.py` created a *new* `ui.Window` with the same title. Hiding a window does not delete it, and Isaac cannot delete a native window whose Python object was lost when the module was reloaded, so several panels piled up. Their old sliders were still alive and one even wrote a wrong NPC count (1) into the stage.
- **Fix (`zaixen_traffic.show_ui`):** one window object is created once, kept on `builtins` (survives module reloads), and **reused** on every arm (`frame.clear()` and rebuild). Stale copies from older versions are hidden. Each row now has an explicit height. Verified by arming twice and by a full-application screenshot: one label, one slider (10), one check box, no overlap (`docs\images\npc_traffic_panel.png`). Old hidden copies may remain until Isaac Sim is restarted; they are invisible and harmless.
- The guide documents how such a panel is built (topic 3.7) and lists everyday tricks (topic 3.8).

---

## 4. Files

### Scripts (`scripts\`)
| File | Role |
|---|---|
| `run_simulation.py` | **The one script to run after opening the scene** (re-arms everything) |
| `zaixen_runtime.py` | The fixed 60 Hz clock; physics step, contact reports, Stop-reset |
| `zaixen_traffic.py` | Signals, 8 NPC loops, conflict zones, kinematic NPC bodies, slider window, `TRAFFIC_STATE`, collision flag |
| `zaixen_ego.py` | `ego_decide`, `ego_perceive`, Ackermann `wheel_commands`, joint-drive glue, failsafes |
| `zaixen_log.py` | CSV recorder (off by default) |
| `validate_scene.py` | 29 in-app checks; writes `logs\validation_report.txt` |
| `test_ring_traffic.py`, `test_ego_loop.py` | Off-line tests / soaks (plain Python) |
| `part1_drivable_surface.py` | Road height rule, colliders, physics materials (ego seating now runs once only) |
| `part2_ring_roads.py` | Ring road, rounded curb returns, continuous centre line, give-way lines |
| `part4_scenery.py` | Instanced scenery |
| `step1…step6c_*.py` | Original build steps (junction, markings, lights, ego placement, old NPCs, greenery) |
| `rearm_*.py`, `step5_npc_cars.py` | **Superseded** by `zaixen_traffic.py` (marked at the top; do not run together with it) |

### Scenes and data
| File | Meaning |
|---|---|
| `zaixen_scene.usd` | **Final scene** |
| `zaixen_scene_backup_v1.usd` | The scene as it was before any of this work |
| `zaixen_scene_backup_v2_autosave_1440.usd` | An Isaac autosave from 14:40 (mid-way, contains the NPC pool) |
| `logs\example_sim_log.csv`, `logs\validation_report.txt` | Example log and last validation report |
| `docs\images\*` | Screenshots used in the guide |

---

## 5. Evidence (what was tested and what happened)

| Test | Scale | Result |
|---|---|---|
| NPC soak, 4 loops | 4 counts × 8 seeds × 30 sim-min | 0 collisions, 0 red-light runs, longest stop 11.8 s (a red light) |
| NPC soak, 8 loops (E–W added) | 4 counts × 8 seeds × 30 sim-min | same |
| **Ego + NPC soak** (real `ego_decide` in a bicycle model) | N = 10, 20, 30 × 8 seeds × 30 sim-min | **0 ego–NPC contacts, 0 red-light runs, 0 off-road, ~22 laps each, ego never stuck longer than a red light** |
| Live physics, 90 s, 10 NPCs | real Isaac physics | ego drove 58 m, 3 legs, stopped on red/yellow, 0 collisions, closest NPC 1.00 m |
| Live physics, 90 s, 30 NPCs | real Isaac physics | ego slowed/stopped for cars ~36 s, 0 collisions, closest 0.74 m |
| Deliberate crash | blind ego vs parked car | contact reported, NPC held, ego stopped cleanly |
| Determinism | 2 Plays, 30 s | 0.000 mm difference |
| In-app validator | on the scene re-opened from disk | **29 / 29 passed** |
| Cost | traffic + signals per step | ~1 ms with 10 NPCs (3 ms budget) |

Sim speed note: with rendering on this PC the simulation runs roughly 2–3× slower than real time (e.g. 18 s of sim time took ~51 s). Determinism is in *simulation* time, so this does not affect results.

---

## 6. Problems we hit and how they were solved (lessons)

1. **Rewritten geometry never applied** — the earlier run had stopped before running it. Always check the live stage, not just the script.
2. **Stale bytecode.** Isaac's Python trusted old `.pyc` files, so *edited scripts silently did not load* (several "fixes" were not running). `run_simulation.py` now deletes cached bytecode and imports fresh.
3. **Right-turn wheels pointed backwards.** Front-wheel angle used `atan2` instead of `atan`; a negative turn radius flipped the wheel ~180°. Fixed and unit-tested for mirror symmetry.
4. **Ego route lock-on.** Progress search could pick the end of the loop when the ego started behind the route start. Now forward-only.
5. **Stale ego pose at Stop** (physics has not restored the start pose yet) fed garbage to the controller; the runtime now rejects invalid poses.
6. **Ego leaving the road → physics explosion** (pose ~10¹²). The wheels are infinite-force velocity servos, so hitting static geometry can blow up. Prevented by the route fix; a **failsafe** now stops the timeline if the pose is ever invalid.
7. **Deadlocks found only by long soaks**: (a) a three-car wait cycle at a mouth (fixed by "only the queue head contests a zone"); (b) claims from cars that could not move (fixed by the "can it really get through?" rule); (c) an NPC waiting for an ego that was waiting for it (fixed: an NPC ignores an ego *behind it in its own lane*).
8. **Near-collisions during U-turns**: NPCs predicted the ego in a straight line although it was turning; the ego also started a turn with a car already in the swept area. Fixed with turn-rate-aware prediction, a wider margin in turns, and "hold before the arc until the swept area is clear".
9. **Contact flicker** counted one crash as five. Collisions are now counted per episode (1 s gap).
10. **Disarm restored the wrong ROS-graph state** after an interrupted session; it now always re-enables the graph (the asset's default).

11. **Duplicate UI windows.** Re-creating a window with the same title on every arm stacked panels (overlapping text, stale sliders). Create it once and reuse it (see §3.7).

---

## 7. Known limits / honest notes

- **Not tested with your ROS controller.** In-sim the ego reads NPC positions from the simulation (ground truth). Real perception, and a ROS node calling `ego_decide`, are the next steps.
- While the in-sim ego drives, the asset's **ROS Ackermann graph is off**; call `zaixen_ego.disarm()` to hand control back.
- NPCs are kinematic: they cannot be pushed. After a hit an NPC stops for 1 s, then continues.
- With many NPCs a red-light queue can back up into the ring mouth for up to ~25 s (congestion, not a deadlock; the queue always clears).
- Signal timing is unchanged (20 s cycle: 8 s green, 2 s yellow, 10 s red) and has no all-red gap; the conflict zones cover a car that is still in the junction when the light changes.
- `Camera_Chase` remains in the scene (it cannot be deleted; it could be *deactivated* if you ever want it hidden).
- Isaac autosaved once during the work (`…autosave_1440.usd`), so that backup is a mid-way snapshot, not a clean "before" copy. `zaixen_scene_backup_v1.usd` is the clean original.
