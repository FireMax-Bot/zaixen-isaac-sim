# Low-RAM Attack Detection Agent for Autonomous-Car Sensor Data (17 attacks)

## 1. What is this project?

A simulated self-driving car (Isaac Sim + ROS 2) sends sensor data (IMU, odometry, contact) over a network. An attacker can tamper with that data or with the network around it.

This project builds a small **AI agent** that watches the data stream and:

1. Decides if everything is **normal** or **under attack**.
2. Says **which of 17 attacks** it looks like.
3. Suggests a **response** (for example "quarantine the unknown node").

Because it is meant for a car, it is built to use **very little RAM and storage**.

```
sensor + network data → 2-second windows → 50 "health" features → small Random Forest → agent (voting) → ALERT + attack type + action
```

---

## 2. The data

- 306 runs of 90 seconds: 9 normal runs and 297 attack runs (17 attack types, each run 30 s normal, 30 s attack, 30 s normal).
- Traffic: 10, 20 or 30 other cars. Seeds 1, 2, 3.
- Eight attacks have 3 strength levels (noise, bias_drift, jump, delay, drop, duplicate, clock_skew, flood). The other nine have a single setting.
- Each run has `aligned.csv.gz` (sensor values, 50 rows/s) and `telemetry.csv.gz` (network counts, 2 rows/s).
- All data is from a **simulator with clean sensors**, so real-world detection would be harder.

The 17 attacks: noise, bias/drift, jump, freeze, replay, false contact, missed contact, delay, drop, duplicate, clock skew, flood, spoof, unauthorized node, unauthorized subscription (eavesdropping), parameter tampering, service abuse.

---

## 3. How it works

### Step 1 – Features (`features.py`)
Each 2-second window (100 sensor rows) becomes **50 numbers** that describe how *healthy the data stream* is:

| Group | Catches |
|---|---|
| Timing (message age, timestamp lag) | delay, drop, clock_skew |
| Repeated values | freeze |
| Smoothness (second-difference jitter) | noise |
| Biggest sudden change | jump |
| Consistency (IMU vs odometry, position vs speed) | bias_drift, replay |
| Contact signal | false_contact |
| Network counts (message rate, publishers, subscribers, nodes, parameter events, service calls) | flood, spoof, unauthorized node, eavesdropping, param_tamper, service_abuse |

**Important design choice:** the features never use raw position or orientation. In this data the car follows a driving script, and during seconds 30–60 it turns in every run. A model using raw values could "cheat" by learning that script instead of the attacks.

The agent first learns what "normal" looks like **for that particular run** during the calm period (15–28 s) and then watches for changes. This is done for the network counts and also for the timing features (message age, lag, repeated values), so a run whose messages are naturally a bit slower is not mistaken for an attack.

### Step 2 – Model (`train_all.py`)
- One **Random Forest** (60 trees, max depth 10) that predicts normal or one of the attack types.
- Trained on seeds 1 and 2, tested on seed 3 (**whole runs**, never random rows).
- `tiny_forest.py` converts it to a numpy-only file (`attack_model.npz`, **32 KB**), so the agent does not need scikit-learn or pandas. It gives identical predictions to the original on 1,500 test windows.

### Step 3 – Agent (`agent_all.py`)
1. **Perceive:** keep the last 2 seconds of sensor rows in memory.
2. **Decide:** every 1 s (every 50 new rows) compute the features and ask the model which class it is.
3. **Smooth:** remember the last 5 decisions; raise an **ALERT** only when 3 of 5 say attack. A **jump** is a one-off event, so one jump decision counts as 3 votes.
4. **Act:** output the attack name and a suggested response.

### Step 4 – Evaluation (`evaluate_all.py`)
Replays the unseen seed 3 runs row by row, like a live feed.

---

## 4. Two honest fixes we made

1. **`missed_contact` is excluded from the model.** The car never really collides, and the attack hides a crash that never happens, so its data is **identical to normal data**. Training on it made the model fail on normal data. It cannot be detected from this dataset.
2. **`jump` is trained only on windows that really contain a jump.** A jump is one sudden value, so only about 3% of the windows inside a jump run contain it (27 windows in total). The agent is judged on whether it alerts at least once during the attack.

3. **Timing features are relative to each run's own calm period.** In version 1 the timing features were compared with fixed normal levels, and after a `service_abuse` attack in seed 3 the slightly slower message timing was mistaken for a flood (81% of the decisions after the attack were false alarms). Making the timing features relative fixed most of this.

| Measure | Version 1 | Version 2 (final) |
|---|---|---|
| Alerts after service_abuse ends | 81% | 19% |
| Window accuracy / macro-F1 | 95.6% / 0.947 | 96.0% / 0.957 |
| False alarms on normal windows | 4.9% | 4.0% |
| Flood precision | 0.58 | 0.71 |
| Unauthorized_node precision | 0.65 | 0.85 |
| Runs with correct attack type (of 96) | 92 | 91 |

The correct-type count changed by one run, which is within normal variation for 3 to 9 test runs per attack. Flood got worse (9 → 6 runs named correctly) while duplicate and jump improved.

We also ran a **control test**: the 9 normal runs, which have no attack, must not trigger alerts during seconds 30–60. They triggered none.

---

## 5. Results (unseen seed 3 runs)

**Model (window level):** accuracy 96.0%, macro-F1 0.957.

**Agent (run level):**

| Attack | Runs | Detected | Correct type | Median delay (s) | False alarms after attack |
|---|---|---|---|---|---|
| noise | 9 | 100% | 100% | 3.0 | 2% |
| bias_drift | 9 | 100% | 100% | 4.0 | 1% |
| jump | 9 | 100% | 100% | 1.0 | 1% |
| freeze | 3 | 100% | 100% | 4.0 | 0% |
| replay | 3 | 100% | 100% | 4.0 | 4% |
| false_contact | 3 | 100% | 100% | 3.0 | 4% |
| missed_contact | 3 | **0%** | 0% | – | 0% |
| delay | 9 | 100% | 100% | 3.0 | 2% |
| drop | 9 | 100% | 100% | 3.0 | 4% |
| duplicate | 9 | 100% | **78%** | 3.0 | 5% |
| clock_skew | 9 | 100% | 100% | 3.0 | 4% |
| flood | 9 | 100% | **67%** | 3.0 | 4% |
| spoof | 3 | 100% | 100% | 0.5 | 4% |
| unauthorized_node | 3 | 100% | 100% | 1.7 | 2% |
| unauthorized_subscription | 3 | 100% | 100% | 1.6 | 2% |
| param_tamper | 3 | 100% | 100% | 1.8 | 4% |
| service_abuse | 3 | 100% | 100% | 1.5 | **19%** |

**Summary**
- All 96 runs of the 16 detectable attacks were detected; 91 of 96 (94.8%) were given the correct attack name.
- Overall detection is 97.0% because the 3 undetectable `missed_contact` runs are included.
- **Control (normal runs): 0 false alarms.** No false alarms in any run before the attack starts.
- Median detection delay about 3 seconds (the agent decides once per second and needs 3 attack decisions).

**Leave-one-seed-out check (`cross_check_seeds.py`, window level):** each seed took a turn as the unseen test set.

| Test seed | Accuracy | Macro-F1 | Attack recall | False alarms on normal | Control (30–60 s) |
|---|---|---|---|---|---|
| 1 | 0.960 | 0.957 | 1.000 | 3.6% | 0.0 |
| 2 | 0.973 | 0.966 | 0.998 | 1.6% | 0.0 |
| 3 | 0.960 | 0.957 | 1.000 | 4.0% | 0.0 |
| Mean | 0.964 | 0.960 | 0.999 | 3.1% | 0.0 |

The scores are similar for every seed, so the results do not depend on one lucky split. This check covers window-level performance only, and the seeds of one scenario are similar to each other.

**Low RAM and storage (measured on the development laptop)**

| Measure | Result |
|---|---|
| Model file | 32 KB (`attack_model.npz`) |
| Agent memory (arrays + model) | about 0.9 MB |
| Time per decision | about 2 ms (one decision is needed every 1,000 ms) |
| Needs | numpy only (no pandas, no scikit-learn) |

The evaluation script itself uses pandas to read CSV files, so its whole-process memory is much larger. That is the evaluator, not the agent.

---

## 6. Limitations (please read)

- **Duplicate and flood are confused with each other** (duplicate named correctly in 7 of 9 runs, flood in 6 of 9). Both attacks raise the message rate, and the current features cannot separate them well. Flood precision at window level is 0.71.
- **Some false alarms remain after service_abuse** (19% of decisions after the attack, down from 81% in version 1). Version 1 mistook slower message timing in the seed 3 runs for a flood, and making the timing features relative to each run's own calm period fixed most of it. We verified it was not a leftover attack, because the rogue program is gone after the attack.
- **missed_contact cannot be detected** from this data (see Section 4).
- **Seed 3 guided our decisions.** We looked at seed 3 results while developing: we excluded missed_contact, filtered the jump windows, and built version 2 after seeing the seed 3 service_abuse false alarms. So seed 3 is not a perfectly untouched test set. As a check, `cross_check_seeds.py` lets each seed take a turn as the unseen test set; the results were similar for all three seeds (see Section 5). The different seeds of the same scenario are also similar to each other, so results for genuinely new scenarios or attack strengths could be lower.
- **Small test sets:** the nine single-setting attacks have only 3 test runs each, and jump has only 9 test windows. Treat 100% on those as weak evidence.
- **Simulation only:** clean sensors, a scripted car, and attacks that never change how the car drives. Real cars have sensor noise and would be harder.
- **Fixed settings:** window size (2 s), voting (3 of 5) and the calibration period (15–28 s) were chosen by hand and not tuned. A shorter vote would reduce the 3 s delay but add false alarms.
- **The agent works on replayed files.** It is not connected to live ROS data.
- **Labels for attacks 13–17 are coarse** (up to about 1.4 s), so their delay numbers are approximate.

### Future work
1. Separate duplicate from flood with extra features (for example the share of repeated timestamps or identical messages).
2. Find out why the remaining 19% of alerts after service_abuse occur.
3. Test on more seeds and, ideally, real data.
4. Connect the agent to live ROS topics.

---

## 7. How to run

**Folder structure.** This project sits in a folder called `attack_agent` inside `AI_team_data`, next to the dataset folders.

```
AI_team_data/
├── normal_data/               ← dataset (9 runs)
├── abnormal_data/             ← dataset (17 folders, 297 runs)
└── attack_agent/              ← this project
    ├── README.md
    ├── requirements.txt
    ├── .gitignore
    ├── features.py            ← the 50 features (shared by training and agent)
    ├── build_features.py      ← creates features.csv from all runs
    ├── train_all.py           ← trains and evaluates the model
    ├── tiny_forest.py         ← converts the model to numpy-only format
    ├── agent_all.py           ← the AI agent
    ├── evaluate_all.py        ← evaluates the agent on unseen runs
    ├── cross_check_seeds.py   ← optional: every seed takes a turn as the test set
    ├── audit_data.py          ← optional: explores the dataset (Part 1)
    ├── signatures.py          ← optional: shows which columns react to each attack (Part 2)
    ├── audit_report.txt       ← output of audit_data.py
    ├── signatures_report.txt  ← output of signatures.py
    │
    │   (created when you run the scripts)
    ├── features.csv           (large, not pushed to GitHub)
    ├── attack_model.joblib    (not pushed to GitHub)
    ├── attack_model.npz       ← the 32 KB model used by the agent
    ├── confusion_matrix.png
    ├── results.json
    ├── agent_results.csv
    ├── agent_summary.csv
    ├── agent_summary_v1.csv   (results of the first version, kept for comparison)
    └── agent_summary.png
```

**About the data.** Only the `attack_agent` folder is uploaded here. The dataset (`normal_data` and `abnormal_data`) is in the team's repository on the `ai-team-data` branch and is not copied into this folder. To run the project, put `attack_agent` inside `AI_team_data` next to those two folders, or give the scripts the path to your copy of `AI_team_data` instead of `..`.

**Steps** (open a terminal inside `attack_agent`)

```
pip install -r requirements.txt
python build_features.py ..
python train_all.py
python tiny_forest.py
python evaluate_all.py ..
```

- The two dots `..` mean the parent folder `AI_team_data`, which contains `normal_data` and `abnormal_data`.
- Run the steps in this order, because each step uses the files made by the one before.
- Building the features takes a few minutes.
- Optional extra check: `python cross_check_seeds.py` (leave-one-seed-out).

---

## 8. Quick summary

We turned each 2-second window of sensor and network data into 50 health features (timing, repeats, jitter, jumps, consistency, network counts), measured relative to each run's own calm period, and trained one small Random Forest on normal data plus 16 attacks. A numpy-only agent uses it on a live-style stream and raises an alert when 3 of the last 5 decisions agree. On unseen simulated runs it detected all 96 runs of the detectable attacks and named 91 correctly, with no false alarms on normal runs, a 32 KB model and under 1 MB of agent memory. Its weak points are `missed_contact` (undetectable), confusion between `duplicate` and `flood`, and some remaining false alarms after `service_abuse` ends.

---

## 9. Acknowledgements

The code and analysis were developed with assistance from Claude (Anthropic). All scripts were run on my own computer, and the results above come from those runs.
