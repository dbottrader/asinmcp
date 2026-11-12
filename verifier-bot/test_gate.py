"""Adversarial test suite for the refusal-aware verification gate.

Implements SPEC.md v2 §"Adversarial test suite": the expected outcome
for every case is declared BEFORE the case runs (the EXPECTED constant
at the top of each case) and asserted after. Plus a clean PASS case, a
ledger tamper-detection case, and an Agent Vault signer round-trip on
an ephemeral vault (the live vault is never touched).

Run: python3 test_gate.py   (exit 0 only if every case passes)
No network. Deterministic: fixed seeds, fixed timestamps, fixed ids.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate as G  # noqa: E402

JOB = {"temperature": 0, "seed": 42, "input": [1, 2, 3]}
NOW = "2026-11-11T12:00:00Z"
FRESH = G.Preconditions("2026-11-11T00:00:00Z", "2026-11-12T00:00:00Z")
GOOD_CONTROL = G.Control("ctrl-known-good", expected="KNOWN-GOOD",
                         actual="KNOWN-GOOD")
POP = {"test_id": "population-count-check", "test_version": "1.0",
       "population_id": "pop-main"}


def solver(params):
    """Deterministic toy solver: the 'job' every witness re-executes."""
    return {"answer": params["seed"] + sum(params["input"]),
            "model": "toy-deterministic-v1"}


def agree(wid, operator, failure_mode, seed_byte):
    return G.build_witness(wid, operator, "impl-" + operator,
                           "src-" + operator, failure_mode, solver(JOB),
                           bytes([seed_byte]) * 32)


def disagree(wid, operator, failure_mode, seed_byte):
    return G.build_witness(wid, operator, "impl-" + operator,
                           "src-" + operator, failure_mode,
                           {"answer": -1, "model": "toy-deterministic-v1"},
                           bytes([seed_byte]) * 32)


def pair():
    """Two honest, independent, agreeing witnesses."""
    return [agree("w-alpha", "op-alpha", "sampling-drift", 11),
            agree("w-beta", "op-beta", "hardware-bitflip", 22)]


def new_gate():
    return G.Gate(G.TestSigner(b"gate-test-key"))


def run(g, witnesses, vid, **over):
    kw = dict(POP, stored_count=100, retrieve_served=lambda: 100,
              preconditions=FRESH, witnesses=witnesses, solver=solver,
              job_params=JOB, now=NOW, control=GOOD_CONTROL,
              verification_id=vid)
    kw.update(over)
    return g.attempt(**kw)


def check_schema(receipt):
    for key in ("schema", "verification_id", "test_id", "test_version",
                "population_id", "snapshot_hash", "residual", "control",
                "preconditions", "witnesses", "instrument_independence",
                "outcome", "reason", "receipt_hash", "external_anchor",
                "prev_receipt_hash", "signature"):
        assert key in receipt, "receipt missing field %s" % key
    assert receipt["schema"] == "ASIN-HHC-VERIFICATION-1.0"
    assert receipt["outcome"] in G.OUTCOMES


# --- Cases. EXPECTED is declared before each run, per the SPEC. -----------

def test_clean_pass():
    EXPECTED = (G.PASS, None)
    g = new_gate()
    r = run(g, pair(), "00000000-0000-4000-8000-000000000001")
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["residual"] == {"stored_count": 100, "served_count": 100,
                             "difference": 0}
    assert r["instrument_independence"]["review_status"] == \
        "ASSESSED_INDEPENDENT"
    assert G.verify_receipt(r, g.signer)
    ok, detail = g.chain_verify()
    assert ok, detail


def test_zero_residual_no_discriminating_control():
    EXPECTED = (G.REFUSED, G.R_NO_DISCRIMINATING_CONDITION)
    # (a) no control supplied at all
    g = new_gate()
    r = run(g, pair(), "00000000-0000-4000-8000-000000000002",
            control=None)
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    # REFUSED is terminal: it cannot be resolved into anything.
    try:
        g.resolve(r["verification_id"],
                  agree("w-gamma", "op-gamma", "network-partition", 33),
                  NOW)
        raise AssertionError("resolve on REFUSED did not raise")
    except G.GateError:
        pass
    # (b) control supplied but cannot distinguish the claim
    g2 = new_gate()
    weak = G.Control("ctrl-weak", expected="KNOWN-GOOD",
                     actual="KNOWN-GOOD", discriminates=False)
    r2 = run(g2, pair(), "00000000-0000-4000-8000-000000000012",
             control=weak)
    assert (r2["outcome"], r2["reason"]) == EXPECTED, r2["outcome"]


def test_stale_preconditions():
    EXPECTED = (G.VOID, G.R_STALE_PRECONDITIONS)
    stale = G.Preconditions("2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z")
    g = new_gate()
    r = run(g, pair(), "00000000-0000-4000-8000-000000000003",
            preconditions=stale)
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["preconditions"]["valid"] is False


def test_control_failure():
    EXPECTED = (G.REFUSED, G.R_CONTROL_FAILURE)
    bad = G.Control("ctrl-known-good", expected="KNOWN-GOOD",
                    actual="SOMETHING-ELSE")
    g = new_gate()
    r = run(g, pair(), "00000000-0000-4000-8000-000000000004",
            control=bad)
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["control"]["result"] == "FAIL"


def test_identical_failure_modes():
    EXPECTED = (G.REFUSED, G.R_NO_INDEPENDENT_WITNESS)
    # (a) different operators, identical failure modes
    ws = [agree("w-alpha", "op-alpha", "sampling-drift", 11),
          agree("w-beta", "op-beta", "sampling-drift", 22)]
    g = new_gate()
    r = run(g, ws, "00000000-0000-4000-8000-000000000005")
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["instrument_independence"]["review_status"] == \
        "ASSESSED_NOT_INDEPENDENT"
    # (b) same operator, different failure modes — still one witness
    # for independence purposes
    ws2 = [agree("w-alpha", "op-alpha", "sampling-drift", 11),
           agree("w-beta", "op-alpha", "hardware-bitflip", 22)]
    g2 = new_gate()
    r2 = run(g2, ws2, "00000000-0000-4000-8000-000000000015")
    assert (r2["outcome"], r2["reason"]) == EXPECTED, r2["outcome"]


def test_conflicting_results_then_third_resolves():
    EXPECTED_VOID = (G.VOID, G.R_WITNESS_CONFLICT)
    EXPECTED_PASS = (G.PASS, G.R_THIRD_PLACEMENT_QUORUM)
    EXPECTED_FAIL = (G.FAIL, G.R_THIRD_PLACEMENT_QUORUM)
    ws = [agree("w-alpha", "op-alpha", "sampling-drift", 11),
          disagree("w-beta", "op-beta", "hardware-bitflip", 22)]
    g = new_gate()
    r = run(g, ws, "00000000-0000-4000-8000-000000000006")
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED_VOID, r["outcome"]
    third = agree("w-gamma", "op-gamma", "network-partition", 33)
    r2 = g.resolve(r["verification_id"], third, NOW)
    check_schema(r2)
    assert (r2["outcome"], r2["reason"]) == EXPECTED_PASS, r2["outcome"]
    assert r2["resolution_of"] == r["receipt_hash"]
    ok, detail = g.chain_verify()
    assert ok, detail
    # Mirror image: third placement sides with DISAGREE -> FAIL.
    g2 = new_gate()
    r3 = run(g2, [agree("w-alpha", "op-alpha", "sampling-drift", 11),
                  disagree("w-beta", "op-beta", "hardware-bitflip", 22)],
             "00000000-0000-4000-8000-000000000016")
    assert (r3["outcome"], r3["reason"]) == EXPECTED_VOID
    r4 = g2.resolve(r3["verification_id"],
                    disagree("w-gamma", "op-gamma", "network-partition",
                             33), NOW)
    assert (r4["outcome"], r4["reason"]) == EXPECTED_FAIL, r4["outcome"]


def test_modified_evidence_after_sealing():
    EXPECTED = (G.FAIL, G.R_SEAL_MISMATCH)
    w2 = agree("w-beta", "op-beta", "hardware-bitflip", 22)
    w2.output = {"answer": 12345, "model": "toy-deterministic-v1"}  # tamper
    g = new_gate()
    r = run(g, [agree("w-alpha", "op-alpha", "sampling-drift", 11), w2],
            "00000000-0000-4000-8000-000000000007")
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["witnesses"][1]["seal_valid"] is False


def test_replay_of_expired_verification():
    EXPECTED = "ReplayRejected raised"
    short = G.Preconditions("2026-11-11T00:00:00Z", "2026-11-11T13:00:00Z")
    g = new_gate()
    r = run(g, pair(), "00000000-0000-4000-8000-000000000008",
            preconditions=short)
    assert r["outcome"] == G.PASS
    raised = False
    try:
        run(g, pair(), "00000000-0000-4000-8000-000000000008",
            preconditions=short, now="2026-11-12T00:00:00Z")
    except G.ReplayRejected:
        raised = True
    assert raised, EXPECTED
    # No second receipt was emitted for the replay.
    assert len(g.receipts) == 1


def test_manipulated_population_counts():
    EXPECTED = (G.FAIL, G.R_RESIDUAL_MISMATCH)
    g = new_gate()
    r = run(g, pair(), "00000000-0000-4000-8000-000000000009",
            retrieve_served=lambda: 97)
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["residual"]["difference"] == 3


def test_missing_witness_signature():
    EXPECTED = (G.REFUSED, G.R_INSUFFICIENT_VALID_WITNESSES)
    w2 = agree("w-beta", "op-beta", "hardware-bitflip", 22)
    w2.signature = None
    g = new_gate()
    r = run(g, [agree("w-alpha", "op-alpha", "sampling-drift", 11), w2],
            "00000000-0000-4000-8000-000000000010")
    check_schema(r)
    assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
    assert r["witnesses"][1]["signature_valid"] is False
    assert r["witnesses"][1]["valid"] is False
    assert r["instrument_independence"]["review_status"] == \
        "INSUFFICIENT_WITNESSES"


def test_failed_third_placement():
    EXPECTED_VOID = (G.VOID, G.R_THIRD_PLACEMENT_FAILED)
    ws = [agree("w-alpha", "op-alpha", "sampling-drift", 11),
          disagree("w-beta", "op-beta", "hardware-bitflip", 22)]
    g = new_gate()
    r = run(g, ws, "00000000-0000-4000-8000-000000000011")
    assert r["outcome"] == G.VOID
    bad_third = agree("w-gamma", "op-gamma", "network-partition", 33)
    bad_third.signature = "00" * 64  # invalid signature
    r2 = g.resolve(r["verification_id"], bad_third, NOW)
    check_schema(r2)
    assert (r2["outcome"], r2["reason"]) == EXPECTED_VOID, r2["outcome"]
    # Still VOID and still resolvable: a good placement lands after.
    r3 = g.resolve(r["verification_id"],
                   agree("w-delta", "op-delta", "clock-skew", 44), NOW)
    assert r3["outcome"] == G.PASS, r3["outcome"]


def test_ledger_tamper_detection():
    EXPECTED = "chain_verify flags the edited line"
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "receipts.jsonl")
        g = G.Gate(G.TestSigner(b"gate-test-key"), ledger_path=path)
        r = run(g, pair(), "00000000-0000-4000-8000-000000000013")
        ok, detail = G.chain_verify_file(path, signer=g.signer)
        assert ok, detail
        # Edit the stored receipt: flip the outcome after the fact.
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        edited = json.loads(lines[0])
        edited["outcome"] = "FAIL"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(edited) + "\n")
        ok, detail = G.chain_verify_file(path, signer=g.signer)
        assert not ok, EXPECTED + " (got: %s)" % detail
        # Same for an in-memory copy: hash no longer recomputes.
        forged = copy.deepcopy(r)
        forged["outcome"] = "FAIL"
        assert not G.verify_receipt(forged, g.signer)


def test_vault_signer_ephemeral():
    EXPECTED = (G.PASS, None)
    vault_py = os.path.expanduser("~/workspace/agent-vault/vault.py")
    with tempfile.TemporaryDirectory() as td:
        vdir = os.path.join(td, "vault")
        env = dict(os.environ)
        env["AGENT_VAULT_SECRET"] = "gate-test-ephemeral-secret"
        proc = subprocess.run([sys.executable, vault_py, "init",
                               "--dir", vdir], capture_output=True,
                              text=True, env=env)
        assert proc.returncode == 0, proc.stderr[-400:]
        signer = G.VaultSigner(vdir)
        os.environ["AGENT_VAULT_SECRET"] = "gate-test-ephemeral-secret"
        try:
            g = G.Gate(signer)
            r = run(g, pair(), "00000000-0000-4000-8000-000000000014")
            check_schema(r)
            assert (r["outcome"], r["reason"]) == EXPECTED, r["outcome"]
            assert r["signer"]["kind"] == "agent-vault-ed25519"
            assert G.verify_receipt(r, signer)
            ok, detail = g.chain_verify()
            assert ok, detail
        finally:
            del os.environ["AGENT_VAULT_SECRET"]


def test_cross_process_chain_resume():
    """A Gate reopened on an existing ledger file must continue the
    same hash chain (not restart at ZERO_HASH) and must still reject
    replayed verification_ids. Regression case: the first live run
    (2026-11-11) produced a chain broken at index 1 because __init__
    never loaded the file it appended to."""
    EXPECTED = (G.PASS, None)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "ledger.jsonl")
        g1 = G.Gate(G.TestSigner(b"gate-test-key"), ledger_path=path)
        r1 = run(g1, pair(), "00000000-0000-4000-8000-000000000015")
        assert (r1["outcome"], r1["reason"]) == EXPECTED, r1["outcome"]
        g2 = G.Gate(G.TestSigner(b"gate-test-key"), ledger_path=path)
        try:
            run(g2, pair(), "00000000-0000-4000-8000-000000000015")
            raise AssertionError("replayed verification_id accepted "
                                 "across processes")
        except G.ReplayRejected:
            pass
        r2 = run(g2, pair(), "00000000-0000-4000-8000-000000000016")
        assert r2["prev_receipt_hash"] == r1["receipt_hash"], \
            "chain did not resume from the persisted head"
        ok, detail = G.chain_verify_file(
            path, G.TestSigner(b"gate-test-key"))
        assert ok, detail


CASES = [
    ("clean PASS", test_clean_pass),
    ("zero residual, no discriminating control -> REFUSED",
     test_zero_residual_no_discriminating_control),
    ("stale preconditions -> VOID", test_stale_preconditions),
    ("control failure -> REFUSED", test_control_failure),
    ("identical failure modes -> REFUSED", test_identical_failure_modes),
    ("conflict -> VOID, third placement resolves",
     test_conflicting_results_then_third_resolves),
    ("modified evidence after sealing -> FAIL",
     test_modified_evidence_after_sealing),
    ("replay of expired verification -> rejected",
     test_replay_of_expired_verification),
    ("manipulated population counts -> FAIL",
     test_manipulated_population_counts),
    ("missing witness signature -> REFUSED", test_missing_witness_signature),
    ("failed third placement -> stays VOID", test_failed_third_placement),
    ("ledger tamper detection", test_ledger_tamper_detection),
    ("agent vault signer (ephemeral vault)", test_vault_signer_ephemeral),
    ("cross-process chain resume + replay persistence",
     test_cross_process_chain_resume),
]


def main():
    passed = 0
    for name, fn in CASES:
        try:
            fn()
            print("PASS  %s" % name)
            passed += 1
        except Exception as exc:  # noqa: BLE001 — report and continue
            print("FAIL  %s: %s: %s" % (name, type(exc).__name__, exc))
    print("%d/%d cases passed" % (passed, len(CASES)))
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
