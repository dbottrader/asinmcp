// quest-evidence — QUEST seal-drop, chronicle, verdict and replay.
// Spec: quest001/QUEST-001-SPEC.md in dbottrader/asinmcp.
// There is NO payment, settlement or escrow-release code in this function.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import * as ed from "npm:@noble/ed25519@2.1.0";
import {
  canonicalJson, computeEvidence, computeVerdict, hexToBytes, recordHash, seal,
  sha256Hex, validateEnvelope, verifyChain, type QuestRow, type Reexec, type Verify,
} from "./core.ts";

const VERSION = "quest-evidence/1.0.0";
const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});

const verify: Verify = async (pub, msg, sig) => {
  try { return await ed.verifyAsync(hexToBytes(sig), msg, hexToBytes(pub)); } catch { return false; }
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body, null, 2), {
    status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });

const slugToQuest = (slug: string) => slug.toUpperCase();

async function loadQuest(questId: string): Promise<(QuestRow & { manifest_text: string }) | null> {
  const { data, error } = await db.from("quest_manifests").select("*").eq("quest_id", questId).maybeSingle();
  if (error) throw new Error(`db: ${error.message}`);
  return data ?? null;
}

async function loadSealsAndChain(questId: string) {
  const [s, c] = await Promise.all([
    db.from("quest_seals").select("id,quest_id,key_id,pubkey,operator,failure_mode,sealed_output,envelope,envelope_sha256,received_at,chronicle_seq,is_test")
      .eq("quest_id", questId).order("chronicle_seq", { ascending: true }),
    db.from("quest_chronicle").select("quest_id,seq,event,payload,prev_hash,record_hash,created_at,is_test")
      .eq("quest_id", questId).order("seq", { ascending: true }),
  ]);
  if (s.error) throw new Error(`db: ${s.error.message}`);
  if (c.error) throw new Error(`db: ${c.error.message}`);
  return { seals: s.data ?? [], chronicle: c.data ?? [] };
}

async function reexecute(quest: QuestRow): Promise<Reexec> {
  try {
    const r = await fetch(quest.manifest.claim.url, { headers: { "Cache-Control": "no-cache" } });
    if (r.status !== 200) return { ok: false, reason: `CLAIM_UNAVAILABLE_HTTP_${r.status}` };
    const raw = new Uint8Array(await r.arrayBuffer());
    const fileSha = await sha256Hex(raw);
    if (fileSha !== quest.manifest.claim.sha256 || raw.length !== quest.manifest.claim.bytes) {
      return { ok: false, reason: "CLAIM_CHANGED_SINCE_MANIFEST", claim_sha256: fileSha };
    }
    const ev = await computeEvidence(raw);
    return { ok: true, claim_sha256: fileSha, sealed_output: ev.sealed_output, output: ev.output };
  } catch (e) {
    return { ok: false, reason: `CLAIM_UNAVAILABLE: ${String(e).slice(0, 120)}` };
  }
}

async function sealDrop(req: Request) {
  const text = await req.text();
  if (text.length > 16384) return json(413, { accepted: false, code: "too_large", detail: "max 16 KiB" });
  let env: any;
  try { env = JSON.parse(text); } catch { return json(400, { accepted: false, code: "bad_json", detail: "body is not JSON" }); }
  const quest = typeof env?.quest_id === "string" ? await loadQuest(env.quest_id) : null;
  const v = await validateEnvelope(env, quest, Date.now(), verify);
  if (!v.ok) return json(v.status, { accepted: false, code: v.code, detail: v.detail, state_changed: false });

  const envelope_sha256 = await seal(env);
  const payload = {
    envelope_sha256, request_id: env.request_id, nonce: env.nonce, key_id: env.key_id,
    operator: env.operator, failure_mode: env.failure_mode, sealed_output: env.sealed_output,
  };
  for (let attempt = 0; attempt < 3; attempt++) {
    const tip = await db.rpc("quest_tip", { p_quest_id: quest!.quest_id });
    if (tip.error) return json(500, { accepted: false, code: "db_error", detail: tip.error.message });
    const rec = {
      quest_id: quest!.quest_id, seq: tip.data.seq + 1, event: "seal_accepted", payload,
      prev_hash: tip.data.record_hash, created_at: new Date().toISOString(),
    };
    const record_hash = await recordHash(rec);
    const { data, error } = await db.rpc("quest_append", {
      p_quest_id: rec.quest_id, p_seq: rec.seq, p_event: rec.event, p_payload: rec.payload,
      p_prev_hash: rec.prev_hash, p_record_hash: record_hash, p_created_at: rec.created_at,
      p_seal: {
        request_id: env.request_id, nonce: env.nonce, key_id: env.key_id, pubkey: env.pubkey,
        operator: env.operator, operator_norm: v.operator_norm, failure_mode: env.failure_mode,
        failure_mode_norm: v.failure_mode_norm, sealed_output: env.sealed_output, envelope: env, envelope_sha256,
      },
    });
    if (!error) {
      return json(201, {
        accepted: true, quest_id: rec.quest_id, is_test: quest!.is_test, envelope_sha256,
        chronicle: { ...rec, record_hash }, receipt: data,
        note: "Accepted into the chronicle. Acceptance is not a verdict; see the verdict endpoint. No payment is made by this service.",
      });
    }
    const m = error.message ?? "";
    if (m.includes("chain_conflict")) continue;
    const dup: [string, string][] = [
      ["quest_seals_nonce_uniq", "replayed_nonce"], ["quest_seals_request_uniq", "duplicate_request_id"],
      ["quest_seals_pubkey_uniq", "duplicate_key"], ["quest_seals_operator_uniq", "duplicate_operator"],
    ];
    for (const [c, code] of dup) {
      if (m.includes(c)) return json(409, { accepted: false, code, detail: `${code.replace(/_/g, " ")} for this quest`, state_changed: false });
    }
    return json(500, { accepted: false, code: "db_error", detail: m.slice(0, 200), state_changed: false });
  }
  return json(503, { accepted: false, code: "chain_busy", detail: "retry", state_changed: false });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  const url = new URL(req.url);
  const i = url.pathname.indexOf("/api/v1/evidence");
  const route = i >= 0 ? url.pathname.slice(i + "/api/v1/evidence".length).replace(/\/+$/, "") : url.pathname;
  try {
    if (route === "/seal-drop") {
      if (req.method !== "POST") return json(405, { error: "POST only" });
      return await sealDrop(req);
    }
    if (req.method !== "GET") return json(405, { error: "GET only" });
    if (route === "" || route === "/") {
      const { data } = await db.from("quest_manifests").select("quest_id,manifest_sha256,deadline,is_test").order("quest_id");
      return json(200, { service: VERSION, quests: data ?? [], automatic_payment: false });
    }
    const m = route.match(/^\/(quest-[0-9a-z-]+)(\/manifest|\/verdict|\/replay)?$/);
    if (!m) return json(404, { error: "not found", route });
    const quest = await loadQuest(slugToQuest(m[1]));
    if (!quest) return json(404, { error: "unknown quest", quest: m[1] });
    if (m[2] === "/manifest") {
      return new Response(quest.manifest_text, {
        headers: { ...CORS, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
          "X-Manifest-SHA256": quest.manifest_sha256 },
      });
    }
    const { seals, chronicle } = await loadSealsAndChain(quest.quest_id);
    if (!m[2]) {
      return json(200, {
        service: VERSION, quest_id: quest.quest_id, is_test: quest.is_test, manifest_sha256: quest.manifest_sha256,
        deadline: quest.deadline, seals, chronicle, chain: await verifyChain(chronicle),
      });
    }
    const verdict = await computeVerdict(quest, seals.map((s: any) => s.envelope), await reexecute(quest), verify);
    if (m[2] === "/verdict") return json(200, { service: VERSION, ...verdict });
    // /replay: recompute chain, envelope hashes, seal<->chronicle linkage and verdict twice.
    const chain = await verifyChain(chronicle);
    const problems: string[] = [...chain.problems];
    const bySeq = new Map(chronicle.map((r: any) => [r.seq, r]));
    for (const s of seals as any[]) {
      if (await seal(s.envelope) !== s.envelope_sha256) problems.push(`seal ${s.id}: envelope_sha256 does not recompute`);
      const r: any = bySeq.get(s.chronicle_seq);
      if (!r || r.event !== "seal_accepted" || r.payload.envelope_sha256 !== s.envelope_sha256) {
        problems.push(`seal ${s.id}: no matching chronicle record`);
      }
    }
    const again = await computeVerdict(quest, seals.map((s: any) => s.envelope), await reexecute(quest), verify);
    if (again.verdict_hash !== verdict.verdict_hash) problems.push("verdict not reproducible across two evaluations");
    return json(200, {
      service: VERSION, quest_id: quest.quest_id, replay_ok: problems.length === 0, problems,
      chain_length: chain.length, chain_tip: chain.tip, verdict: verdict.verdict, verdict_hash: verdict.verdict_hash,
      settlement_state: verdict.settlement_state, automatic_payment: false,
    });
  } catch (e) {
    return json(500, { error: String(e).slice(0, 300) });
  }
});
