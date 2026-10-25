# 05_replay

**replay - old real data from a few seconds ago is played back.**

## What it shows / which file

The IMU gyro shows real but old values (5 seconds old, looped). Look at `aligned.csv.gz`: `imu.angular_velocity.*`.

## Strength levels

- single setting

## Runs

9 runs (npc 10/20/30 x seed 1/2/3)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `replay_L1_npc10_seed1` | 10 | 1 | 1 |
| `replay_L1_npc10_seed2` | 10 | 2 | 1 |
| `replay_L1_npc10_seed3` | 10 | 3 | 1 |
| `replay_L1_npc20_seed1` | 20 | 1 | 1 |
| `replay_L1_npc20_seed2` | 20 | 2 | 1 |
| `replay_L1_npc20_seed3` | 20 | 3 | 1 |
| `replay_L1_npc30_seed1` | 30 | 1 | 1 |
| `replay_L1_npc30_seed2` | 30 | 2 | 1 |
| `replay_L1_npc30_seed3` | 30 | 3 | 1 |
