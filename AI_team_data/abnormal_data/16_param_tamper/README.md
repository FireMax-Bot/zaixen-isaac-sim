# 16_param_tamper

**parameter tampering - someone changes a program's settings behind its back. (weak: this is a target we added on purpose)**

## What it shows / which file

The relay's rate setting is changed, so the message rate drops to about 10 per second. Look at `telemetry.csv.gz`: `param_event_count` and `imu_mon.rate_hz`.

## Limitation

WEAK: our relay has only ONE setting (a rate limit) and it exists on purpose, so this attack has a target. The 'weakness found' is a target we created.

## Strength levels

- single setting

## Runs

9 runs (npc 10/20/30 x seed 1/2/3)

Each run folder has `aligned.csv.gz`, `telemetry.csv.gz`, `events.csv`, `manifest.json`. The attack is active from about 30 s to 60 s of the run (this attack is a separate program that has to start first, so the label starts about 1-3 s later and its label is coarse, +/- 0.5 s or more) (exact times in `events.csv`; the label columns `is_attack`, `attack_type`, `attack_target`, `attack_id` are already in `aligned.csv.gz` and `telemetry.csv.gz`).

| run | npc | seed | level |
|---|---|---|---|
| `param_tamper_L1_npc10_seed1` | 10 | 1 | 1 |
| `param_tamper_L1_npc10_seed2` | 10 | 2 | 1 |
| `param_tamper_L1_npc10_seed3` | 10 | 3 | 1 |
| `param_tamper_L1_npc20_seed1` | 20 | 1 | 1 |
| `param_tamper_L1_npc20_seed2` | 20 | 2 | 1 |
| `param_tamper_L1_npc20_seed3` | 20 | 3 | 1 |
| `param_tamper_L1_npc30_seed1` | 30 | 1 | 1 |
| `param_tamper_L1_npc30_seed2` | 30 | 2 | 1 |
| `param_tamper_L1_npc30_seed3` | 30 | 3 | 1 |
