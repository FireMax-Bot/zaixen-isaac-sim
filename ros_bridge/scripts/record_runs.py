#!/usr/bin/env python3
"""Stage B recorder: one ROS 2 bag per Isaac Sim run (Play ... Stop).

Leave this running in a terminal. It waits for the sim, starts a new bag when
/clock appears, and closes it when the sim is Stopped. Pause does NOT end a run.
Every message is stored with its SIM-time stamp (not wall-clock).

Label each run before pressing Play:  runlabel npc10   (writes ~/ros2_ws/data/label.txt).
The label goes into the bag folder name, run_info.json and data/runs_manifest.csv.

Usage:  python3 record_runs.py [output_dir]      (default ~/ros2_ws/data/bags)
Needs ROS_DISCOVERY_SERVER set (see bridge_setup.md). Ctrl+C closes the current bag.
"""
import json
import os
import re
import sys
import time

import rclpy
import rosbag2_py
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from rclpy.serialization import deserialize_message
from rosgraph_msgs.msg import Clock

# topic -> message type. The ego drives itself inside Isaac Sim (nothing on ROS commands it).
TOPICS = {
    "/clock": "rosgraph_msgs/msg/Clock",
    "/imu": "sensor_msgs/msg/Imu",
    "/odom": "nav_msgs/msg/Odometry",
    "/contact": "std_msgs/msg/Float32",
    "/tf": "tf2_msgs/msg/TFMessage",
}
WARMUP_S = 3.0        # subscribing in the first ~1 s after node start receives nothing (see bridge_setup.md)
GONE_S = 1.5          # /clock publisher missing this long (wall) = sim Stopped
BACKWARDS_S = 0.5     # sim time jumping back more than this = new run (Stop+Play between checks)


def load_type(name):
    from rosidl_runtime_py.utilities import get_message
    return get_message(name)


class Recorder:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        data_dir = os.path.dirname(os.path.abspath(out_dir))
        self.label_file = os.path.join(data_dir, "label.txt")
        self.manifest = os.path.join(data_dir, "runs_manifest.csv")
        self.node = rclpy.create_node(
            "zaixen_recorder", start_parameter_services=False,
            parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.writer = None
        self.run_dir = None
        self.run_no = 0
        self.sim_ns = None          # latest /clock value
        self.counts = {}
        self.gone_since = None
        self.runs = []

    def subscribe(self):
        for topic, typ in TOPICS.items():
            self.node.create_subscription(
                load_type(typ), topic, lambda raw, t=topic: self.on_raw(t, raw),
                qos_profile_sensor_data, raw=True)

    # ---- run handling -------------------------------------------------
    def start_run(self):
        self.run_no += 1
        try:
            label = re.sub(r"[^A-Za-z0-9_-]", "", open(self.label_file).read().strip()) or "nolabel"
        except OSError:
            label = "nolabel"
        self.label = label
        self.wall_start = time.strftime("%Y-%m-%d %H:%M:%S")
        self.run_dir = os.path.join(self.out_dir, "run_%s_%02d_%s" % (time.strftime("%Y%m%d_%H%M%S"), self.run_no, label))
        self.writer = rosbag2_py.SequentialWriter()
        self.writer.open(rosbag2_py.StorageOptions(uri=self.run_dir, storage_id="sqlite3"),
                         rosbag2_py.ConverterOptions("", ""))
        for topic, typ in TOPICS.items():
            self.writer.create_topic(rosbag2_py.TopicMetadata(
                name=topic, type=typ, serialization_format="cdr", offered_qos_profiles=""))
        self.counts = {t: 0 for t in TOPICS}
        self.first_ns = self.sim_ns
        print("\n>>> RUN %d [%s] started -> %s (sim t=%.3f)" % (self.run_no, label, self.run_dir, self.sim_ns / 1e9), flush=True)

    def end_run(self, why):
        if self.writer is None:
            return
        self.writer = None  # closing the writer flushes the bag
        dur = (self.sim_ns - self.first_ns) / 1e9 if self.sim_ns is not None else 0.0
        summary = ", ".join("%s=%d" % (t, n) for t, n in self.counts.items())
        print("\n<<< RUN %d [%s] ended (%s): %.1f sim-s | %s" % (self.run_no, self.label, why, dur, summary), flush=True)
        self.runs.append(self.run_dir)
        info = {"bag": os.path.basename(self.run_dir), "label": self.label, "wall_start": self.wall_start,
                "wall_end": time.strftime("%Y-%m-%d %H:%M:%S"), "sim_start_s": self.first_ns / 1e9,
                "sim_end_s": self.sim_ns / 1e9, "ended_because": why, "messages": self.counts}
        with open(os.path.join(self.run_dir, "run_info.json"), "w") as f:
            json.dump(info, f, indent=2)
        new = not os.path.exists(self.manifest)
        with open(self.manifest, "a") as f:
            if new:
                f.write("bag,label,wall_start,sim_start_s,sim_end_s,sim_duration_s,imu_msgs,ended_because\n")
            f.write("%s,%s,%s,%.3f,%.3f,%.1f,%d,%s\n" % (info["bag"], self.label, self.wall_start, info["sim_start_s"],
                    info["sim_end_s"], dur, self.counts.get("/imu", 0), why))

    # ---- messages -----------------------------------------------------
    def on_raw(self, topic, raw):
        if topic == "/clock":
            clk = deserialize_message(raw, Clock).clock
            ns = clk.sec * 1_000_000_000 + clk.nanosec
            if self.writer is not None and self.sim_ns is not None and ns < self.sim_ns - int(BACKWARDS_S * 1e9):
                self.end_run("sim time went backwards")
            self.sim_ns = ns
            self.gone_since = None
            if self.writer is None:
                self.start_run()
        if self.writer is None or self.sim_ns is None:
            return
        self.writer.write(topic, bytes(raw), self.sim_ns)
        self.counts[topic] += 1

    def check_stopped(self):
        if self.writer is None:
            return
        if self.node.count_publishers("/clock") == 0:
            if self.gone_since is None:
                self.gone_since = time.time()
            elif time.time() - self.gone_since > GONE_S:
                self.end_run("sim stopped")
                self.gone_since = None
        else:
            self.gone_since = None

    def status_line(self):
        if self.writer is None:
            return "waiting for Isaac Sim to Play ...   (runs recorded: %d)" % len(self.runs)
        return "RUN %d  sim t=%8.2f  " % (self.run_no, self.sim_ns / 1e9) + " ".join(
            "%s:%d" % (t.lstrip("/")[:7], n) for t, n in self.counts.items())


def main():
    out_dir = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/ros2_ws/data/bags")
    rclpy.init()
    rec = Recorder(out_dir)
    print("Warming up %.0fs, output dir: %s" % (WARMUP_S, out_dir), flush=True)
    t = time.time()
    while time.time() - t < WARMUP_S:
        rclpy.spin_once(rec.node, timeout_sec=0.1)
    rec.subscribe()
    print("Ready. Press Play in Isaac Sim. Ctrl+C to quit.", flush=True)
    last = 0.0
    try:
        while rclpy.ok():
            rclpy.spin_once(rec.node, timeout_sec=0.1)
            rec.check_stopped()
            if time.time() - last > 1.0:
                last = time.time()
                print("\r" + rec.status_line() + "   ", end="", flush=True)
    except KeyboardInterrupt:
        pass
    rec.end_run("recorder quit")
    print("Bags: " + (", ".join(rec.runs) if rec.runs else "none"))
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
