# Zaixen attack layer - data dictionary

Time: every timestamp is SIMULATION time (from `/clock`), stored as integer nanoseconds (`sim_time_ns`) plus a derived seconds column.
The ego car is driven by an in-sim Python callback, not by ROS. Attacks change the DATA a detector sees, not how the car drives.
Sensors are idealized (no noise); covariance fields are all-zero and are not logged.

> **`raw_clean.csv` is for our verification only and MUST NEVER be used for training.** It holds the true values copied from the raw sim topics in the same attacked run (the relay input). A detector only ever sees `raw.csv` / `aligned*.csv` / `telemetry.csv`.

## Files per run (`data/runs/<scenario>_seed<N>_<UTCdate>/`)

| file | what | use |
|---|---|---|
| `raw.csv` | long format, what the detector sees (the `_mon` topics) | training / detection |
| `raw_clean.csv` | long format, true values from the raw sim topics | **verification only, never training** |
| `events.csv` | one row per `/attack_event` (the only source of labels) | labels |
| `telemetry.csv` | 2 Hz wide graph/rate features (Product B) | training / detection |
| `aligned_first30s.csv` | 50 Hz aligned table, first 30 s (smoke check) | training format |
| `manifest.json` | seed, config, git commit, versions, `ego_driven_by`, baseline subscriber counts | provenance |
| `collector_summary.json`, `relay_stats.json`, `run_state.json`, `telemetry_baseline.json` | measured stats | provenance |

## raw.csv / raw_clean.csv

| column | meaning |
|---|---|
| `sim_time_ns`, `sim_time_s` | `/clock` value at the moment the collector received the message |
| `header_stamp_ns` | the message's own `header.stamp` in ns (empty for stamp-less topics such as `/contact`). Delay and clock-skew attacks change only its relation to `sim_time_ns` |
| `topic` | `/imu_mon`, `/odom_mon`, `/contact_mon` (raw.csv) or `/imu`, `/odom`, `/contact` (raw_clean.csv) |
| `field` | flattened field path; arrays would appear as `name[i]` |
| `value` | float |

## events.csv

| column | meaning |
|---|---|
| `sim_time_ns` | sim time stamped by the scheduler when it published the event |
| `recv_sim_time_ns` | sim time at the collector |
| `event` | `start` or `stop` |
| `attack_id`, `attack_type`, `attack_target` | identify the attack |
| `params_json` | flattened parameters (fields, attack_params, seed, attack_index, nominal start/stop) |
| `run_id` | run folder name |

## aligned.csv

50 Hz sim-time grid, last-value-hold per field. `<topic>` is the short name (imu, odom, contact); the `_mon` and raw sim topic names both map to it so attacked and converted-normal data share one schema.

| column | meaning |
|---|---|
| `sim_time_ns` | Grid time, integer ns of simulation time (50 Hz grid, strictly increasing) |
| `sim_time_s` | sim_time_ns / 1e9 (derived) |
| `t_rel_s` | Seconds since the run's t0 (scheduler start; first bag message for converted bags) |
| `imu.orientation.x` | Last value of this field (held) |
| `imu.orientation.y` | Last value of this field (held) |
| `imu.orientation.z` | Last value of this field (held) |
| `imu.orientation.w` | Last value of this field (held) |
| `imu.angular_velocity.x` | Last value of this field (held) |
| `imu.angular_velocity.y` | Last value of this field (held) |
| `imu.angular_velocity.z` | Last value of this field (held) |
| `imu.linear_acceleration.x` | Last value of this field (held) |
| `imu.linear_acceleration.y` | Last value of this field (held) |
| `imu.linear_acceleration.z` | Last value of this field (held) |
| `imu.age_s` | Seconds since this topic's last message at the grid time (drops and freezes stay visible) |
| `imu.stamp_lag_s` | sim_time(receipt) - header.stamp of the last message, seconds (delay / clock-skew visible) |
| `odom.pose.pose.position.x` | Last value of this field (held) |
| `odom.pose.pose.position.y` | Last value of this field (held) |
| `odom.pose.pose.position.z` | Last value of this field (held) |
| `odom.pose.pose.orientation.x` | Last value of this field (held) |
| `odom.pose.pose.orientation.y` | Last value of this field (held) |
| `odom.pose.pose.orientation.z` | Last value of this field (held) |
| `odom.pose.pose.orientation.w` | Last value of this field (held) |
| `odom.twist.twist.linear.x` | Last value of this field (held) |
| `odom.twist.twist.linear.y` | Last value of this field (held) |
| `odom.twist.twist.linear.z` | Last value of this field (held) |
| `odom.twist.twist.angular.x` | Last value of this field (held) |
| `odom.twist.twist.angular.y` | Last value of this field (held) |
| `odom.twist.twist.angular.z` | Last value of this field (held) |
| `odom.age_s` | Seconds since this topic's last message at the grid time (drops and freezes stay visible) |
| `odom.stamp_lag_s` | sim_time(receipt) - header.stamp of the last message, seconds (delay / clock-skew visible) |
| `contact.data` | Last value of this field (held) |
| `contact.age_s` | Seconds since this topic's last message at the grid time (drops and freezes stay visible) |
| `is_attack` | 1 while an attack is active (start <= sim_time < stop), else 0. From /attack_event only |
| `attack_type` | Attack name from the event, `none` when is_attack = 0 |
| `attack_target` | Topic key / target from the event, `none` when is_attack = 0 |
| `attack_id` | Event id (atk00, ...), `none` when is_attack = 0 |

## telemetry.csv (Product B)

One row every 0.5 s of sim time. Window columns cover the last 1 s of sim time; `collector_*` are cumulative.

| column | meaning |
|---|---|
| `sim_time_ns`, `sim_time_s` | tick time |
| `is_attack`, `attack_type`, `attack_target`, `attack_id` | labels from /attack_event |
| `imu_mon.rate_hz` | messages received in the last 1 s sim |
| `imu_mon.pub_count` | publishers on the topic (normal: 1) |
| `imu_mon.sub_count` | subscribers on the topic (baseline in manifest; an eavesdropper = baseline + 1) |
| `imu_mon.max_gap_s` | largest gap between consecutive messages in the window |
| `imu_mon.stamp_lag_mean_s` | mean of (receipt sim time - header.stamp); empty for stamp-less topics |
| `imu_mon.late_count` | messages in the window with stamp lag > 0.1 s |
| `odom_mon.rate_hz` | messages received in the last 1 s sim |
| `odom_mon.pub_count` | publishers on the topic (normal: 1) |
| `odom_mon.sub_count` | subscribers on the topic (baseline in manifest; an eavesdropper = baseline + 1) |
| `odom_mon.max_gap_s` | largest gap between consecutive messages in the window |
| `odom_mon.stamp_lag_mean_s` | mean of (receipt sim time - header.stamp); empty for stamp-less topics |
| `odom_mon.late_count` | messages in the window with stamp lag > 0.1 s |
| `contact_mon.rate_hz` | messages received in the last 1 s sim |
| `contact_mon.pub_count` | publishers on the topic (normal: 1) |
| `contact_mon.sub_count` | subscribers on the topic (baseline in manifest; an eavesdropper = baseline + 1) |
| `contact_mon.max_gap_s` | largest gap between consecutive messages in the window |
| `contact_mon.stamp_lag_mean_s` | mean of (receipt sim time - header.stamp); empty for stamp-less topics |
| `contact_mon.late_count` | messages in the window with stamp lag > 0.1 s |
| `node_count` | nodes in the monitored graph |
| `node_list_hash` | md5 prefix of the sorted node list |
| `new_nodes` | `;`-separated nodes not in the baseline node set |
| `param_event_count` | /parameter_events messages in the last 1 s |
| `service_call_count` | /zaixen/service_log entries in the last 1 s (our own instrumentation: Humble has no network-level service introspection) |
| `collector_queue_drops` | cumulative collector queue overflows |
| `collector_late_writes` | cumulative writes delayed > 1 s |

## Units and sampling (dataset)
- Time: simulation time in seconds / integer nanoseconds. `aligned.csv.gz` is a fixed 50 Hz grid (20 ms), last value held. `telemetry.csv.gz` is 2 Hz.
- `imu.orientation.*`, `odom.pose.pose.orientation.*`: unit quaternion (x, y, z, w), no unit.
- `imu.angular_velocity.*`, `odom.twist.twist.angular.*`: rad/s. `imu.linear_acceleration.*`: m/s^2.
- `odom.pose.pose.position.*`: metres, relative to the start pose. `odom.twist.twist.linear.*`: m/s.
- `contact.data`: force-like value, unit unverified, always 0.0 in normal driving.
- `*.age_s`, `*.stamp_lag_s`: seconds. Rates: messages per second of simulation time.
- Idealized sensors: no noise. Covariance fields are all zero and are not logged.

## Rules
- `raw_clean` (true values) is verification only and must never be used for training. It is NOT shipped in this branch.
- Labels come only from `events.csv`.

## dataset_index.csv
One row per run: `relative_path`, `type` (normal|attack), `attack_name`, `npc`, `seed`, `level` (1-3; 1 for single-configuration attacks, 0 for normal), `duration_s`, `n_rows` (rows in aligned.csv), `attack_start_s` / `attack_stop_s` (measured, seconds from run start; blank for normal), `startup_attempts`, `status`, plus `attack_no` (1-17), `levels_in_cell`, `level_values` (the settings), `t0_sim_s`.
