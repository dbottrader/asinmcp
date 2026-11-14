// QUEST seal-drop core: pure logic, no I/O. Shared by index.ts (Deno edge
// function) and the local Node test-suite. Implements QUEST-001-SPEC.md.
// NOTHING in this module (or anywhere in the function) moves HHC.

export type Verify = (pubHex: string, msg: Uint8Array, sigHex: string) => Promise<boolean>;

export const ENVELOPE_SCHEMA = "ASIN-HHC-QUEST-SEAL-1.0";
export const VERDICT_SCHEMA = "ASIN-HHC-QUEST-VERDICT-1.0";
export const ZERO_HASH = "0".repeat(64);
export const SETTLEMENT_STATE = "awaiting_human_authorization";
export const MAX_SKEW_MS = 5 * 60 * 1000;
export const SIGNED_FIELDS = [
  "schema", "quest_id", "manifest_sha256", "request_id", "nonce", "issued_at",
  "expires_at", "key_id", "pubkey", "operator", "failure_mode", "implementation",
  "output", "sealed_output", "observed",
];
const ALL_FIELDS = new Set([...SIGNED_FIELDS, "signature", "envelope_signature"]);

const enc = new TextEncoder();
export const utf8 = (s: string) => enc.encode(s);

export async function sha256Hex(data: Uint8Array | string): Promise<string> {
  const bytes = typeof data === "string" ? utf8(data) : data;
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return [...d].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function hexToBytes(h: string): Uint8Array {
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.slice(2 * i, 2 * i + 2), 16);
  return out;
}

export const isHex = (s: unknown, n: number) =>
  typeof s === "string" && s.length === n && /^[0-9a-f]+$/.test(s);

// Python-compatible key order (code point order) for str keys.
function sortedKeys(o: Record<string, unknown>): string[] {
  return Object.keys(o).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

function dumpScalar(v: unknown): string {
  if (v === null) return "null";
  if (v === true) return "true";
  if (v === false) return "false";
  if (typeof v === "number") {
    if (!Number.isSafeInteger(v)) throw new Error("non-integer number not allowed in canonical form");
    return String(v);
  }
  if (typeof v === "string") {
    if (/[\uD800-\uDFFF]/.test(v.replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, ""))) {
      throw new Error("lone surrogate");
    }
    return JSON.stringify(v);
  }
  throw new Error("unsupported value type");
}

// gate.py canonical_json: sort_keys, separators (",", ":"), ensure_ascii=False.
export function canonicalJson(v: unknown): string {
  if (Array.isArray(v)) return "[" + v.map(canonicalJson).join(",") + "]";
  if (v !== null && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return "{" + sortedKeys(o).map((k) => JSON.stringify(k) + ":" + canonicalJson(o[k])).join(",") + "}";
  }
  return dumpScalar(v);
}

// Python json.dumps(sort_keys=True, ensure_ascii=False) DEFAULT separators.
export function pyDumpsDefault(v: unknown): string {
  if (Array.isArray(v)) return "[" + v.map(pyDumpsDefault).join(", ") + "]";
  if (v !== null && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return "{" + sortedKeys(o).map((k) => JSON.stringify(k) + ": " + pyDumpsDefault(o[k])).join(", ") + "}";
  }
  return dumpScalar(v);
}

export const seal = (v: unknown) => sha256Hex(canonicalJson(v));

export function normName(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, "");
}

// ---------------------------------------------------------------- evidence
export interface Evidence {
  output: { count: number; head_hash: string };
  sealed_output: string;
  observed: { claim_sha256: string; claim_bytes: number; first_entry_seal: string };
  consistent_with_declared: boolean;
  problems: string[];
}

export async function computeEvidence(raw: Uint8Array): Promise<Evidence> {
  const doc = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
  const entries = doc?.entries;
  if (!Array.isArray(entries) || entries.length === 0) throw new Error(".entries null/empty/not array");
  let prev = doc?.ledger_anchor?.tip_hash;
  if (!isHex(prev, 64)) throw new Error(".ledger_anchor.tip_hash missing");
  const problems: string[] = [];
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e === null || typeof e !== "object" || Array.isArray(e)) throw new Error("non-object entry");
    if (e.prev_index_hash !== prev) problems.push(`entry ${i}: prev_index_hash does not link`);
    const c: Record<string, unknown> = {};
    for (const k of Object.keys(e)) if (k !== "index_hash") c[k] = e[k];
    const h = await sha256Hex(pyDumpsDefault(c));
    if (h !== e.index_hash) problems.push(`entry ${i}: index_hash does not recompute`);
    prev = h;
  }
  const output = { count: entries.length, head_hash: prev as string };
  if (doc.entry_count !== output.count) problems.push("declared entry_count != counted");
  if (doc.head_hash !== output.head_hash) problems.push("declared head_hash != recomputed head");
  return {
    output,
    sealed_output: await seal(output),
    observed: {
      claim_sha256: await sha256Hex(raw),
      claim_bytes: raw.length,
      first_entry_seal: await seal(entries[0]),
    },
    consistent_with_declared: problems.length === 0,
    problems,
  };
}

// ---------------------------------------------------------------- intake
export interface QuestRow {
  quest_id: string;
  manifest: any;          // parsed manifest
  manifest_sha256: string;
  valid_from: string;     // ISO
  deadline: string;       // ISO
  is_test: boolean;
}

export interface Rejection { ok: false; status: number; code: string; detail: string }
export interface Acceptance { ok: true; env: any; operator_norm: string; failure_mode_norm: string }

const rej = (status: number, code: string, detail: string): Rejection => ({ ok: false, status, code, detail });

function parseTs(s: unknown): number | null {
  if (typeof s !== "string") return null;
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)$/.test(s)) return null;
  const t = Date.parse(s);
  return Number.isNaN(t) ? null : t;
}

const okText = (s: unknown, max: number) =>
  typeof s === "string" && s.trim().length > 0 && s.length <= max && !/[\u0000-\u001f\u007f]/.test(s);

/** Stateless validation. Uniqueness (nonce / key / operator / request_id)
 * is enforced atomically by the database insert. */
export async function validateEnvelope(
  env: any, quest: QuestRow | null, nowMs: number, verify: Verify,
): Promise<Acceptance | Rejection> {
  if (env === null || typeof env !== "object" || Array.isArray(env)) return rej(400, "bad_json", "envelope must be a JSON object");
  for (const k of ALL_FIELDS) if (!(k in env)) return rej(400, "missing_field", k);
  for (const k of Object.keys(env)) if (!ALL_FIELDS.has(k)) return rej(400, "unknown_field", k);
  if (env.schema !== ENVELOPE_SCHEMA) return rej(400, "bad_schema", `schema must be ${ENVELOPE_SCHEMA}`);
  if (!quest) return rej(404, "unknown_quest", String(env.quest_id));
  if (env.quest_id !== quest.quest_id) return rej(404, "unknown_quest", String(env.quest_id));
  if (!isHex(env.manifest_sha256, 64)) return rej(422, "bad_hash_format", "manifest_sha256 must be 64 lowercase hex");
  if (env.manifest_sha256 !== quest.manifest_sha256) return rej(409, "wrong_manifest", "manifest_sha256 does not match the current manifest");
  for (const [k, n] of [["pubkey", 64], ["key_id", 64], ["nonce", 64], ["sealed_output", 64], ["signature", 128], ["envelope_signature", 128]] as const) {
    if (!isHex(env[k], n)) return rej(422, "bad_hash_format", `${k} must be ${n} lowercase hex`);
  }
  const out = env.output;
  if (out === null || typeof out !== "object" || Array.isArray(out) ||
      Object.keys(out).sort().join(",") !== "count,head_hash") return rej(422, "bad_output", "output must be exactly {count, head_hash}");
  if (!Number.isSafeInteger(out.count) || out.count < 0) return rej(422, "bad_output", "count must be a non-negative integer");
  if (!isHex(out.head_hash, 64)) return rej(422, "bad_hash_format", "output.head_hash must be 64 lowercase hex");
  const ob = env.observed;
  if (ob === null || typeof ob !== "object" || Array.isArray(ob) ||
      Object.keys(ob).sort().join(",") !== "claim_bytes,claim_sha256,first_entry_seal") return rej(422, "bad_observed", "observed must be exactly {claim_sha256, claim_bytes, first_entry_seal}");
  if (!isHex(ob.claim_sha256, 64) || !isHex(ob.first_entry_seal, 64)) return rej(422, "bad_hash_format", "observed hashes must be 64 lowercase hex");
  if (!Number.isSafeInteger(ob.claim_bytes)) return rej(422, "bad_observed", "claim_bytes must be an integer");
  if (typeof env.request_id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(env.request_id)) return rej(422, "bad_request_id", "request_id must be a lowercase UUID");
  if (!okText(env.operator, 80)) return rej(422, "bad_operator", "operator must be 1-80 printable chars");
  if (!okText(env.failure_mode, 400)) return rej(422, "bad_failure_mode", "failure_mode must be 1-400 printable chars");
  if (!okText(env.implementation, 400)) return rej(422, "bad_implementation", "implementation must be 1-400 printable chars");
  if (await seal(out) !== env.sealed_output) return rej(422, "seal_mismatch", "sealed_output != sha256(canonical_json(output))");
  if (await sha256Hex(hexToBytes(env.pubkey)) !== env.key_id) return rej(422, "bad_key_id", "key_id must be sha256 of the 32 raw pubkey bytes");

  const issued = parseTs(env.issued_at), expires = parseTs(env.expires_at);
  if (issued === null || expires === null) return rej(422, "bad_timestamp", "issued_at/expires_at must be ISO-8601 with offset");
  const validFrom = Date.parse(quest.valid_from), deadline = Date.parse(quest.deadline);
  if (nowMs > deadline) return rej(410, "quest_closed", `deadline ${quest.deadline} has passed`);
  if (issued > nowMs + MAX_SKEW_MS) return rej(422, "issued_in_future", "issued_at is more than 5 minutes in the future");
  if (issued < validFrom) return rej(422, "issued_before_window", `issued_at precedes manifest valid_from ${quest.valid_from}`);
  if (expires <= issued) return rej(422, "bad_window", "expires_at must be after issued_at");
  if (expires <= nowMs) return rej(422, "expired", "envelope expires_at has passed");
  if (expires > deadline) return rej(422, "bad_window", "expires_at is after the quest deadline");

  const opNorm = normName(env.operator);
  const inel: string[] = (quest.manifest?.independence?.ineligible_operators ?? []).map(normName);
  if (!opNorm || inel.includes(opNorm)) return rej(422, "operator_ineligible", "coordinator/publisher operators cannot witness this quest");

  if (!(await verify(env.pubkey, utf8(env.sealed_output), env.signature))) return rej(422, "bad_signature", "signature does not verify over the sealed_output hex string");
  const signed: Record<string, unknown> = {};
  for (const k of SIGNED_FIELDS) signed[k] = env[k];
  let signedBytes: Uint8Array;
  try { signedBytes = utf8(canonicalJson(signed)); } catch (e) { return rej(422, "bad_envelope", String(e)); }
  if (!(await verify(env.pubkey, signedBytes, env.envelope_signature))) return rej(422, "bad_signature", "envelope_signature does not verify over canonical_json(signed fields)");

  return { ok: true, env, operator_norm: opNorm, failure_mode_norm: env.failure_mode.trim().toLowerCase().replace(/\s+/g, " ") };
}

// ---------------------------------------------------------------- chronicle
export interface ChronicleRecord {
  quest_id: string; seq: number; event: string; payload: unknown; prev_hash: string; created_at: string;
}
export const recordHash = (r: ChronicleRecord) =>
  seal({ quest_id: r.quest_id, seq: r.seq, event: r.event, payload: r.payload, prev_hash: r.prev_hash, created_at: r.created_at });

export async function verifyChain(records: (ChronicleRecord & { record_hash: string })[]) {
  const problems: string[] = [];
  let prev = ZERO_HASH;
  const sorted = [...records].sort((a, b) => a.seq - b.seq);
  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    if (r.seq !== i) problems.push(`seq gap at ${i} (found ${r.seq})`);
    if (r.prev_hash !== prev) problems.push(`seq ${r.seq}: prev_hash does not link`);
    const h = await recordHash(r);
    if (h !== r.record_hash) problems.push(`seq ${r.seq}: record_hash does not recompute`);
    prev = r.record_hash;
  }
  return { ok: problems.length === 0, length: sorted.length, tip: prev, problems };
}

// ---------------------------------------------------------------- verdict
export interface Reexec { ok: boolean; reason?: string; claim_sha256?: string; sealed_output?: string; output?: unknown }

/** Deterministic verdict over stored envelopes (in chronicle order) and the
 * service's own re-execution of the claim. Never pays. */
export async function computeVerdict(quest: QuestRow, envelopes: any[], reexec: Reexec, verify: Verify) {
  const per: any[] = [];
  const valid: any[] = [];
  for (const env of envelopes) {
    const signed: Record<string, unknown> = {};
    for (const k of SIGNED_FIELDS) signed[k] = env[k];
    const ok = (await seal(env.output)) === env.sealed_output &&
      (await verify(env.pubkey, utf8(env.sealed_output), env.signature)) &&
      (await verify(env.pubkey, utf8(canonicalJson(signed)), env.envelope_signature));
    const rec = {
      operator: env.operator, key_id: env.key_id, failure_mode: env.failure_mode,
      sealed_output: env.sealed_output, signatures_valid: ok,
      matches_reexecution: reexec.ok ? env.sealed_output === reexec.sealed_output : null,
    };
    per.push(rec);
    if (ok) valid.push({ env, rec });
  }
  if (valid.length < 2) for (const r of per) r.matches_reexecution = null; // no answer oracle before quorum
  const indep = (a: any, b: any) =>
    normName(a.env.operator) !== normName(b.env.operator) && a.env.pubkey !== b.env.pubkey &&
    a.env.failure_mode.trim().toLowerCase().replace(/\s+/g, " ") !== b.env.failure_mode.trim().toLowerCase().replace(/\s+/g, " ");

  let verdict = "HOLD", reason = "INSUFFICIENT_VALID_WITNESSES", pair: any[] | null = null;
  if (!reexec.ok) {
    verdict = "HOLD"; reason = reexec.reason ?? "REEXECUTION_UNAVAILABLE";
  } else if (valid.length >= 2) {
    const agree = valid.filter((v) => v.env.sealed_output === reexec.sealed_output);
    const disagree = valid.filter((v) => v.env.sealed_output !== reexec.sealed_output);
    const findPair = (xs: any[], ys: any[] = xs) => {
      for (let i = 0; i < xs.length; i++) for (let j = 0; j < ys.length; j++) {
        if (xs[i] !== ys[j] && indep(xs[i], ys[j])) return [xs[i], ys[j]];
      }
      return null;
    };
    const passPair = findPair(agree);
    const conflict = findPair(agree, disagree);
    const failPair = (() => {
      for (let i = 0; i < disagree.length; i++) for (let j = i + 1; j < disagree.length; j++) {
        if (disagree[i].env.sealed_output === disagree[j].env.sealed_output && indep(disagree[i], disagree[j])) return [disagree[i], disagree[j]];
      }
      return null;
    })();
    if (passPair && !conflict) { verdict = "PASS"; reason = "TWO_INDEPENDENT_MATCHING_SEALS"; pair = passPair; }
    else if (conflict) { verdict = "VOID"; reason = "WITNESS_CONFLICT"; }
    else if (failPair) { verdict = "FAIL"; reason = "INDEPENDENT_WITNESSES_REPRODUCE_DIFFERENT_RESULT"; }
    else { verdict = "HOLD"; reason = "NO_INDEPENDENT_PAIR"; }
  }
  const reward = quest.manifest?.reward ?? null;
  const payout_plan = verdict === "PASS" && reward && pair
    ? pair.map((p, i) => ({ role: i === 0 ? "alpha" : "beta", operator: p.env.operator, key_id: p.env.key_id, hhc: reward.per_verifier_hhc }))
    : [];
  const body = {
    schema: VERDICT_SCHEMA,
    quest_id: quest.quest_id,
    manifest_sha256: quest.manifest_sha256,
    is_test: quest.is_test,
    verdict, reason,
    // The service's own expected seal is withheld until two valid seals exist,
    // so it cannot serve as an answer key for witnesses.
    reexecution: !reexec.ok ? { error: reexec.reason }
      : valid.length >= 2 ? { claim_sha256: reexec.claim_sha256, sealed_output: reexec.sealed_output }
      : { claim_sha256: reexec.claim_sha256, sealed_output_withheld: true },
    seals_considered: per.length,
    seals_valid: valid.length,
    seals: per,
    payout_plan,
    settlement_state: SETTLEMENT_STATE,
    automatic_payment: false,
  };
  return { ...body, verdict_hash: await seal(body) };
}
