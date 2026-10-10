# Off-line closed-loop test of the ego decision logic (plain Python, no Isaac Sim):
#   python scripts/test_ego_loop.py [--long]
# A kinematic-bicycle ego (real wheelbase, steering + speed rate limits) runs the REAL ego_decide()/ego_perceive()
# at 60 Hz on the same 8-loop NPC network the sim uses, with 0..30 NPCs, and we check:
#   * ego never overlaps an NPC (oriented-rectangle test)          * ego never runs a red light
#   * ego never leaves the 2 m road on the arms                    * ego keeps completing laps (no deadlock with cars)
#   * ego stops at the line on red, and slows for cars ahead (counted)
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zaixen_traffic as zt
import zaixen_ego as ze
from test_ring_traffic import corners, overlap

DT = 1.0 / 60.0


def run(n_npcs, seconds, seed):
    sim = zt.TrafficSim(seed=seed)
    ego = zt.Ego(-13.04, -0.507, 0.0)
    sim.reset(n_npcs, ego)
    # kinematic bicycle state at the rear axle
    yaw, v = 0.0, 0.0
    rx, ry = ego.x - ze.REAR_AXLE, ego.y
    plan, v_cmd, steer = ze.Plan(), 0.0, 0.0
    st = dict(npc_hits=0, red_runs=0, off_road=0, laps=0, stops_red=0, slow_obs=0, max_ego_stall=0.0, max_npc_stall=0.0, stall=0.0)
    prev_leg, prev_v_c = "E", 0.0
    crossed_prev = False
    red_time = {"E": 0.0, "W": 0.0}
    t, n = 0.0, int(seconds / DT)
    for _ in range(n):
        ph = zt.signal_phases(t)
        cx, cy = rx + ze.REAR_AXLE * math.cos(yaw), ry + ze.REAR_AXLE * math.sin(yaw)
        pose = ze.EgoPose(cx, cy, yaw, v)
        npcs = [(c.x, c.y, c.h) for c in sim.cars if c.active]
        obst = ze.ego_perceive(npcs, pose, plan)
        cmd, plan = ze.ego_decide(ph["X"], obst, pose, plan)
        # actuators: rate-limited speed + steering, first-order speed response
        v_cmd += max(-ze.A_DEC * DT, min(ze.A_ACC * DT, cmd.speed - v_cmd))
        steer += max(-ze.STEER_RATE * DT, min(ze.STEER_RATE * DT, cmd.steer - steer))
        v += (v_cmd - v) * min(1.0, DT / 0.15)
        yaw += v * math.tan(steer) / ze.WHEELBASE * DT
        rx += v * math.cos(yaw) * DT
        ry += v * math.sin(yaw) * DT
        cx, cy = rx + ze.REAR_AXLE * math.cos(yaw), ry + ze.REAR_AXLE * math.sin(yaw)
        ego.x, ego.y, ego.yaw = cx, cy, yaw
        ego.vx, ego.vy = v * math.cos(yaw), v * math.sin(yaw)
        ego.wz = v * math.tan(steer) / ze.WHEELBASE
        sim.step(DT, ph, ego)
        t += DT
        # ---- checks
        eb = corners(cx, cy, yaw, 0.52, ze.TRACK + 0.06)                       # ego body incl. wheels
        for c in sim.cars:
            if c.active and (c.x - cx) ** 2 + (c.y - cy) ** 2 < 1.0 and overlap(eb, corners(c.x, c.y, c.h)):
                st["npc_hits"] += 1
        if abs(cx) < 12.6 and any(abs(p[1]) > 1.0 for p in eb):
            st["off_road"] += 1
        if cmd.leg != prev_leg and cmd.leg in ("E", "W"):
            st["laps"] += 0.5
        prev_leg = cmd.leg
        if cmd.reason == "red" and v < 0.03 and prev_v_c >= 0.03:
            st["stops_red"] += 1
        if cmd.reason == "obstacle" and cmd.speed < ze.V_CRUISE * 0.8:
            st["slow_obs"] += 1
        prev_v_c = v
        st["stall"] = st["stall"] + DT if v < 0.03 else 0.0
        st["max_ego_stall"] = max(st["max_ego_stall"], st["stall"])
        st["max_npc_stall"] = max([st["max_npc_stall"]] + [c.stall for c in sim.cars if c.active])
        # red light violation: front bumper across the stop line >0.5 s after red began
        front = cx + ze.FRONT_X * math.cos(yaw)
        for leg, line, sign in (("E", -ze.STOP_FRONT, 1), ("W", ze.STOP_FRONT, -1)):
            if cmd.leg == leg:
                past = (front - line) * sign > 0 and (front - line) * sign < 0.6
                red_time[leg] = red_time[leg] + DT if ph["X"] == "RED" else 0.0
                if past and ph["X"] == "RED" and red_time[leg] > 0.5 and v > 0.2 and abs(front - line) < 0.08:
                    st["red_runs"] += 1
    return st


def main():
    secs = 1800 if "--long" in sys.argv else 300
    ok = True
    for n in (0, 6, 12, 20, 30):
        for seed in (1, 2) if n else (1,):
            st = run(n, secs, seed)
            bad = st["npc_hits"] or st["red_runs"] or st["off_road"] or st["laps"] < secs / 120 or st["max_ego_stall"] > 60
            ok &= not bad
            print(f"NPCs={n:2d} seed={seed}  ego-NPC hits={st['npc_hits']}  red-runs={st['red_runs']}  off-road={st['off_road']}  "
                  f"laps={st['laps']:.1f}  stops-on-red={st['stops_red']}  slow-for-car steps={st['slow_obs']}  "
                  f"max-ego-stall={st['max_ego_stall']:.1f}s  max-npc-stall={st['max_npc_stall']:.1f}s  {'FAIL' if bad else 'ok'}")
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
