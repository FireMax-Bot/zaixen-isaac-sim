# How we recorded the ROS bags (steps, in simple English)

**Goal:** get the car's sensor data (IMU, odometry, contact) out of Isaac Sim (on Windows)
into ROS 2 (on WSL / Ubuntu), and save it as ROS bags, one bag per run. **No attacks.**

This folder:
```
ros_bridge/
  README_HOW_WE_DID_IT.md     <- this file (the steps)
  bridge_setup_reference.md   <- the technical list of every change, with file paths
  scripts/                    <- all scripts we wrote (copy them to WSL, see step 3)
  windows/                    <- the Windows files we changed (examples to copy)
```
The recorded data and the explanation for the AI team are in `../AI_team_data/`.

---

## The big picture (what is connected to what)

```
 Windows                                   WSL2 (Ubuntu 22.04, ROS 2 Humble)
 Isaac Sim  --- ROS 2 bridge --->  [Discovery Server :11811]  --->  record_runs.py  --->  ROS bags
 (car drives itself)                                           \-->  bridge_check.py (test)
        ^
        '--- auto_record.py presses Play / Stop and sets the NPC count (port 8226)
```
- Isaac Sim publishes the sensor topics. WSL listens.
- A small program, the **Discovery Server**, is the "meeting point" so both sides find each other.
- `record_runs.py` listens all the time. When the sim starts it opens a new bag; when you press Stop it closes it.

---

## Part 1. One-time setup

### Step 1. Windows networking (once)
Put this in `C:\Users\User\.wslconfig` (example: `windows/.wslconfig.example`):
```
[wsl2]
networkingMode=mirrored
```
Then in PowerShell run `wsl --shutdown` and open WSL again.
**Why:** by default WSL sits behind a private network (NAT) and the two sides cannot find each other.
Mirrored mode makes WSL share the Windows network. Check in WSL: `wslinfo --networking-mode` must say `mirrored`.

### Step 2. WSL settings (once)
Add these lines at the end of `~/.bashrc` (WSL):
```bash
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=0
export ROS_DISCOVERY_SERVER=127.0.0.1:11811
export ROS_SUPER_CLIENT=True
# start the discovery server automatically (does nothing if already running)
[ -x "$HOME/.local/bin/dds-server" ] && "$HOME/.local/bin/dds-server" start >/dev/null 2>&1
```
**Remove or comment out** any line `export FASTRTPS_DEFAULT_PROFILES_FILE=...`. An old one pointed to a wrong
address (192.168.1.5) and **blocked everything**. Same on Windows (next step).

### Step 3. Copy the scripts into WSL (once)
```bash
mkdir -p ~/ros2_ws/scripts ~/ros2_ws/data/bags ~/.local/bin
cp "/mnt/d/Robotics/Projects/zaixen-isaac-sim/ros_bridge/scripts/"*.py ~/ros2_ws/scripts/
cp "/mnt/d/Robotics/Projects/zaixen-isaac-sim/ros_bridge/scripts/dds-server" "/mnt/d/Robotics/Projects/zaixen-isaac-sim/ros_bridge/scripts/runlabel" ~/.local/bin/
chmod +x ~/.local/bin/dds-server ~/.local/bin/runlabel
```
Open a new WSL terminal (so `.bashrc` runs). Check: `dds-server status` must say `RUNNING`.

### Step 4. Windows launch file (once)
Use `windows/run_isaacsim_humble.bat` (copy it over your `.bat`). The important lines:
```bat
set ROS_DISTRO=humble
set RMW_IMPLEMENTATION=rmw_fastrtps_cpp
rem set FASTRTPS_DEFAULT_PROFILES_FILE=...        <- must stay switched off
set ROS_DOMAIN_ID=0
set ROS_DISCOVERY_SERVER=127.0.0.1:11811          <- tells Isaac Sim to use the meeting point
set PATH=%PATH%;...\isaacsim.ros2.core\humble\lib <- ROS 2 Humble libraries (same version as WSL)
```

---

## Part 2. Start-up order (every time)

1. **WSL terminal A:** `dds-server status` -> must say `RUNNING`.
2. **Windows:** start Isaac Sim with the `.bat` (start it **after** step 1).
3. In Isaac Sim: open `zaixen_scene.usd`, then `Window > Script Editor` -> open `scripts\run_simulation.py` -> **Run**. Wait for "Simulation armed".
   **Without this the car does not drive**: the driving, lights and traffic are Python code, not saved in the .usd.
4. **WSL terminal A:** start the recorder and leave it open:
   ```bash
   python3 ~/ros2_ws/scripts/record_runs.py
   ```
   It prints `waiting for Isaac Sim to Play ...`.

---

## Part 3. Check that the bridge works (before recording)

Press **Play** in Isaac Sim, then in WSL:
```bash
ros2 topic list -t --no-daemon                 # you must see /clock /imu /odom /contact /tf
python3 ~/ros2_ws/scripts/bridge_check.py 10   # a table: each topic, type, rate, one sample
```
Good result: 4 topics at about 60 messages per simulated second, with simulation-time stamps.
Always add `--no-daemon` to `ros2` commands (the ROS 2 background daemon does not work with the meeting point).

Pause, Stop test: `python3 ~/ros2_ws/scripts/bridge_check.py --watch 60` prints the simulation time every second.
On **Pause** it freezes; on **Stop** all topics disappear; on **Play** again it restarts near 0.

---

## Part 4. Recording

### Option A: by hand
1. WSL terminal B: `runlabel npc10` (the name for the next bag)
2. Isaac Sim: set the NPC slider (`NPC Traffic` panel) to 10, press **Play**.
3. After at least 60 simulated seconds press **Stop**. The recorder (terminal A) prints `RUN ... ended`.

### Option B: automatic (what we used for npc10, npc20, npc30)
The Isaac Sim "python server" on port 8226 accepts Python code. `auto_record.py` uses it to press
Play and Stop and to set the NPC count, so you do not touch Isaac Sim:
```bash
python3 ~/ros2_ws/scripts/auto_record.py --counts 10,20,30 --sim-seconds 60
```
For each number it: writes the label, sets the NPC count, presses Play, waits for 60 simulated seconds, presses Stop,
checks that the recorder saved a bag. It also switches the CSV log on and puts the NPC count back at the end.
**Do not press Play/Stop yourself while it runs.** (Needs the recorder from Part 2 step 4 already running.)

### The CSV ground-truth log
Isaac Sim can also write a CSV with the real state of the world (light colour, car state, NPC positions).
`auto_record.py` switches it on. By hand: tick **"Log to CSV"** in the NPC Traffic panel.
Files go to `D:\Robotics\Projects\Zaixen_simulation\logs\`. Switch it off with `zaixen_log.disable()` so the file is closed.

---

## Part 5. Where is everything saved? (check that it worked)

| What | Where |
|---|---|
| ROS bags (WSL) | `~/ros2_ws/data/bags/run_<date>_<n>_<label>/` (open from Windows: `\\wsl.localhost\Ubuntu-22.04\home\isc_noel\ros2_ws\data\bags`) |
| List of bags | `~/ros2_ws/data/runs_manifest.csv` |
| Which CSV run matches which bag | `~/ros2_ws/data/batch_index.csv` |
| CSV ground truth | `D:\Robotics\Projects\Zaixen_simulation\logs\sim_log_<date>.csv` |

Quick look: `cat ~/ros2_ws/data/runs_manifest.csv`. Each bag folder also has `run_info.json`.
The `run` column in the CSV counts every Stop since Isaac Sim started, so it is not 1, 2, 3.
That is normal (see `batch_index.csv`).

### Compare two runs (proof that the sim repeats)
We compared runs by simulation time. `/imu`, `/odom` and `/tf` were **identical** (0 differences over 1,384 steps).
Later, npc0, npc10 and npc20 also gave identical `/odom`. Only npc30 differs because the car was held up by traffic.

---

## Part 6. Problems we hit and how we fixed them

| Problem | Why | Fix |
|---|---|---|
| WSL sees no Isaac Sim topics | an old `FASTRTPS_DEFAULT_PROFILES_FILE` (on WSL **and** Windows) pointed to a wrong address and turned off the normal transports | switch both lines off. Use mirrored networking and the discovery server |
| `ros2 topic list` empty even when it works | ROS 2 background daemon + mirrored mode do not mix | always use `--no-daemon` |
| Topics seen, but no data arrives in my own script | A node that subscribes in its **first second** gets **nothing** (silently) | start the node, spin it for 3 s, **then** subscribe (the scripts do this). `ros2 topic echo` hides it because it discovers first |
| Car does not move | the driving is Python in Isaac Sim, not saved in the .usd | run `scripts\run_simulation.py` after opening the scene, then Play |
| Teleop (keyboard) does nothing | the car drives itself inside Isaac Sim; nothing listens to ROS drive commands | we record the car's own loop instead of driving by hand |
| Bags / CSV "not saved" | looked in the wrong place | bags are on the WSL side, CSV on D: (table above) |
| Two Plays differ? | they do not: the sim is deterministic | -- |

Things we tried that were **not** the cause (so you do not repeat them): ROS Jazzy vs Humble libraries (we use Humble to match WSL anyway), shared memory, port clashes.

---

## Part 7. Rules to remember
- Timestamps are **simulation time**. They restart at 0 on every Play.
- Topics exist only while the sim is **playing**.
- The first 0.15 to 0.25 s of each run is not in the bag.
- Pause does not split a run. Stop ends it.
- `/contact` has no timestamp inside the message; the recorder stamps it with the latest `/clock`.
- **No attack code exists yet.** Nothing here changes any ROS message.
