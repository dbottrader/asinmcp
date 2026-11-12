"""End-to-end demo of the refusal-aware verification gate.

Builds an EPHEMERAL Agent Vault in a temp dir (the live vault at
~/workspace/agent-vault/live/ is never touched), then runs four
attempts against it and prints every receipt:

  1. PASS    — honest witnesses, counts match, control passes
  2. FAIL    — manipulated population counts (residual != 0)
  3. VOID    — independent witnesses conflict, resolved to PASS by an
               independent third placement (two receipts)
  4. REFUSED — zero residual but no discriminating control exists

Finishes with a chain verification of all emitted receipts.

Run: python3 demo_gate.py
"""

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
BASE = dict(test_id="population-count-check", test_version="1.0",
            population_id="pop-main", solver=None)  # solver set below


def solver(params):
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


def show(title, receipt):
    print("=" * 72)
    print(title, "->", receipt["outcome"],
          ("(%s)" % receipt["reason"]) if receipt["reason"] else "")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print()


def main():
    vault_py = os.path.expanduser("~/workspace/agent-vault/vault.py")
    os.environ["AGENT_VAULT_SECRET"] = "gate-demo-ephemeral-secret"
    with tempfile.TemporaryDirectory() as td:
        vdir = os.path.join(td, "vault")
        proc = subprocess.run([sys.executable, vault_py, "init",
                               "--dir", vdir], capture_output=True,
                              text=True, env=dict(os.environ))
        if proc.returncode != 0:
            print("vault init failed:", proc.stderr[-400:])
            return 1
        signer = G.VaultSigner(vdir)
        ledger = os.path.join(td, "gate-receipts.jsonl")
        g = G.Gate(signer, ledger_path=ledger)
        kw = dict(BASE, solver=solver, job_params=JOB, now=NOW,
                  preconditions=FRESH, stored_count=100)

        # 1. PASS
        r = g.attempt(retrieve_served=lambda: 100,
                      witnesses=[agree("w-alpha", "op-alpha",
                                       "sampling-drift", 11),
                                 agree("w-beta", "op-beta",
                                       "hardware-bitflip", 22)],
                      control=GOOD_CONTROL,
                      verification_id="demo-00000001-pass", **kw)
        show("1. clean verification", r)

        # 2. FAIL — served count does not match the stored claim
        r = g.attempt(retrieve_served=lambda: 97,
                      witnesses=[agree("w-alpha", "op-alpha",
                                       "sampling-drift", 11),
                                 agree("w-beta", "op-beta",
                                       "hardware-bitflip", 22)],
                      control=GOOD_CONTROL,
                      verification_id="demo-00000002-fail", **kw)
        show("2. manipulated population counts", r)

        # 3. VOID — witnesses conflict; third placement resolves to PASS
        r = g.attempt(retrieve_served=lambda: 100,
                      witnesses=[agree("w-alpha", "op-alpha",
                                       "sampling-drift", 11),
                                 disagree("w-beta", "op-beta",
                                          "hardware-bitflip", 22)],
                      control=GOOD_CONTROL,
                      verification_id="demo-00000003-void", **kw)
        show("3a. conflicting independent witnesses", r)
        r = g.resolve("demo-00000003-void",
                      agree("w-gamma", "op-gamma", "network-partition",
                            33), NOW)
        show("3b. third placement resolves 2-of-3", r)

        # 4. REFUSED — counts match but nothing can discriminate the claim
        r = g.attempt(retrieve_served=lambda: 100,
                      witnesses=[agree("w-alpha", "op-alpha",
                                       "sampling-drift", 11),
                                 agree("w-beta", "op-beta",
                                       "hardware-bitflip", 22)],
                      control=None,
                      verification_id="demo-00000004-refused", **kw)
        show("4. no discriminating control", r)

        ok, detail = G.chain_verify_file(ledger, signer=signer)
        print("=" * 72)
        print("Chain verify (file, hashes + vault signatures):", detail
              if ok else "FAILED — " + detail)
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
