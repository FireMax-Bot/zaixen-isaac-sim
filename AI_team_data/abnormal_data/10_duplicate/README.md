# 10_duplicate

**duplicate - the same message is sent several times.**

## What it shows / which file

Some IMU messages are repeated with the same time stamp. Look at `telemetry.csv.gz`: `imu_mon.rate_hz` (rises above 60).

## Strength levels

- L1: p=0.1, m=1
- L2: p=0.3, m=2
- L3: p=0.6, m=3

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `duplicate_L1_npc10_seed1` | 10 | 1 | 1 |
| `duplicate_L1_npc10_seed2` | 10 | 2 | 1 |
| `duplicate_L1_npc10_seed3` | 10 | 3 | 1 |
| `duplicate_L1_npc20_seed1` | 20 | 1 | 1 |
| `duplicate_L1_npc20_seed2` | 20 | 2 | 1 |
| `duplicate_L1_npc20_seed3` | 20 | 3 | 1 |
| `duplicate_L1_npc30_seed1` | 30 | 1 | 1 |
| `duplicate_L1_npc30_seed2` | 30 | 2 | 1 |
| `duplicate_L1_npc30_seed3` | 30 | 3 | 1 |
| `duplicate_L2_npc10_seed1` | 10 | 1 | 2 |
| `duplicate_L2_npc10_seed2` | 10 | 2 | 2 |
| `duplicate_L2_npc10_seed3` | 10 | 3 | 2 |
| `duplicate_L2_npc20_seed1` | 20 | 1 | 2 |
| `duplicate_L2_npc20_seed2` | 20 | 2 | 2 |
| `duplicate_L2_npc20_seed3` | 20 | 3 | 2 |
| `duplicate_L2_npc30_seed1` | 30 | 1 | 2 |
| `duplicate_L2_npc30_seed2` | 30 | 2 | 2 |
| `duplicate_L2_npc30_seed3` | 30 | 3 | 2 |
| `duplicate_L3_npc10_seed1` | 10 | 1 | 3 |
| `duplicate_L3_npc10_seed2` | 10 | 2 | 3 |
| `duplicate_L3_npc10_seed3` | 10 | 3 | 3 |
| `duplicate_L3_npc20_seed1` | 20 | 1 | 3 |
| `duplicate_L3_npc20_seed2` | 20 | 2 | 3 |
| `duplicate_L3_npc20_seed3` | 20 | 3 | 3 |
| `duplicate_L3_npc30_seed1` | 30 | 1 | 3 |
| `duplicate_L3_npc30_seed2` | 30 | 2 | 3 |
| `duplicate_L3_npc30_seed3` | 30 | 3 | 3 |
