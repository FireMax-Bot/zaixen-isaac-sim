# Zaixen simulation: normal-driving data (version 1)

> ## READ THIS FIRST: THERE ARE NO ATTACKS IN THIS DATA
> Everything here is **clean, normal driving**. We have **not** attacked, changed or
> injected anything on the ROS bus. No fake data, no noise, no hacking.
> Use this as the **"normal" baseline**. Attack data will come later (a separate stage).

Recorded on **2026-10-10** in Isaac Sim 6.0.1 (a simulator, not a real car).

---

## 1. What is this?
A small toy city ("mini-world") was built in Isaac Sim. One small car (the **ego**, a
Leatherback) drives itself back and forth along one road. We recorded what the car's
sensors published on ROS 2, four times, with a different number of other cars (NPCs) on
the roads each time.

Nobody drove the car by hand and nobody sent it ROS commands. The car decides by itself
inside the simulator (stops at red lights, goes on green, slows down for cars in front).

## 2. What is in this folder?

```
AI_team_data/
  README.md          <- this file
  run_index.csv      <- one line per run: which bag, which CSV, how many NPC cars
  ros_bags/          <- the ROS 2 recordings (what the detector will see)
  csv_logs/          <- the "answer sheet" from the simulator (ground truth)
```

| Run label | Other cars (NPCs) | Length (sim seconds) | ROS bag folder | CSV file | `run` column in CSV |
|---|---|---|---|---|---|
| npc0  | 0  | 67.2 | `ros_bags/run_20261010_222328_01_npc0`  | `csv_logs/sim_log_20261010_222152.csv` | 9  |
| npc10 | 10 | 60.3 | `ros_bags/run_20261010_223042_02_npc10` | `csv_logs/sim_log_20261010_223041.csv` | 10 |
| npc20 | 20 | 60.1 | `ros_bags/run_20261010_223333_03_npc20` | `csv_logs/sim_log_20261010_223041.csv` | 11 |
| npc30 | 30 | 59.9 | `ros_bags/run_20261010_223657_04_npc30` | `csv_logs/sim_log_20261010_223041.csv` | 12 |

**Two kinds of data:**
- **ROS bags** = what the car's sensors sent over ROS. This is what the anomaly detector will listen to.
- **CSV logs** = what was *really* happening inside the simulator (light colour, why the car stopped, where every NPC was). Use it to **label** and to understand the bags. It is **not** on ROS.

## 3. On what conditions was it run?
- **Software:** Isaac Sim 6.0.1 on Windows. ROS 2 Humble on Ubuntu 22.04 (WSL2). Fast DDS. ROS domain 0.
- **Scene:** `zaixen_scene.usd`. Metres, Z up. A road crossing with 4 traffic lights, a ring road around it, and about 2,000 trees/bushes/fences (scenery only, no effect on sensors).
- **The ego car:** drives along the east-west road, crosses the crossing, U-turns at the end, comes back, repeats. Top speed about **0.9 m/s**. It is a real physics vehicle. It stops at the stop line on red or yellow, and slows or stops for cars ahead.
- **Traffic lights:** repeat every **20 s**. One road: green 8 s, yellow 2 s, red 10 s. The other road is shifted by 10 s. The ego starts at the left end (x about -13 m) facing east, with the light red.
- **Other cars (NPCs):** simple moving blocks that follow fixed lanes, obey the lights and keep a gap. We tried 0, 10, 20 and 30 of them.
- **Clock:** fixed **60 steps per second** of *simulation* time. All timestamps are **simulation time**, not wall-clock.
- **Speed:** the simulator runs slower than real time (about 0.4x with few cars, about 0.26x with 30 cars). A 60 s run took 2.5 to 4 minutes of real time. This does not change the data.
- **Repeatable:** the simulation is deterministic. Playing it twice gives the same result. We checked: `/odom` was **identical to 0.0000 m** between npc0, npc10 and npc20.
- **Sensors are perfect on purpose:** no noise, no drift. Real sensors are noisier. This is a known gap between simulation and real life.
- **Recording:** npc10, npc20 and npc30 were started and stopped automatically by a script (Play, wait 60 simulated seconds, Stop). The npc0 trial was started and stopped by hand in Isaac Sim (about 67 s). In all runs nobody drove the car.
- **No attacks. No manual driving. No changes to any topic.**

## 4. What is inside the ROS bags?
Format: ROS 2 bag, `sqlite3` storage, `cdr` messages (the normal `ros2 bag` format).

| Topic | Message type | Rate | What it is |
|---|---|---|---|
| `/clock` | `rosgraph_msgs/msg/Clock` | 60 Hz | simulation time |
| `/imu` | `sensor_msgs/msg/Imu` | 60 Hz | acceleration (m/s^2), turn rate (rad/s), orientation. `frame_id` = `chassis` |
| `/odom` | `nav_msgs/msg/Odometry` | 60 Hz | wheel/vehicle odometry. Frames `odom` -> `base_link`. Position (m), speed (m/s) |
| `/contact` | `std_msgs/msg/Float32` | 60 Hz | contact signal. Only value ever seen: **0.0** (no crash happened) |
| `/tf` | `tf2_msgs/msg/TFMessage` | 60 Hz | the transform `odom` -> `base_link` |

**Things to know about the timestamps:**
- Time starts at 0 at every Play. It **restarts at 0 in each run**.
- `ros2 bag info` shows the date as 1970. That is just "seconds since Play", ignore the date.
- Each message in the bag is stored with its **simulation-time** stamp.
- `/contact` has no timestamp inside the message (it is only a number). Its time in the bag is the latest `/clock` value when it arrived, so it can be off by one step (1/60 s).
- `/imu` and `/odom` header stamps match the bag time to within one step (0.017 s).
- `/odom` starts at **x = 0, y = 0** at the start of each run. It is relative to the start pose, **not** the world position (the car really starts at x about -13 m). For world position use the CSV (`ego_x`, `ego_y`).
- The first **0.15 to 0.25 s** of each run is missing (the recorder needs a moment to connect after Play). Counts can differ by a few messages between topics (up to about 10).

## 5. What is inside the CSV logs? (ground truth, not on ROS)
One row for **every simulation step (60 per second)**, 137 columns. Main columns:

| Column | Meaning |
|---|---|
| `run` | run number. Goes up by 1 each time the simulator is stopped |
| `step` | step counter inside the run |
| `sim_time` | seconds since Play. **Use this to line up with the ROS bag** |
| `ego_x`, `ego_y`, `ego_yaw` | where the car really is (m, m, radians) |
| `ego_speed` | real speed (m/s) |
| `ego_leg` | which part of the route: `E` east-going, `W` west-going, `UE` U-turn at the east end |
| `ego_reason` | why the car is doing what it does: `go`, `red` (stopped at a light), `obstacle` (slowed or stopped for a car ahead) |
| `ego_cmd_speed`, `ego_steer` | what the car's brain asked for |
| `ego_obstacle_dist` | distance to the car ahead in metres (empty = nothing close) |
| `light_X`, `light_Y` | colour of the two roads' lights: RED / YELLOW / GREEN. `light_X` is the road the ego drives on |
| `collision`, `collisions_total` | 1 when the ego hit a car. **Always 0 in these runs** |
| `n_npc` | number of NPC cars driving in this run |
| `npc0_x ... npc29_v` | position, direction and speed of each NPC (empty when that NPC is not used) |

## 6. How to use it

**Look at a bag (needs ROS 2 Humble):**
```bash
ros2 bag info ros_bags/run_20261010_223042_02_npc10
ros2 bag play ros_bags/run_20261010_223042_02_npc10
```

**Read a bag in Python (needs ROS 2 Humble):**
```python
import rosbag2_py
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri="ros_bags/run_20261010_223042_02_npc10", storage_id="sqlite3"),
            rosbag2_py.ConverterOptions("", ""))
while reader.has_next():
    topic, data, t_ns = reader.read_next()          # t_ns = simulation time in nanoseconds
    if topic == "/odom":
        msg = deserialize_message(data, Odometry)
        print(t_ns / 1e9, msg.pose.pose.position.x, msg.twist.twist.linear.x)
```
(Without ROS installed, the pip package `rosbags` can read these bags. We have not tested that.)

**Read a CSV and line it up with a bag:**
```python
import pandas as pd
df = pd.read_csv("csv_logs/sim_log_20261010_223041.csv")
run = df[df["run"] == 10]            # run 10 = npc10 (see the table above)
print(run[["sim_time", "ego_reason", "light_X"]].head())
```
Match a ROS message to a CSV row by **simulation time**: `t_ns / 1e9` is about `sim_time`.

## 7. Things to be careful about
1. **There are no attacks here.** Do not treat anything as an "anomaly" label. It is all normal.
2. **npc0, npc10 and npc20 give the same ROS data.** The ego's sensors do not see the other cars, so the ego drives exactly the same until a car gets in its way. Only **npc30** is different: the ego was slowed by cars ahead for about 30 s, and had a close call near the east U-turn at about sim 42.6 to 47.6 s (gap reported as 0.0 m; the collision flag stayed 0 and `/contact` stayed 0.0).
3. **`/contact` never changed** (always 0.0). We have not yet checked that it reacts to a real crash.
4. **The light colour, the car's reason for stopping and the NPC positions are not on ROS**. They are only in the CSV. A detector that only listens to ROS cannot see them.
5. **Only 60 seconds per run**, and the ego follows one fixed route. This is a small first set.
6. Sensors have **no noise**. Real data will look different.

## 8. Questions?
Ask the simulation team. Full setup and how the recording was done: see the folder
`ros bag run` (next to this folder) and `REPORT_Zaixen_Simulation.md` (how the scene was built).
