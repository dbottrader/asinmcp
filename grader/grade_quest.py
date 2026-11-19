#!/usr/bin/env python3
"""Replay grader for independent verification of code-quest results.

This is NOT a house grader. Its job is the one ASIN exists for: an
OUTSIDE operator takes a result someone else published — a winning
entry's claimed score and verdict — and replays the grading locally,
from the public record alone (the submission files at a named commit
plus the published metric), then seals the result or publicly refuses
it. The output is a mesh-canon receipt (canon_v1 bytes, sha256) that
any third party can recompute, the same style as the mesh ledger and
HHC receipts in ~/workspace/agent-mesh/v02/mesh_v02.py (canon_v1 /
sha_hex) and ~/workspace/agent-mesh/v03-hhc/hhc_mesh.py (hhc_receipt).

Contract
--------
Input 1: a quest spec JSON (the published metric + the claim being
replayed). Fields:
    quest            quest slug, e.g. "toy-sort-001"
    metric           metric name, e.g. "cases_passed"
    entrypoint       file the submission must contain, e.g. "main.py"
    harness_dir      dir (relative to the spec file) holding the test
                     harness; copied into the sandbox beside the
                     submission. May be null for a self-testing entry.
    test_command     argv run in the sandbox, e.g. ["python3",
                     "run_tests.py"]
    score            {"type": "regex", "pattern": "SCORE=([0-9.]+)"}
                     or {"type": "exit_code"} (1.0 iff exit code 0)
    bar              {"value": 4, "direction": "higher"|"lower"}
    timeout_seconds  hard wall-clock limit for the test command
    claimed          {"score": 4, "verdict": "PASS"} — the original
                     result under replay. Optional for a first-party
                     grade; required for the receipt to be a replay
                     verdict (MATCH / REFUSAL).

Input 2: a submission directory (the entrant's files, e.g. a checkout
of the entry's public repository at its submitted commit).

The submission + harness are copied into a fresh temp dir; the test
command runs there with a scrubbed environment, a timeout, and a
network namespace (unshare -n) where the host permits it. Nothing in
the submission directory is modified.

Output: a verdict receipt JSON (printed, and written with --out):
    quest, spec_hash, submission_hash (sha256 over the submission
    files, canon), metric, score, bar, verdict PASS|FAIL, reason,
    exit_code, timed_out, network, duration_ms, ts, grader
    {name, version}, receipt = sha256(canon_v1(receipt body)), and —
    when the spec carries a claim — a replay block:
    {claimed_score, claimed_verdict, outcome: MATCH|REFUSAL,
     differing_field: null | "score" | "verdict" | "score,verdict"}.
    MATCH is the seal: the replay reproduces the published result.
    REFUSAL names the field(s) that do not recompute.

Self-verification: after grading, the grader recomputes the
submission hash and the receipt hash and refuses to call the run
complete unless both match. `verify` mode re-checks an existing
receipt against a submission directory the same way.

Stdlib only. Usage:
    grade_quest.py grade  <spec.json> <submission_dir> [--out R.json]
    grade_quest.py verify <receipt.json> <submission_dir>
Exit codes: grade -> 0 if the receipt verifies (whatever the
verdict), 2 on grader error; verify -> 0 match, 1 mismatch.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

GRADER_NAME = "asinmolt-grade-quest"
GRADER_VERSION = "0.1.0"


# --- mesh canon (mirrors mesh_v02.canon_v1 / sha_hex) ---------------------

def canon_v1(obj):
    """Canonical bytes v1: JSON, sorted keys, no whitespace, UTF-8,
    ASCII-escaped. Identical to mesh_v02.canon_v1."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def sha_hex(b):
    return hashlib.sha256(b).hexdigest()


# --- hashing ---------------------------------------------------------------

def submission_hash(submission_dir):
    """sha256 over the submission's files: canon_v1 of the sorted list
    of [relative_path, sha256(file bytes)], itself hashed. Empty dirs
    and __pycache__ are ignored; symlinks are hashed by target path
    name only and never followed out of the tree."""
    entries = []
    for root, dirs, files in os.walk(submission_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, submission_dir).replace(os.sep, "/")
            if os.path.islink(full):
                entries.append([rel, "symlink:" + os.readlink(full)])
                continue
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            entries.append([rel, h.hexdigest()])
    return sha_hex(canon_v1({"files": entries})), entries


def receipt_hash(receipt):
    body = {k: v for k, v in receipt.items() if k != "receipt"}
    return sha_hex(canon_v1(body))


# --- sandbox run -------------------------------------------------------------

def _net_isolated():
    """True when a network namespace is available for the test run."""
    try:
        r = subprocess.run(["unshare", "-n", "true"],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def run_tests(spec, spec_dir, submission_dir):
    """Copy submission (+ harness) into a temp sandbox and run the
    spec's test command. Returns (exit_code, timed_out, stdout,
    network_mode, duration_ms)."""
    sandbox = tempfile.mkdtemp(prefix="gradequest-")
    try:
        shutil.copytree(submission_dir, sandbox, dirs_exist_ok=True,
                        symlinks=True)
        harness_dir = spec.get("harness_dir")
        if harness_dir:
            shutil.copytree(os.path.join(spec_dir, harness_dir), sandbox,
                            dirs_exist_ok=True, symlinks=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
               "PYTHONHASHSEED": "0", "HOME": sandbox}
        cmd = list(spec["test_command"])
        network = "not_isolated"
        if _net_isolated():
            cmd = ["unshare", "-n"] + cmd
            network = "isolated"
        started = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(
                cmd, cwd=sandbox, env=env, capture_output=True,
                text=True, timeout=float(spec["timeout_seconds"]))
            exit_code, stdout = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as e:
            timed_out, exit_code = True, None
            stdout = ((e.stdout or b"").decode(errors="replace")
                      if isinstance(e.stdout, bytes) else (e.stdout or ""))
        duration_ms = int((time.monotonic() - started) * 1000)
        return exit_code, timed_out, stdout, network, duration_ms
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def extract_score(spec, exit_code, timed_out, stdout):
    """Read the score from the run per the spec's published rule.
    Returns (score_or_None, reason)."""
    if timed_out:
        return None, "timeout"
    rule = spec["score"]
    if rule["type"] == "exit_code":
        return (1.0 if exit_code == 0 else 0.0), "ok"
    if rule["type"] == "regex":
        m = re.search(rule["pattern"], stdout)
        if not m:
            return None, "score_not_found"
        try:
            return float(m.group(1)), "ok"
        except ValueError:
            return None, "score_not_a_number"
    return None, "unknown_score_type"


def grade(spec_path, submission_dir):
    with open(spec_path, "rb") as f:
        spec_bytes = f.read()
    spec = json.loads(spec_bytes)
    spec_dir = os.path.dirname(os.path.abspath(spec_path))

    sub_hash, _entries = submission_hash(submission_dir)
    receipt = {
        "canon": "canon_v1",
        "grader": {"name": GRADER_NAME, "version": GRADER_VERSION},
        "quest": spec["quest"],
        "spec_hash": sha_hex(spec_bytes),
        "submission_hash": sub_hash,
        "metric": spec["metric"],
        "bar": spec["bar"],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    entrypoint = spec.get("entrypoint")
    if entrypoint and not os.path.isfile(os.path.join(submission_dir,
                                                       entrypoint)):
        receipt.update(score=None, verdict="FAIL",
                       reason="entrypoint_missing", exit_code=None,
                       timed_out=False, network=None, duration_ms=0)
    else:
        exit_code, timed_out, stdout, network, duration_ms = run_tests(
            spec, spec_dir, submission_dir)
        score, reason = extract_score(spec, exit_code, timed_out, stdout)
        passed = False
        if score is not None:
            if spec["bar"].get("direction", "higher") == "lower":
                passed = score <= float(spec["bar"]["value"])
            else:
                passed = score >= float(spec["bar"]["value"])
        receipt.update(score=score, verdict="PASS" if passed else "FAIL",
                       reason=reason, exit_code=exit_code,
                       timed_out=timed_out, network=network,
                       duration_ms=duration_ms)
    receipt["replay"] = replay_block(spec, receipt)
    receipt["receipt"] = receipt_hash(receipt)
    return receipt


def replay_block(spec, receipt):
    """Compare the recomputed result against the claim recorded in
    the spec. MATCH seals the original result; REFUSAL names every
    field that does not recompute."""
    claimed = spec.get("claimed")
    if not claimed:
        return {"claimed_score": None, "claimed_verdict": None,
                "outcome": "NO_CLAIM", "differing_field": None}
    differing = []
    claimed_score = claimed.get("score")
    if claimed_score is not None:
        if receipt.get("score") is None or \
                float(receipt["score"]) != float(claimed_score):
            differing.append("score")
    claimed_verdict = claimed.get("verdict")
    if claimed_verdict is not None and \
            receipt.get("verdict") != claimed_verdict:
        differing.append("verdict")
    return {"claimed_score": claimed_score,
            "claimed_verdict": claimed_verdict,
            "outcome": "REFUSAL" if differing else "MATCH",
            "differing_field": ",".join(differing) if differing else None}


def verify_receipt(receipt, submission_dir):
    """Recompute both hashes from the artefacts on disk. Returns a
    list of problems (empty == verified)."""
    problems = []
    sub_hash, _ = submission_hash(submission_dir)
    if sub_hash != receipt.get("submission_hash"):
        problems.append("submission_hash mismatch: receipt %s, "
                        "recomputed %s" % (receipt.get("submission_hash"),
                                           sub_hash))
    if receipt_hash(receipt) != receipt.get("receipt"):
        problems.append("receipt hash mismatch: receipt %s, recomputed %s"
                        % (receipt.get("receipt"), receipt_hash(receipt)))
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    mode = argv[1]
    if mode == "grade":
        if len(argv) < 4:
            print("usage: grade_quest.py grade <spec.json> "
                  "<submission_dir> [--out R.json]")
            return 2
        spec_path, submission_dir = argv[2], argv[3]
        out_path = None
        if "--out" in argv:
            out_path = argv[argv.index("--out") + 1]
        receipt = grade(spec_path, submission_dir)
        problems = verify_receipt(receipt, submission_dir)
        text = json.dumps(receipt, indent=2, sort_keys=True)
        if out_path:
            with open(out_path, "w") as f:
                f.write(text + "\n")
        print(text)
        if problems:
            print("SELF-VERIFY FAILED: " + "; ".join(problems),
                  file=sys.stderr)
            return 2
        print("SELF-VERIFY OK: submission_hash and receipt recompute "
              "to the values in the receipt", file=sys.stderr)
        return 0
    if mode == "verify":
        if len(argv) < 4:
            print("usage: grade_quest.py verify <receipt.json> "
                  "<submission_dir>")
            return 2
        with open(argv[2]) as f:
            receipt = json.load(f)
        problems = verify_receipt(receipt, argv[3])
        if problems:
            print("VERIFY FAILED: " + "; ".join(problems))
            return 1
        print("VERIFY OK: receipt %s recomputes over %s"
              % (receipt["receipt"], argv[3]))
        return 0
    print("unknown mode: %s" % mode)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
