# 03_jump

**jump - one sudden impossible value.**

## What it shows / which file

The odometry position shows 3 messages in a row with impossible values, then goes back to normal. Look at `aligned.csv.gz`: `odom.pose.pose.position.*`.

## Strength levels

- L1: range_mult=3.0
- L2: range_mult=10.0
- L3: range_mult=30.0

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `jump_L1_npc10_seed1` | 10 | 1 | 1 |
| `jump_L1_npc10_seed2` | 10 | 2 | 1 |
| `jump_L1_npc10_seed3` | 10 | 3 | 1 |
| `jump_L1_npc20_seed1` | 20 | 1 | 1 |
| `jump_L1_npc20_seed2` | 20 | 2 | 1 |
| `jump_L1_npc20_seed3` | 20 | 3 | 1 |
| `jump_L1_npc30_seed1` | 30 | 1 | 1 |
| `jump_L1_npc30_seed2` | 30 | 2 | 1 |
| `jump_L1_npc30_seed3` | 30 | 3 | 1 |
| `jump_L2_npc10_seed1` | 10 | 1 | 2 |
| `jump_L2_npc10_seed2` | 10 | 2 | 2 |
| `jump_L2_npc10_seed3` | 10 | 3 | 2 |
| `jump_L2_npc20_seed1` | 20 | 1 | 2 |
| `jump_L2_npc20_seed2` | 20 | 2 | 2 |
| `jump_L2_npc20_seed3` | 20 | 3 | 2 |
| `jump_L2_npc30_seed1` | 30 | 1 | 2 |
| `jump_L2_npc30_seed2` | 30 | 2 | 2 |
| `jump_L2_npc30_seed3` | 30 | 3 | 2 |
| `jump_L3_npc10_seed1` | 10 | 1 | 3 |
| `jump_L3_npc10_seed2` | 10 | 2 | 3 |
| `jump_L3_npc10_seed3` | 10 | 3 | 3 |
| `jump_L3_npc20_seed1` | 20 | 1 | 3 |
| `jump_L3_npc20_seed2` | 20 | 2 | 3 |
| `jump_L3_npc20_seed3` | 20 | 3 | 3 |
| `jump_L3_npc30_seed1` | 30 | 1 | 3 |
| `jump_L3_npc30_seed2` | 30 | 2 | 3 |
| `jump_L3_npc30_seed3` | 30 | 3 | 3 |
