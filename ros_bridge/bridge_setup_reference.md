# Isaac Sim (Windows) <-> ROS 2 Humble (WSL2) bridge setup

Stage A. Last updated 2026-10-10.

## Every change made

### Windows side
| File | Change |
|---|---|
| `C:\Users\User\.wslconfig` | `[wsl2]` / `networkingMode=mirrored` (already present; confirmed with `wslinfo --networking-mode` -> `mirrored`) |
| `D:\Robotics\run_isaacsim_humble.bat` (user edited) | `FASTRTPS_DEFAULT_PROFILES_FILE=...fastdds_udp_only.xml` line **disabled** (`rem`). It pointed at the old address 192.168.1.5 and turned off built-in transports. |
| same `.bat` | `set ROS_DISCOVERY_SERVER=127.0.0.1:11811` added (Isaac Sim is a client of the discovery server) |
| same `.bat` | `ROS_DISTRO=humble` and the PATH entry now ends in `isaacsim.ros2.core\humble\lib` (was jazzy). Same Fast DDS 2.6 as WSL. |

`D:\Robotics\fastdds_udp_only.xml` is no longer used (not deleted).

### WSL side
| File | Change |
|---|---|
| `~/.bashrc` | `FASTRTPS_DEFAULT_PROFILES_FILE=$HOME/fastdds_udp_only.xml` export **commented out** (stale NAT workaround, wrong IP) |
| `~/.bashrc` | added `export ROS_DISCOVERY_SERVER=127.0.0.1:11811` and `export ROS_SUPER_CLIENT=True` |
| `~/.bashrc` | added auto-start line: runs `~/.local/bin/dds-server start` (does nothing if already running) |
| `~/.bashrc` | already had `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `ROS_DOMAIN_ID=0` (unchanged) |
| `~/.local/bin/dds-server` | NEW helper script: `dds-server status | start | stop` |
| `~/ros2_ws/scripts/bridge_check.py` | NEW probe: sim clock + IMU + odom + contact, rates and one sample each |
| `ros_bridge\bridge_setup_reference.md` | this file |

Deleted during cleanup: `~/cyclonedds.xml`, the pip download cache (~960 MB), `__pycache__` folders under `~/ros2_ws`.

## Start-up order for every run

1. **Open a WSL terminal.** The discovery server starts by itself (also after `wsl --shutdown`).
2. **Check it:** `dds-server status` -> must print `RUNNING: discovery server on port 11811`.
3. **Start Isaac Sim** with `run_isaacsim_humble.bat` (only after step 2: it must find the server at startup).
4. Open `zaixen_scene.usd`. In Isaac Sim: `Window > Script Editor` > open `scripts\run_simulation.py` > **Run**, wait for "Simulation armed", then press **Play**. Without this step the ego stands still (the driving logic is Python, not stored in the .usd).
5. In WSL, use `ros2 ... --no-daemon` for CLI commands, for example:
   ```bash
   ros2 topic list -t --no-daemon
   ros2 topic echo /imu --once --no-daemon
   python3 ~/ros2_ws/scripts/bridge_check.py 10
   ```
If you restart WSL or the server, restart Isaac Sim too.

## Topics published by the scene
| Topic | Type | Rate seen (wall-clock) |
|---|---|---|
| `/clock` | `rosgraph_msgs/msg/Clock` | about 21 Hz |
| `/imu` | `sensor_msgs/msg/Imu` (frame `chassis`) | about 22 Hz |
| `/odom` | `nav_msgs/msg/Odometry` (`odom` -> `base_link`) | about 22 Hz |
| `/contact` | `std_msgs/msg/Float32` (no header, so no own timestamp) | about 22 Hz |
| `/tf` | `tf2_msgs/msg/TFMessage` | not measured |

## Rules learned the hard way (Part 3)

1. **Warm up before subscribing.** A WSL node that creates its subscriptions in its first ~1 s receives **nothing** (from any of them, no error). Spin the node for at least 1 s (use 3 s), then create the subscriptions. Tested: 1, 2 and 3 s warm-ups worked every time; 0 s failed every time. `ros2 topic echo/hz` hide this because they discover first. `bridge_check.py` and the Stage B collector must do the same.
2. **`use_sim_time` works** once the node has warmed up (node clock follows `/clock` within about 0.02 s).
3. **Topics only exist while the sim is playing.** After **Stop**, all topics disappear (`ros2 topic list` shows only `/parameter_events` and `/rosout`).
4. **Sim speed:** the scene ran at about 0.43x real time. Topics publish at 60 Hz of *sim* time (about 26 Hz wall-clock), so judge rates in sim time.
5. Isaac Sim 6.0.1 bundles both `humble` and `jazzy` ROS libs. The `.bat` now uses **humble** to match WSL. Switching did not by itself fix the missing data, but it keeps versions identical.
6. A Windows `FASTRTPS_DEFAULT_PROFILES_FILE` pointing at a stale IP (the old NAT workaround) blocks discovery completely. Keep it disabled.

## Sim-time test result (Part 3, verified 2026-10-10)
Watcher log (`bridge_check.py --watch`, node with `use_sim_time=True`):
- **Pause:** `/clock` held at 5.600 for about 10 wall-seconds, then continued from 5.983. The node clock held and continued with it.
- **Stop:** topics vanished from `ros2 topic list`; the clock stayed at its last value (11.600).
- **Play after Stop:** a node that was already running reconnected by itself, and the sim clock restarted near 0 (0.7 s), so **sim time resets to 0 on every Stop/Play**. Recorded data must be split per run.

## Quick test commands
```bash
dds-server status
ros2 topic list -t --no-daemon
python3 ~/ros2_ws/scripts/bridge_check.py 10        # 4-topic table with rates + samples
python3 ~/ros2_ws/scripts/bridge_check.py --watch 60  # prints sim clock every second
```

## Stage B: recording the ego's own loop
The ego drives itself inside Isaac Sim (`ego_decide`, see REPORT_Zaixen_Simulation.md). Nothing on ROS commands it, so manual teleop cannot work: while the in-sim driver is armed the asset's ROS Ackermann graph is switched off (`zaixen_ego.disarm()` hands control back). Decision: **no manual driving; record the autonomous loop.**

- Recorder: `python3 ~/ros2_ws/scripts/record_runs.py` (leave it running in a terminal; it waits for Play).
- One bag per Play..Stop run, in `~/ros2_ws/data/bags/run_<date>_<n>/`. Pause does not split a run. Sim time restarts at 0 on every Stop/Play.
- Topics stored: `/clock /imu /odom /contact /tf`, all stamped with sim time. `/contact` has no stamp of its own, so it gets the latest `/clock` value at arrival (up to one sim step of jitter, and the first ~0.2 s of each run may be missing).
- `/odom` is relative to the start pose (x=0 at the start), not world coordinates.
- First verified run: 15.75 sim-s, 946 msgs per 60 Hz topic, timestamps monotonic, max gap 0.033 s, ego moved 2.4 m by itself.
- Ground truth (light state, ego decision, collision flag, NPC positions) is NOT on ROS. It is in the optional CSV logger (`zaixen_log.enable()`, files in `D:\Robotics\Projects\Zaixen_simulation\logs\`), which shares `sim_time` with the bags.

## Recording procedure (normal baseline, several NPC counts, CSV on)
Once per session:
1. WSL terminal A: `dds-server status` (must say RUNNING), then `python3 ~/ros2_ws/scripts/record_runs.py` and leave it open.
2. Windows: start Isaac Sim with the `.bat`, open `zaixen_scene.usd`, run `scripts\run_simulation.py`.
3. Switch the CSV logger on once: tick "Log to CSV" in the NPC Traffic panel (or `import zaixen_log; zaixen_log.enable()`). Files go to `...\Zaixen_simulation\logs\`.

For each NPC count N (suggested 0, 10, 20, 30):
1. WSL terminal B: `runlabel npcN`
2. Isaac Sim: set the NPC slider to N (or `zaixen_traffic.set_npc_count(N)`), while stopped.
3. Press **Play**, let it run at least 60 sim-seconds (about 2.5 min on the wall clock), press **Stop**.
4. Terminal A prints `RUN ... ended`. Check `cat ~/ros2_ws/data/runs_manifest.csv`.

Each bag folder contains `run_info.json` (label, start/end, counts). The CSV `n_npc` column and `sim_time` line up with the bag stamps.

## Automated recording (port 8226)
`isaac_exec.py` is a tiny client for Isaac Sim's python server (port 8226, no auth in this setup; send Python source, half-close, read JSON). `auto_record.py` uses it to run the whole loop:
```bash
# recorder must already be running in another terminal: python3 ~/ros2_ws/scripts/record_runs.py
python3 ~/ros2_ws/scripts/auto_record.py --counts 10,20,30 --sim-seconds 60
```
For each count it writes the label, sets the NPC count, presses Play, waits for the sim seconds, presses Stop and checks the recorder saved the bag. It switches on a fresh CSV for the batch and restores the original NPC count at the end. Links are in `~/ros2_ws/data/batch_index.csv` (label, bag, csv file, csv `run` id); the bag list is `~/ros2_ws/data/runs_manifest.csv`. Do not press Play/Stop yourself while it runs.
Reading the data from Windows: `\\wsl.localhost\Ubuntu-22.04\home\isc_noel\ros2_ws\data\bags` (distro name may differ).

## Finding: NPC count barely changes the ROS data (batch of 2026-10-10)
Runs npc0, npc10, npc20 gave **identical** ego `/odom` (max difference 0.0000 m). Only npc30 differs (ego followed a slow car at about 0.4 m for ~30 s, and showed a 0.0 m gap for ~5 s near the east U-turn at x~10.9, t=42.6..47.6 s, with the collision flag still 0 and `/contact` 0.0 in every run). The detector only sees the ego's sensors, so NPCs matter only when they interact with the ego. For a varied baseline use higher counts (25-30), longer runs, or other sources of variation, not 0/10/20.
