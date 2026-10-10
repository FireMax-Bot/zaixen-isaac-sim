#!/usr/bin/env python3
"""Tiny client for Isaac Sim's python server (port 8226, no auth on this setup).

Protocol: send Python source over TCP, half-close, read one JSON reply.
CLI:   python3 isaac_exec.py "1+1"            (prints output / result)
Import: from isaac_exec import run; reply = run("import zaixen_log; zaixen_log.status()")
"""
import json
import socket
import sys

HOST, PORT = "127.0.0.1", 8226


def run(code, timeout=60.0):
    with socket.create_connection((HOST, PORT), timeout=10) as s:
        s.settimeout(timeout)
        s.sendall(code.encode())
        s.shutdown(socket.SHUT_WR)
        data = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return json.loads(data.decode())


if __name__ == "__main__":
    r = run(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    if r.get("output"):
        print(r["output"])
    if "result" in r:
        print("=>", r["result"])
    if r.get("status") != "ok":
        print("ERROR:", r.get("ename"), r.get("evalue"))
        sys.exit(1)
