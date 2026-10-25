# 12_flood

**flood - the wire is swamped with huge numbers of messages.**

## What it shows / which file

The IMU topic carries far more than 60 messages per second. Look at `telemetry.csv.gz`: `imu_mon.rate_hz` (about 160 / 260 / 460).

## Strength levels

- L1: rate_hz=100.0
- L2: rate_hz=200.0
- L3: rate_hz=400.0

## Runs

27 runs (npc 10/20/30 x seed 1/2/3 x 3 levels)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `flood_L1_npc10_seed1` | 10 | 1 | 1 |
| `flood_L1_npc10_seed2` | 10 | 2 | 1 |
| `flood_L1_npc10_seed3` | 10 | 3 | 1 |
| `flood_L1_npc20_seed1` | 20 | 1 | 1 |
| `flood_L1_npc20_seed2` | 20 | 2 | 1 |
| `flood_L1_npc20_seed3` | 20 | 3 | 1 |
| `flood_L1_npc30_seed1` | 30 | 1 | 1 |
| `flood_L1_npc30_seed2` | 30 | 2 | 1 |
| `flood_L1_npc30_seed3` | 30 | 3 | 1 |
| `flood_L2_npc10_seed1` | 10 | 1 | 2 |
| `flood_L2_npc10_seed2` | 10 | 2 | 2 |
| `flood_L2_npc10_seed3` | 10 | 3 | 2 |
| `flood_L2_npc20_seed1` | 20 | 1 | 2 |
| `flood_L2_npc20_seed2` | 20 | 2 | 2 |
| `flood_L2_npc20_seed3` | 20 | 3 | 2 |
| `flood_L2_npc30_seed1` | 30 | 1 | 2 |
| `flood_L2_npc30_seed2` | 30 | 2 | 2 |
| `flood_L2_npc30_seed3` | 30 | 3 | 2 |
| `flood_L3_npc10_seed1` | 10 | 1 | 3 |
| `flood_L3_npc10_seed2` | 10 | 2 | 3 |
| `flood_L3_npc10_seed3` | 10 | 3 | 3 |
| `flood_L3_npc20_seed1` | 20 | 1 | 3 |
| `flood_L3_npc20_seed2` | 20 | 2 | 3 |
| `flood_L3_npc20_seed3` | 20 | 3 | 3 |
| `flood_L3_npc30_seed1` | 30 | 1 | 3 |
| `flood_L3_npc30_seed2` | 30 | 2 | 3 |
| `flood_L3_npc30_seed3` | 30 | 3 | 3 |
