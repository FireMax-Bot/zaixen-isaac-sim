# 15_unauthorized_subscription

**eavesdropping - a program secretly listens; no values change, only the listener count goes up.**

## What it shows / which file

Nothing changes in the sensor values. Look at `telemetry.csv.gz`: `imu_mon.sub_count` and `odom_mon.sub_count` (2 becomes 3). This is the code name `unauthorized_subscription`.

## Strength levels

- single setting

## Runs

9 runs (npc 10/20/30 x seed 1/2/3)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (this attack is a separate program that has to start first, so the label starts about 1-3 s later and its label is coarse, +/- 0.5 s or more) (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `unauthorized_subscription_L1_npc10_seed1` | 10 | 1 | 1 |
| `unauthorized_subscription_L1_npc10_seed2` | 10 | 2 | 1 |
| `unauthorized_subscription_L1_npc10_seed3` | 10 | 3 | 1 |
| `unauthorized_subscription_L1_npc20_seed1` | 20 | 1 | 1 |
| `unauthorized_subscription_L1_npc20_seed2` | 20 | 2 | 1 |
| `unauthorized_subscription_L1_npc20_seed3` | 20 | 3 | 1 |
| `unauthorized_subscription_L1_npc30_seed1` | 30 | 1 | 1 |
| `unauthorized_subscription_L1_npc30_seed2` | 30 | 2 | 1 |
| `unauthorized_subscription_L1_npc30_seed3` | 30 | 3 | 1 |
