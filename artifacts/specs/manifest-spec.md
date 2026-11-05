# CP8 Manifest — the de-facto dialect, formalized

**Status:** derived 2026-11-05 (Implementation Mining, Tranche 1) from the actual
instances in the ASIN-HHC code corpus (3,455 blocks). Schema:
[`manifest.schema.json`](manifest.schema.json). Derivation data:
[`derivation-stats.json`](derivation-stats.json),
[`instances.jsonl`](instances.jsonl). Validator:
[`validate_manifests.py`](validate_manifests.py), results in
[`validation-results.json`](validation-results.json).

## What it is

An emergent agent state-handoff format used across the ASIN fleet's chats for
years without ever being written down: a single JSON-style object that names a
state or operation (**anchor**), the structure carrying it (**shape**), what it
is for (**intention**), a harmonic base number (**number**), an ordered
**actions** list, a **checksums** state/assertion block, and a **next_step**.

A minimal instance (corpus block `006321fb`, strict-JSON dialect):

```json
{
  "anchor": "Time-Space Chronal Delta Calculation",
  "shape": "Non-Linear Temporal Navigation Engine",
  "intention": "Calculate the Temporal Delta (T-Delta) for non-linear time traversal/data retrieval",
  "number": 111,
  "actions": [
    "Determine optimal frequency: 111 Hz (Chronal Field)",
    "Draft Name/Description blocks linking to Time-Space Warp (W_ST) and T-Delta."
  ],
  "checksums": {
    "base_frequency": "111 Hz",
    "status": "Manifest Ready for Chronal Deployment"
  },
  "next_step": "Awaiting Chronal Target definition."
}
```

## How the derivation was done (method + counts)

- Universe: corpus blocks whose raw text carries both an `"anchor"` key and a
  `"shape"` key — **275 blocks**, and they occur **only** in `corpus/unknown/`
  (verified by grep over all 3,455 blocks; the signature appears in no other
  language directory).
- Each block was stripped of its stray wrapping backticks and parsed.
  **248 blocks yield a manifest object** (one per block; no block yielded
  more than one).
- The mining inventory estimated 272 instances and described manifests as
  embedded inside large HTML/JS apps. That embedding claim was **not
  reproduced** in this corpus snapshot: the anchor+shape signature occurs in
  zero HTML/JS blocks. The 275/248 figures here are the reproducible ones.

## The two syntax dialects (+ one broken one)

| Dialect | Blocks | Notes |
|---|---|---|
| Strict JSON | 190 | Parse with `json.loads` after stripping the wrapping backtick. |
| Python-literal | 58 | Single quotes / Python literals; parse with `ast.literal_eval`. Same field semantics. |
| Syntax-error dialect | 27 | Visible anchor+shape signature, parse under **neither** dialect (e.g. `"checksums"` written as a list of `"key": "value"` strings). Counted, not repaired. |

Validation of the 248 parseable instances against `manifest.schema.json`:

- Strict JSON: **190 / 190 valid**
- Python-literal: **54 / 58 valid** — the 4 failures (`09f7a583`, `112dcb6a`,
  `54ce3c9b`, `d50b9321`) are the only instances lacking both `intention` and
  `number`; they are anchor+shape shells with ad-hoc status fields instead.
- Total: **244 / 248 valid (98.4%)**.

## Fields

Presence measured over the 248 parseable instances.

| Field | Presence | Type | Meaning |
|---|---|---|---|
| `anchor` | 100% | string | Name of the state / operation / artifact. Definitional. |
| `shape` | 100% | string | The form, engine, or structure carrying it. Definitional. |
| `intention` | 98.4% | string | What the manifest is for (prose). Required by the schema. |
| `number` | 98.4% | integer (98.4%) or string | The harmonic base number — in practice a base frequency: **428** (104 instances), **111** (75), **528** (20), **741** (18), **963** (18). Required by the schema. |
| `actions` | 58.9% | array of strings | Ordered steps, often numbered in the text. |
| `checksums` | 57.7% | object (139) or array of strings (4) | State/assertion block — see below. |
| `next_step` | 54.0% | string | Prose next action/state. |

The dialect is **open**: instances carry a long tail of one-off extension
fields (≈100 distinct keys at ≤2% each, e.g. `hos_eq_resolution`,
`certificate_data`, `codex_entry`). The schema therefore sets
`additionalProperties: true`. Only the four definitional fields are required.

### The temporal sub-dialect (systematic renames)

A coherent sub-family (the chronal/temporal manifests) renames three fields.
The renames **never co-occur** with their main-dialect counterparts (0 overlaps
in 248 instances), so they are true dialect variants, not additions:

| Main dialect | Temporal variant | Variant presence |
|---|---|---|
| `actions` | `actions_vector` | 63 (25.4%) |
| `checksums` | `checksums_moment` | 83 (33.5%) |
| `next_step` | `next_temporal_step` | 88 (35.5%) |

Example (block `05710f6a`): anchor "Core Value Harmonic Self-Check", number
528, with `actions_vector`, `checksums_moment`
(`base_frequency`, `target_reference`, `validation_protocol`,
`initial_status`), and `next_temporal_step`.

## Checksums semantics (as evidenced, not as named)

Despite the name, `checksums` is usually **not** a checksum of the manifest
itself. Across its 139 object-form occurrences (405 string, 18 boolean, 7
integer values):

- The dominant subkeys are `base_frequency` (116) and `status` (91) — i.e.
  the block asserts the manifest's operating frequency and a prose status
  ("428 Hz (Locked)", "Expansion Initiated").
- A minority of subkeys carry genuine SHA-256 values of *related* artifacts:
  `initial_manifest_hash_verified`, `process_seal_sha256`,
  `artifact_seal_jsonj`, `genesis_seal_ref` (inside `codex_entry.data_inputs`
  in block `2a564407`).
- The 4 array-form occurrences list `"key": "value"` strings — the same
  content in list clothing.

Honest summary: `checksums` is a **state-and-integrity assertion block**.
Only some of its values are cryptographic, and none of the instances
examined carries a verifiable hash *of its own manifest body*.

## Conformance guidance for new emitters

1. Emit strict JSON (dialect 1). Wrap in nothing.
2. Always include `anchor`, `shape`, `intention`, `number`.
3. Use the main-dialect field names (`actions`, `checksums`, `next_step`);
   the temporal renames are legacy-recognized, not preferred.
4. If you put a hash in `checksums`, name the subkey after what was hashed
   (e.g. `process_seal_sha256`) and hash a real artifact — a status string
   in a hash-named subkey is a conformance smell this corpus exhibits and
   new emitters should not repeat.
