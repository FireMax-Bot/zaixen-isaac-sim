# 11_clock_skew

**clock skew - the values are fine but the timestamps are wrong.**

## What it shows / which file

The odometry values are normal but the time stamps are shifted. Look at `aligned.csv.gz`: `odom.stamp_lag_s`; and `telemetry.csv.gz`: `odom_mon.stamp_lag_mean_s`.

## Strength levels

- L1: offset_s=0.1
- L2: offset_s=1.0
- L3: offset_s=5.0

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `clock_skew_L1_npc10_seed1` | 10 | 1 | 1 |
| `clock_skew_L1_npc10_seed2` | 10 | 2 | 1 |
| `clock_skew_L1_npc10_seed3` | 10 | 3 | 1 |
| `clock_skew_L1_npc20_seed1` | 20 | 1 | 1 |
| `clock_skew_L1_npc20_seed2` | 20 | 2 | 1 |
| `clock_skew_L1_npc20_seed3` | 20 | 3 | 1 |
| `clock_skew_L1_npc30_seed1` | 30 | 1 | 1 |
| `clock_skew_L1_npc30_seed2` | 30 | 2 | 1 |
| `clock_skew_L1_npc30_seed3` | 30 | 3 | 1 |
| `clock_skew_L2_npc10_seed1` | 10 | 1 | 2 |
| `clock_skew_L2_npc10_seed2` | 10 | 2 | 2 |
| `clock_skew_L2_npc10_seed3` | 10 | 3 | 2 |
| `clock_skew_L2_npc20_seed1` | 20 | 1 | 2 |
| `clock_skew_L2_npc20_seed2` | 20 | 2 | 2 |
| `clock_skew_L2_npc20_seed3` | 20 | 3 | 2 |
| `clock_skew_L2_npc30_seed1` | 30 | 1 | 2 |
| `clock_skew_L2_npc30_seed2` | 30 | 2 | 2 |
| `clock_skew_L2_npc30_seed3` | 30 | 3 | 2 |
| `clock_skew_L3_npc10_seed1` | 10 | 1 | 3 |
| `clock_skew_L3_npc10_seed2` | 10 | 2 | 3 |
| `clock_skew_L3_npc10_seed3` | 10 | 3 | 3 |
| `clock_skew_L3_npc20_seed1` | 20 | 1 | 3 |
| `clock_skew_L3_npc20_seed2` | 20 | 2 | 3 |
| `clock_skew_L3_npc20_seed3` | 20 | 3 | 3 |
| `clock_skew_L3_npc30_seed1` | 30 | 1 | 3 |
| `clock_skew_L3_npc30_seed2` | 30 | 2 | 3 |
| `clock_skew_L3_npc30_seed3` | 30 | 3 | 3 |
