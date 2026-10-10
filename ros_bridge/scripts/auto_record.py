#!/usr/bin/env python3
"""Automate the recording loop through Isaac Sim's python server (port 8226).

For each NPC count: write the run label, set the NPC count, press Play, wait for N sim-seconds,
press Stop, then confirm the recorder saved a new bag (record_runs.py must already be running).
Also switches the CSV logger on (new file for this batch) and links CSV run id <-> bag in
~/ros2_ws/data/batch_index.csv.

Usage: python3 auto_record.py [--counts 10,20,30] [--sim-seconds 60] [--prefix npc]
The NPC count that was set before the batch is restored at the end.
"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isaac_exec import run  # noqa: E402

DATA = os.path.expanduser("~/ros2_ws/data")
MANIFEST = os.path.join(DATA, "runs_manifest.csv")
LABEL = os.path.join(DATA, "label.txt")
INDEX = os.path.join(DATA, "batch_index.csv")


def q(stmts, expr="None"):
    """Run statements in Isaac Sim, return the JSON-decoded value of expr (printed as JSON); raise on error."""
    r = run(stmts + "\nimport json as _j\nprint(_j.dumps(" + expr + "))")
    if r.get("status") != "ok":
        raise RuntimeError("Isaac Sim error: %s %s" % (r.get("ename"), r.get("evalue")))
    lines = [l for l in (r.get("output") or "").splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


TL = "import omni.timeline as T\ntl = T.get_timeline_interface()"


def playing():
    return q(TL, "tl.is_playing()")


def sim_time():
    return q("import zaixen_runtime as rt", "rt.sim_time()")


def manifest_rows():
    try:
        return list(csv.DictReader(open(MANIFEST)))
    except OSError:
        return []


def wait_for(cond, timeout, what):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return
        time.sleep(1.0)
    raise TimeoutError("timed out waiting for " + what)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", default="10,20,30")
    ap.add_argument("--sim-seconds", type=float, default=60.0)
    ap.add_argument("--prefix", default="npc")
    a = ap.parse_args()
    counts = [int(c) for c in a.counts.split(",")]

    # --- preflight ---
    if playing():
        sys.exit("Isaac Sim is already Playing. Press Stop first, then rerun.")
    orig_count = q("import zaixen_traffic as zt", "zt._S.get('count')")
    print("original NPC count: %s (will be restored at the end)" % orig_count)
    csv_path = q("import zaixen_log as zl\nzl.enable()", "zl.status()['path']")
    print("CSV logger ON -> %s" % csv_path)
    os.makedirs(DATA, exist_ok=True)
    new_index = not os.path.exists(INDEX)

    try:
        for n in counts:
            label = "%s%d" % (a.prefix, n)
            before = len(manifest_rows())
            with open(LABEL, "w") as f:
                f.write(label + "\n")
            got = q("import zaixen_traffic as zt", "zt.set_npc_count(%d)" % n)
            print("\n=== %s: NPC count set to %s" % (label, got))
            csv_run = q("import zaixen_runtime as rt", "rt.run_id()")
            q(TL + "\ntl.play()")
            wait_for(playing, 20, "Play")
            t0 = time.time()
            last_t, last_move = -1.0, time.time()
            while True:
                st = sim_time()
                if st >= a.sim_seconds:
                    break
                if st > last_t + 1e-6:
                    last_t, last_move = st, time.time()
                elif time.time() - last_move > 40:
                    raise RuntimeError("sim time stopped advancing at %.1f" % st)
                print("\r   playing: sim t=%6.1f / %.0f   (wall %3.0fs)" % (st, a.sim_seconds, time.time() - t0), end="", flush=True)
                time.sleep(3.0)
            q(TL + "\ntl.stop()")
            print("\n   Stop pressed, waiting for the recorder to save the bag ...")
            wait_for(lambda: len(manifest_rows()) > before, 30, "the recorder to write the manifest row (is record_runs.py running?)")
            row = manifest_rows()[-1]
            ok = row["label"] == label
            print("   saved: %s  (%s sim-s, %s imu msgs)%s" % (row["bag"], row["sim_duration_s"], row["imu_msgs"], "" if ok else "  !! LABEL MISMATCH"))
            with open(INDEX, "a") as f:
                if new_index:
                    f.write("label,npc_count,bag,csv_file,csv_run_id,sim_duration_s\n")
                    new_index = False
                f.write("%s,%d,%s,%s,%s,%s\n" % (label, n, row["bag"], os.path.basename(csv_path.replace("\\", "/")), csv_run, row["sim_duration_s"]))
            time.sleep(4.0)  # let Stop finish resetting the scene
    finally:
        try:
            q(TL + "\nif tl.is_playing():\n    tl.stop()")
            if orig_count is not None:
                q("import zaixen_traffic as zt", "zt.set_npc_count(%d)" % orig_count)
                print("\nrestored NPC count to %s" % orig_count)
        except Exception as e:  # noqa: BLE001
            print("cleanup problem:", e)
    print("\nBatch done. See %s and %s" % (INDEX, MANIFEST))


if __name__ == "__main__":
    main()
