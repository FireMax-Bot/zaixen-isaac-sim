# 09_drop

**drop - some messages never arrive.**

## What it shows / which file

Some odometry messages are missing. Look at `aligned.csv.gz`: `odom.age_s` (gaps); and `telemetry.csv.gz`: `odom_mon.rate_hz` (falls below 60).

## Strength levels

- L1: p=0.1
- L2: p=0.3
- L3: p=0.6

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `drop_L1_npc10_seed1` | 10 | 1 | 1 |
| `drop_L1_npc10_seed2` | 10 | 2 | 1 |
| `drop_L1_npc10_seed3` | 10 | 3 | 1 |
| `drop_L1_npc20_seed1` | 20 | 1 | 1 |
| `drop_L1_npc20_seed2` | 20 | 2 | 1 |
| `drop_L1_npc20_seed3` | 20 | 3 | 1 |
| `drop_L1_npc30_seed1` | 30 | 1 | 1 |
| `drop_L1_npc30_seed2` | 30 | 2 | 1 |
| `drop_L1_npc30_seed3` | 30 | 3 | 1 |
| `drop_L2_npc10_seed1` | 10 | 1 | 2 |
| `drop_L2_npc10_seed2` | 10 | 2 | 2 |
| `drop_L2_npc10_seed3` | 10 | 3 | 2 |
| `drop_L2_npc20_seed1` | 20 | 1 | 2 |
| `drop_L2_npc20_seed2` | 20 | 2 | 2 |
| `drop_L2_npc20_seed3` | 20 | 3 | 2 |
| `drop_L2_npc30_seed1` | 30 | 1 | 2 |
| `drop_L2_npc30_seed2` | 30 | 2 | 2 |
| `drop_L2_npc30_seed3` | 30 | 3 | 2 |
| `drop_L3_npc10_seed1` | 10 | 1 | 3 |
| `drop_L3_npc10_seed2` | 10 | 2 | 3 |
| `drop_L3_npc10_seed3` | 10 | 3 | 3 |
| `drop_L3_npc20_seed1` | 20 | 1 | 3 |
| `drop_L3_npc20_seed2` | 20 | 2 | 3 |
| `drop_L3_npc20_seed3` | 20 | 3 | 3 |
| `drop_L3_npc30_seed1` | 30 | 1 | 3 |
| `drop_L3_npc30_seed2` | 30 | 2 | 3 |
| `drop_L3_npc30_seed3` | 30 | 3 | 3 |
