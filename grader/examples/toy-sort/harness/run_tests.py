#!/usr/bin/env python3
"""Toy harness for quest toy-sort-001.

Runs the submission's main.py on four cases (a line of space-separated
integers in, the same integers sorted ascending out) and prints
SCORE=<cases passed>. This file is the published metric's test half:
it ships with the quest spec, never with the submission.
"""
import subprocess
import sys

CASES = [
    ("3 1 2", "1 2 3"),
    ("9 4 7 1", "1 4 7 9"),
    ("5 5 2", "2 5 5"),
    ("0 -3 8", "-3 0 8"),
]


def main():
    passed = 0
    for given, expected in CASES:
        try:
            proc = subprocess.run(
                [sys.executable, "main.py"], input=given + "\n",
                capture_output=True, text=True, timeout=10)
            got = proc.stdout.strip()
        except Exception as e:  # timeout, crash on launch
            got = "<error: %s>" % e
        ok = got == expected
        passed += 1 if ok else 0
        print("case in=%r expected=%r got=%r %s"
              % (given, expected, got, "ok" if ok else "MISS"))
    print("SCORE=%d" % passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
