#!/usr/bin/env python3
"""Unit tests for the QUEST-001 reference verifiers. Offline except the
optional live test (set QUEST001_LIVE=1)."""
import hashlib, json, os, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
Q = os.path.dirname(HERE)
REPO = os.path.dirname(Q)
FX = os.path.join(HERE, "fixtures")
sys.path.insert(0, Q)
import verify_quest001 as v  # noqa: E402

EXP = json.load(open(os.path.join(FX, "expected.json")))
SH = os.path.join(Q, "verify_quest001.sh")
LIVE_INDEX = os.path.join(REPO, "artifacts", "specs", "provenance-index.json")
LIVE_PINS = {  # verified 2026-11-14 15:05Z against the GitHub Pages copy
    "claim_sha256": "a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e",
    "count": 78,
    "head_hash": "fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6",
    "first_entry_seal": "c1bb3019aa5187d91e028f5a734f992a2bfd222dbff07158e9af3d4cfa8563ca",
    "first_entry_seal_jq_r_WRONG": "1c26576b7effb0a72f09de1e58bee4943ed0410292f0569d1eafcbd82ff653ea",
}


def raw(name):
    return open(os.path.join(FX, name), "rb").read()


def run_sh(path, *extra):
    p = subprocess.run(["bash", SH, path, *extra], capture_output=True, text=True)
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None), p.stderr


class Canonical(unittest.TestCase):
    def test_no_trailing_newline_and_compact(self):
        b = v.canonical_json({"b": 1, "a": "é"})
        self.assertEqual(b, '{"a":"é","b":1}'.encode())
        self.assertFalse(b.endswith(b"\n"))

    def test_matches_gate_py(self):
        sys.path.insert(0, os.path.join(REPO, "verifier-bot"))
        sys.path.insert(0, REPO)
        try:
            import gate  # noqa
        except Exception as e:  # gate imports ed25519 from ~/workspace/asinmcp
            self.skipTest(f"gate.py not importable here: {e}")
        for o in ({"count": 78, "head_hash": "ab" * 32}, {"x": ["é", None, True]}):
            self.assertEqual(v.seal(o), gate.seal(o))


class Fixtures(unittest.TestCase):
    def test_python_matches_pins(self):
        for name, e in EXP.items():
            ev = v.compute_evidence(raw(name))
            self.assertEqual(ev["output"], e["output"], name)
            self.assertEqual(ev["sealed_output"], e["sealed_output"], name)
            self.assertEqual(ev["observed"]["first_entry_seal"], e["first_entry_seal"], name)
            self.assertEqual(ev["consistent_with_declared"], e["consistent_with_declared"], name)

    def test_jq_r_pitfall_is_a_different_digest(self):
        for name, e in EXP.items():
            self.assertNotEqual(e["first_entry_seal"], e["first_entry_seal_jq_r_WRONG"])
            self.assertNotEqual(e["sealed_output"], e["sealed_output_with_trailing_lf_WRONG"])

    def test_jq_r_vs_j_real_tools(self):
        for name, e in EXP.items():
            p = os.path.join(FX, name)
            j = subprocess.run(["jq", "-j", "-c", "-S", ".entries[0]", p], capture_output=True).stdout
            r = subprocess.run(["jq", "-r", "-c", "-S", ".entries[0]", p], capture_output=True).stdout
            self.assertEqual(hashlib.sha256(j).hexdigest(), e["first_entry_seal"], name)
            self.assertEqual(hashlib.sha256(r).hexdigest(), e["first_entry_seal_jq_r_WRONG"], name)

    def test_tampered_detected(self):
        ev = v.compute_evidence(raw("tampered-index.json"))
        self.assertFalse(ev["consistent_with_declared"])
        self.assertTrue(any("index_hash" in p for p in ev["problems"]))

    def test_null_and_empty_entries_rejected(self):
        for n in ("null-entries.json", "empty-entries.json"):
            with self.assertRaises(v.ClaimError):
                v.compute_evidence(raw(n))


class ShellAgreesWithPython(unittest.TestCase):
    def test_fixtures(self):
        for name, e in EXP.items():
            rc, out, err = run_sh(os.path.join(FX, name))
            self.assertEqual(rc, 0 if e["consistent_with_declared"] else 2, err)
            self.assertEqual(out["output"], e["output"], name)
            self.assertEqual(out["sealed_output"], e["sealed_output"], name)
            self.assertEqual(out["observed"]["first_entry_seal"], e["first_entry_seal"], name)
            self.assertEqual(out["observed"]["claim_sha256"], e["claim_sha256"], name)

    def test_null_entries_shell(self):
        for n in ("null-entries.json", "empty-entries.json"):
            rc, out, err = run_sh(os.path.join(FX, n))
            self.assertEqual(rc, 3, n)
            self.assertIn(".entries", err)

    def test_changed_claim_refused(self):
        rc, out, err = run_sh(os.path.join(FX, "mini-index.json"), "0" * 64, "1")
        self.assertEqual(rc, 3)
        self.assertIn("claim changed", err)

    def test_repo_copy_of_live_index(self):
        b = open(LIVE_INDEX, "rb").read()
        if hashlib.sha256(b).hexdigest() != LIVE_PINS["claim_sha256"]:
            self.skipTest("repo copy of the index changed since pins")
        ev = v.compute_evidence(b)
        rc, out, err = run_sh(LIVE_INDEX, LIVE_PINS["claim_sha256"], str(len(b)))
        self.assertEqual(rc, 0, err)
        for got in (ev, out):
            self.assertEqual(got["output"], {"count": LIVE_PINS["count"], "head_hash": LIVE_PINS["head_hash"]})
            self.assertEqual(got["observed"]["first_entry_seal"], LIVE_PINS["first_entry_seal"])
        self.assertEqual(ev["sealed_output"], out["sealed_output"])
        first = v.canonical_json(json.loads(b)["entries"][0])
        self.assertEqual(hashlib.sha256(first + b"\n").hexdigest(), LIVE_PINS["first_entry_seal_jq_r_WRONG"])


class Envelope(unittest.TestCase):
    def setUp(self):
        self.m = json.loads(open(os.path.join(Q, "manifest-test.json"), "rb").read())
        self.msha = hashlib.sha256(open(os.path.join(Q, "manifest-test.json"), "rb").read()).hexdigest()
        self.seed = hashlib.sha256(b"unit-test-seed").digest()
        self.ev = v.compute_evidence(raw("mini-index.json"))
        self.now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)

    def env(self, **kw):
        return v.build_envelope(self.seed, self.m, self.msha, self.ev, "op-a", "fm-a", "impl", now=self.now, **kw)

    def test_roundtrip(self):
        e = self.env()
        self.assertEqual(v.check_envelope(e), [])
        self.assertEqual(e["key_id"], hashlib.sha256(bytes.fromhex(e["pubkey"])).hexdigest())
        self.assertEqual(len(e["nonce"]), 64)

    def test_expires_clamped_to_deadline(self):
        e = v.build_envelope(self.seed, self.m, self.msha, self.ev, "a", "b", "c",
                             ttl_hours=1000, now=self.now)
        self.assertEqual(v.parse_iso(e["expires_at"]), v.parse_iso(self.m["deadline"]))

    def test_tamper_output(self):
        e = self.env()
        e["output"] = dict(e["output"], count=3)
        self.assertIn("sealed_output != sha256(canonical_json(output))", v.check_envelope(e))

    def test_tamper_nonce_breaks_envelope_signature(self):
        e = self.env()
        e["nonce"] = "f" * 64
        self.assertEqual(v.check_envelope(e), ["envelope_signature invalid"])

    def test_vendored_ed25519_interop(self):
        sys.path.insert(0, REPO)
        import ed25519
        e = self.env()
        self.assertTrue(ed25519.verify(e["pubkey"], e["sealed_output"].encode(), e["signature"]))
        self.assertEqual(ed25519.pubkey_from_seed(self.seed).hex(), e["pubkey"])


class Manifest(unittest.TestCase):
    def test_manifests(self):
        for name in ("manifest.json", "manifest-test.json"):
            b = open(os.path.join(Q, name), "rb").read()
            self.assertFalse(b.endswith(b"\n"), "manifest bytes must have no trailing LF")
            m = json.loads(b)
            self.assertEqual(m["deadline_epoch"], int(v.parse_iso(m["deadline"]).timestamp()))
            self.assertEqual(v.parse_iso(m["deadline_utc"]), v.parse_iso(m["deadline"]))
            self.assertEqual(m["spec"]["sha256"], hashlib.sha256(open(os.path.join(Q, "QUEST-001-SPEC.md"), "rb").read()).hexdigest())
            self.assertFalse(m["settlement"]["automatic_payment"])
            self.assertNotIn("demo.asin-hhc.com", b.decode())
            self.assertNotIn("UNDECIDED", b.decode())
        m = json.loads(open(os.path.join(Q, "manifest.json"), "rb").read())
        self.assertEqual((m["reward"]["total_hhc"], m["reward"]["per_verifier_hhc"], m["reward"]["split"]), (10, 5, "50/50"))
        self.assertIn("grokace", m["independence"]["ineligible_operators"])


@unittest.skipUnless(os.environ.get("QUEST001_LIVE"), "set QUEST001_LIVE=1 for network test")
class Live(unittest.TestCase):
    def test_live_both_tools_agree(self):
        m = json.loads(open(os.path.join(Q, "manifest.json"), "rb").read())
        ev = v.evidence_for_manifest(m)
        rc, out, err = run_sh(m["claim"]["url"], m["claim"]["sha256"], str(m["claim"]["bytes"]))
        self.assertEqual(rc, 0, err)
        self.assertEqual(ev["sealed_output"], out["sealed_output"])
        self.assertEqual(ev["output"], out["output"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
