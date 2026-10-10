# Off-line stress test for zaixen_traffic (plain Python, no Isaac Sim needed):
#   python scripts/test_ring_traffic.py            -> quick run
#   python scripts/test_ring_traffic.py --long     -> 30 min of sim time per scenario
#
# Checks, per NPC count and with a scripted ego shuttling along the E-W arms:
#   * no two cars ever overlap (true oriented-rectangle test, not the planner's circles)
#   * no NPC touches the ego
#   * no NPC crosses the stop line more than 0.5 s after its light turned red
#   * no car is stuck (v ~ 0) for longer than two signal cycles (queue spill-back at saturation)
#   * every lane path stays clear of the curb geometry
#   * every car makes real progress (laps completed)
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zaixen_traffic as zt


def corners(x, y, h, L=zt.CAR_L, W=zt.CAR_W):
    c, s = math.cos(h), math.sin(h)
    return [(x + c * a - s * b, y + s * a + c * b) for a, b in ((L / 2, W / 2), (L / 2, -W / 2), (-L / 2, -W / 2), (-L / 2, W / 2))]


def overlap(p, q):
    for poly in (p, q):
        for i in range(4):
            ex, ey = poly[(i + 1) % 4][0] - poly[i][0], poly[(i + 1) % 4][1] - poly[i][1]
            ax, ay = -ey, ex
            pp = [ax * u + ay * v for u, v in p]
            qq = [ax * u + ay * v for u, v in q]
            if max(pp) < min(qq) - 1e-9 or max(qq) < min(pp) - 1e-9:
                return False
    return True


def curb_clearance(routes):
    """Smallest distance from any lane-path point (minus the car half width) to a curb feature."""
    yc = math.sqrt((zt.R_IN - zt.CURB_R) ** 2 - (zt.ROAD_HALF_W + zt.CURB_R) ** 2)
    xc = zt.ROAD_HALF_W + zt.CURB_R
    fillets = []
    for sx in (1, -1):
        for sy in (1, -1):
            fillets += [(sx * xc, sy * yc), (sx * yc, sy * xc)]
    worst = (9.0, None)
    for r in routes:
        for i in range(0, r.n, 2):
            x, y = r.xs[i], r.ys[i]
            rad = math.hypot(x, y)
            d = min(zt.R_IN - 0.0 - 99, 99)
            cands = []
            for fx, fy in fillets:                       # curb-return arcs (pavement is inside the circle)
                cands.append(math.hypot(x - fx, y - fy) - zt.CURB_R)
            if r.kind[i] != "conn":                                                     # arm edge (junction plaza excluded)
                across, along = (abs(x), abs(y)) if r.axis == "Y" else (abs(y), abs(x))
                if 1.0 < along < yc:
                    cands.append(abs(across - zt.ROAD_HALF_W))
            cands.append(zt.RING_R + zt.ROAD_HALF_W - rad)                             # outer ring edge
            gap = min(cands) - zt.CAR_W / 2
            if r.kind[i] == "ring" and abs(rad - zt.LANE_IN_R) < 0.01:
                gap = min(gap, rad - zt.R_IN - zt.CAR_W / 2)
            if gap < worst[0]:
                worst = (gap, (r.name, round(x, 2), round(y, 2), r.kind[i]))
    return worst


def run(n_cars, sim_seconds, seed, with_ego=False, dt=0.05):
    sim = zt.TrafficSim(seed=seed)
    ego = zt.Ego(-13.0, -0.5, 0.0) if with_ego else None
    sim.reset(n_cars, ego)
    got = sim.n_active()
    stats = dict(n=got, car_car=0, car_ego=0, red_runs=0, max_stall=0.0, min_gap=9.0, laps={}, mean_v=0.0)
    laps0 = {c.id: (c.route.name, c.s) for c in sim.cars if c.active}
    travelled = {c.id: 0.0 for c in sim.cars if c.active}
    last_s = {c.id: c.s for c in sim.cars if c.active}
    crossed = {}
    t = 0.0
    ego_dir, ego_x, ego_v = 1.0, -13.0, 0.9
    red_since = {}
    vsum = vcount = 0
    while t < sim_seconds:
        ph = zt.signal_phases(t)
        # scripted ego: shuttles along y=-0.5 (eastbound) / y=+0.5 (westbound), obeys the X signal
        if with_ego:
            x_line = -zt.STOP_FRONT if ego_dir > 0 else zt.STOP_FRONT
            gap_to_line = (x_line - (ego_x + ego_dir * 0.24)) * ego_dir
            stop = ph["X"] != "GREEN" and 0.0 <= gap_to_line < 3.0
            v = 0.0 if stop and gap_to_line < 0.35 else (min(ego_v, 0.6) if stop else ego_v)
            for c in sim.cars:                            # a sane driver also brakes for a car in its lane ahead
                if not c.active:
                    continue
                for tproj in (0.0, 0.5, 1.0):
                    cx = c.x + math.cos(c.h) * c.v * tproj
                    cy = c.y + math.sin(c.h) * c.v * tproj
                    lon = (cx - ego_x) * ego_dir
                    lat = cy - (-0.5 if ego_dir > 0 else 0.5)
                    if 0.0 < lon < 0.95 and abs(lat) < 0.5:
                        v = 0.0
            ego_x += ego_dir * v * dt
            if ego_x > 13.0 or ego_x < -13.0:
                ego_dir = -ego_dir
            ego.x, ego.y, ego.yaw = ego_x, (-0.5 if ego_dir > 0 else 0.5), (0.0 if ego_dir > 0 else math.pi)
            ego.vx, ego.vy = ego_dir * v, 0.0
        sim.step(dt, ph, ego)
        t += dt
        act = [c for c in sim.cars if c.active]
        polys = {c.id: corners(c.x, c.y, c.h) for c in act}
        for i in range(len(act)):
            for j in range(i + 1, len(act)):
                a, b = act[i], act[j]
                if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < 1.0 and overlap(polys[a.id], polys[b.id]):
                    stats["car_car"] += 1
                d = math.hypot(a.x - b.x, a.y - b.y)
                if d < stats["min_gap"]:
                    stats["min_gap"] = d
            if with_ego and overlap(polys[act[i].id], corners(ego.x, ego.y, ego.yaw)):
                stats["car_ego"] += 1
        for c in act:
            ds = (c.s - last_s[c.id]) % c.route.length
            travelled[c.id] += ds if ds < 5 else 0.0
            last_s[c.id] = c.s
            stats["max_stall"] = max(stats["max_stall"], c.stall)
            vsum += c.v; vcount += 1
            front = c.s + zt.CAR_L / 2
            if ph[c.route.axis] == "RED":
                red_since[c.id] = red_since.get(c.id, 0.0) + dt
            else:
                red_since[c.id] = 0.0
            was = crossed.get(c.id, False)
            now_crossed = front > c.route.s_line and front < c.route.s_line + 2.0
            if now_crossed and not was and ph[c.route.axis] == "RED" and red_since[c.id] > 0.5:
                stats["red_runs"] += 1
            crossed[c.id] = now_crossed
    stats["laps"] = {cid: round(d / sim.cars[cid].route.length, 1) for cid, d in travelled.items()}
    stats["mean_v"] = vsum / max(vcount, 1)
    return stats


def main():
    long_run = "--long" in sys.argv
    secs = 1800 if long_run else 360
    routes = zt.build_routes()
    print("route lengths:", {r.name: round(r.length, 2) for r in routes}, " stop-line s:", {r.name: round(r.s_line, 2) for r in routes})
    gap, where = curb_clearance(routes)
    print(f"min curb clearance (car edge to curb): {gap:.3f} m at {where}")
    ok = gap > 0.10
    for n in (0, 4, 10, 16, 24, zt.MAX_NPCS):
        for seed in (1, 2) if n else (1,):
            st = run(n, secs, seed, with_ego="--ego" in sys.argv)
            laps = list(st["laps"].values())
            bad = st["car_car"] or st["car_ego"] or st["red_runs"] or st["max_stall"] > 30.0 or (laps and min(laps) < 1.0 and secs >= 300)
            ok &= not bad
            print(f"N={st['n']:2d} seed={seed}  car-car={st['car_car']}  car-ego={st['car_ego']}  red-runs={st['red_runs']}  "
                  f"max-stall={st['max_stall']:.1f}s  min-centre-dist={st['min_gap']:.2f}m  mean-v={st['mean_v']:.2f}  "
                  f"laps(min/avg)={min(laps) if laps else 0:.1f}/{(sum(laps)/len(laps)) if laps else 0:.1f}  {'FAIL' if bad else 'ok'}")
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
