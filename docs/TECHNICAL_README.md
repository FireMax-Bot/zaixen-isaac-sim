# Zaixen Simulation

A deterministic Isaac Sim traffic scene with an autonomous ego vehicle, exposed over ROS 2, built to generate labelled normal and attack data for training and testing an anomaly-detection agent.

**Status:** Layer 1 (vehicle and scene) complete and verified. ROS 2 bridge working. Dataset generation, attack injection and the defence agent are in progress.
**Scope:** defensive research. Every attack runs against our own simulation on an isolated ROS 2 domain.

---

## 1. About the project

The project has three layers.

| Layer | What it is | Status |
|---|---|---|
| 1. Simulated vehicle | Isaac Sim scene, traffic, and an autonomous ego car that publishes its data on ROS 2 | This repository, complete |
| 2. Attack module | Small ROS 2 nodes that fake, replay, flood or alter messages on the live bus | Planned |
| 3. Defence agent | Watches the same topics, flags abnormal behaviour, and later responds | Separate, planned |

The workflow it supports:

1. Record a baseline: the ego drives normally, no attack.
2. Run each attack alone against the undefended car. Record video and data.
3. Measure how far each attack pushes the car from the baseline.
4. Repeat with the defence agent active and compare side by side.

Because every attack and every sensor reading travels over standard ROS 2 topics, the same attack tools can later plug into the defence agent with no rework.

## 2. Problem

ROS 2 systems usually run without DDS authentication or encryption. Any process on the same domain can publish to any topic. To build and evaluate a defence we need:

- a repeatable vehicle simulation with a clear normal behaviour,
- controlled anomalies injected on the ROS 2 bus,
- ground-truth labels for every injected event,
- measurable before and after comparisons.

A real vehicle is costly and unsafe for this, so we simulate it.

## 3. Requirements

| # | Requirement | Status |
|---|---|---|
| R1 | Identical runs give identical trajectories | Met (0.000 mm difference between two Plays) |
| R2 | Ego decides from the light and obstacles, not from a replayed path | Met, in simulation |
| R3 | Signalised junction with continuous traffic | Met |
| R4 | Real collisions between the ego and other cars | Met |
| R5 | Sensor data on ROS 2 topics with sim-time stamps | Partial: `/odom` and `/tf` live; `/clock`, `/imu`, contact in progress |
| R6 | Reliable Windows-to-WSL2 ROS 2 discovery | Met (see 6.6) |
| R7 | Normal dataset with natural variation | Planned |
| R8 | Live attack injection with automatic labels | Planned |
| R9 | Raw (rosbag2) and time-aligned (Parquet) outputs | Planned |

## 4. Architecture

```
Windows 11                                    WSL2 (Ubuntu 22.04, ROS 2 Humble)
+----------------------------------+          +------------------------------------+
| Isaac Sim 6.0.1                  |          | Fast DDS Discovery Server          |
|  scene: junction + ring road     |   DDS    | ROS 2 nodes                        |
|  traffic lights + NPC cars       | <------> |  telemetry monitor                 |
|  ego car (Leatherback, PhysX)    |          |  data collector      (planned)     |
|  ROS 2 bridge graphs             |          |  attack injector     (planned)     |
|  Python server on port 8226      |          |  defence agent       (separate)    |
+----------------------------------+          +------------------------------------+
```

Isaac Sim does not run inside WSL2, so it runs on Windows. ROS 2 runs in WSL2. The two meet over DDS.

Target data pipeline:

```
Isaac Sim sensors -> ROS 2 topics -> collector -> rosbag2 (raw)
                                              \-> Parquet at 50 Hz (aligned, labelled)
attack injector --(live, on the bus)--> topics, and writes the label track
```

## 5. Methodology

- **Live injection.** Attacks are applied on the running bus while the car drives. The true physics keeps running underneath, so the inconsistency between sensors is genuine.
- **Normal data as a distribution.** A seeded sweep varies NPC count, ego speed, start offset and light phase. Each run is reproducible and the set is diverse.
- **Automatic labels.** The injector knows what it injected and when, and writes the label track: type, target, start, end.
- **Clean sensors by design.** Simulated sensors carry no noise. A made-up noise model would be a guess. Real-sensor noise is a documented sim-to-real gap (see 8).

## 6. Implementation

### 6.1 Scene

- Isaac Sim 6.0.1, mini scale. Units are metres, Z-up.
- A plus-shaped road: two roads, each 2 m wide, crossing at a signalised junction.
- Four arms end on a ring road of 15 m radius. The inner lane runs clockwise, the outer lane runs counter-clockwise.
- Rounded curb corners, lane paint, give-way lines, an unbroken ring centre line, lamps.
- About 2,000 scenery props (trees, bushes, hedges, fences, benches, bins, flowers, grass) as a `PointInstancer`. They have no colliders, so they are cheap.
- Roads carry collision meshes aligned with the visible surface.

### 6.2 Traffic signals

- Fixed 20 s cycle: GREEN 8 s, YELLOW 2 s, RED 10 s.
- The cross road is offset by 10 s, so it is red while the first road is green.
- No all-red interval. Conflict zones cover a car still in the junction when the light changes.
- State is held in a Python dict, `TRAFFIC_STATE`, with keys `X` and `Y`. It is not yet on a ROS 2 topic.

### 6.3 NPC traffic

- One pool of up to 30 cars (default 10). A slider in the **NPC Traffic** panel sets the count.
- Eight fixed closed loops: four on the N-S arms plus the ring, and four on the E-W arms.
- Cars obey the lights, keep a gap, take turns at merges and crossings through precomputed conflict zones, and always yield to the ego.
- Each NPC is a kinematic rigid body with a collider and a contact-report API. It cannot be pushed.
- NPC size is 0.480 x 0.300 m. The ego is 0.476 x 0.305 m.

### 6.4 Ego vehicle

- NVIDIA Leatherback (`leatherback_ROS.usd`), a PhysX vehicle.
- Route on the E-W arms: east across the junction, smooth U-turn (0.5 m radius semicircle) at the end, west across the junction, U-turn, repeat.
- Decision logic is one pure-Python function: `ego_decide(light, obstacle_dist, pose, plan)`, returning `(cmd, plan)`. It has no Isaac Sim imports, so it can move into a ROS 2 node unchanged.
- It stops at its stop line on red or yellow, goes on green, and slows or stops for cars ahead.
- It is driven through real vehicle controls: Ackermann front-wheel angles and four wheel speeds written to the asset's joint drives every physics step. No teleporting.
- Obstacle distance comes from ground-truth NPC positions (`ego_perceive`), not from a sensor.
- While the in-sim driver runs, the asset's ROS Ackermann graph is switched off. `zaixen_ego.disarm()` switches it back on.

### 6.5 Determinism

- Fixed 60 Hz simulation clock. Cars, lights, ego and logger run on the physics step, not on wall-clock time.
- Nothing moves while stopped. Stop resets everything to the same seeded start.

### 6.6 ROS 2 bridge

| Item | Value |
|---|---|
| ROS 2 distro | Humble on both sides |
| Domain | `ROS_DOMAIN_ID=0` |
| RMW | `rmw_fastrtps_cpp` |
| Isaac Sim launcher | `run_isaacsim_humble.bat` |
| WSL2 networking | `networkingMode=mirrored` in `.wslconfig` |
| Discovery | Fast DDS Discovery Server at `127.0.0.1:11811` |
| WSL environment | `ROS_DISCOVERY_SERVER=127.0.0.1:11811`, `ROS_SUPER_CLIENT=True` |

Default multicast discovery was unreliable across the WSL2 boundary: it worked on some runs and failed on others. Mirrored networking plus a discovery server removes the dependency on multicast.

Use `--no-daemon` with `ros2` CLI commands. Mirrored networking is known to break the `ros2` CLI daemon even when data flows.

### 6.7 Published topics

| Topic | Type | Status |
|---|---|---|
| `/odom` | `nav_msgs/msg/Odometry` (frames `odom` to `base_link`) | Live |
| `/tf` | `tf2_msgs/msg/TFMessage` | Live |
| `/clock` | `rosgraph_msgs/msg/Clock` | In progress |
| `/imu` | `sensor_msgs/msg/Imu` | In progress |
| Contact | TODO: message type | In progress |

All stamps are sim time.

### 6.8 Logging

An optional CSV recorder, off by default, writes to `logs/sim_log_<YYYYMMDD_HHMMSS>.csv`. It has 137 columns: run, step, sim time, ego pose, speed, decision and reason, obstacle distance, light state, collision flag, and x, y, yaw, speed for each of the 30 NPC slots. Enable it with `zaixen_log.enable()` or the **Log to CSV** box. `zaixen_log.enable(every=6)` logs at 10 Hz.

## 7. Testing and results

| Test | Scale | Result |
|---|---|---|
| NPC soak, 4 loops, then 8 loops | 4 counts x 8 seeds x 30 simulated min | 0 collisions, 0 red-light runs, longest stop 11.8 s (a red light) |
| Ego and NPC soak (real `ego_decide`, bicycle model) | N = 10, 20, 30 x 8 seeds x 30 simulated min | 0 ego-NPC contacts, 0 red-light runs, 0 off-road, about 22 laps each |
| Live physics, 10 NPCs | 90 s | Ego drove 58 m over 3 legs, stopped on red and yellow, 0 collisions, closest NPC 1.00 m |
| Live physics, 30 NPCs | 90 s | Ego slowed or stopped for cars about 36 s, 0 collisions, closest NPC 0.74 m |
| Deliberate crash | Blind ego vs parked car | Contact detected at t = 4.77 s, flag set, NPC held, ego stopped, no instability |
| Determinism | 2 Plays, 30 s | 0.000 mm difference in ego position |
| In-app validator | Scene reopened from disk | 29 of 29 checks passed (`logs/validation_report.txt`) |
| Per-step cost | Traffic and signals, 10 NPCs | About 1 ms (3 ms budget) |

With rendering on the development PC (RTX 3060, 12 GB), the simulation runs about 2-3 times slower than real time. Determinism is in simulation time, so results are unaffected.

TODO: bridge reliability. Record how many of N full restarts gave a working `ros2 topic echo /odom --once --no-daemon`.

TODO: dataset results (number of normal runs, run length, size, attack events per type) once generation is done.

## 8. Limitations

1. **The ego is driven by an in-sim callback, not by ROS 2.** A drive command sent over ROS 2 will not move the car today. Attacks on `/imu`, `/odom` and contact change the data the detector sees, but not how the car drives. A V1 attack must not be described as having caused a crash.
2. **Obstacle sensing is ground truth.** A sensor-spoofing attack has no effect on the ego's decisions until a real sensor replaces it.
3. **Sensors are idealised and noise-free.** Models trained only on this data have not seen real noise, drift or bias. This is a sim-to-real gap.
4. **No all-red interval** in the signal cycle.
5. **NPCs are kinematic.** They cannot be pushed. After a hit an NPC stops for 1 s, then continues.
6. **Congestion.** With many NPCs, a red-light queue can back up into a ring mouth for up to about 25 s. The queue always clears.
7. **Low-poly scene at small scale.** Results are relative (deviation from baseline), not guarantees for a production vehicle.
8. **Modest hardware.** RTX camera and RTX lidar are held back to limit VRAM use.

## 9. Future work

- Move `ego_decide` into a ROS 2 node so commands travel over the bus.
- Publish traffic-light state on a ROS 2 topic.
- Replace ground-truth obstacle sensing with lidar or a physics raycast.
- Add RTX lidar for cross-sensor consistency checks.
- Add synthesised GPS/GNSS for position-spoofing scenarios.
- Defence agent with in-path mitigation, and measurement of its resource cost.

## 10. Reproducing

### Requirements

- Windows 11, NVIDIA GPU (developed on RTX 3060, 12 GB), 32 GB RAM
- Isaac Sim 6.0.1
- WSL2 Ubuntu 22.04 with ROS 2 Humble
- Network access to NVIDIA's asset server (the scene references the Leatherback asset by URL)

### Run order

1. WSL: confirm `.wslconfig` has `networkingMode=mirrored`. Run `wsl --shutdown` once after changing it.
2. WSL: start the Fast DDS Discovery Server. TODO: add the exact command or auto-start method.
3. Windows: launch Isaac Sim with `run_isaacsim_humble.bat`.
4. Windows: `File > Open` `zaixen_scene.usd`.
5. Windows: `Window > Script Editor`, open `scripts/run_simulation.py`, run it (Ctrl+Enter). Wait for "Simulation armed" and the **NPC Traffic** panel.
6. Press **Play**. Press **Stop** to reset to the identical start.
7. WSL: check the bridge.
   ```
   ros2 topic list -t --no-daemon
   ros2 topic echo /odom --once --no-daemon
   ```

Opening the scene and pressing Play is not enough. Signals, NPC driving, the ego controller, collision handling and the logger are Python code. Code cannot be stored in a `.usd`, so `run_simulation.py` must be run after every scene open or Isaac Sim restart.

### Replaying recorded data

```
ros2 bag info <bag_dir>
ros2 bag play <bag_dir> --clock
```

## 11. Repository layout

```
zaixen_scene.usd              final scene
scripts/
  run_simulation.py           run this after opening the scene
  zaixen_runtime.py           fixed 60 Hz clock, contact reports, Stop-reset
  zaixen_traffic.py           signals, NPC loops, conflict zones, slider panel
  zaixen_ego.py               ego_decide, ego_perceive, Ackermann drive glue
  zaixen_log.py               CSV recorder
  validate_scene.py           29 in-app checks
  test_ring_traffic.py        off-line soak tests
  test_ego_loop.py            off-line ego soak tests
  part1..part4, step1..step6  scene build scripts
ros_bridge/                   WSL2 bridge setup, recorder scripts, run_isaacsim_humble.bat
logs/                         example log, validation report
docs/                         this file, report, beginner guide, images
AI_team_data/                 normal-driving dataset (only on the ai-team-data branch)
```

Superseded scripts (`rearm_*.py`, `step5_npc_cars.py`) are marked at the top of each file. Do not run them together with `zaixen_traffic.py`.

## 12. Data

| Item | Format | Notes |
|---|---|---|
| Raw | rosbag2 (MCAP) | Exact bus contents, replayable |
| Aligned | Parquet, 50 Hz | One row per tick: sensor columns plus label columns |
| Labels | Parquet columns and a separate event list | `label`, `attack_type`, `target`, `start`, `end` |

TODO: topic list per bag, bag sizes, and the Parquet schema once the collector is built.

## 13. Uploading to GitHub

Branches and tags:

- `main`: scene, scripts and docs.
- `ai-team-data`: branched from `main`, adds `AI_team_data/`. Data versions are tags, for example `dataset-v1-normal`.

GitHub rejects single files over 100 MB. Everything so far is far below that, so Git LFS is not used. If future bags grow large, track them with Git LFS first. The backup scenes (`zaixen_scene_backup_*.usd`) are left out of the repository.

## 14. Assets and licensing

- The ego uses NVIDIA's Leatherback asset, loaded from NVIDIA's asset servers. It is not redistributed here. Check NVIDIA's terms before publishing any USD file that embeds it.
- This repository's own code is released under the MIT licence (see `LICENSE`).

## 15. Security and responsible use

The attack tooling is for defensive evaluation against this simulation only. Run it on an isolated ROS 2 domain or an offline network. Do not point it at systems you do not own.

## 16. Team

Ziaxen. TODO: add contributors and contact.
