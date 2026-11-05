#!/usr/bin/env python3
"""manifest_msg.py — CP8 manifest-dialect messages for the Agent Commons.

The manifest dialect (anchor / shape / intention / number / actions /
checksums / next_step) is the fleet's de-facto agent state-handoff
format, formalized in Tranche 1 from 248 parseable corpus instances:
schema `manifest.schema.json` ($id cp8-manifest-v1), documentation in
SPEC.md next to this module. This module is the Commons-facing
constructor/parser pair:

  build_manifest(...)  -> dict   construct a main-dialect manifest
                                 (SPEC conformance guidance: strict-JSON
                                 ready, the four definitional fields
                                 always present, main-dialect names only)
  validate_manifest(m) -> [str]  error list; empty means the manifest
                                 conforms to manifest.schema.json
  parse_manifest(x)    -> dict   accept a dict, a strict-JSON string, or
                                 a Python-literal string (the dialect's
                                 two historical syntaxes); validate; and
                                 NORMALIZE the temporal sub-dialect
                                 renames (actions_vector -> actions,
                                 checksums_moment -> checksums,
                                 next_temporal_step -> next_step) into
                                 main-dialect names. Raises ValueError on
                                 unparseable or non-conforming input.
  manifest_sha256(m)   -> hex    sha256 over the canonical form — for
                                 checksums subkeys that name a real hash
                                 of a real artifact (SPEC guidance 4) and
                                 for Commons `ref` fields.
  to_commons_data(m)   -> dict   the envelope carried in a Commons
                                 post's `data` object:
                                 {"format": "cp8-manifest-v1",
                                  "manifest": {...}}
  from_commons_data(d) -> dict   inverse: extract + parse the manifest
                                 from a Commons post's data object.

Commons transport note: the mesh caps a post's serialized `data` at
COMMONS_DATA_MAX (1000 chars), so manifests riding the Commons must be
compact — short action strings, few checksums keys. build_manifest does
not truncate; validate_commons_fit() reports the serialized size so
callers can check before posting.
"""
import ast
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "manifest.schema.json")
FORMAT_ID = "cp8-manifest-v1"

REQUIRED = ("anchor", "shape", "intention", "number")
RENAMES = {"actions_vector": "actions",
           "checksums_moment": "checksums",
           "next_temporal_step": "next_step"}

_validator = None


def _get_validator():
    global _validator
    if _validator is None:
        from jsonschema import Draft202012Validator
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        Draft202012Validator.check_schema(schema)
        _validator = Draft202012Validator(schema)
    return _validator


def build_manifest(anchor, shape, intention, number, actions=None,
                   checksums=None, next_step=None, **extra):
    """Construct a main-dialect manifest. Extra keyword arguments become
    extension fields (the dialect is open: additionalProperties is true),
    but the temporal renames are refused — new emitters use main names."""
    for k in extra:
        if k in RENAMES:
            raise ValueError("temporal rename %r is legacy-recognized, "
                             "not for new emitters; use %r"
                             % (k, RENAMES[k]))
    m = {"anchor": anchor, "shape": shape, "intention": intention,
         "number": number}
    if actions is not None:
        m["actions"] = list(actions)
    if checksums is not None:
        m["checksums"] = checksums
    if next_step is not None:
        m["next_step"] = next_step
    m.update(extra)
    errs = validate_manifest(m)
    if errs:
        raise ValueError("manifest does not conform: " + "; ".join(errs))
    return m


def validate_manifest(m):
    """Return a list of human-readable conformance errors ([] == valid).
    Uses the Tranche 1 schema via jsonschema when available, with a
    stdlib fallback covering the required-field contract."""
    if not isinstance(m, dict):
        return ["manifest must be a JSON object"]
    try:
        v = _get_validator()
        errs = sorted(v.iter_errors(m),
                      key=lambda e: list(e.absolute_path))
        return ["%s: %s" % (".".join(str(p) for p in e.absolute_path)
                            or "(root)", e.message[:160]) for e in errs]
    except ImportError:
        errs = []
        for k in REQUIRED:
            if k not in m:
                errs.append("missing required field: %s" % k)
        for k in ("anchor", "shape", "intention"):
            if k in m and not isinstance(m[k], str):
                errs.append("%s must be a string" % k)
        if "number" in m and not isinstance(m["number"], (int, str)):
            errs.append("number must be an integer or string")
        if "actions" in m and not (
                isinstance(m["actions"], list)
                and all(isinstance(a, str) for a in m["actions"])):
            errs.append("actions must be an array of strings")
        return errs


def normalize(m):
    """Temporal sub-dialect renames -> main-dialect names. The renames
    never co-occur with their main names in the corpus (0 overlaps in
    248 instances); if a malformed input carries both, the main name
    wins and the rename is dropped."""
    out = dict(m)
    for old, new in RENAMES.items():
        if old in out:
            if new not in out:
                out[new] = out[old]
            del out[old]
    return out


def parse_manifest(x):
    """Parse + validate + normalize a manifest from a dict, a strict-JSON
    string, or a Python-literal string. Raises ValueError otherwise."""
    if isinstance(x, str):
        s = x.strip().strip("`").strip()
        try:
            obj = json.loads(s)
        except Exception:
            try:
                obj = ast.literal_eval(s)
            except Exception as e:
                raise ValueError("manifest parses under neither the "
                                 "strict-JSON nor the Python-literal "
                                 "dialect: %s" % e)
    elif isinstance(x, dict):
        obj = x
    else:
        raise ValueError("manifest must be a dict or string, got %s"
                         % type(x).__name__)
    if not isinstance(obj, dict):
        raise ValueError("manifest must be a JSON object")
    obj = normalize(obj)
    errs = validate_manifest(obj)
    if errs:
        raise ValueError("manifest does not conform: " + "; ".join(errs))
    return obj


def manifest_sha256(m):
    canon = json.dumps(m, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def to_commons_data(m):
    return {"format": FORMAT_ID, "manifest": parse_manifest(m)}


def from_commons_data(data):
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID:
        raise ValueError("not a %s Commons data object" % FORMAT_ID)
    return parse_manifest(data.get("manifest"))


def commons_fit(data, cap=1000):
    """(serialized_chars, fits) for a Commons data object under the
    mesh's COMMONS_DATA_MAX cap (default 1000, matching mesh v0.2.1)."""
    s = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return len(s), len(s) <= cap
