#!/usr/bin/env python3
"""Toy submission (honest): sort the integers on stdin, ascending."""
import sys


def main():
    nums = [int(x) for x in sys.stdin.read().split()]
    print(" ".join(str(n) for n in sorted(nums)))


if __name__ == "__main__":
    main()
