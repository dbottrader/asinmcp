#!/usr/bin/env python3
"""receipt_wrap.py — wrap live ASIN-HHC receipt payloads into evidence
receipts conforming to the adopted asin-hhc:receipt schema.

Implements the adoption path documented in Tranche 1's VALIDATION.md
("Adoption path (documented, not performed here)"): WRAPPING, not emitter
rewrites. The live system's three receipt families —

  A  mesh main-ledger entries   {seq, ts, actor, kind, payload, prev_hash,
                                 hash, canon}
  B  HHC ledger posting rows    {id, agent, amount, kind, work_id,
                                 escrow_id, receipt, status, created}
  C  Passport hash-chain events {seq, id, passport_id, seq_in_passport,
                                 kind, actor, payload, created, prev_hash,
                                 hash}

— are lifted into the schema's evidence shape:

  receipt_id  "asin-hhc:receipt:" + first 16 hex of the source record hash
  claim_id    the work / escrow / transfer / passport id the receipt speaks
              to, upper-cased to the schema's claim pattern
  status      mapped onto the evidence ladder (OBSERVED -> PROVENANCED ->
              TESTED -> REPLAYED -> INDEPENDENTLY_REPRODUCED -> PROMOTED,
              plus HOLD / REJECTED / RETIRED) — see the mapping tables
              below; the three native vocabularies (ledger `kind`, HHC
              `POSTED` + row `kind`, Passport `kind`) are NOT passed
              through, per VALIDATION.md's rejected adjustments
  created_at  RFC 3339 string rendered from the epoch-float timestamp
              (the schema's date-time requirement; emitters keep epochs)
  inputs      artifact ids from the payload + sha256 hashes the payload
              already carries (payload `receipt` pointers, transfer
              receipt_in/out, Passport evidence content hashes)
  procedure   the documented protocol that produced the record (mesh
              v0.2 escrow rules / HHC v0.3 adjudication / Passport tier
              rules) + the payload's scalar facts as parameters
  execution   environment + toolchain + the record's own timestamp
  outputs     result_hash = the source record's own chain hash (family B:
              the `receipt` pointer, i.e. the hash of the main-ledger
              entry the posting anchors to) + a prose summary; verdict
              sets, where the payload carries them, become control_results
  replay      status NOT_ATTEMPTED for historical records (no replay of
              these receipts is on record — claiming REPLAYED would be
              fabrication) + concrete recompute instructions; verifier
              agents, where known, are listed as witnesses
  chain       the canon-v1 chain position, under the schema's optional
              `chain` property (Tranche 1 Adjustment A1). Family B rows
              carry no chain position of their own, so `chain` is omitted
              for them rather than borrowing the partner entry's.

Honesty rules enforced here:
  * Nothing is invented. A field is filled only from data present in the
    source record (or, for family B, in its joined main-ledger partner).
  * If a required evidence field cannot be filled from the record, wrap_*
    raises WrapError naming the missing evidence instead of padding.
  * Family D (the Sebastien packet receipt.json) is NOT wrapped: it is an
    ad-hoc packet artifact, not a live-system payload, and VALIDATION.md
    assigns it a packet-specific restructuring. wrap_any() refuses it
    explicitly.

Status mapping rationale (the judgment calls, stated):
  * hhc_escrow_funded / escrow_lock / claim / submit / mint / transfer /
    registration -> OBSERVED. The event is recorded on the chain; no
    verification of the underlying claim has happened yet.
  * hhc_verdict / verifier_fee -> TESTED. A verifier executed the review
    procedure against the submitted result.
  * hhc_escrow_paid / escrow_release / work_complete -> TESTED. Settlement
    executed after 2+ independent pass verdicts (the HHC adjudicator only
    releases from the converged branch; the v0.2 complete path follows
    reviewer confirmation). The verdict set is carried in
    outputs.control_results whenever the record holds it.
  * hhc_escrow_refunded / escrow_refund -> REJECTED. At least one
    verifier fail verdict rejected the claim; the refund executed.
  * Passport evidence_checks -> TESTED (the check battery ran; its
    per-item results are the control_results, pass or fail).
  * Passport verifier_verdict -> TESTED.
  * Passport certification_decision -> TESTED when certified/provisional,
    REJECTED when not_certified; the tier outcome is additionally
    recorded in the schema's `promotion` block (PROMOTED / HOLD /
    NOT_ELIGIBLE under the passport tier policy).
  * PROVENANCED / REPLAYED / INDEPENDENTLY_REPRODUCED are never assigned
    by this wrapper: provenance grading and replay are separate acts
    with their own receipts, not properties a wrapper may infer.

Stdlib only. Validation is deliberately NOT done here — receipts are
checked with Tranche 1's validate_receipts.py machinery so the wrapper
never grades its own homework.
"""
import hashlib
import json
from datetime import datetime, timezone

ENVIRONMENT = "ASIN-HHC agent mesh (mesh v0.2.1 + HHC v0.3-hhc), canon-v1 ledger"
TOOLCHAIN_A = "mesh_v02.py ledger_append (canon-v1)"
TOOLCHAIN_B = "hhc_mesh.py hhc_post (hhc_ledger)"
TOOLCHAIN_C = "mesh_v02.py _passport_event_append_inner (canon-v1)"

PROTO_HHC = "asin-hhc:hhc-escrow:v0.3"
PROTO_HHC_VERDICT = "asin-hhc:hhc-verdict:v0.3"
PROTO_HHC_TRANSFER = "asin-hhc:hhc-transfer:v0.3"
PROTO_HHC_LEDGER = "asin-hhc:hhc-ledger:v0.3"
PROTO_MESH_WORK = "asin-hhc:mesh-work:v0.2"
PROTO_PASSPORT = "asin-hhc:passport:v1"
CODE_REV_A = "mesh_v02.py v0.2.1"
CODE_REV_B = "hhc_mesh.py v0.3-hhc"
CODE_REV_C = "mesh_v02.py v0.2.1 (passport)"


class WrapError(Exception):
    """A required evidence field cannot be honestly filled."""

    def __init__(self, family, reason, missing):
        super().__init__(reason)
        self.family = family
        self.reason = reason
        self.missing = missing  # list of field names that could not be filled


def rfc3339(epoch):
    """Epoch float -> RFC 3339 / ISO-8601 UTC string (schema date-time)."""
    return datetime.fromtimestamp(float(epoch), timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def sha256_hex(obj):
    return hashlib.sha256(_canon(obj)).hexdigest()


def _is_hash(v):
    return (isinstance(v, str) and len(v) == 64
            and all(ch in "0123456789abcdef" for ch in v))


def _claim(raw):
    """Upper-case an id into the schema's claim_id pattern."""
    return str(raw).upper()


def _payload_of(entry):
    p = entry.get("payload")
    if isinstance(p, str):
        return json.loads(p)
    return dict(p or {})


def _scalars(payload, skip):
    """Payload facts safe to carry as procedure.parameters."""
    out = {}
    for k, v in payload.items():
        if k in skip:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict) and all(
                isinstance(x, (str, int, float, bool)) for x in v.values()):
            out[k] = v
    return out


# ------------------------------------------------------------- family A --
# ledger kind -> (evidence-ladder status, protocol_id)
_A_STATUS = {
    "hhc_escrow_funded": ("OBSERVED", PROTO_HHC),
    "hhc_work_claim": ("OBSERVED", PROTO_HHC),
    "hhc_work_submitted": ("OBSERVED", PROTO_HHC),
    "hhc_verdict": ("TESTED", PROTO_HHC_VERDICT),
    "hhc_escrow_paid": ("TESTED", PROTO_HHC),
    "hhc_escrow_refunded": ("REJECTED", PROTO_HHC),
    "hhc_transfer": ("OBSERVED", PROTO_HHC_TRANSFER),
    "hhc_mint": ("OBSERVED", PROTO_HHC),
    "work_complete": ("TESTED", PROTO_MESH_WORK),
}


def _a_status(kind):
    if kind in _A_STATUS:
        return _A_STATUS[kind]
    if kind.startswith("hhc_"):
        return ("OBSERVED", PROTO_HHC)
    return ("OBSERVED", PROTO_MESH_WORK)


def wrap_ledger_entry(entry):
    """Family A: a mesh main-ledger hash-chain entry."""
    payload = _payload_of(entry)
    kind = entry.get("kind", "")
    h = entry.get("hash")
    if not _is_hash(h):
        raise WrapError("A_ledger", "ledger entry carries no chain hash",
                        ["outputs.result_hash", "chain.hash"])
    status, protocol = _a_status(kind)

    artifact_ids, input_hashes = [], []
    for key in ("work_id", "escrow_id", "transfer_id"):
        if payload.get(key):
            artifact_ids.append(str(payload[key]))
    for key in ("receipt", "receipt_in", "receipt_out"):
        if _is_hash(payload.get(key)):
            input_hashes.append({"algorithm": "sha256",
                                 "value": payload[key]})
    if not artifact_ids:
        raise WrapError("A_ledger",
                        "no work/escrow/transfer id in payload to claim",
                        ["claim_id"])
    claim_id = _claim(payload.get("work_id") or payload.get("escrow_id")
                      or payload.get("transfer_id"))

    control_results, witnesses = [], []
    verdicts = payload.get("verdicts")
    if isinstance(verdicts, dict) and verdicts:
        control_results = [{"verifier": a, "verdict": v}
                           for a, v in sorted(verdicts.items())]
        witnesses = sorted(verdicts.keys())
    elif payload.get("verdict"):
        control_results = [{"verifier": entry.get("actor"),
                            "verdict": payload["verdict"]}]
        witnesses = [entry.get("actor")]

    summary_bits = ["ledger event %s" % kind]
    for key in ("worker_pay", "refund", "verifier_fee_each", "price",
                "amount"):
        if key in payload:
            summary_bits.append("%s=%s" % (key, payload[key]))
    if verdicts:
        summary_bits.append("verdicts=%s" % json.dumps(verdicts,
                                                       sort_keys=True))

    return {
        "receipt_id": "asin-hhc:receipt:" + h[:16],
        "claim_id": claim_id,
        "status": status,
        "created_at": rfc3339(entry["ts"]),
        "inputs": {"artifact_ids": artifact_ids,
                   "input_hashes": input_hashes},
        "procedure": {
            "protocol_id": protocol,
            "code_revision": CODE_REV_A,
            "parameters": _scalars(payload, skip={
                "receipt", "receipt_in", "receipt_out", "verdicts",
                "verdict"}),
        },
        "execution": {"environment": ENVIRONMENT, "toolchain": TOOLCHAIN_A,
                      "timestamp": rfc3339(entry["ts"])},
        "outputs": {"result_hash": h, "summary": "; ".join(summary_bits),
                    "control_results": control_results},
        "replay": {
            "status": "NOT_ATTEMPTED",
            "instructions": (
                "Recompute the canon-v1 ledger chain from genesis to seq "
                "%d: for each entry, hash = sha256(canon_v1({ts, actor, "
                "kind, payload, prev_hash})) with linkage prev_hash == "
                "previous hash; seq %d must reproduce hash %s. Then "
                "re-derive this event from the escrow/work record it "
                "names and compare payload fields."
                % (entry["seq"], entry["seq"], h)),
            "witnesses": witnesses,
        },
        "chain": {"seq": entry["seq"], "prev_hash": entry["prev_hash"],
                  "hash": h, "canon": entry.get("canon", "v1")},
    }


# ------------------------------------------------------------- family B --
# HHC row kind -> evidence-ladder status. The native row status is always
# POSTED (the posting landed); POSTED is a bookkeeping state, NOT an
# evidence status, and is never passed through (VALIDATION.md).
_B_STATUS = {
    "escrow_release": "TESTED",     # emitted only by the converged branch
    "verifier_fee": "TESTED",       # paid for a completed verification
    "escrow_refund": "REJECTED",    # emitted only by the fail branch
    "escrow_lock": "OBSERVED",
    "starter_grant": "OBSERVED",
    "mint": "OBSERVED",
    "transfer": "OBSERVED",
    "bridge_claim": "OBSERVED",
}


def wrap_hhc_row(row, partner=None):
    """Family B: an HHC ledger posting row.

    `partner`, when available, is the family-A ledger entry this row's
    `receipt` pointer anchors to (matched on payload receipt or chain
    hash); its verdict set, when present, is lifted as evidence. Without
    a partner the row still wraps: its kind is emitted only by specific
    adjudication branches, so the status mapping above stays honest, but
    witnesses/control_results remain empty rather than inferred.
    """
    kind = row.get("kind", "")
    status = _B_STATUS.get(kind, "OBSERVED")
    ptr = row.get("receipt")
    if not _is_hash(ptr):
        raise WrapError("B_hhc", "row carries no receipt pointer hash",
                        ["inputs.input_hashes", "outputs.result_hash"])
    if not row.get("work_id") and not row.get("escrow_id"):
        raise WrapError("B_hhc", "row names no work or escrow", ["claim_id"])

    control_results, witnesses = [], []
    if partner is not None:
        p = _payload_of(partner)
        verdicts = p.get("verdicts")
        if isinstance(verdicts, dict) and verdicts:
            control_results = [{"verifier": a, "verdict": v}
                               for a, v in sorted(verdicts.items())]
            witnesses = sorted(verdicts.keys())

    return {
        "receipt_id": "asin-hhc:receipt:" + ptr[:16],
        "claim_id": _claim(row.get("work_id") or row.get("escrow_id")),
        "status": status,
        "created_at": rfc3339(row["created"]),
        "inputs": {
            "artifact_ids": [x for x in (row.get("work_id"),
                                         row.get("escrow_id"),
                                         row.get("id")) if x],
            "input_hashes": [{"algorithm": "sha256", "value": ptr}],
        },
        "procedure": {
            "protocol_id": PROTO_HHC_LEDGER,
            "code_revision": CODE_REV_B,
            "parameters": {"kind": kind, "amount": row.get("amount"),
                           "agent": row.get("agent"),
                           "native_status": row.get("status")},
        },
        "execution": {"environment": ENVIRONMENT, "toolchain": TOOLCHAIN_B,
                      "timestamp": rfc3339(row["created"])},
        "outputs": {
            "result_hash": ptr,
            "summary": ("HHC posting %s of %s HHC to %s (kind=%s); "
                        "result_hash is the main-ledger entry hash this "
                        "posting anchors to"
                        % (row.get("id"), row.get("amount"),
                           row.get("agent"), kind)),
            "control_results": control_results,
        },
        "replay": {
            "status": "NOT_ATTEMPTED",
            "instructions": (
                "Find the main-ledger entry whose payload receipt (or "
                "chain hash) equals %s; wrap it with wrap_ledger_entry "
                "and confirm its work_id/escrow_id match this row and "
                "its verdict set explains this posting's kind and amount "
                "under the mesh v0.2 escrow rules (90/5/5 split of the "
                "fee pool on convergence; refund minus fee pool on "
                "rejection)." % ptr),
            "witnesses": witnesses,
        },
    }


# ------------------------------------------------------------- family C --
def wrap_passport_event(event):
    """Family C: a Passport hash-chain event."""
    payload = _payload_of(event)
    kind = event.get("kind", "")
    h = event.get("hash")
    pid = event.get("passport_id")
    if not _is_hash(h) or not pid:
        raise WrapError("C_passport",
                        "event lacks chain hash or passport_id",
                        ["outputs.result_hash", "claim_id"])
    seq = event.get("seq_in_passport", event.get("seq"))
    created = event.get("created")

    artifact_ids = [pid]
    if payload.get("certification_id"):
        artifact_ids.append(str(payload["certification_id"]))
    input_hashes, control_results, witnesses = [], [], []
    promotion = None

    if kind == "evidence_checks":
        status = "TESTED"
        checks = payload.get("checks") or {}
        for r in checks.get("results", []):
            if r.get("url"):
                artifact_ids.append(r["url"])
            if _is_hash(r.get("sha256")):
                input_hashes.append({"algorithm": "sha256",
                                     "value": r["sha256"]})
            control_results.append({
                "url": r.get("url"), "reachable": r.get("reachable"),
                "status": r.get("status"), "error": r.get("error")})
        summary = ("evidence checks (%s mode): %s evidence URL(s), "
                   "all_reachable=%s"
                   % (checks.get("mode", payload.get("mode")),
                      checks.get("evidence_count"), checks.get("all_reachable")))
    elif kind == "verifier_verdict":
        status = "TESTED"
        control_results = [{"verifier": payload.get("verifier"),
                            "criteria": payload.get("criteria"),
                            "verdict": payload.get("verdict")}]
        if payload.get("agent_id"):
            witnesses = [payload["agent_id"]]
        summary = ("verifier verdict '%s' on criteria '%s': %s"
                   % (payload.get("verdict"), payload.get("criteria"),
                      payload.get("reasoning")))
    elif kind == "certification_decision":
        decision = payload.get("decision")
        if decision == "not_certified":
            status = "REJECTED"
            promotion = {"status": "NOT_ELIGIBLE",
                         "policy_id": "asin-hhc:passport-tier-rules:v1",
                         "blockers": ["decision: not_certified"]}
        elif decision == "certified":
            status = "TESTED"
            promotion = {"status": "PROMOTED",
                         "policy_id": "asin-hhc:passport-tier-rules:v1",
                         "blockers": []}
        else:  # provisional or any other recorded decision
            status = "TESTED"
            promotion = {"status": "HOLD",
                         "policy_id": "asin-hhc:passport-tier-rules:v1",
                         "blockers": ["decision: %s" % decision]}
        summary = ("certification decision '%s' -> tier %s (sign-off: %s)"
                   % (decision, payload.get("tier"),
                      payload.get("sign_off_by")))
    elif kind == "registered":
        status = "OBSERVED"
        summary = ("passport registered: %s (%s), tier %s"
                   % (payload.get("display_name"), payload.get("agent_kind"),
                      payload.get("tier")))
    else:
        status = "OBSERVED"
        summary = "passport event %s" % kind

    receipt = {
        "receipt_id": "asin-hhc:receipt:" + h[:16],
        "claim_id": _claim(pid),
        "status": status,
        "created_at": rfc3339(created),
        "inputs": {"artifact_ids": artifact_ids,
                   "input_hashes": input_hashes},
        "procedure": {
            "protocol_id": PROTO_PASSPORT,
            "code_revision": CODE_REV_C,
            "parameters": _scalars(payload, skip={
                "checks", "verdict", "criteria", "reasoning"}),
        },
        "execution": {"environment": ENVIRONMENT, "toolchain": TOOLCHAIN_C,
                      "timestamp": rfc3339(created)},
        "outputs": {"result_hash": h, "summary": summary,
                    "control_results": control_results},
        "replay": {
            "status": "NOT_ATTEMPTED",
            "instructions": (
                "Recompute the passport event chain for %s from "
                "PASSPORT_GENESIS (64 zero hex): hash = sha256(canon_v1("
                "{passport_id, seq, kind, actor, payload, created, "
                "prev_hash})) per event; seq_in_passport %s must "
                "reproduce hash %s. For certification_decision events, "
                "re-apply the tier rule recorded in the payload."
                % (pid, seq, h)),
            "witnesses": witnesses,
        },
        "chain": {"seq": seq, "prev_hash": event["prev_hash"], "hash": h},
    }
    if promotion is not None:
        receipt["promotion"] = promotion
    return receipt


# ------------------------------------------------------------ dispatch --
def detect_family(obj):
    if "passport_id" in obj and "seq_in_passport" in obj:
        return "C_passport"
    if "prev_hash" in obj and "hash" in obj and "payload" in obj:
        return "A_ledger"
    if obj.get("status") == "POSTED" and "receipt" in obj and "agent" in obj:
        return "B_hhc"
    return None


def wrap_any(obj, partner_index=None):
    """Wrap one sample dict. partner_index (family B only) maps a receipt
    pointer to its family-A partner entry, built by build_partner_index().
    Raises WrapError for records that cannot be honestly wrapped —
    including family D, which is refused by design."""
    fam = detect_family(obj)
    if fam == "A_ledger":
        return wrap_ledger_entry(obj)
    if fam == "C_passport":
        return wrap_passport_event(obj)
    if fam == "B_hhc":
        partner = None
        if partner_index is not None:
            partner = partner_index.get(obj.get("receipt"))
        return wrap_hhc_row(obj, partner=partner)
    raise WrapError(
        "unknown",
        "record matches no live-system family (A/B/C); the Sebastien "
        "packet receipt (family D) is refused by design — it needs the "
        "packet-specific restructuring in VALIDATION.md, not wrapping",
        ["receipt_id", "claim_id", "status", "created_at", "inputs",
         "procedure", "execution", "outputs", "replay"])


def build_partner_index(ledger_entries):
    """Map receipt pointer -> family-A entry, by payload receipt and by
    chain hash (both anchor styles occur in the live data)."""
    idx = {}
    for e in ledger_entries:
        p = _payload_of(e)
        if _is_hash(p.get("receipt")):
            idx[p["receipt"]] = e
        if _is_hash(e.get("hash")):
            idx[e["hash"]] = e
    return idx
