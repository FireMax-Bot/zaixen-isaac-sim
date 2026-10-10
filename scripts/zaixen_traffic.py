# zaixen_traffic.py -- NPC traffic on the plus roads + ring road, and the signal cycle.
#
# One module, two layers:
#   * core   (pure Python, no omni imports): lane paths, car-following, gap/priority logic.
#            Tested off-line by test_ring_traffic.py (NPCs) and test_ego_loop.py (NPCs + the autonomous ego).
#   * glue   (Isaac Sim): builds the car pool (kinematic rigid bodies with contact reports), drives the prims,
#            cycles the traffic-light materials, and offers the "NPC Traffic" slider window.
#            Runs from the fixed 60 Hz physics step via zaixen_runtime (never wall-clock time).
#
# Use (Script Editor, or via run_simulation.py):
#   import zaixen_traffic as zt
#   zt.arm()                 # lights + NPC traffic + slider window
#   zt.set_npc_count(14)     # any number 0..MAX_NPCS, live
#   zt.TRAFFIC_STATE         # {"X": phase, "Y": phase, "t": sim seconds} -- what the ego reads
#   zt.collision_flag()      # 1 while the ego touches an NPC
#   zt.disarm()
#
# NPCs use ALL FOUR arms: loops L1-L4 drive the N-S arms (Y signal), L5-L8 are the same loops turned 90 degrees and
# drive the E-W arms (X signal), sharing those lanes with the ego. Wherever two loops cross or merge (junction, ring
# mouths) a precomputed conflict zone lets the first car to arrive through and makes the other stop short of it.
#
# Network (m, Z-up, right-hand traffic, 1 m lanes, matches part2_ring_roads.py)
#   Y arms : northbound lane x=+0.5, southbound lane x=-0.5 (straight through the signalised junction)
#   ring   : inner lane r=14.5 runs clockwise, outer lane r=15.5 runs counter-clockwise
#   Every turn between an arm and the ring is one circular arc, tangent to both lanes:
#     right turns  -> radius 1.3 arc centred on the curb-return fillet centre   (inner ring lane)
#     left  turns  -> radius 2.0 arc                                            (outer ring lane)
#   Four fixed closed loops (each NPC keeps its loop forever, no teleporting):
#     L1  north-bound, right/right : N end -> clockwise, east half        -> S arm north-bound
#     L2  south-bound, right/right : S end -> clockwise, west half        -> N arm south-bound
#     L3  north-bound, left/left   : N end -> counter-clockwise, west half -> S arm north-bound
#     L4  south-bound, left/left   : S end -> counter-clockwise, east half -> N arm south-bound
#   The ego lives on the E-W arms; NPCs only cross those arms at the signalised junction.
import math
import random
import re

# ------------------------------------------------------------------ layout (mirrors part2_ring_roads.py)
ROAD_HALF_W = 1.0
LANE_OFF = 0.5
RING_R = 15.0
R_IN = RING_R - ROAD_HALF_W          # 14.0  ring inner edge
LANE_IN_R = RING_R - 0.5             # 14.5  clockwise lane
LANE_OUT_R = RING_R + 0.5            # 15.5  counter-clockwise lane
CURB_R = 0.8
STOP_FRONT = 1.75                    # front bumper stops here (behind the stop line at 1.6..1.72)
SIGNAL_CYCLE = 20.0

# ------------------------------------------------------------------ vehicle + behaviour tuning
CAR_SCALE = 0.6                      # NPC prims are 0.8 x 0.5 m; x0.6 = 0.48 x 0.30 m = ego footprint
CAR_L, CAR_W = 0.8 * CAR_SCALE, 0.5 * CAR_SCALE
MAX_NPCS = 30
DEFAULT_NPCS = 10
CRUISE = 1.0                         # m/s free flow (each car scales this by its own 0.85..1.1 factor)
A_ACC, A_COMF, A_HARD = 1.0, 2.0, 4.5
A_LAT = 0.55                         # lateral accel limit -> curve speed
T_CAR = 0.72                         # centre distance below which two car paths "conflict"
T_EGO = 0.72
STEP = 0.15                          # corridor sample spacing (m)
LOOK_BASE = 0.9                      # braking corridor length = v^2/(2*A_COMF) + LOOK_BASE
CONF_LEN = 3.0                       # conflicts are checked over at least this much path, so a crossing
                                     # car is modelled through its whole crossing, not just its next step
DS = 0.04                            # route resample spacing (m)
COLORS = ["Red", "Blue", "Yellow", "Orange", "Purple", "Teal", "White", "Lime"]


# ================================================================== core: routes
def _arc(cx, cy, r, a0, a1, step=DS):
    n = max(2, int(math.ceil(abs(math.radians(a1 - a0)) * r / step)))
    ccw = a1 > a0
    out = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def _line(x0, y0, x1, y1, step=DS):
    n = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / step)))
    return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]


def _rot180(pts):
    return [(-x, -y) for x, y in pts]


class Route:
    """Closed loop resampled at uniform arclength. kind[i] in {'line','conn','ring'}."""

    def __init__(self, name, segs, axis):
        self.axis = axis                                # "Y": drives the N-S arms (Y signal), "X": the E-W arms (X signal)
        pts, kinds = [], []
        for kind, seg in segs:
            for p in seg:
                if pts and abs(p[0] - pts[-1][0]) < 1e-9 and abs(p[1] - pts[-1][1]) < 1e-9:
                    continue
                pts.append(p)
                kinds.append(kind)
        if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6:
            pts.pop(); kinds.pop()                      # closed: last == first
        cum = [0.0]
        for i in range(1, len(pts) + 1):
            a, b = pts[i - 1], pts[i % len(pts)]
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        total = cum[-1]
        n = int(round(total / DS))
        self.name, self.n, self.length, self.ds = name, n, total, total / n
        xs, ys, kd = [], [], []
        k = 0
        for i in range(n):
            s = i * self.ds
            while cum[k + 1] < s:
                k += 1
            a, b = pts[k], pts[(k + 1) % len(pts)]
            f = (s - cum[k]) / max(cum[k + 1] - cum[k], 1e-12)
            xs.append(a[0] + (b[0] - a[0]) * f)
            ys.append(a[1] + (b[1] - a[1]) * f)
            kd.append(kinds[k])
        self.xs, self.ys, self.kind = xs, ys, kd
        hx, hy = [], []
        for i in range(n):
            dx = xs[(i + 1) % n] - xs[i - 1]
            dy = ys[(i + 1) % n] - ys[i - 1]
            m = math.hypot(dx, dy)
            hx.append(dx / m); hy.append(dy / m)
        self.hx, self.hy = hx, hy
        # curvature-limited speed, smoothed backwards so cars slow down BEFORE a turn
        vc = []
        for i in range(n):
            a1 = math.atan2(hy[(i + 5) % n], hx[(i + 5) % n]) - math.atan2(hy[i - 5], hx[i - 5])
            a1 = (a1 + math.pi) % (2 * math.pi) - math.pi
            kappa = abs(a1) / (10 * self.ds)
            vc.append(min(3.0, math.sqrt(A_LAT / kappa)) if kappa > 1e-4 else 3.0)
        for _ in range(2):
            for i in range(n - 1, -1 - n, -1):
                j = i % n
                nxt = vc[(j + 1) % n]
                vc[j] = min(vc[j], math.sqrt(nxt * nxt + 2 * A_COMF * self.ds))
        self.vcurve = vc
        # stop line: first sample on the leading straight within STOP_FRONT of the junction centre (along the arm axis)
        along, across = (ys, xs) if axis == "Y" else (xs, ys)
        self.s_line = next(i for i in range(n) if abs(along[i]) <= STOP_FRONT and abs(across[i]) < 1.0) * self.ds
        self.spawn_idx = [i for i in range(n)
                          if kd[i] == "ring" or (kd[i] == "line" and 3.5 <= abs(along[i]) <= 11.5)]

    def xy(self, s):
        f = (s % self.length) / self.ds
        i = int(f); f -= i
        j = i + 1 if i + 1 < self.n else 0
        return (self.xs[i] + (self.xs[j] - self.xs[i]) * f, self.ys[i] + (self.ys[j] - self.ys[i]) * f)

    def heading(self, s):
        f = (s % self.length) / self.ds
        i = int(f); f -= i
        j = i + 1 if i + 1 < self.n else 0
        x = self.hx[i] + (self.hx[j] - self.hx[i]) * f
        y = self.hy[i] + (self.hy[j] - self.hy[i]) * f
        return math.atan2(y, x)

    def vlim(self, s):
        return self.vcurve[int((s % self.length) / self.ds) % self.n]


def build_routes():
    yc = math.sqrt((R_IN - CURB_R) ** 2 - (ROAD_HALF_W + CURB_R) ** 2)   # 13.077 fillet centre y
    xc = ROAD_HALF_W + CURB_R                                              # 1.8
    rho_r = xc - LANE_OFF                                                  # 1.3
    a_b = math.degrees(math.atan2(yc, xc))                                 # 82.16
    rho_l = 2.0
    yl = math.sqrt((LANE_OUT_R - rho_l) ** 2 - (rho_l - LANE_OFF) ** 2)    # 13.416
    phi_l = math.degrees(math.atan2(yl, -(rho_l - LANE_OFF)))              # 96.37
    exit_r = _arc(xc, yc, rho_r, 180.0, a_b)                               # N arm NB lane -> CW inner lane
    entry_r = _arc(-xc, yc, rho_r, 180.0 - a_b, 0.0)                       # CW inner lane -> N arm SB lane
    exit_l = _arc(-(rho_l - LANE_OFF), yl, rho_l, 0.0, phi_l)              # N arm NB lane -> CCW outer lane
    entry_l = _arc(rho_l - LANE_OFF, yl, rho_l, 180.0 - phi_l, 180.0)      # CCW outer lane -> N arm SB lane
    cw = lambda p0, p1: _arc(0, 0, LANE_IN_R, p0, p1)
    ccw = lambda p0, p1: _arc(0, 0, LANE_OUT_R, p0, p1)
    y_loops = [
        ("L1", [("line", _line(LANE_OFF, -yc, LANE_OFF, yc)), ("conn", exit_r), ("ring", cw(a_b, -a_b)),
                ("conn", _rot180(entry_r))]),
        ("L2", [("line", _line(-LANE_OFF, yc, -LANE_OFF, -yc)), ("conn", _rot180(exit_r)),
                ("ring", cw(180.0 + a_b, 180.0 - a_b)), ("conn", entry_r)]),
        ("L3", [("line", _line(LANE_OFF, -yl, LANE_OFF, yl)), ("conn", exit_l),
                ("ring", ccw(phi_l, 360.0 - phi_l)), ("conn", _rot180(entry_l))]),
        ("L4", [("line", _line(-LANE_OFF, yl, -LANE_OFF, -yl)), ("conn", _rot180(exit_l)),
                ("ring", ccw(180.0 + phi_l, 540.0 - phi_l)), ("conn", entry_l)]),
    ]
    # the E-W arms: the same four loops turned 90 degrees (x, y) -> (-y, x); they obey the X signal
    x_loops = [(f"L{int(nm[1]) + 4}", [(kind, [(-y, x) for x, y in pts]) for kind, pts in segs]) for nm, segs in y_loops]
    return [Route(nm, segs, "Y") for nm, segs in y_loops] + [Route(nm, segs, "X") for nm, segs in x_loops]


# ================================================================== core: signals
def signal_phase(t):
    """Y-axis phase at cycle time t (s). X is the same pattern shifted by half a cycle."""
    t %= SIGNAL_CYCLE
    return "GREEN" if t < 8.0 else ("YELLOW" if t < 10.0 else "RED")


def signal_phases(t):
    return {"Y": signal_phase(t), "X": signal_phase(t + SIGNAL_CYCLE / 2.0)}


# ================================================================== core: conflict zones
def _zones_for(A, B):
    """Conflict zones between two closed routes, from A's point of view.

    A zone is a stretch of A (a0, alen) that lies within T_CAR of a stretch of B (b0, blen) where the two
    paths CROSS or MERGE. Where they run on top of each other (shared lane) or peel apart (diverge) there
    is no zone: that is ordinary car-following, handled separately.
    """
    cell = T_CAR
    grid = {}
    for j in range(0, B.n, 2):
        grid.setdefault((int(math.floor(B.xs[j] / cell)), int(math.floor(B.ys[j] / cell))), []).append(j)
    t2, c2 = T_CAR * T_CAR, 0.12 * 0.12
    info = {}
    idxs = list(range(0, A.n, 2))
    for i in idxs:
        x, y = A.xs[i], A.ys[i]
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        best = None
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for j in grid.get((gx, gy), ()):
                    d = (x - B.xs[j]) ** 2 + (y - B.ys[j]) ** 2
                    if d < t2 and (best is None or d < best[0]):
                        best = (d, j)
        if best is not None:
            d, j = best
            info[i] = (j, d < c2 and A.hx[i] * B.hx[j] + A.hy[i] * B.hy[j] > 0.9)
    start = next((k for k, i in enumerate(idxs) if i not in info), None)
    if start is None:
        return []
    order = idxs[start:] + idxs[:start]
    runs, cur = [], []
    for i in order:
        if i in info:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    zones = []
    for run in runs:
        while run and info[run[0]][1]:                       # starts on top of B -> the paths are diverging
            run = run[1:]
        if not run:
            continue
        for t, i in enumerate(run):                          # ends on top of B -> the paths are merging
            if info[i][1]:
                run = run[:t + 1]
                break
        a0 = run[0] * A.ds
        alen = ((run[-1] - run[0]) % A.n) * A.ds
        js = [info[i][0] for i in run]
        offs = [((j - js[0] + B.n // 2) % B.n) - B.n // 2 for j in js]
        b0 = ((js[0] + min(offs)) % B.n) * B.ds
        blen = (max(offs) - min(offs)) * B.ds
        zones.append((a0 - 0.05, alen + 0.10, b0 - 0.15, blen + 0.30))
    return zones


def _zone_rel(s, L, z0, zlen):
    """Where a car (centre at arclength s) is relative to a zone: (0, dist_to_entry) before, (1, 0) inside, (2, 0) after."""
    front = s + CAR_L / 2.0 + 0.02
    rear = s - CAR_L / 2.0 - 0.05
    u = ((front - z0 + L / 2.0) % L) - L / 2.0
    if u < 0.0:
        return 0, -u
    w = ((rear - (z0 + zlen) + L / 2.0) % L) - L / 2.0
    return (1, 0.0) if w <= 0.0 else (2, 0.0)


# ================================================================== core: traffic simulation
class Car:
    __slots__ = ("id", "route", "ri", "s", "v", "vf", "active", "x", "y", "h", "dfree", "stall", "hold", "red", "hard")

    def __init__(self, i):
        self.id, self.route, self.ri, self.s, self.v, self.vf = i, None, 0, 0.0, 0.0, 1.0
        self.active, self.x, self.y, self.h, self.stall, self.dfree = False, 0.0, 0.0, 0.0, 0.0, 1e9
        self.hold, self.red, self.hard = 0.0, False, 1e9   # hold: s left standing after touching the ego; red: stopping for a signal


class Ego:
    """Ego pose for the yield logic: position, yaw and velocity (world frame)."""
    __slots__ = ("x", "y", "yaw", "vx", "vy", "wz")

    def __init__(self, x, y, yaw, vx=0.0, vy=0.0, wz=0.0):
        self.x, self.y, self.yaw, self.vx, self.vy, self.wz = x, y, yaw, vx, vy, wz


CONTACT_HOLD = 1.0       # s an NPC stands still after the ego last touched it
JUNCTION_BOX = 1.4       # |x|,|y| below this = inside the signalised junction (incl. crosswalk edge)
ZONE_MARGIN = 0.15       # a loser stops with its bumper this far before a conflict zone
FOLLOW_GAP = 0.80        # centre-to-centre distance a follower holds behind its leader (0.32 m bumper gap)


class TrafficSim:
    def __init__(self, max_cars=MAX_NPCS, seed=11, routes=None):
        self.routes = routes or build_routes()
        self.cars = [Car(i) for i in range(max_cars)]
        self.rng = random.Random(seed)
        self.time = 0.0
        self.right = {}          # (id_a, id_b, zone) -> (winner id, last time the pair was contested)
        self.zones = []          # (route a, route b, a0, alen, b0, blen)
        for ia in range(len(self.routes)):
            for ib in range(ia + 1, len(self.routes)):
                A, B = self.routes[ia], self.routes[ib]
                zb = _zones_for(B, A)                       # each route's own stretch, measured from its own side
                for a0, alen, b0, blen in _zones_for(A, B):
                    ax, ay = A.xy(a0 + alen / 2.0)
                    near = [(math.hypot(B.xy(z[0] + z[1] / 2.0)[0] - ax, B.xy(z[0] + z[1] / 2.0)[1] - ay), z) for z in zb]
                    if near and min(near)[0] < 2.0:
                        b0, blen = min(near)[1][0], min(near)[1][1]
                    self.zones.append((ia, ib, a0, alen, b0, blen))

    # ---------------------------------------------------------- population
    def n_active(self):
        return sum(1 for c in self.cars if c.active)

    def _place(self, c, ri, s):
        route = self.routes[ri]
        c.route, c.ri, c.s = route, ri, s % route.length
        c.vf = self.rng.uniform(0.85, 1.10)
        c.v = min(CRUISE * c.vf, route.vlim(c.s)) * 0.8
        c.active, c.stall = True, 0.0
        self._pose(c)

    def _pose(self, c):
        c.x, c.y = c.route.xy(c.s)
        c.h = c.route.heading(c.s)

    def _clear_spot(self, route, s, ego):
        x, y = route.xy(s)
        for o in self.cars:
            if o.active and (o.x - x) ** 2 + (o.y - y) ** 2 < 1.9 ** 2:
                return False
        return not (ego and (ego.x - x) ** 2 + (ego.y - y) ** 2 < 2.5 ** 2)

    def spawn_one(self, ego=None):
        car = next((c for c in self.cars if not c.active), None)
        if car is None:
            return False
        counts = [sum(1 for c in self.cars if c.active and c.ri == k) for k in range(len(self.routes))]
        for ri in sorted(range(len(self.routes)), key=lambda k: (counts[k], self.rng.random())):
            route = self.routes[ri]
            for _ in range(300):
                s = route.spawn_idx[self.rng.randrange(len(route.spawn_idx))] * route.ds
                if self._clear_spot(route, s, ego):
                    self._place(car, ri, s)
                    return True
        return False

    def set_count(self, n, ego=None):
        n = max(0, min(int(n), len(self.cars)))
        while self.n_active() > n:
            last = max((c for c in self.cars if c.active), key=lambda c: c.id)
            last.active = False
        while self.n_active() < n:
            if not self.spawn_one(ego):
                break
        return self.n_active()

    def reset(self, n, ego=None):
        for c in self.cars:
            c.active = False
        self.right.clear()
        return self.set_count(n, ego)

    # ---------------------------------------------------------- stepping
    def notify_contact(self, car_id):
        """The ego touched this car: it stands still until the ego has been clear of it for CONTACT_HOLD seconds."""
        self.cars[car_id].hold = CONTACT_HOLD

    def step(self, dt, phases=None, ego=None):
        """phases: {"X": phase, "Y": phase} (a bare string is taken as the Y phase, X red)."""
        if phases is None:
            phases = {"X": "RED", "Y": "GREEN"}
        elif isinstance(phases, str):
            phases = {"Y": phases, "X": "RED"}
        n = max(1, int(math.ceil(dt / 0.05)))
        for _ in range(n):
            self._sub(dt / n, phases, ego)
        self.time += dt
        if len(self.right) > 300:
            self.right = {k: v for k, v in self.right.items() if self.time - v[1] < 1.0}

    def _contest(self, c, dc, o, do, zid):
        """Both cars are before the same zone: decide once who goes first, then keep that decision."""
        key = (c.id, o.id, zid) if c.id < o.id else (o.id, c.id, zid)
        held = self.right.get(key)
        if held is not None and self.time - held[1] < 1.0:
            win = held[0]
        else:
            tc, to = dc / max(c.v, 0.4), do / max(o.v, 0.4)
            win = c.id if (tc < to - 0.05 or (abs(tc - to) <= 0.05 and c.id < o.id)) else o.id
        self.right[key] = (win, self.time)
        return win

    def _sub(self, h, phases, ego):
        act = [c for c in self.cars if c.active]
        for c in act:
            c.dfree, c.red = 1e9, False
        by_route = [[] for _ in self.routes]
        for c in act:
            by_route[c.ri].append(c)

        # ---- traffic light (each route obeys its own axis): stop unless already past the line or unable to stop
        for c in act:
            phase = phases[c.route.axis]
            if phase == "GREEN":
                continue
            line_d = c.route.s_line - (c.s + CAR_L / 2.0)
            if line_d < -0.01 or line_d > 40.0:
                continue
            need = c.v * c.v / (2 * (A_HARD if phase == "RED" else A_COMF))
            if line_d >= need - 0.05:
                c.dfree = min(c.dfree, max(0.0, line_d - 0.03))
                c.red = True

        # ---- car following: the car ahead in the lane, on the same route (exact) or another route (geometric)
        for c in act:
            ch, sh, L = math.cos(c.h), math.sin(c.h), c.route.length
            for o in act:
                if o is c:
                    continue
                if o.ri == c.ri:
                    gap = (o.s - c.s) % L
                    if gap < 4.0:
                        c.dfree = min(c.dfree, gap - FOLLOW_GAP)
                    continue
                dx, dy = o.x - c.x, o.y - c.y
                if dx * dx + dy * dy > 9.0:
                    continue
                lon = dx * ch + dy * sh
                if 0.0 < lon < 3.0 and abs(-dx * sh + dy * ch) < 0.38 and math.cos(o.h - c.h) > 0.7:
                    c.dfree = min(c.dfree, lon - FOLLOW_GAP)

        # ---- conflict zones (crossings and merges): first to arrive owns the zone, the other stops short of it
        #      pass 1: a car already inside a zone keeps it; every car still before it must wait (a hard fact).
        #      pass 2: cars that are both about to enter contest it. A car only holds a claim if it could really drive
        #      into and through the zone: not held by a red light, not stuck behind another car, not held out by a
        #      different zone. (Claims from cars that cannot move are what produce wait-cycles between cars.)
        pending = []
        for zid, (ia, ib, a0, alen, b0, blen) in enumerate(self.zones):
            LA, LB = self.routes[ia].length, self.routes[ib].length
            sa = [(c,) + _zone_rel(c.s, LA, a0, alen) for c in by_route[ia]]
            sb = [(o,) + _zone_rel(o.s, LB, b0, blen) for o in by_route[ib]]
            for c, sc, dc in sa:
                if sc == 2:
                    continue
                for o, so, do in sb:
                    if so == 2:
                        continue
                    if sc == 1 and so == 0:
                        o.dfree = min(o.dfree, max(0.0, do - ZONE_MARGIN))
                    elif sc == 0 and so == 1:
                        c.dfree = min(c.dfree, max(0.0, dc - ZONE_MARGIN))
            # only the car at the head of each queue contests a zone; the cars behind it just follow their leader
            head_a = min(((d, c.id, c) for c, st, d in sa if st == 0), default=None, key=lambda r: (r[0], r[1]))
            head_b = min(((d, o.id, o) for o, st, d in sb if st == 0), default=None, key=lambda r: (r[0], r[1]))
            if head_a and head_b:
                pending.append((zid, head_a[2], head_a[0], head_b[2], head_b[0]))
        for c in act:
            c.hard = c.dfree
        for zid, c, dc, o, do in pending:
            if c.hard < dc + 0.2 or o.hard < do + 0.2:
                continue                                     # one of them cannot get through: the other one goes
            if dc > c.v * c.v / (2 * A_COMF) + 2.5 and do > o.v * o.v / (2 * A_COMF) + 2.5:
                continue                                     # both still far away: nothing to decide yet
            if self._contest(c, dc, o, do, zid) == c.id:
                o.dfree = min(o.dfree, max(0.0, do - ZONE_MARGIN))
            else:
                c.dfree = min(c.dfree, max(0.0, dc - ZONE_MARGIN))

        # ---- ego: always has right of way (position + short velocity projection)
        if ego is not None:
            now = [(ego.x + 0.12 * math.cos(ego.yaw), ego.y + 0.12 * math.sin(ego.yaw)),
                   (ego.x - 0.12 * math.cos(ego.yaw), ego.y - 0.12 * math.sin(ego.yaw))]      # where the ego IS
            samples = list(now)
            sp = math.hypot(ego.vx, ego.vy)
            if sp > 0.05:                                                                     # where it is GOING:
                wz = getattr(ego, "wz", 0.0)                                                  # constant speed + turn rate
                psi = math.atan2(ego.vy, ego.vx)
                for tt in (0.3, 0.6, 0.9, 1.2, 1.5):
                    if abs(wz) > 0.05:
                        samples.append((ego.x + sp / wz * (math.sin(psi + wz * tt) - math.sin(psi)),
                                        ego.y - sp / wz * (math.cos(psi + wz * tt) - math.cos(psi))))
                    else:
                        samples.append((ego.x + ego.vx * tt, ego.y + ego.vy * tt))
            # margin between an NPC centre and the ego's predicted centre line. In a tight turn the ego's body corners
            # swing out to ~0.77 m from the turn centre (well outside its centre line), so the margin grows with turn rate.
            t_e = T_EGO + 0.25 * min(1.0, abs(getattr(ego, "wz", 0.0)))
            t2 = t_e * t_e
            for c in act:
                look = max(c.v * c.v / (2 * A_COMF) + LOOK_BASE, CONF_LEN)
                if (c.x - ego.x) ** 2 + (c.y - ego.y) ** 2 > (look + 2.5) ** 2:
                    continue
                r = c.route
                for k in range(int(look / STEP) + 2):
                    px, py = r.xy(c.s + k * STEP)
                    if k == 0 and any((px - qx) ** 2 + (py - qy) ** 2 < t2 for qx, qy in now):
                        # Already inside the ego's body zone. Only a car committed inside the signalised junction (it
                        # entered on the last of the yellow and the ego has just been released) keeps going to clear
                        # it: stopping in the middle of the junction would block the ego. Anywhere else: stop.
                        # An ego BEHIND this car in its own lane is no threat to it (the ego must hold back): ignoring it
                        # also prevents a deadlock where the ego waits for this car and this car waits for the ego.
                        # (An ego merely beside the car, about to cross its lane, IS a threat.)
                        edx, edy = ego.x - c.x, ego.y - c.y
                        behind = (edx * math.cos(c.h) + edy * math.sin(c.h) < -0.05
                                  and abs(-edx * math.sin(c.h) + edy * math.cos(c.h)) < 0.5)
                        if not behind and not (abs(c.x) < JUNCTION_BOX and abs(c.y) < JUNCTION_BOX):
                            c.dfree = 0.0
                        break
                    if any((px - qx) ** 2 + (py - qy) ** 2 < t2 for qx, qy in samples):
                        c.dfree = min(c.dfree, max(0.0, (k - 1) * STEP))     # the ego is coming here: stop short of it
                        break

        # ---- integrate
        for c in act:
            r = c.route
            if c.hold > 0.0:                                 # touched the ego: stand still until it has been clear a while
                c.dfree = 0.0
                c.hold -= h
            vcap = min(CRUISE * c.vf, r.vlim(c.s))
            vt = vcap if c.dfree >= 1e8 else min(vcap, math.sqrt(2 * A_COMF * max(c.dfree, 0.0)))
            v = min(vt, c.v + A_ACC * h) if vt > c.v else max(vt, c.v - A_HARD * h)
            c.s = (c.s + 0.5 * (c.v + v) * h) % r.length
            c.v = v
            c.stall = c.stall + h if v < 0.03 else 0.0
            self._pose(c)


# ================================================================== glue: Isaac Sim
# Everything below runs from the runtime's fixed 60 Hz physics step (zaixen_runtime): nothing here reads wall-clock time.
TRAFFIC_STATE = {"X": "RED", "Y": "GREEN", "t": 0.0}      # live signal state; the ego controller reads TRAFFIC_STATE["X"]
COLLISION = {"ego_npc_step": -100, "npc_npc_step": -100, "total": 0}
SEED = 11                                                   # fixed seed: every Play starts from the same traffic
EGO_START = (-13.04, -0.507, 0.0)                           # where the ego stands at t = 0 (x, y, yaw)
_S = {}                                                     # runtime state (kept here so nothing gets garbage-collected)


def _lazy_omni():
    import omni.usd
    import omni.kit.app
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema
    return omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema


def _material(stage, UsdShade, Sdf, Gf, path, color, rough=0.4):
    if stage.GetPrimAtPath(path).IsValid():
        return UsdShade.Material(stage.GetPrimAtPath(path))
    m = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, path + "/Shader")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(rough)
    m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    return m


def build_pool(stage=None, count=MAX_NPCS):
    """(Re)build /World/Junction/NPCCars: `count` ego-sized cars, all hidden and inactive.
    Each car is a KINEMATIC rigid body (moved by the traffic logic, cannot be pushed) with a contact-report API, so the
    ego really collides with it and the collision is reported. The ego-scale (x0.6) lives on a child Model prim."""
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    stage = stage or omni.usd.get_context().get_stage()
    if stage.GetPrimAtPath("/World/Junction/NPCCars").IsValid():
        stage.RemovePrim("/World/Junction/NPCCars")
    palette = {"Red": (0.75, 0.08, 0.08), "Blue": (0.08, 0.20, 0.75), "Yellow": (0.85, 0.70, 0.05),
               "Orange": (0.85, 0.40, 0.05), "Purple": (0.45, 0.10, 0.65), "Teal": (0.05, 0.55, 0.55),
               "White": (0.85, 0.85, 0.85), "Lime": (0.45, 0.75, 0.10)}
    wheel_mat = _material(stage, UsdShade, Sdf, Gf, "/World/Looks/WheelRubber", (0.03, 0.03, 0.03), 0.9)
    glass_mat = _material(stage, UsdShade, Sdf, Gf, "/World/Looks/CarWindow", (0.05, 0.08, 0.12), 0.15)
    UsdGeom.Scope.Define(stage, "/World/Junction/NPCCars")
    car_l, car_w, car_h = 0.8, 0.4, 0.35                   # unscaled prototype (the Model prim applies CAR_SCALE)
    cab_l, cab_w, cab_h = 0.42, 0.30, 0.16
    wheel_r, wheel_t = 0.09, 0.06

    def box(path, size, tr, mat, collide=False):
        g = UsdGeom.Cube.Define(stage, path)
        g.CreateSizeAttr(1.0)
        x = UsdGeom.Xformable(g); x.ClearXformOpOrder()
        x.AddTranslateOp().Set(Gf.Vec3d(*tr)); x.AddScaleOp().Set(Gf.Vec3f(*size))
        UsdShade.MaterialBindingAPI.Apply(g.GetPrim()).Bind(mat)
        if collide:
            UsdPhysics.CollisionAPI.Apply(g.GetPrim())

    for i in range(count):
        color = COLORS[i % len(COLORS)]
        body_mat = _material(stage, UsdShade, Sdf, Gf, f"/World/Looks/Car_{color}", palette[color])
        path = f"/World/Junction/NPCCars/Car_{i:02d}_{color}"
        car = UsdGeom.Xform.Define(stage, path)
        xf = UsdGeom.Xformable(car); xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(0, 0, -5.0))
        xf.AddRotateZOp().Set(0.0)
        rb = UsdPhysics.RigidBodyAPI.Apply(car.GetPrim())
        rb.CreateKinematicEnabledAttr(True)
        rb.CreateRigidBodyEnabledAttr(False)               # switched on only while the car is active
        PhysxSchema.PhysxContactReportAPI.Apply(car.GetPrim()).CreateThresholdAttr(0.0)
        model = UsdGeom.Xform.Define(stage, path + "/Model")
        UsdGeom.Xformable(model).AddScaleOp().Set(Gf.Vec3f(CAR_SCALE, CAR_SCALE, CAR_SCALE))
        m = path + "/Model"
        box(m + "/Body", (car_l, car_w, car_h), (0, 0, car_h / 2), body_mat, collide=True)
        cz = car_h + cab_h / 2
        box(m + "/Cabin", (cab_l, cab_w, cab_h), (-0.05, 0, cz), body_mat)
        box(m + "/WindowFront", (0.02, cab_w * 0.92, cab_h * 0.75), (-0.05 + cab_l / 2 - 0.01, 0, cz), glass_mat)
        box(m + "/WindowRear", (0.02, cab_w * 0.92, cab_h * 0.75), (-0.05 - cab_l / 2 + 0.01, 0, cz), glass_mat)
        wx, wy = car_l / 2 - wheel_r - 0.06, car_w / 2 + wheel_t / 2 - 0.01
        for nm, sx, sy in (("FL", wx, wy), ("FR", wx, -wy), ("RL", -wx, wy), ("RR", -wx, -wy)):
            cyl = UsdGeom.Cylinder.Define(stage, f"{m}/Wheel_{nm}")
            cyl.CreateRadiusAttr(wheel_r); cyl.CreateHeightAttr(wheel_t); cyl.CreateAxisAttr("Y")
            cx = UsdGeom.Xformable(cyl); cx.ClearXformOpOrder()
            cx.AddTranslateOp().Set(Gf.Vec3d(sx, sy, wheel_r))
            UsdShade.MaterialBindingAPI.Apply(cyl.GetPrim()).Bind(wheel_mat)
        UsdGeom.Imageable(car.GetPrim()).MakeInvisible()
        UsdPhysics.CollisionAPI(stage.GetPrimAtPath(m + "/Body")).CreateCollisionEnabledAttr(False)
    return count


def _collect_pool(stage):
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    pool = []
    for child in stage.GetPrimAtPath("/World/Junction/NPCCars").GetChildren():
        if not child.GetName().startswith("Car_"):
            continue
        t_op = r_op = None
        for op in UsdGeom.Xformable(child).GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                t_op = op
            elif op.GetOpType() == UsdGeom.XformOp.TypeRotateZ:
                r_op = op
        pool.append((child, t_op, r_op, stage.GetPrimAtPath(str(child.GetPath()) + "/Model/Body"),
                     UsdPhysics.RigidBodyAPI(child)))
    pool.sort(key=lambda p: p[0].GetName())
    return pool


def _apply_visibility():
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    for car, (prim, t_op, r_op, body, rb) in zip(_S["sim"].cars, _S["pool"]):
        img = UsdGeom.Imageable(prim)
        if car.active:
            img.MakeVisible()
        else:
            img.MakeInvisible()
            t_op.Set(Gf.Vec3d(0, 0, -5.0))
        rb.GetRigidBodyEnabledAttr().Set(bool(car.active))
        UsdPhysics.CollisionAPI(body).GetCollisionEnabledAttr().Set(bool(car.active))


def _write_poses():
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    z = _S["road_top"]
    with Sdf.ChangeBlock():
        for car, (prim, t_op, r_op, body, rb) in zip(_S["sim"].cars, _S["pool"]):
            if car.active:
                t_op.Set(Gf.Vec3d(car.x, car.y, z))
                r_op.Set(math.degrees(car.h))


def _set_signals(phases):
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    stage = _S["stage"]
    emissive = {"green": Gf.Vec3f(0.0, 18.0, 0.0), "amber": Gf.Vec3f(18.0, 10.0, 0.0), "red": Gf.Vec3f(18.0, 0.0, 0.0)}
    off = Gf.Vec3f(0.03, 0.03, 0.03)
    names = {"GREEN": "green", "YELLOW": "amber", "RED": "red"}
    for axis in ("X", "Y"):
        if _S["phases"].get(axis) == phases[axis]:
            continue
        _S["phases"][axis] = phases[axis]
        for col in ("red", "amber", "green"):
            sh = UsdShade.Shader(stage.GetPrimAtPath(f"/World/Looks/Signal_{axis}_{col.capitalize()}/Shader"))
            sh.GetInput("emissiveColor").Set(emissive[col] if col == names[phases[axis]] else off)


def _on_reset():
    """Every Stop (and arm) lands here: same seed, same start, t = 0."""
    import zaixen_runtime as rt
    _S["sim"] = TrafficSim(seed=SEED)
    _S["sim"].reset(_S["count"], rt.ego() or Ego(*EGO_START))          # keep spawns clear of the ego's start pose
    _S["phases"] = {}
    ph = signal_phases(0.0)
    _set_signals(ph)
    TRAFFIC_STATE.update(X=ph["X"], Y=ph["Y"], t=0.0)
    COLLISION.update(ego_npc_step=-100, npc_npc_step=-100, total=0)
    _apply_visibility()
    _write_poses()


def _on_step(dt, t):
    import zaixen_runtime as rt
    ph = signal_phases(t)
    _set_signals(ph)
    TRAFFIC_STATE.update(X=ph["X"], Y=ph["Y"], t=t)
    _S["sim"].step(dt, ph, rt.ego())
    _write_poses()


_CAR_RE = re.compile(r"/World/Junction/NPCCars/Car_(\d+)_")


def _npc_id(path):
    m = _CAR_RE.match(path)
    return int(m.group(1)) if m else None


def _on_contact(pairs):
    import zaixen_runtime as rt
    for a, b in pairs:
        ia, ib = _npc_id(a), _npc_id(b)
        ego_a, ego_b = a.startswith("/World/Ego"), b.startswith("/World/Ego")
        npc = ia if (ia is not None and ego_b) else (ib if (ib is not None and ego_a) else None)
        if npc is not None:                                        # the ego hit this car
            if rt.step_count() - COLLISION["ego_npc_step"] > 60:   # contact flickers while pressed against a car:
                COLLISION["total"] += 1                            # a new collision = no contact for the last second
            COLLISION["ego_npc_step"] = rt.step_count()
            _S["sim"].notify_contact(npc)
        elif ia is not None and ib is not None:
            COLLISION["npc_npc_step"] = rt.step_count()


def collision_flag(window=6):
    """1 while the ego is in contact with an NPC (bridging contact flicker: any contact in the last `window` physics
    steps, default 0.1 s), else 0. The ego controller uses window=60 (1 s) so it does not push into a car again."""
    import zaixen_runtime as rt
    return 1 if rt.step_count() - COLLISION["ego_npc_step"] <= window else 0


def set_npc_count(n):
    """Set how many NPC cars are driving (0..MAX_NPCS). Safe to call live; the change is remembered in the stage."""
    sim = _S.get("sim")
    if sim is None:
        raise RuntimeError("call zaixen_traffic.arm() first")
    import zaixen_runtime as rt
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    got = sim.set_count(n, rt.ego())
    _S["count"] = got
    _apply_visibility()
    _write_poses()
    _S["stage"].GetPrimAtPath("/World/Junction").CreateAttribute(
        "zaixen:npcCount", Sdf.ValueTypeNames.Int, custom=True).Set(int(got))
    if "model" in _S and _S["model"].as_int != got:
        _S["model"].set_value(got)
    if "label" in _S:
        _S["label"].text = f"{got} NPC cars driving  (max {len(sim.cars)})"
    return got


WINDOW_TITLE = "NPC Traffic"
_WINDOW_KEEPER = "_zaixen_npc_traffic_window"          # attribute on the builtins module: survives our module reloads


def _hide_window():
    """Hide the panel. It is never destroyed: Isaac cannot delete a native window that belongs to a lost Python object."""
    import builtins
    win = getattr(builtins, _WINDOW_KEEPER, None)
    if win is not None:
        win.visible = False
    for k in ("model", "label", "log_cb"):
        _S.pop(k, None)


def show_ui():
    """The 'NPC Traffic' panel: a label showing the count, a slider, and the CSV-log check box.

    ONE window object is created the first time and then REUSED on every later arm (frame cleared and rebuilt). Creating
    a new ui.Window with the same title each time stacked several copies on top of each other: overlapping text, and old
    sliders that still called stale code."""
    import builtins
    import omni.ui as ui
    win = getattr(builtins, _WINDOW_KEEPER, None)
    if win is None:
        for h in ui.Workspace.get_windows():                 # hide stale copies left over from older versions of this file
            if getattr(h, "title", None) == WINDOW_TITLE:
                h.visible = False
        win = ui.Window(WINDOW_TITLE, width=360, height=140)
        setattr(builtins, _WINDOW_KEEPER, win)
    win.visible = True
    win.frame.clear()
    n = _S["sim"].n_active()
    model = ui.SimpleIntModel(n)
    _S["model"] = model
    with win.frame:
        with ui.VStack(spacing=8, height=0):                # each row has an explicit height so rows cannot overlap
            _S["label"] = ui.Label(f"{n} NPC cars driving  (max {len(_S['sim'].cars)})", height=22)
            ui.IntSlider(model, min=0, max=len(_S["sim"].cars), height=24)
            with ui.HStack(height=24, spacing=8):
                cb = ui.CheckBox(width=24)
                cb.model.set_value(False)
                ui.Label("Log to CSV (off by default)", height=24)

                def _toggle(m):
                    import zaixen_log
                    zaixen_log.enable() if m.as_bool else zaixen_log.disable()
                cb.model.add_value_changed_fn(_toggle)
                _S["log_cb"] = cb
    model.add_value_changed_fn(lambda m: set_npc_count(m.as_int) if m.as_int != _S["sim"].n_active() else None)
    _S["window"] = win


def arm(count=None, ui_window=True):
    """Register the traffic + signals with the runtime (fixed-step, resets on Stop). See zaixen_runtime."""
    omni, Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema = _lazy_omni()
    import zaixen_runtime as rt
    disarm()
    stage = omni.usd.get_context().get_stage()
    j = stage.GetPrimAtPath("/World/Junction")
    pool_prim = stage.GetPrimAtPath("/World/Junction/NPCCars")
    kids = [c for c in pool_prim.GetChildren()] if pool_prim.IsValid() else []
    if len(kids) < MAX_NPCS or not kids[0].GetChild("Model").IsValid():
        build_pool(stage)                                          # missing, or an older (non-kinematic) pool
    if count is None:
        a = j.GetAttribute("zaixen:npcCount")
        count = a.Get() if a and a.Get() is not None else DEFAULT_NPCS
    _S.update(stage=stage, pool=_collect_pool(stage), count=int(count), phases={},
              road_top=j.GetAttribute("zaixen:roadSurfaceZ").Get(), sim=TrafficSim(seed=SEED))
    if not rt._S["armed"]:
        rt.arm()
    rt.register("traffic", on_reset=_on_reset, on_step=_on_step, on_contact=_on_contact, order=20)
    _on_reset()
    if ui_window:
        show_ui()
    set_npc_count(count)
    print(f"[zaixen_traffic] armed: {_S['sim'].n_active()} NPC cars on {len(_S['sim'].routes)} loops; "
          f"lights + traffic run on the fixed 60 Hz physics step (press Play).")


def disarm():
    import zaixen_runtime as rt
    rt.unregister("traffic")
    _hide_window()
