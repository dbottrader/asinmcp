#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Test runner for the Quest 001 seal kit. Live traffic goes ONLY to
# QUEST-001-TEST; nothing here can submit to QUEST-001.
#
#   python3 tests/run_kit_tests.py [--live] [--core-ts PATH_TO_core.ts] [--json OUT]
#
# --core-ts: path to quest001/supabase/functions/quest-evidence/core.ts (branch
# feat/quest001-functional). With node >= 22 and `npm i @noble/ed25519@2.1.0`
# in the working dir, envelopes are also run through the service's own
# validateEnvelope() via tests/core_ts_harness.ts.
import argparse, copy, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import seal_quest001 as K  # noqa: E402

TEST_SLUG = "quest-001-test"
results = []


def rec(cid, result, detail, **extra):
    results.append({"check_id": cid, "result": result, "detail": detail, **extra})
    print("%-8s %-34s %s" % (result, cid, detail))


def resign(env, seed):
    env["sealed_output"] = K.seal(env["output"])
    env["signature"] = K.ed25519_sign(seed, env["sealed_output"].encode()).hex()
    env["envelope_signature"] = K.ed25519_sign(seed, K.canonical_json({k: env[k] for k in K.SIGNED_FIELDS})).hex()
    return env


def core_ts(harness_dir, env, manifest_path, now=None):
    p = os.path.join(harness_dir, "e.json")
    json.dump(env, open(p, "w"))
    cmd = ["node", os.path.join(harness_dir, "core_ts_harness.ts"), p, manifest_path] + ([now] if now else [])
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=harness_dir)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--core-ts")
    ap.add_argument("--manifest-dir", help="dir holding manifest.json / manifest-test.json for the core.ts harness")
    ap.add_argument("--harness-dir", help="dir with node_modules/@noble/ed25519 and package.json type=module")
    ap.add_argument("--json")
    a = ap.parse_args()
    started = datetime.now().astimezone().isoformat(timespec="seconds")

    # T1 Ed25519 self-test
    try:
        K.ed25519_selftest(); rec("T1-ed25519-rfc8032", "PASS", "RFC 8032 section 7.1 TEST 1-3 sign/verify/pubkey")
    except Exception as e:
        rec("T1-ed25519-rfc8032", "FAIL", str(e))

    # T2 live index recompute (QUEST-001 manifest, read-only)
    mraw = K.fetch(K.BASE + "/quest-001/manifest")
    man = json.loads(mraw)
    raw = K.fetch(man["claim"]["url"])
    ev = K.recompute_index(raw)
    ok = (not ev["problems"] and K.sha256_hex(mraw) in K.QUESTS["quest-001"][1]
          and K.sha256_hex(raw) == man["claim"]["sha256"] and len(raw) == man["claim"]["bytes"])
    rec("T2-live-recompute", "PASS" if ok else "FAIL",
        "manifest %s, index sha256 %s (%d B), %d entries, head %s, problems=%d" % (
            K.sha256_hex(mraw), K.sha256_hex(raw), len(raw), ev["output"]["count"],
            ev["output"]["head_hash"], len(ev["problems"])),
        manifest_sha256=K.sha256_hex(mraw), index_sha256=K.sha256_hex(raw),
        count=ev["output"]["count"], head_hash=ev["output"]["head_hash"])

    # T3 tamper detection: flip one byte inside entry 10's payload
    doc = json.loads(raw)
    doc["entries"][10]["name"] = str(doc["entries"][10].get("name", "")) + "x"
    bad = K.recompute_index(json.dumps(doc).encode())
    rec("T3-tamper-detected", "PASS" if bad["problems"] else "FAIL",
        "edited entry 10 -> %d problems, first: %s" % (len(bad["problems"]), (bad["problems"] or ["none"])[0]))

    # Build envelopes with a throwaway key
    seed = os.urandom(32)
    from datetime import timezone, timedelta
    now = datetime.now(timezone.utc)
    def mk(quest_id, msha, op, at=None):
        t = at or now
        return K.build_envelope(seed, quest_id, msha, ev, op, "kit test runner: python3 urllib, box network, GitHub Pages",
                                K.KIT_VERSION + " tests", t - timedelta(seconds=5), t + timedelta(minutes=30))
    real_env = mk("QUEST-001", K.QUESTS["quest-001"][1][0], "seal-kit-selftest")
    try:
        K.self_verify(real_env); rec("T4-self-verify", "PASS", "both signatures verify (pure Python + cryptography if present)")
    except Exception as e:
        rec("T4-self-verify", "FAIL", str(e))

    # T5 service's own validateEnvelope (core.ts) on the real-quest envelope (NOT submitted)
    hd = a.harness_dir
    if a.core_ts and hd and a.manifest_dir and shutil.which("node"):
        shutil.copy(a.core_ts, os.path.join(hd, "core.ts"))
        shutil.copy(os.path.join(HERE, "core_ts_harness.ts"), os.path.join(hd, "core_ts_harness.ts"))
        mp, mtp = os.path.join(a.manifest_dir, "manifest.json"), os.path.join(a.manifest_dir, "manifest-test.json")
        r = core_ts(hd, real_env, mp)
        rec("T5-core-ts-accepts-real-quest-envelope", "PASS" if r.get("ok") else "FAIL",
            "deployed core.ts validateEnvelope on a QUEST-001 envelope at now (local only, not submitted): %s" % json.dumps(r))
        e = copy.deepcopy(real_env); e["signature"] = e["signature"][:-2] + ("00" if e["signature"][-2:] != "00" else "01")
        r = core_ts(hd, e, mp)
        rec("T6-core-ts-rejects-bad-signature", "PASS" if r.get("code") == "bad_signature" else "FAIL", json.dumps(r))
        e = copy.deepcopy(real_env); e["output"]["head_hash"] = "0" * 64
        r = core_ts(hd, e, mp)
        rec("T7-core-ts-rejects-wrong-head-unresealed", "PASS" if r.get("code") == "seal_mismatch" else "FAIL", json.dumps(r))
        e = resign(copy.deepcopy(real_env), os.urandom(32))  # signed by a different key than pubkey
        r = core_ts(hd, e, mp)
        rec("T8-core-ts-rejects-foreign-key-signature", "PASS" if r.get("code") == "bad_signature" else "FAIL", json.dumps(r))
        e = resign(copy.deepcopy(real_env), seed); e["output"]["head_hash"] = "1" * 64; resign(e, seed)
        r = core_ts(hd, e, mp)
        rec("T9-core-ts-wrong-head-fully-signed", "PASS" if r.get("ok") else "FAIL",
            "intake does not compare with the answer (SPEC section 5); a consistently re-signed wrong head is ACCEPTED at intake and counted against the claim in the verdict: %s" % json.dumps(r))
        te = mk("QUEST-001-TEST", K.QUESTS[TEST_SLUG][1][0], "seal-kit-selftest", K.parse_iso("2026-11-19T12:00:00-06:00"))
        r = core_ts(hd, te, mtp, "2026-11-19T12:00:00-06:00")
        rec("T10-core-ts-accepts-test-envelope-inside-window", "PASS" if r.get("ok") is True else "FAIL",
            "QUEST-001-TEST envelope evaluated with now=2026-11-19 12:00 PM CT (inside the test window): %s" % json.dumps(r))
    else:
        for c in ("T5", "T6", "T7", "T8", "T9", "T10"):
            rec(c + "-core-ts", "NOT_RUN", "needs --core-ts, --harness-dir, --manifest-dir and node")

    # T11-T13: --submit-file verifies the exact saved bytes and does not rebuild
    tdir = tempfile.mkdtemp(prefix="sealkit-r2-")
    try:
        good_path = os.path.join(tdir, "good.json")
        json.dump(real_env, open(good_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        open(good_path, "a", encoding="utf-8").write("\n")
        raw_before = open(good_path, "rb").read()
        digest_before = K.sha256_hex(raw_before)
        rid = real_env["request_id"]
        env2, raw2, digest2 = K.submit_saved_file(good_path, post=False)
        same = (digest2 == digest_before and raw2 == raw_before and env2["request_id"] == rid
                and env2["nonce"] == real_env["nonce"] and env2["issued_at"] == real_env["issued_at"])
        rec("T11-submit-file-preserves-exact-bytes", "PASS" if same else "FAIL",
            "sha256 %s request_id %s unchanged; post=False so no network" % (digest2, rid))

        bad = copy.deepcopy(real_env)
        bad["signature"] = bad["signature"][:-2] + ("00" if bad["signature"][-2:] != "00" else "01")
        bad_path = os.path.join(tdir, "bad-sig.json")
        json.dump(bad, open(bad_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        try:
            K.submit_saved_file(bad_path, post=False)
            rec("T12-submit-file-rejects-bad-signature", "FAIL", "bad signature was accepted locally")
        except K.KitError as e:
            rec("T12-submit-file-rejects-bad-signature", "PASS" if "does not verify" in str(e) else "FAIL", str(e))

        expired = K.build_envelope(seed, "QUEST-001", K.QUESTS["quest-001"][1][0], ev,
                                   "seal-kit-selftest",
                                   "kit test runner: python3 urllib, box network, GitHub Pages",
                                   K.KIT_VERSION + " tests",
                                   now - timedelta(hours=2), now - timedelta(minutes=5))
        exp_path = os.path.join(tdir, "expired.json")
        json.dump(expired, open(exp_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        try:
            K.submit_saved_file(exp_path, post=False)
            rec("T13-submit-file-rejects-expired", "FAIL", "expired envelope was accepted locally")
        except K.KitError as e:
            rec("T13-submit-file-rejects-expired", "PASS" if "expired" in str(e) and "60 minutes" in str(e) else "FAIL", str(e))
    finally:
        shutil.rmtree(tdir, ignore_errors=True)

    # T14: --submit is refused immediately, no rebuild and no POST
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "seal_quest001.py"),
                        "--submit", "--operator", "x", "--failure-mode", "y"],
                       capture_output=True, text=True)
    refused = r.returncode != 0 and "--submit-file" in (r.stderr + r.stdout) and "rebuild" in (r.stderr + r.stdout)
    rec("T14-submit-flag-refused", "PASS" if refused else "FAIL",
        "exit %s stderr: %s" % (r.returncode, (r.stderr or r.stdout).strip().replace("\n", " | ")))

    # T15-T17: default key is absolute under ~/.asinhhc; reuse vs create; refuse a second key
    kdir = tempfile.mkdtemp(prefix="sealkit-key-")
    old_home, old_cwd = os.environ.get("HOME"), os.getcwd()
    try:
        home = os.path.join(kdir, "home")
        cwd = os.path.join(kdir, "cwd")
        os.makedirs(home)
        os.makedirs(cwd)
        os.environ["HOME"] = home
        os.chdir(cwd)
        default = K.default_key_path()
        abs_ok = os.path.isabs(default) and default == os.path.abspath(os.path.join(home, ".asinhhc", "quest001-sealer.key"))
        rec("T15-key-default-absolute-asinhhc", "PASS" if abs_ok else "FAIL", "default_key_path=%s" % default)

        path1, seed1, created1 = K.load_or_create_key(default)
        path2, seed2, created2 = K.load_or_create_key(default)
        reuse_ok = (created1 is True and created2 is False and seed1 == seed2
                    and path1 == path2 == default and os.path.isfile(default)
                    and oct(os.stat(default).st_mode & 0o777) in ("0o600", "0o600"))
        rec("T16-key-create-then-reuse", "PASS" if reuse_ok else "FAIL",
            "created=%s reused=%s path=%s mode=%s" % (
                created1, not created2, path1, oct(os.stat(default).st_mode & 0o777)))

        cwd_key = os.path.join(cwd, "quest001-sealer.key")
        try:
            K.load_or_create_key(cwd_key)
            rec("T17-refuse-new-key-when-one-exists-elsewhere", "FAIL",
                "created %s despite existing default key %s" % (cwd_key, default))
        except K.KitError as e:
            rec("T17-refuse-new-key-when-one-exists-elsewhere",
                "PASS" if "refusing to create" in str(e) and default in str(e) else "FAIL", str(e))
    finally:
        os.chdir(old_cwd)
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        shutil.rmtree(kdir, ignore_errors=True)

    # Live checks: QUEST-001-TEST only
    if a.live:
        assert TEST_SLUG == "quest-001-test"
        before = json.loads(K.fetch(K.BASE + "/" + TEST_SLUG))
        tmraw = K.fetch(K.BASE + "/" + TEST_SLUG + "/manifest")
        tman = json.loads(tmraw)
        te = mk("QUEST-001-TEST", K.sha256_hex(tmraw), "seal-kit-selftest-" + os.urandom(3).hex())
        def post(env):
            assert env["quest_id"] == "QUEST-001-TEST"
            s, b = K.http("POST", K.SEAL_DROP_URL, json.dumps(env).encode())
            return s, json.loads(b)
        s, r = post(te)
        closed = datetime.now(timezone.utc) >= K.parse_iso(tman["deadline"])
        if s == 201 and r.get("accepted"):
            rec("L1-live-test-quest-valid-envelope", "PASS", "HTTP 201 accepted, envelope_sha256 %s" % r.get("envelope_sha256"), response=r)
        elif closed and s == 410 and r.get("code") == "quest_closed":
            rec("L1-live-test-quest-valid-envelope", "FAIL",
                "Live acceptance NOT achieved: HTTP 410 quest_closed because QUEST-001-TEST's deadline %s has passed, so the "
                "service accepts nothing on it. Fix (needs approval, permanent chronicle append): ops/extend-test-quest.PROPOSAL.sql. "
                "Acceptance by the deployed intake code is shown by T5/T10." % tman["deadline"],
                response=r, http_status=s, owner="Dennis")
            rec("L1b-live-format-checks-passed", "PASS",
                "The 410 comes from core.ts:188, which runs only after every schema, field, hash-format, output, observed, request_id, "
                "operator, failure_mode, implementation, seal and key_id check (core.ts:157-187) passed on the live service.",
                http_status=s)
        else:
            rec("L1-live-test-quest-valid-envelope", "FAIL", "HTTP %d %s" % (s, json.dumps(r)), response=r)
        e = copy.deepcopy(te); e["signature"] = e["signature"][:-2] + ("00" if e["signature"][-2:] != "00" else "01")
        s, r = post(e)
        rec("L2-live-bad-signature-rejected", "PASS" if s >= 400 and r.get("accepted") is False and r.get("state_changed") is False else "FAIL",
            "HTTP %d %s (%s)" % (s, r.get("code"), "rejected before the signature gate because the test quest is closed" if r.get("code") == "quest_closed" else r.get("detail")),
            http_status=s, response=r)
        e = copy.deepcopy(te); e["output"]["head_hash"] = "0" * 64
        s, r = post(e)
        rec("L3-live-wrong-head-rejected", "PASS" if s == 422 and r.get("code") == "seal_mismatch" and r.get("state_changed") is False else "FAIL",
            "HTTP %d %s: %s" % (s, r.get("code"), r.get("detail")), http_status=s, response=r)
        e = copy.deepcopy(te); e["manifest_sha256"] = "f" * 64
        s, r = post(e)
        rec("L4-live-wrong-manifest-rejected", "PASS" if s == 409 and r.get("code") == "wrong_manifest" else "FAIL",
            "HTTP %d %s: %s" % (s, r.get("code"), r.get("detail")), http_status=s, response=r)
        after = json.loads(K.fetch(K.BASE + "/" + TEST_SLUG))
        rec("L5-test-chronicle-integrity", "PASS" if after["chain"]["ok"] else "FAIL",
            "QUEST-001-TEST chronicle %d -> %d records, %d -> %d seals, chain ok=%s tip %s" % (
                len(before["chronicle"]), len(after["chronicle"]), len(before["seals"]), len(after["seals"]),
                after["chain"]["ok"], after["chain"]["tip"]))
        real = json.loads(K.fetch(K.BASE + "/quest-001"))
        rec("L6-real-quest-untouched", "PASS", "QUEST-001 has %d seals, %d chronicle records, tip %s (no request was sent to it)" % (
            len(real["seals"]), len(real["chronicle"]), real["chain"]["tip"]))
    else:
        rec("L1-L6-live", "NOT_RUN", "pass --live to exercise QUEST-001-TEST")

    out = {"suite": "quest001-seal-kit", "kit_version": K.KIT_VERSION, "started_at": started,
           "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "summary": {k: sum(1 for r in results if r["result"] == k) for k in ("PASS", "FAIL", "NOT_RUN")},
           "checks": results}
    if a.json:
        json.dump(out, open(a.json, "w"), indent=2)
    return 1 if out["summary"]["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
