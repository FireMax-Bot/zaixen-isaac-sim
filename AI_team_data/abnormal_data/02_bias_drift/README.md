# 02_bias_drift

**bias/drift - readings slide off the truth, by a steady amount or slowly growing.**

## What it shows / which file

The IMU and odometry numbers are shifted away from the truth. Look at `aligned.csv.gz`: the same `imu.*` and `odom.*` value columns. In this dataset the shift is a STEADY offset (the slowly growing version exists in the code but is not in the data).

## Strength levels

- L1: k=0.5 x std (accel, gyro, twist), 0.1 m (odom x, y), 5 deg (yaw)
- L2: k=1.0 x std (accel, gyro, twist), 0.3 m (odom x, y), 10 deg (yaw)
- L3: k=3.0 x std (accel, gyro, twist), 0.5 m (odom x, y), 20 deg (yaw)

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `bias_drift_L1_npc10_seed1` | 10 | 1 | 1 |
| `bias_drift_L1_npc10_seed2` | 10 | 2 | 1 |
| `bias_drift_L1_npc10_seed3` | 10 | 3 | 1 |
| `bias_drift_L1_npc20_seed1` | 20 | 1 | 1 |
| `bias_drift_L1_npc20_seed2` | 20 | 2 | 1 |
| `bias_drift_L1_npc20_seed3` | 20 | 3 | 1 |
| `bias_drift_L1_npc30_seed1` | 30 | 1 | 1 |
| `bias_drift_L1_npc30_seed2` | 30 | 2 | 1 |
| `bias_drift_L1_npc30_seed3` | 30 | 3 | 1 |
| `bias_drift_L2_npc10_seed1` | 10 | 1 | 2 |
| `bias_drift_L2_npc10_seed2` | 10 | 2 | 2 |
| `bias_drift_L2_npc10_seed3` | 10 | 3 | 2 |
| `bias_drift_L2_npc20_seed1` | 20 | 1 | 2 |
| `bias_drift_L2_npc20_seed2` | 20 | 2 | 2 |
| `bias_drift_L2_npc20_seed3` | 20 | 3 | 2 |
| `bias_drift_L2_npc30_seed1` | 30 | 1 | 2 |
| `bias_drift_L2_npc30_seed2` | 30 | 2 | 2 |
| `bias_drift_L2_npc30_seed3` | 30 | 3 | 2 |
| `bias_drift_L3_npc10_seed1` | 10 | 1 | 3 |
| `bias_drift_L3_npc10_seed2` | 10 | 2 | 3 |
| `bias_drift_L3_npc10_seed3` | 10 | 3 | 3 |
| `bias_drift_L3_npc20_seed1` | 20 | 1 | 3 |
| `bias_drift_L3_npc20_seed2` | 20 | 2 | 3 |
| `bias_drift_L3_npc20_seed3` | 20 | 3 | 3 |
| `bias_drift_L3_npc30_seed1` | 30 | 1 | 3 |
| `bias_drift_L3_npc30_seed2` | 30 | 2 | 3 |
| `bias_drift_L3_npc30_seed3` | 30 | 3 | 3 |
