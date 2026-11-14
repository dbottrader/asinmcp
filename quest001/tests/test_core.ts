// Node >= 22 (type stripping) test-suite for supabase/functions/quest-evidence/core.ts.
// Run from quest001/:  npm i --no-save @noble/ed25519@2.1.0 && node tests/test_core.ts
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import * as ed from "@noble/ed25519";
import {
  canonicalJson, computeEvidence, computeVerdict, hexToBytes, recordHash, seal, sha256Hex,
  validateEnvelope, verifyChain, ZERO_HASH, type QuestRow, type Verify,
} from "../supabase/functions/quest-evidence/core.ts";

const Q = new URL("..", import.meta.url).pathname;
const verify: Verify = async (p, m, s) => { try { return await ed.verifyAsync(hexToBytes(s), m, hexToBytes(p)); } catch { return false; } };
const mtext = readFileSync(Q + "manifest-test.json");
const manifest = JSON.parse(mtext.toString("utf-8"));
const quest: QuestRow = {
  quest_id: manifest.quest_id, manifest, manifest_sha256: await sha256Hex(new Uint8Array(mtext)),
  valid_from: manifest.valid_from, deadline: manifest.deadline, is_test: true,
};
const NOW = Date.parse("2026-11-15T12:00:00Z");
let n = 0;
const t = async (name: string, f: () => Promise<void> | void) => { await f(); n++; console.log("ok -", name); };

// Python builds envelopes so this also proves cross-language interop.
function pyEnv(seedTag: string, operator: string, fm: string, fixture = "mini-index.json", extra = "") {
  const code = `
import sys, json, hashlib; sys.path.insert(0, ${JSON.stringify(Q)})
import verify_quest001 as v
from datetime import datetime, timezone
m = json.loads(open(${JSON.stringify(Q + "manifest-test.json")}, "rb").read())
msha = hashlib.sha256(open(${JSON.stringify(Q + "manifest-test.json")}, "rb").read()).hexdigest()
ev = v.compute_evidence(open(${JSON.stringify(Q + "tests/fixtures/")} + ${JSON.stringify(fixture)}, "rb").read())
seed = hashlib.sha256(${JSON.stringify(seedTag)}.encode()).digest()
e = v.build_envelope(seed, m, msha, ev, ${JSON.stringify(operator)}, ${JSON.stringify(fm)}, "py-ref", now=datetime(2026,11,15,11,0,tzinfo=timezone.utc))
${extra}
print(json.dumps(e, ensure_ascii=False))`;
  return JSON.parse(execFileSync("python3", ["-c", code]).toString("utf-8"));
}

await t("canonicalJson matches python gate form", async () => {
  const o = { b: [1, "é", null, true], a: { z: "😀", y: "a/b\"\n" } };
  const py = execFileSync("python3", ["-c", `import json,sys;sys.stdout.write(json.dumps(json.loads(sys.argv[1]),sort_keys=True,separators=(",",":"),ensure_ascii=False))`, JSON.stringify(o)]).toString("utf-8");
  assert.equal(canonicalJson(o), py);
  assert.throws(() => canonicalJson({ x: 1.5 }));
});

await t("computeEvidence == python pins (fixtures + live repo copy)", async () => {
  const exp = JSON.parse(readFileSync(Q + "tests/fixtures/expected.json", "utf-8"));
  for (const [name, e] of Object.entries<any>(exp)) {
    const ev = await computeEvidence(new Uint8Array(readFileSync(Q + "tests/fixtures/" + name)));
    assert.deepEqual(ev.output, e.output, name);
    assert.equal(ev.sealed_output, e.sealed_output, name);
    assert.equal(ev.observed.first_entry_seal, e.first_entry_seal, name);
    assert.equal(ev.consistent_with_declared, e.consistent_with_declared, name);
  }
  const live = new Uint8Array(readFileSync(Q + "../artifacts/specs/provenance-index.json"));
  if (await sha256Hex(live) === "a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e") {
    const ev = await computeEvidence(live);
    assert.equal(ev.output.count, 78);
    assert.equal(ev.output.head_hash, "fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6");
    assert.equal(ev.observed.first_entry_seal, "c1bb3019aa5187d91e028f5a734f992a2bfd222dbff07158e9af3d4cfa8563ca");
  }
});

const good = pyEnv("seed-a", "op-a", "fm-a");
await t("python envelope accepted", async () => {
  const r = await validateEnvelope(good, quest, NOW, verify);
  assert.equal(r.ok, true, JSON.stringify(r));
});

const cases: [string, (e: any) => any, string, QuestRow | null, number?][] = [
  ["bad signature", (e) => ({ ...e, signature: e.signature.slice(0, -2) + (e.signature.endsWith("00") ? "11" : "00") }), "bad_signature", quest],
  ["bad envelope signature (nonce swapped)", (e) => ({ ...e, nonce: "a".repeat(64) }), "bad_signature", quest],
  ["wrong manifest", (e) => ({ ...e, manifest_sha256: "b".repeat(64) }), "wrong_manifest", quest],
  ["short hash", (e) => ({ ...e, output: { ...e.output, head_hash: e.output.head_hash.slice(0, 16) } }), "bad_hash_format", quest],
  ["uppercase hash", (e) => ({ ...e, sealed_output: e.sealed_output.toUpperCase() }), "bad_hash_format", quest],
  ["seal mismatch", (e) => ({ ...e, output: { ...e.output, count: 99 } }), "seal_mismatch", quest],
  ["unknown quest", (e) => ({ ...e }), "unknown_quest", null],
  ["extra field", (e) => ({ ...e, extra: 1 }), "unknown_field", quest],
  ["missing field", (e) => { const x = { ...e }; delete x.nonce; return x; }, "missing_field", quest],
  ["bad key_id", (e) => ({ ...e, key_id: "c".repeat(64) }), "bad_key_id", quest],
  ["expired", (e) => e, "expired", quest, Date.parse("2026-11-16T12:00:01Z")],
  ["issued in future", (e) => e, "issued_in_future", quest, Date.parse("2026-11-15T10:50:00Z")],
  ["quest closed", (e) => e, "quest_closed", quest, Date.parse("2026-11-20T06:00:00Z")],
];
for (const [name, mut, code, q, now] of cases) {
  await t(`reject: ${name}`, async () => {
    const r: any = await validateEnvelope(mut(structuredClone(good)), q, now ?? NOW, verify);
    assert.equal(r.ok, false); assert.equal(r.code, code, JSON.stringify(r));
  });
}
await t("reject: ineligible operator (normalized)", async () => {
  const e = pyEnv("seed-x", "Ineligible Probe", "fm-x");
  const r: any = await validateEnvelope(e, quest, NOW, verify);
  assert.equal(r.code, "operator_ineligible"); assert.equal(r.status, 422);
});
await t("reject: expires after deadline / before issued", async () => {
  const e = pyEnv("seed-y", "op-y", "fm-y", "mini-index.json", `e["expires_at"]="2026-11-21T00:00:00Z"; e["envelope_signature"]=v.ed_sign(seed, v.envelope_signing_bytes(e))`);
  const r: any = await validateEnvelope(e, quest, NOW, verify);
  assert.equal(r.code, "bad_window");
});

// ---- verdict
const realEv = await computeEvidence(new Uint8Array(readFileSync(Q + "tests/fixtures/mini-index.json")));
const reexec = { ok: true, claim_sha256: realEv.observed.claim_sha256, sealed_output: realEv.sealed_output };
const b = pyEnv("seed-b", "op-b", "fm-b");
const sameOp = pyEnv("seed-c", "OP-A", "fm-c");
const sameFm = pyEnv("seed-d", "op-d", "FM-A");
const wrong1 = pyEnv("seed-e", "op-e", "fm-e", "tampered-index.json");
const wrong2 = pyEnv("seed-f", "op-f", "fm-f", "tampered-index.json");

await t("verdict HOLD with <2 seals", async () => {
  const v = await computeVerdict(quest, [good], reexec, verify);
  assert.equal(v.verdict, "HOLD"); assert.equal(v.reason, "INSUFFICIENT_VALID_WITNESSES");
  assert.equal(v.settlement_state, "awaiting_human_authorization"); assert.equal(v.automatic_payment, false);
});
await t("verdict HOLD when pair not independent (same operator / same failure_mode)", async () => {
  assert.equal((await computeVerdict(quest, [good, sameOp], reexec, verify)).reason, "NO_INDEPENDENT_PAIR");
  assert.equal((await computeVerdict(quest, [good, sameFm], reexec, verify)).reason, "NO_INDEPENDENT_PAIR");
});
await t("verdict PASS with two independent matching seals; payout plan 5+5 but never paid", async () => {
  const q2 = { ...quest, manifest: { ...manifest, reward: { per_verifier_hhc: 5 } } };
  const v = await computeVerdict(q2, [good, b], reexec, verify);
  assert.equal(v.verdict, "PASS");
  assert.deepEqual(v.payout_plan.map((p: any) => [p.role, p.operator, p.hhc]), [["alpha", "op-a", 5], ["beta", "op-b", 5]]);
  assert.equal(v.settlement_state, "awaiting_human_authorization"); assert.equal(v.automatic_payment, false);
  const again = await computeVerdict(q2, [good, b], reexec, verify);
  assert.equal(again.verdict_hash, v.verdict_hash);
});
await t("verdict VOID on conflict, FAIL when independent pair reproduces a different result", async () => {
  assert.equal((await computeVerdict(quest, [good, b, wrong1], reexec, verify)).verdict, "VOID");
  assert.equal((await computeVerdict(quest, [wrong1, wrong2], reexec, verify)).verdict, "FAIL");
});
await t("verdict ignores seals whose signature no longer verifies", async () => {
  const bad = { ...b, envelope_signature: "0".repeat(128) };
  const v = await computeVerdict(quest, [good, bad], reexec, verify);
  assert.equal(v.verdict, "HOLD"); assert.equal(v.seals_valid, 1);
});
await t("verdict HOLD when re-execution unavailable", async () => {
  const v = await computeVerdict(quest, [good, b], { ok: false, reason: "CLAIM_CHANGED_SINCE_MANIFEST" }, verify);
  assert.equal(v.verdict, "HOLD"); assert.equal(v.reason, "CLAIM_CHANGED_SINCE_MANIFEST");
});

// ---- chronicle
await t("chronicle chain verifies and detects tampering", async () => {
  const recs: any[] = [];
  let prev = ZERO_HASH;
  for (let i = 0; i < 3; i++) {
    const r = { quest_id: "Q", seq: i, event: "e", payload: { i }, prev_hash: prev, created_at: `2026-11-14T00:00:0${i}.000Z` };
    const h = await recordHash(r); recs.push({ ...r, record_hash: h }); prev = h;
  }
  assert.equal((await verifyChain(recs)).ok, true);
  recs[1].payload = { i: 42 };
  assert.equal((await verifyChain(recs)).ok, false);
});

console.log(`\n${n} tests passed`);
