#!/usr/bin/env python3
"""Toy submission (the published claim does not survive replay):
sorts descending, so it passes none of the harness's cases — yet the
result under replay claims SCORE=4 / PASS."""
import sys


def main():
    nums = [int(x) for x in sys.stdin.read().split()]
    print(" ".join(str(n) for n in sorted(nums, reverse=True)))


if __name__ == "__main__":
    main()
