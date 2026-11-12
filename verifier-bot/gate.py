"""Refusal-aware verification gate — ASIN-HHC Verifier Bot, node side.

Implements SPEC.md design v2 (~/workspace/verifier-bot/SPEC.md): the four
outcomes PASS / FAIL / VOID / REFUSED, the seven mandatory checks, the
ASIN-HHC-VERIFICATION-1.0 receipt schema, hash-chained receipts, and
signing through the Agent Vault (with a test signer for offline tests).

Standard library only. No network. Deterministic: the caller supplies
`now` (ISO-8601) and all randomness lives in key generation helpers,
never in the decision procedure.

Design notes / decisions where the SPEC left room:

- Blindness is by construction: an attempt never receives the claimant's
  claimed output. The gate runs the solver callable itself; the only
  outputs compared are the gate's own sealed re-execution and the
  witnesses' sealed outputs.
- A witness verdict is AGREE when its sealed output hash equals the
  gate's re-execution seal, DISAGREE otherwise.
- VOID resolution emits a *resolution receipt* carrying the same
  verification_id plus `resolution_of` = the VOID receipt's hash. Each
  submission (attempt or resolution) emits exactly one receipt.
- Replay protection: a verification_id may be used for exactly one
  attempt. Re-submitting an id raises ReplayRejected — this is what
  rejects a replayed (including expired) verification.
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field

# --- reuse-first: vendored Ed25519 from asinmcp (read-only import),
# --- the same primitive the Agent Vault uses.
_ED_PATH = os.path.expanduser("~/workspace/asinmcp")
if _ED_PATH not in sys.path:
    sys.path.insert(0, _ED_PATH)
import ed25519  # noqa: E402

SCHEMA = "ASIN-HHC-VERIFICATION-1.0"
ZERO_HASH = "0" * 64
EXTERNAL = "EXTERNAL_TO_TEST_POPULATION"

# The four outcomes. Never collapsed into a boolean.
PASS = "PASS"
FAIL = "FAIL"
VOID = "VOID"
REFUSED = "REFUSED"
OUTCOMES = (PASS, FAIL, VOID, REFUSED)

# Reason codes.
R_NO_DISCRIMINATING_CONDITION = "NO_DISCRIMINATING_CONDITION"
R_CONTROL_FAILURE = "CONTROL_FAILURE"
R_NO_INDEPENDENT_WITNESS = "NO_INDEPENDENT_WITNESS"
R_INSUFFICIENT_VALID_WITNESSES = "INSUFFICIENT_VALID_WITNESSES"
R_STALE_PRECONDITIONS = "STALE_PRECONDITIONS"
R_RESIDUAL_MISMATCH = "RESIDUAL_MISMATCH"
R_SEAL_MISMATCH = "SEAL_MISMATCH"
R_WITNESS_CONFLICT = "WITNESS_CONFLICT"
R_REEXECUTION_MISMATCH = "REEXECUTION_MISMATCH"
R_THIRD_PLACEMENT_QUORUM = "THIRD_PLACEMENT_QUORUM"
R_THIRD_PLACEMENT_FAILED = "THIRD_PLACEMENT_FAILED"

# Legal outcome transitions. REFUSED, PASS and FAIL are terminal for an
# attempt; VOID may move only via an independent third placement.
_TRANSITIONS = {
    None: {PASS, FAIL, VOID, REFUSED},
    VOID: {PASS, FAIL, VOID},   # VOID -> VOID = a failed placement attempt
    PASS: set(),
    FAIL: set(),
    REFUSED: set(),
}


class GateError(Exception):
    """Base class for gate errors."""


class ReplayRejected(GateError):
    """A verification_id was submitted twice. The attempt is rejected
    outright — no receipt is emitted for a replay."""


class SignerError(GateError):
    """The signing backend failed."""


# ---------------------------------------------------------------------------
# Canonical form, hashing, sealing
# ---------------------------------------------------------------------------

def canonical_json(obj) -> bytes:
    """Canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(output) -> str:
    """Seal an output: sha256 over its canonical form. Sealing happens
    BEFORE any comparison; re-hashing later detects modification."""
    return sha256_hex(canonical_json(output))


def parse_time(ts: str):
    """Parse an ISO-8601 timestamp into an aware datetime (UTC assumed
    when no offset is given)."""
    from datetime import datetime, timezone
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class Preconditions:
    established_at: str  # ISO-8601
    expires_at: str      # ISO-8601

    def is_fresh(self, now: str) -> bool:
        return parse_time(self.established_at) <= parse_time(now) \
            < parse_time(self.expires_at)


@dataclass
class Control:
    """A control record from outside the tested population, with a known
    expected result. `actual` may be a value or a zero-arg callable.
    `discriminates=False` models a control that cannot distinguish the
    claim from its negation (e.g. it would read the same either way)."""
    control_id: str
    expected: object
    actual: object
    source: str = EXTERNAL
    discriminates: bool = True

    def evaluate(self):
        return self.actual() if callable(self.actual) else self.actual

    @property
    def is_external(self) -> bool:
        return self.source == EXTERNAL


@dataclass
class Witness:
    """A witness placement. `sealed_output` is the sha256 seal of
    `output`, made before submission; `signature` is an Ed25519
    signature (hex) over the sealed-output hex string, verifiable with
    `pubkey` (hex). A witness whose output no longer hashes to its seal
    is tampered evidence; a witness with a missing/invalid signature is
    simply invalid."""
    id: str
    operator: str
    implementation: str
    data_source: str
    failure_mode: str
    output: object
    sealed_output: str
    signature: object  # hex str or None
    pubkey: str


def witness_keypair(seed_bytes: bytes):
    """Deterministic Ed25519 keypair from a 32-byte seed.
    Returns (seed_hex, pubkey_hex)."""
    return ed25519.generate_keypair(seed_bytes)


def build_witness(wid, operator, implementation, data_source,
                  failure_mode, output, seed_bytes) -> Witness:
    """Build a correctly sealed and signed witness (the honest path)."""
    seed_hex, pub_hex = witness_keypair(seed_bytes)
    sealed = seal(output)
    sig = ed25519.sign(seed_hex, sealed.encode("utf-8"))
    return Witness(id=wid, operator=operator, implementation=implementation,
                   data_source=data_source, failure_mode=failure_mode,
                   output=output, sealed_output=sealed, signature=sig,
                   pubkey=pub_hex)


# ---------------------------------------------------------------------------
# Signers
# ---------------------------------------------------------------------------

class TestSigner:
    """HMAC-SHA256 signer for offline tests. Fast and deterministic;
    NOT a production signer (verification key == signing key)."""

    kind = "test-hmac-sha256"

    def __init__(self, key: bytes):
        self._key = key

    def meta(self):
        return {"kind": self.kind, "fingerprint": sha256_hex(self._key)}

    def sign(self, payload: bytes) -> dict:
        sig = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return {"value": sig, "kind": self.kind}

    def verify(self, payload: bytes, signature: dict) -> bool:
        if not isinstance(signature, dict) or "value" not in signature:
            return False
        expected = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature["value"])


class VaultSigner:
    """Signs via the Agent Vault CLI (~/workspace/agent-vault/vault.py).

    The vault unseals per invocation and signs only within its written
    policy; the default policy's `doc.sign` action is used. The payload
    signed is the receipt_hash (hex, UTF-8). The vault's own receipt
    data (ts, nonce, its receipt hash) rides inside the signature dict
    so `verify` can rebuild the vault's envelope exactly.
    """

    kind = "agent-vault-ed25519"

    def __init__(self, vault_dir, action="doc.sign", vault_py=None,
                 python=None):
        self.vault_dir = os.path.expanduser(vault_dir)
        self.action = action
        self.vault_py = vault_py or os.path.expanduser(
            "~/workspace/agent-vault/vault.py")
        self.python = python or sys.executable
        ident_path = os.path.join(self.vault_dir, "identity.json")
        with open(ident_path, "r", encoding="utf-8") as fh:
            ident = json.load(fh)
        self._meta = {"kind": self.kind,
                      "fingerprint": ident["fingerprint"],
                      "pubkey": ident["pubkey"],
                      "vault_id": ident["vault_id"]}

    def meta(self):
        return dict(self._meta)

    def _run(self, args, payload: bytes):
        fd, tmp = tempfile.mkstemp(prefix="gate-payload-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
            cmd = [self.python, self.vault_py] + args + \
                ["--payload-file", tmp]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  env=dict(os.environ))
            if proc.returncode not in (0, 2):
                raise SignerError(
                    "vault command failed (%d): %s"
                    % (proc.returncode, proc.stderr.strip()[-400:]))
            try:
                return proc.returncode, json.loads(proc.stdout)
            except json.JSONDecodeError:
                raise SignerError("vault returned non-JSON: %r"
                                  % proc.stdout[:200])
        finally:
            os.unlink(tmp)

    def sign(self, payload: bytes) -> dict:
        rc, out = self._run(["sign", "--dir", self.vault_dir,
                             "--action", self.action], payload)
        if rc != 0 or "signature" not in out:
            raise SignerError("vault refused to sign: %s" % out)
        return {"value": out["signature"], "kind": self.kind,
                "action": self.action, "ts": out["ts"],
                "nonce": out["nonce"],
                "vault_receipt_hash": out["receipt_hash"],
                "vault_receipt_seq": out["receipt_seq"]}

    def verify(self, payload: bytes, signature: dict) -> bool:
        if not isinstance(signature, dict) or "value" not in signature:
            return False
        rc, out = self._run(
            ["verify", "--dir", self.vault_dir, "--action", self.action,
             "--signature", signature["value"], "--ts", signature["ts"],
             "--nonce", signature["nonce"]], payload)
        return rc == 0 and out.get("valid") is True


def receipt_hash_of(receipt: dict) -> str:
    """sha256 of the canonical receipt excluding the receipt_hash and
    signature fields (exactly those two keys)."""
    body = {k: v for k, v in receipt.items()
            if k not in ("receipt_hash", "signature")}
    return sha256_hex(canonical_json(body))


def verify_receipt(receipt: dict, signer) -> bool:
    """Independently verify a receipt: hash recomputes and the signer
    verifies the signature over the hash bytes."""
    if receipt.get("receipt_hash") != receipt_hash_of(receipt):
        return False
    payload = receipt["receipt_hash"].encode("utf-8")
    return signer.verify(payload, receipt.get("signature"))


def chain_verify(lines, signer=None):
    """Verify a hash-chained receipt sequence (list of receipt dicts).
    Returns (ok, detail). Detects edits, reordering and truncation of
    the linkage; with a signer, also verifies every signature."""
    prev = ZERO_HASH
    for i, receipt in enumerate(lines):
        if receipt.get("prev_receipt_hash") != prev:
            return False, "BROKEN at index %d: prev_receipt_hash mismatch" % i
        if receipt.get("receipt_hash") != receipt_hash_of(receipt):
            return False, "BROKEN at index %d: receipt_hash mismatch" % i
        if signer is not None and not verify_receipt(receipt, signer):
            return False, "BROKEN at index %d: signature invalid" % i
        prev = receipt["receipt_hash"]
    return True, "OK (%d receipts)" % len(lines)


def chain_verify_file(path, signer=None):
    with open(path, "r", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    return chain_verify(lines, signer=signer)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

class Gate:
    """The refusal-aware verification gate (node side).

    One Gate instance owns one receipt chain. Receipts are kept in
    memory (`self.receipts`) and, when `ledger_path` is given, appended
    as canonical JSONL so the chain survives the process and external
    chain_verify_file() can replay it.
    """

    def __init__(self, signer, ledger_path=None):
        self.signer = signer
        self.ledger_path = ledger_path
        self.receipts = []
        self._used_attempt_ids = set()
        self._void = {}  # verification_id -> resolution context
        if ledger_path and os.path.exists(ledger_path):
            # Resume the persisted chain: continue the hash chain from
            # the file's last receipt and keep replay protection across
            # process restarts. (Fixed 2026-11-11 after the first live
            # run produced a chain broken at index 1 — see live-run/.)
            with open(ledger_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        r = json.loads(line)
                        self.receipts.append(r)
                        self._used_attempt_ids.add(r["verification_id"])
            self._restore_void()

    def _seals_path(self):
        return (self.ledger_path + ".seals.json") if self.ledger_path \
            else None

    def _save_seal(self, verification_id, gate_seal):
        path = self._seals_path()
        if not path:
            return
        seals = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                seals = json.load(fh)
        seals[verification_id] = gate_seal
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(seals, fh)

    def _restore_void(self):
        """Rebuild resolvable VOID contexts from the persisted ledger
        plus the gate-seal sidecar, so a witness-conflict VOID stays
        resolvable across process restarts. A VOID whose gate seal was
        never persisted cannot be re-measured and is skipped."""
        from types import SimpleNamespace
        seals = {}
        path = self._seals_path()
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                seals = json.load(fh)
        resolved = {r["resolution_of"] for r in self.receipts
                    if r.get("resolution_of")
                    and r["outcome"] in (PASS, FAIL)}
        for r in self.receipts:
            if r["outcome"] != VOID or r["reason"] != R_WITNESS_CONFLICT:
                continue
            if r["receipt_hash"] in resolved:
                continue
            vid = r["verification_id"]
            if vid not in seals:
                continue
            standins = [SimpleNamespace(
                id=b["id"], operator=b["operator"],
                failure_mode=b["failure_mode"], verdict=b["verdict"])
                for b in r["witnesses"] if b["valid"]]
            pair = self._independent_pair(standins)
            pair_ids = {w.id for w in pair} if pair else set()
            verdicts = [w.verdict for w in standins if w.id in pair_ids]
            self._void[vid] = {
                "receipt": r, "gate_seal": seals[vid],
                "agree": verdicts.count("AGREE"),
                "disagree": verdicts.count("DISAGREE"),
                "witnesses": standins,
                "resolved": False,
            }

    # -- internals ---------------------------------------------------------

    def _check_transition(self, from_outcome, to_outcome):
        if to_outcome not in _TRANSITIONS[from_outcome]:
            raise GateError("illegal outcome transition %s -> %s"
                            % (from_outcome, to_outcome))

    def _emit(self, receipt):
        """Hash, sign, chain and store one receipt."""
        receipt["prev_receipt_hash"] = \
            self.receipts[-1]["receipt_hash"] if self.receipts else ZERO_HASH
        receipt["receipt_hash"] = receipt_hash_of(receipt)
        payload = receipt["receipt_hash"].encode("utf-8")
        receipt["signature"] = self.signer.sign(payload)
        self.receipts.append(receipt)
        if self.ledger_path:
            with open(self.ledger_path, "a", encoding="utf-8") as fh:
                fh.write(canonical_json(receipt).decode("utf-8") + "\n")
        return receipt

    @staticmethod
    def _witness_facts(witness, gate_seal):
        """Measure a witness: seal integrity, signature validity, verdict.
        Tamper (output no longer hashes to its seal) is reported apart
        from mere invalidity — tampered evidence is a FAIL signal, an
        unsigned witness is just not a witness."""
        seal_ok = seal(witness.output) == witness.sealed_output
        sig_ok = False
        if witness.signature:
            try:
                sig_ok = bool(ed25519.verify(
                    witness.pubkey, witness.sealed_output.encode("utf-8"),
                    witness.signature))
            except Exception:
                sig_ok = False
        valid = seal_ok and sig_ok
        verdict = None
        if seal_ok:
            verdict = "AGREE" if witness.sealed_output == gate_seal \
                else "DISAGREE"
        return {"seal_ok": seal_ok, "signature_ok": sig_ok,
                "valid": valid, "verdict": verdict}

    @staticmethod
    def _independent_pair(witnesses):
        """Assessed independence: some pair of valid witnesses differs
        in BOTH failure_mode and operator. Returns the pair or None."""
        for i in range(len(witnesses)):
            for j in range(i + 1, len(witnesses)):
                a, b = witnesses[i], witnesses[j]
                if a.failure_mode != b.failure_mode \
                        and a.operator != b.operator:
                    return (a, b)
        return None

    # -- the attempt --------------------------------------------------------

    def attempt(self, *, test_id, test_version, population_id,
                stored_count, retrieve_served, preconditions, witnesses,
                solver, job_params, now, control=None,
                verification_id=None, declared_independence=False):
        """Run one verification attempt and emit exactly one receipt.

        retrieve_served: zero-arg callable returning the independently
            retrieved population count.
        solver: callable(job_params) -> output. Run by the gate itself,
            blind — the claimant's claimed output is never an input.
        job_params must carry temperature == 0 and a fixed seed.
        now: ISO-8601 timestamp for this attempt (caller-supplied, so
            tests are deterministic).
        """
        if job_params.get("temperature") != 0 or "seed" not in job_params:
            raise ValueError("job_params must include temperature=0 and "
                             "a fixed seed (deterministic re-execution)")
        vid = verification_id or str(uuid.uuid4())
        if vid in self._used_attempt_ids:
            raise ReplayRejected(
                "verification_id %s already used — replay rejected" % vid)
        self._used_attempt_ids.add(vid)

        # Check 1 — residual calculation: stored vs independently served.
        served_count = retrieve_served()
        difference = stored_count - served_count

        # Check 2 — precondition freshness.
        fresh = preconditions.is_fresh(now)

        # Check 3 — independent control (must be external to count).
        control_block = {"control_id": None, "source": None,
                         "result": None}
        control_failed = False
        control_discriminating = False
        if control is not None:
            actual = control.evaluate()
            result = PASS if actual == control.expected else FAIL
            control_failed = result == FAIL
            control_discriminating = bool(control.discriminates) \
                and control.is_external
            control_block = {"control_id": control.control_id,
                             "source": control.source,
                             "result": result}

        # Check 5+6 — blind deterministic re-execution, sealed BEFORE
        # any comparison takes place.
        gate_output = solver(job_params)
        gate_seal = seal(gate_output)

        # Witness measurement: seal integrity, signatures, verdicts.
        facts = [self._witness_facts(w, gate_seal) for w in witnesses]
        tampered = any(not f["seal_ok"] for f in facts)
        valid_ws = [w for w, f in zip(witnesses, facts) if f["valid"]]

        # Check 4 — instrument independence, assessed from measured
        # metadata (operator + failure mode), never merely declared.
        pair = self._independent_pair(valid_ws)
        if len(valid_ws) < 2:
            review_status = "INSUFFICIENT_WITNESSES"
        elif pair is not None:
            review_status = "ASSESSED_INDEPENDENT"
        else:
            review_status = "ASSESSED_NOT_INDEPENDENT"
        pair_ids = {w.id for w in pair} if pair else set()
        verdicts = [f["verdict"] for w, f in zip(witnesses, facts)
                    if f["valid"] and w.id in pair_ids]

        # Decision procedure, in the SPEC's check order. The first
        # matching rule decides; every rule's inputs were measured above.
        if not fresh:
            outcome, reason = VOID, R_STALE_PRECONDITIONS
        elif control_failed:
            outcome, reason = REFUSED, R_CONTROL_FAILURE
        elif tampered:
            outcome, reason = FAIL, R_SEAL_MISMATCH
        elif len(valid_ws) < 2:
            outcome, reason = REFUSED, R_INSUFFICIENT_VALID_WITNESSES
        elif pair is None:
            outcome, reason = REFUSED, R_NO_INDEPENDENT_WITNESS
        elif not control_discriminating:
            # Nothing in this attempt can distinguish the claim from
            # its negation — except a nonzero residual, which is itself
            # discriminating evidence against the claim.
            if difference != 0:
                outcome, reason = FAIL, R_RESIDUAL_MISMATCH
            else:
                outcome, reason = REFUSED, R_NO_DISCRIMINATING_CONDITION
        elif difference != 0:
            outcome, reason = FAIL, R_RESIDUAL_MISMATCH
        elif "AGREE" in verdicts and "DISAGREE" in verdicts:
            # Check 7 — conflict preserved as VOID until a third
            # placement establishes 2-of-3.
            outcome, reason = VOID, R_WITNESS_CONFLICT
        elif verdicts and all(v == "DISAGREE" for v in verdicts):
            outcome, reason = FAIL, R_REEXECUTION_MISMATCH
        else:
            outcome, reason = PASS, None

        witness_block = []
        for idx, (w, f) in enumerate(zip(witnesses, facts)):
            witness_block.append({
                "id": w.id, "operator": w.operator,
                "implementation": w.implementation,
                "data_source": w.data_source,
                "failure_mode": w.failure_mode,
                "sealed_output": w.sealed_output,
                "seal_valid": f["seal_ok"],
                "signature_valid": f["signature_ok"],
                "valid": f["valid"],
                "verdict": f["verdict"],
                "placement": idx + 1,
            })

        receipt = {
            "schema": SCHEMA,
            "verification_id": vid,
            "test_id": test_id,
            "test_version": test_version,
            "population_id": population_id,
            "snapshot_hash": sha256_hex(canonical_json({
                "test_id": test_id, "test_version": test_version,
                "population_id": population_id,
                "stored_count": stored_count,
                "served_count": served_count,
                "gate_seal": gate_seal})),
            "residual": {"stored_count": stored_count,
                         "served_count": served_count,
                         "difference": difference},
            "control": control_block,
            "preconditions": {
                "established_at": preconditions.established_at,
                "expires_at": preconditions.expires_at,
                "valid": fresh},
            "witnesses": witness_block,
            "instrument_independence": {
                "declared": bool(declared_independence),
                "review_status": review_status},
            "outcome": outcome,
            "reason": reason,
            "external_anchor": None,
            "attempted_at": now,
            "resolution_of": None,
            "signer": self.signer.meta(),
        }
        self._check_transition(None, outcome)
        receipt = self._emit(receipt)

        if outcome == VOID and reason == R_WITNESS_CONFLICT:
            self._void[vid] = {
                "receipt": receipt, "gate_seal": gate_seal,
                "agree": verdicts.count("AGREE"),
                "disagree": verdicts.count("DISAGREE"),
                "witnesses": list(witnesses),
                "resolved": False,
            }
            self._save_seal(vid, gate_seal)
        return receipt

    # -- VOID resolution ------------------------------------------------------

    def resolve(self, verification_id, third_witness, now):
        """Attempt a third placement for a VOID (witness-conflict)
        attempt. Emits exactly one resolution receipt. A valid,
        independent third witness resolves 2-of-3 to PASS or FAIL; an
        invalid, tampered, or non-independent one leaves the attempt
        VOID (and it may be retried with another placement). Resolving
        a PASS / FAIL / REFUSED attempt is an error — REFUSED is
        terminal and can never become a PASS."""
        ctx = self._void.get(verification_id)
        if ctx is None:
            raise GateError("no resolvable VOID attempt for %s"
                            % verification_id)
        if ctx["resolved"]:
            raise GateError("attempt %s already resolved" % verification_id)
        original = ctx["receipt"]
        self._check_transition(VOID, VOID)  # resolution path is legal

        f = self._witness_facts(third_witness, ctx["gate_seal"])
        independent = f["valid"] and all(
            third_witness.failure_mode != w.failure_mode
            and third_witness.operator != w.operator
            for w in ctx["witnesses"])
        agree, disagree = ctx["agree"], ctx["disagree"]
        if independent:
            if f["verdict"] == "AGREE":
                agree += 1
            else:
                disagree += 1
            if agree >= 2:
                outcome, reason = PASS, R_THIRD_PLACEMENT_QUORUM
            elif disagree >= 2:
                outcome, reason = FAIL, R_THIRD_PLACEMENT_QUORUM
            else:
                outcome, reason = VOID, R_THIRD_PLACEMENT_FAILED
        else:
            outcome, reason = VOID, R_THIRD_PLACEMENT_FAILED
        self._check_transition(VOID, outcome)

        third_block = {
            "id": third_witness.id, "operator": third_witness.operator,
            "implementation": third_witness.implementation,
            "data_source": third_witness.data_source,
            "failure_mode": third_witness.failure_mode,
            "sealed_output": third_witness.sealed_output,
            "seal_valid": f["seal_ok"],
            "signature_valid": f["signature_ok"],
            "valid": f["valid"],
            "verdict": f["verdict"],
            "placement": len(original["witnesses"]) + 1,
        }
        receipt = {
            "schema": SCHEMA,
            "verification_id": verification_id,
            "test_id": original["test_id"],
            "test_version": original["test_version"],
            "population_id": original["population_id"],
            "snapshot_hash": original["snapshot_hash"],
            "residual": dict(original["residual"]),
            "control": dict(original["control"]),
            "preconditions": dict(original["preconditions"]),
            "witnesses": list(original["witnesses"]) + [third_block],
            "instrument_independence": {
                "declared": original["instrument_independence"]["declared"],
                "review_status": "ASSESSED_INDEPENDENT" if independent
                                 else "ASSESSED_NOT_INDEPENDENT"},
            "outcome": outcome,
            "reason": reason,
            "external_anchor": None,
            "attempted_at": now,
            "resolution_of": original["receipt_hash"],
            "signer": self.signer.meta(),
        }
        receipt = self._emit(receipt)
        if outcome in (PASS, FAIL):
            ctx["resolved"] = True
        return receipt

    def chain_verify(self, signer=None):
        """Verify this gate's own receipt chain."""
        return chain_verify(self.receipts,
                            signer=signer if signer is not None
                            else self.signer)
