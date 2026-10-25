# Normal data

9 runs with NO attack. Each run is 90 seconds of the ego car driving its loop with 10, 20 or 30 other cars (NPCs), seeds 1, 2, 3.

Each folder (`normal_npc10_seed1`, ...) holds:
- `aligned.csv.gz` - the sensor table, 50 rows per second (IMU, odometry, contact) + label columns (all `is_attack = 0`)
- `telemetry.csv.gz` - the network features, 2 rows per second (message rates, node count, ...)
- `events.csv` - empty for normal runs (no attack events)
- `manifest.json` - seed, settings, versions, git commit

Read it with `pandas.read_csv("aligned.csv.gz")`. The sensors are clean (no noise), and the car is driven by a program inside the simulator, not by ROS.

Note: the normal parts of the attack runs (first 30 s and last 30 s, label 0) are also normal data.
