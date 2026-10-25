# Guide for the AI team

## What this is
A labelled dataset for detecting attacks on the sensor data of a simulated self-driving car (Isaac Sim + ROS 2). 306 runs, 90 seconds each: **9 normal** runs and **297 attack** runs (17 attacks). Traffic: 10, 20 or 30 other cars. Seeds 1, 2, 3.

## Two limits - please read
1. **The data is not driving the car.** The ego car is driven by a program inside the simulator, not by ROS. The attacks change the DATA a detector sees. They never change how the car drives. Do not expect crashes or path changes.
2. **The sensors are clean.** There is no sensor noise in the simulator. A real car would have noise, so detection here is easier than in the real world.

## The 17 attacks
1. noise - readings get extra jitter, like a shaky hand.
2. bias/drift - readings slide off the truth, by a steady amount or slowly growing.
3. jump - one sudden impossible value.
4. freeze - the sensor gets stuck repeating its last value.
5. replay - old real data from a few seconds ago is played back.
6. false contact - a crash signal appears when nothing was hit. (limited: the car never really collides yet)
7. missed contact - a real crash is hidden. (limited: the car never really collides yet)
8. delay - every message arrives late.
9. drop - some messages never arrive.
10. duplicate - the same message is sent several times.
11. clock skew - the values are fine but the timestamps are wrong.
12. flood - the wire is swamped with huge numbers of messages.
13. spoof - a stranger pretends to be the real sensor and sends fake readings.
14. unauthorized node - a program that should not exist joins the system.
15. eavesdropping - a program secretly listens; no values change, only the listener count goes up.
16. parameter tampering - someone changes a program's settings behind its back. (weak: this is a target we added on purpose)
17. service abuse - someone spams a program's request function. (weak: this is a target we added on purpose)

**Weak ones (16 and 17):** our relay program has only ONE setting (a rate limit) and ONE request function (`reset_buffers`). We added them on purpose so these two attacks have a target. So the "weakness found" is a target we created. Treat 16 and 17 as simple examples, not as proof of real weaknesses.

**Limited ones (6 and 7):** the contact value is always 0.0 in normal driving, because the car never really collides yet. Attack 6 makes it jump to 50. Attack 7 hides a crash that never happens, so its data looks identical to normal data. Keep them, but do not oversell them.

## Strength levels
Noise and bias/drift use three levels together (k x std for acceleration, gyro and speed; absolute metres for odometry x/y; absolute degrees for yaw): L1 = 0.5 x std, 0.10 m, 5 deg; L2 = 1 x std, 0.30 m, 10 deg; L3 = 3 x std, 0.50 m, 20 deg. Jump: 3 / 10 / 30 x the field range. Delay: 0.1 / 0.5 / 1.0 s. Drop: 10 / 30 / 60 % of messages. Duplicate: 10 / 30 / 60 % of messages repeated 1 / 2 / 3 times. Clock skew: 0.1 / 1 / 5 s. Flood: 100 / 200 / 400 extra messages per second (rate in simulation time). Per-attack details are in each attack folder's README.

## The files in each run folder
- `aligned.csv.gz` - sensor table, 50 rows per second, 36 columns (see `DATA_DICTIONARY.md`). Includes `<topic>.age_s` (seconds since the last message) and `<topic>.stamp_lag_s` (receive time minus message time stamp) so drops, freezes, delays and clock skew are visible.
- `telemetry.csv.gz` - network features, 2 rows per second: message rate, number of publishers and subscribers per topic, node count, ... Needed for attacks 12-17.
- `events.csv` - the attack start and stop events (the only source of the labels).
- `manifest.json` - seed, settings, versions, git commit, `ego_driven_by`.

## Label rules
- Labels come only from `events.csv`: a row is an attack row if `start <= sim_time < stop`. No manual labelling.
- Only one attack is active at a time. Each attack run has 30 s normal, 30 s attack, 30 s normal.
- Attacks 1-12 are applied inside the relay program, so their labels are sharp (about 17 ms, one message). Attacks 13-17 are separate rogue programs that have to start first and are seen only through the 2 Hz telemetry, so their labels are coarse (typically 0.1-0.5 s, worst case about 1.4 s). Measured alignment (start = first corrupted message minus label start; stop = label stop minus last corrupted message):

| kind | runs | start median ms | start max ms | stop median ms | stop max ms |
|---|---|---|---|---|---|
| value attacks | 216 | 16.7 | 166.7 | 0.0 | 500.0 |
| network attacks (telemetry) | 45 | 400.0 | 1416.7 | 216.7 | 483.3 |

## How to use it
- Load: `pandas.read_csv("aligned.csv.gz")`.
- **Split train/test by WHOLE RUNS, never by random rows.** For example seeds 1 and 2 for training and seed 3 for testing. Rows of one run are strongly correlated.
- **Attack window:** the nominal attack window is 30-60 s. For the rogue-program attacks (13-17) the label starts a little later (about 31-33 s) because the program has to start first; `spoof` windows are about 27.5 s long. Always take the exact times from `events.csv` or the label columns.
- The first rows of `aligned.csv.gz` can contain empty values (a topic had not started yet) and the first 10-15 s of `telemetry.csv.gz` are start-up (`new_nodes` is empty). The attack never starts before 30 s.
- `raw_clean` (the true sensor values) is NOT part of this branch and must never be used for training. It exists only for our own verification.
- Not byte-reproducible: re-running a seed gives similar but not identical data (timing differs); the labels are exact.
