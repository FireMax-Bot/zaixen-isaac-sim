#!/usr/bin/env python3
"""Check the Isaac Sim -> WSL bridge: sim clock, then IMU / odometry / contact.

Usage:  python3 bridge_check.py [seconds]      (default 8)
        python3 bridge_check.py --watch [seconds]   print sim time each second
                                                    (press Pause/Stop in Isaac Sim to see it freeze)
Run in a shell that has ROS_DISCOVERY_SERVER set (see docs/bridge_setup.md).
"""
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32

TOPICS = [
    ("/clock", Clock, "rosgraph_msgs/msg/Clock"),
    ("/imu", Imu, "sensor_msgs/msg/Imu"),
    ("/odom", Odometry, "nav_msgs/msg/Odometry"),
    ("/contact", Float32, "std_msgs/msg/Float32"),
]


def stamp_s(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


class BridgeCheck(Node):
    def __init__(self):
        # No parameter services: a read-only probe doesn't need the extra DDS endpoints.
        super().__init__("bridge_check", start_parameter_services=False, parameter_overrides=[
            rclpy.parameter.Parameter("use_sim_time", rclpy.Parameter.Type.BOOL, True)])
        self.count = {t: 0 for t, _, _ in TOPICS}
        self.first_sim = {}
        self.last_sim = {}
        self.sample = {}
        self.sim_now = None  # latest /clock value

    def start(self):
        for topic, cls, _ in TOPICS:
            self.create_subscription(cls, topic, lambda m, t=topic: self.on_msg(t, m), qos_profile_sensor_data)

    def on_msg(self, topic, msg):
        if topic == "/clock":
            sim = stamp_s(msg.clock)
            self.sim_now = sim
        elif hasattr(msg, "header"):
            sim = stamp_s(msg.header.stamp)
        else:  # Float32 has no header: use the latest /clock value
            sim = self.sim_now
        if sim is None:
            return
        self.count[topic] += 1
        self.first_sim.setdefault(topic, sim)
        self.last_sim[topic] = sim
        self.sample.setdefault(topic, (sim, msg))


def sample_text(topic, msg):
    if topic == "/clock":
        return "clock=%.3f" % stamp_s(msg.clock)
    if topic == "/imu":
        a, w = msg.linear_acceleration, msg.angular_velocity
        return "accel=(%.3f, %.3f, %.3f) gyro=(%.3f, %.3f, %.3f)" % (a.x, a.y, a.z, w.x, w.y, w.z)
    if topic == "/odom":
        p, v = msg.pose.pose.position, msg.twist.twist.linear
        return "pos=(%.3f, %.3f, %.3f) lin_vel_x=%.3f frame=%s->%s" % (p.x, p.y, p.z, v.x, msg.header.frame_id, msg.child_frame_id)
    return "data=%.4f" % msg.data


def main():
    args = sys.argv[1:]
    watch = "--watch" in args
    nums = [a for a in args if a != "--watch"]
    secs = float(nums[0]) if nums else (30.0 if watch else 8.0)

    rclpy.init()
    node = BridgeCheck()
    # WARM-UP IS REQUIRED: subscriptions created in the first ~1 s after the node starts
    # receive nothing over the discovery server (all of them, silently). Spin first, then subscribe.
    warm = time.time()
    while time.time() - warm < 3.0:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.start()
    t0 = time.time()
    next_print = t0 + 1.0
    while rclpy.ok() and time.time() - t0 < secs:
        rclpy.spin_once(node, timeout_sec=0.1)
        if watch and time.time() >= next_print:
            next_print += 1.0
            print("wall %5.1fs  sim /clock = %s  node.get_clock() = %.3f" % (
                time.time() - t0,
                "%.3f" % node.sim_now if node.sim_now is not None else "none",
                stamp_s(node.get_clock().now().to_msg())), flush=True)
    wall = time.time() - t0
    if watch:
        node.destroy_node()
        rclpy.shutdown()
        return

    print("Measured over %.1f wall-seconds (use_sim_time=True)\n" % wall)
    print("%-9s %-28s %6s %10s %10s  %s" % ("topic", "type", "msgs", "Hz(wall)", "Hz(sim)", "sample (sim-time stamp)"))
    for topic, _, typ in TOPICS:
        n = node.count[topic]
        if n == 0:
            print("%-9s %-28s %6d %10s %10s  NO DATA" % (topic, typ, 0, "-", "-"))
            continue
        sim_span = node.last_sim[topic] - node.first_sim[topic]
        hz_sim = (n - 1) / sim_span if sim_span > 0 else float("nan")
        sim, msg = node.sample[topic]
        print("%-9s %-28s %6d %10.1f %10.1f  [sim %.3f] %s" % (topic, typ, n, n / wall, hz_sim, sim, sample_text(topic, msg)))
    sim_span = (node.last_sim.get("/clock", 0) - node.first_sim.get("/clock", 0)) if node.count["/clock"] else 0
    print("\nSim time advanced %.2f s in %.2f wall-seconds (real-time factor %.2f)" % (sim_span, wall, sim_span / wall))
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
