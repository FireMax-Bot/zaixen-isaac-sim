# 08_delay

**delay - every message arrives late.**

## What it shows / which file

Every IMU message arrives late but keeps its old time stamp. Look at `aligned.csv.gz`: `imu.stamp_lag_s` (jumps to the delay) and `imu.age_s`; and `telemetry.csv.gz`: `imu_mon.stamp_lag_mean_s`.

## Strength levels

- L1: d_s=0.1
- L2: d_s=0.5
- L3: d_s=1.0

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `delay_L1_npc10_seed1` | 10 | 1 | 1 |
| `delay_L1_npc10_seed2` | 10 | 2 | 1 |
| `delay_L1_npc10_seed3` | 10 | 3 | 1 |
| `delay_L1_npc20_seed1` | 20 | 1 | 1 |
| `delay_L1_npc20_seed2` | 20 | 2 | 1 |
| `delay_L1_npc20_seed3` | 20 | 3 | 1 |
| `delay_L1_npc30_seed1` | 30 | 1 | 1 |
| `delay_L1_npc30_seed2` | 30 | 2 | 1 |
| `delay_L1_npc30_seed3` | 30 | 3 | 1 |
| `delay_L2_npc10_seed1` | 10 | 1 | 2 |
| `delay_L2_npc10_seed2` | 10 | 2 | 2 |
| `delay_L2_npc10_seed3` | 10 | 3 | 2 |
| `delay_L2_npc20_seed1` | 20 | 1 | 2 |
| `delay_L2_npc20_seed2` | 20 | 2 | 2 |
| `delay_L2_npc20_seed3` | 20 | 3 | 2 |
| `delay_L2_npc30_seed1` | 30 | 1 | 2 |
| `delay_L2_npc30_seed2` | 30 | 2 | 2 |
| `delay_L2_npc30_seed3` | 30 | 3 | 2 |
| `delay_L3_npc10_seed1` | 10 | 1 | 3 |
| `delay_L3_npc10_seed2` | 10 | 2 | 3 |
| `delay_L3_npc10_seed3` | 10 | 3 | 3 |
| `delay_L3_npc20_seed1` | 20 | 1 | 3 |
| `delay_L3_npc20_seed2` | 20 | 2 | 3 |
| `delay_L3_npc20_seed3` | 20 | 3 | 3 |
| `delay_L3_npc30_seed1` | 30 | 1 | 3 |
| `delay_L3_npc30_seed2` | 30 | 2 | 3 |
| `delay_L3_npc30_seed3` | 30 | 3 | 3 |
