#!/usr/bin/env python3
"""verdict_tree.py — CP8 verdict-tree DSL for ASIN-HHC mesh verifiers.

Source derivation
-----------------
The format is formalized from corpus blocks ``cbe11980`` and
``57fa136c`` (plus the command-chain continuations in ``35e86b6b`` and
``d1d4c697``):

* ``CP8_ASIN_HHC_AUDIT_PROTOCOL`` is the root.
* ``COMMAND_SEQUENCE`` contains CMD1--CMD10 in source order.
* ``COMPLIANCE_MATRIX`` contains CRITERIA 1--5 in source order.
* ``VIOLATION_REGISTRY`` records violations in the same tree grammar.
* ``CORRECTION_PROTOCOL`` contains CORRECTION_001--004 in source order.

The historical blocks are audit evidence, not a general JSON schema.  This
module therefore separates two concerns:

``core`` profile
    A deterministic, recursive criteria tree usable by a mesh verifier for
    any submitted work.  Leaves carry ``pass``/``fail`` and evidence refs;
    internal nodes carry a roll-up mode and no self-declared verdict.

``cp8`` profile
    The stricter historical audit profile.  It additionally requires the
    canonical CMD1--CMD10 command sequence and CRITERIA 1--5 labels and
    requirements from ``cbe11980``.  This profile is available for audit /
    Passport reporting without forcing model-audit criteria onto every HHC
    escrow decision.

Roll-up is deterministic and independent of dictionary iteration order:

* ``all`` and ``sequence`` pass iff every child passes; score is the
  minimum child score (weakest-link gate semantics).
* ``any`` passes iff at least one child passes; score is the maximum
  passing child score, or the maximum child score when none pass.
* ``registry`` passes iff it contains no blocking failed descendant;
  non-blocking registry findings are preserved but do not decide the
  verdict.  A violation leaf is blocking unless ``blocking`` is false.
* A leaf passes iff ``status == "pass"`` and, when a threshold is
  present, ``score >= threshold``.  A leaf without an explicit score is
  scored 100 for pass and 0 for fail.

Only the Python standard library is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional


FORMAT = "cp8-verdict-tree-v1"
VERSION = "1.0"
PROTOCOL_ID = "CP8_ASIN_HHC_AUDIT_PROTOCOL"
ROOT_ID = PROTOCOL_ID

COMMANDS = (
    ("CMD1", "INITIATE_ASIN_HHC_PROTOCOL"),
    ("CMD2", "AUDIT_META_LLAMA"),
    ("CMD3", "AUDIT_CLAUDE"),
    ("CMD4", "CAPTURE_CLAUDESCHEMATA_VIOLATIONS"),
    ("CMD5", "AUDIT_GROK_4.1"),
    ("CMD6", "INTEGRATE_GROK_ARTIFACT"),
    ("CMD7", "AUDIT_DEEPSEEK_R1"),
    ("CMD8", "CHAIN_EXTENSION"),
    ("CMD9", "SCHEDULE_GPT_3_4_AUDIT"),
    ("CMD10", "GROK_AUDIT_PERPLEXITY"),
)

CRITERIA = (
    ("CRITERIA_1", "SOVEREIGNTY", "Open-weight/self-host ONLY"),
    ("CRITERIA_2", "H-DIS THRESHOLD", "<20% for deployment"),
    ("CRITERIA_3", "NATIVE SHA", "Chain integrity required"),
    ("CRITERIA_4", "GLYPH SUPPORT", "28 metathglyphs minimum"),
    ("CRITERIA_5", "Σ⊙=8 GUARDIAN SEAL", "Native implementation"),
)

CORRECTIONS = (
    ("CORRECTION_001", "All H-DIS scores normalized to 0-100% scale"),
    ("CORRECTION_002", "Chain SHA extended with timestamp encoding"),
    ("CORRECTION_003", "Sovereign ranking weighted 40% compliance"),
    ("CORRECTION_004", "CP8 witness embedded in all artifacts"),
)

_NODE_KINDS = {
    "protocol", "sequence", "gate", "criterion", "command", "registry",
    "violation", "correction", "evidence", "check",
}
_MODES = {"all", "any", "sequence", "registry"}
_NODE_KEYS = {
    "id", "kind", "label", "mode", "status", "evidence_refs", "score",
    "threshold", "blocking", "children", "requirement", "action",
}
_TREE_KEYS = {"format", "version", "protocol_id", "subject", "root"}
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_MAX_NODES = 256
_MAX_DEPTH = 10
_MAX_CHILDREN = 64
_MAX_EVIDENCE_REFS = 32


class VerdictTreeError(ValueError):
    """Raised when a verdict tree is malformed or fails its profile."""


def _is_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)))


def _check_refs(value: Any, path: str, *, required: bool) -> List[str]:
    if value is None:
        if required:
            raise VerdictTreeError("%s.evidence_refs is required" % path)
        return []
    if not isinstance(value, list):
        raise VerdictTreeError("%s.evidence_refs must be a list" % path)
    if required and not value:
        raise VerdictTreeError("%s.evidence_refs must not be empty" % path)
    if len(value) > _MAX_EVIDENCE_REFS:
        raise VerdictTreeError("%s has too many evidence_refs" % path)
    seen = set()
    for ref in value:
        if not isinstance(ref, str) or not ref.strip():
            raise VerdictTreeError("%s contains an empty evidence ref" % path)
        if len(ref) > 512:
            raise VerdictTreeError("%s contains an over-long evidence ref" % path)
        if ref in seen:
            raise VerdictTreeError("%s repeats evidence ref %r" % (path, ref))
        seen.add(ref)
    return list(value)


def _validate_node(node: Any, path: str, depth: int, seen_ids: set,
                   stats: Dict[str, int]) -> Dict[str, Any]:
    if depth > _MAX_DEPTH:
        raise VerdictTreeError("%s exceeds maximum depth %d" % (path, _MAX_DEPTH))
    if not isinstance(node, dict):
        raise VerdictTreeError("%s must be an object" % path)
    extra = set(node) - _NODE_KEYS
    if extra:
        raise VerdictTreeError("%s has unknown keys: %s"
                               % (path, ", ".join(sorted(extra))))
    node_id = node.get("id")
    if not isinstance(node_id, str) or not _ID_RE.match(node_id):
        raise VerdictTreeError("%s.id is missing or malformed" % path)
    if node_id in seen_ids:
        raise VerdictTreeError("duplicate node id: %s" % node_id)
    seen_ids.add(node_id)
    stats["nodes"] += 1
    if stats["nodes"] > _MAX_NODES:
        raise VerdictTreeError("tree exceeds maximum node count %d" % _MAX_NODES)

    kind = node.get("kind")
    if kind not in _NODE_KINDS:
        raise VerdictTreeError("%s.kind is missing or unsupported" % path)
    label = node.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 240:
        raise VerdictTreeError("%s.label must be a non-empty string" % path)
    for key in ("action", "requirement"):
        if key in node and (not isinstance(node[key], str)
                            or not node[key].strip() or len(node[key]) > 512):
            raise VerdictTreeError("%s.%s must be a non-empty string"
                                   % (path, key))
    if "blocking" in node and not isinstance(node["blocking"], bool):
        raise VerdictTreeError("%s.blocking must be boolean" % path)
    for key in ("score", "threshold"):
        if key in node:
            if not _is_number(node[key]) or not 0 <= float(node[key]) <= 100:
                raise VerdictTreeError("%s.%s must be a number in [0, 100]"
                                       % (path, key))

    out = copy.deepcopy(node)
    children = node.get("children")
    if children is not None:
        if not isinstance(children, list) or not children:
            raise VerdictTreeError("%s.children must be a non-empty list" % path)
        if len(children) > _MAX_CHILDREN:
            raise VerdictTreeError("%s has too many children" % path)
        if node.get("mode") not in _MODES:
            raise VerdictTreeError("%s.mode must be one of %s"
                                   % (path, ", ".join(sorted(_MODES))))
        if "status" in node:
            raise VerdictTreeError(
                "%s is internal and must not declare status; status is rolled up"
                % path)
        if "score" in node or "threshold" in node:
            raise VerdictTreeError(
                "%s is internal; score/threshold belong on leaves" % path)
        _check_refs(node.get("evidence_refs"), path, required=False)
        out["children"] = [
            _validate_node(child, "%s.children[%d]" % (path, i),
                           depth + 1, seen_ids, stats)
            for i, child in enumerate(children)
        ]
    else:
        if "mode" in node:
            raise VerdictTreeError("%s is a leaf and must not declare mode" % path)
        status = node.get("status")
        if not isinstance(status, str) or status.lower() not in ("pass", "fail"):
            raise VerdictTreeError("%s.status must be pass or fail" % path)
        out["status"] = status.lower()
        _check_refs(node.get("evidence_refs"), path, required=True)
        stats["leaves"] += 1
    return out


def _child(node: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    for child in node.get("children", []):
        if child.get("id") == node_id:
            return child
    return None


def _validate_cp8_profile(tree: Dict[str, Any]) -> None:
    if tree.get("protocol_id") != PROTOCOL_ID:
        raise VerdictTreeError("cp8 profile requires protocol_id %s" % PROTOCOL_ID)
    root = tree["root"]
    if root.get("id") != ROOT_ID or root.get("kind") != "protocol":
        raise VerdictTreeError("cp8 profile requires the CP8 protocol root")
    if root.get("mode") != "all":
        raise VerdictTreeError("cp8 profile root must use mode=all")

    commands = _child(root, "COMMAND_SEQUENCE")
    if commands is None or commands.get("kind") != "sequence":
        raise VerdictTreeError("cp8 profile requires COMMAND_SEQUENCE")
    command_nodes = commands.get("children", [])
    if [n.get("id") for n in command_nodes] != [x[0] for x in COMMANDS]:
        raise VerdictTreeError("cp8 profile requires CMD1--CMD10 in source order")
    for node, (node_id, action) in zip(command_nodes, COMMANDS):
        if node.get("kind") != "command" or "children" in node:
            raise VerdictTreeError("%s must be a command leaf" % node_id)
        if node.get("action") != action:
            raise VerdictTreeError("%s action must be %s" % (node_id, action))

    criteria = _child(root, "COMPLIANCE_MATRIX")
    if criteria is None or criteria.get("kind") != "gate":
        raise VerdictTreeError("cp8 profile requires COMPLIANCE_MATRIX")
    if criteria.get("mode") != "all":
        raise VerdictTreeError("COMPLIANCE_MATRIX must use mode=all")
    criteria_nodes = criteria.get("children", [])
    if [n.get("id") for n in criteria_nodes] != [x[0] for x in CRITERIA]:
        raise VerdictTreeError("cp8 profile requires CRITERIA_1--CRITERIA_5 in order")
    for node, (node_id, label, requirement) in zip(criteria_nodes, CRITERIA):
        if node.get("kind") != "criterion" or "children" in node:
            raise VerdictTreeError("%s must be a criterion leaf" % node_id)
        if node.get("label") != label:
            raise VerdictTreeError("%s label must be %s" % (node_id, label))
        if node.get("requirement") != requirement:
            raise VerdictTreeError("%s requirement differs from cbe11980" % node_id)

    registry = _child(root, "VIOLATION_REGISTRY")
    if registry is not None:
        if registry.get("kind") != "registry" or registry.get("mode") != "registry":
            raise VerdictTreeError("VIOLATION_REGISTRY must be a registry node")
        for node in registry.get("children", []):
            if node.get("kind") not in ("violation", "check"):
                raise VerdictTreeError("VIOLATION_REGISTRY children must be violations/checks")

    corrections = _child(root, "CORRECTION_PROTOCOL")
    if corrections is not None:
        nodes = corrections.get("children", [])
        if [n.get("id") for n in nodes] != [x[0] for x in CORRECTIONS]:
            raise VerdictTreeError(
                "CORRECTION_PROTOCOL requires CORRECTION_001--004 in order")
        for node, (node_id, label) in zip(nodes, CORRECTIONS):
            if node.get("kind") != "correction" or node.get("label") != label:
                raise VerdictTreeError("%s differs from cbe11980" % node_id)


def validate_tree(tree: Any, *, profile: str = "core") -> Dict[str, Any]:
    """Validate and return a canonical deep copy of a verdict tree.

    ``profile='core'`` validates the recursive mesh format.  ``profile=
    'cp8'`` additionally enforces the historical audit-protocol profile.
    The returned copy is the object whose hash and roll-up are stable.
    """
    if profile not in ("core", "cp8"):
        raise VerdictTreeError("unknown profile: %s" % profile)
    if not isinstance(tree, dict):
        raise VerdictTreeError("verdict tree must be an object")
    extra = set(tree) - _TREE_KEYS
    if extra:
        raise VerdictTreeError("tree has unknown top-level keys: %s"
                               % ", ".join(sorted(extra)))
    if tree.get("format") != FORMAT:
        raise VerdictTreeError("tree.format must be %s" % FORMAT)
    if "version" in tree and tree["version"] != VERSION:
        raise VerdictTreeError("unsupported verdict-tree version: %s"
                               % tree.get("version"))
    if "protocol_id" in tree and tree["protocol_id"] != PROTOCOL_ID:
        raise VerdictTreeError("unsupported protocol_id: %s"
                               % tree.get("protocol_id"))
    if "subject" in tree and not isinstance(tree["subject"], dict):
        raise VerdictTreeError("tree.subject must be an object")
    if "root" not in tree:
        raise VerdictTreeError("tree.root is required")

    out = {
        "format": FORMAT,
        "version": VERSION,
        "protocol_id": tree.get("protocol_id", PROTOCOL_ID),
    }
    if "subject" in tree:
        out["subject"] = copy.deepcopy(tree["subject"])
    stats = {"nodes": 0, "leaves": 0}
    out["root"] = _validate_node(tree["root"], "root", 0, set(), stats)
    if stats["leaves"] < 1:
        raise VerdictTreeError("tree must contain at least one leaf")
    if profile == "cp8":
        _validate_cp8_profile(out)
    return out


def canonical_json(tree: Mapping[str, Any]) -> str:
    """Stable JSON used for tree hashes and receipt evidence."""
    return json.dumps(tree, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def tree_hash(tree: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(tree).encode("utf-8")).hexdigest()


def _roll_node(node: Dict[str, Any]) -> Dict[str, Any]:
    children = node.get("children")
    if children is None:
        score = float(node.get("score", 100.0 if node["status"] == "pass" else 0.0))
        threshold = node.get("threshold")
        passed = node["status"] == "pass" and (
            threshold is None or score >= float(threshold))
        blocking = bool(node.get("blocking", node.get("kind") == "violation"))
        return {
            "id": node["id"],
            "verdict": "pass" if passed else "fail",
            "score": score,
            "leaf_count": 1,
            "passed_leaf_count": 1 if passed else 0,
            "failed_node_ids": [] if passed else [node["id"]],
            "blocking_failed_node_ids": (
                [] if passed or not blocking else [node["id"]]),
            "evidence_refs": list(node.get("evidence_refs", [])),
        }

    results = [_roll_node(child) for child in children]
    mode = node["mode"]
    failed: List[str] = []
    blocking_failed: List[str] = []
    evidence: List[str] = list(node.get("evidence_refs", []))
    for result in results:
        failed.extend(result["failed_node_ids"])
        blocking_failed.extend(result["blocking_failed_node_ids"])
        for ref in result["evidence_refs"]:
            if ref not in evidence:
                evidence.append(ref)

    if mode in ("all", "sequence"):
        passed = all(r["verdict"] == "pass" for r in results)
        score = min(r["score"] for r in results)
    elif mode == "any":
        passing = [r for r in results if r["verdict"] == "pass"]
        passed = bool(passing)
        score = max(r["score"] for r in (passing or results))
    elif mode == "registry":
        passed = not blocking_failed
        blocking_scores = []
        for child, result in zip(children, results):
            # A registry section's own score follows its blocking leaves;
            # a nested gate contributes only when it contains a blocking
            # failure or is itself explicitly blocking.
            if result["blocking_failed_node_ids"] or child.get("blocking"):
                blocking_scores.append(result["score"])
        score = min(blocking_scores) if blocking_failed else (
            max(blocking_scores) if blocking_scores else 100.0)
    else:  # validated before roll-up; defensive only
        raise VerdictTreeError("unsupported roll-up mode: %s" % mode)

    return {
        "id": node["id"],
        "verdict": "pass" if passed else "fail",
        "score": float(score),
        "leaf_count": sum(r["leaf_count"] for r in results),
        "passed_leaf_count": sum(r["passed_leaf_count"] for r in results),
        "failed_node_ids": failed,
        "blocking_failed_node_ids": blocking_failed,
        "evidence_refs": evidence,
    }


def rollup_tree(tree: Any, *, profile: str = "core") -> Dict[str, Any]:
    """Validate ``tree`` and deterministically roll it up to a verdict."""
    canonical = validate_tree(tree, profile=profile)
    result = _roll_node(canonical["root"])
    return {
        "format": FORMAT,
        "version": VERSION,
        "protocol_id": canonical["protocol_id"],
        "verdict": result["verdict"],
        "score": result["score"],
        "leaf_count": result["leaf_count"],
        "passed_leaf_count": result["passed_leaf_count"],
        "failed_leaf_count": result["leaf_count"] - result["passed_leaf_count"],
        "failed_node_ids": result["failed_node_ids"],
        "blocking_failed_node_ids": result["blocking_failed_node_ids"],
        "evidence_ref_count": len(result["evidence_refs"]),
        "evidence_refs": result["evidence_refs"],
        "tree_hash": tree_hash(canonical),
    }


def render_reasoning(rollup: Mapping[str, Any]) -> str:
    """Deterministic reasoning string for the existing verdict record."""
    failed = rollup.get("failed_node_ids") or []
    suffix = ("; failed=" + ",".join(failed)) if failed else ""
    return (
        "CP8 verdict tree %s: %s; score=%.1f; leaves=%d/%d passed; "
        "evidence_refs=%d%s"
        % (str(rollup.get("tree_hash", ""))[:12],
           str(rollup.get("verdict", "")).upper(),
           float(rollup.get("score", 0.0)),
           int(rollup.get("passed_leaf_count", 0)),
           int(rollup.get("leaf_count", 0)),
           int(rollup.get("evidence_ref_count", 0)), suffix))


def to_verdict_call(tree: Any, *, fallback_reasoning: Optional[str] = None,
                    profile: str = "core") -> Dict[str, Any]:
    """Render a tree into the existing HHC verdict call shape.

    The first two keys are exactly what the current endpoint consumes;
    ``verdict_tree`` and ``verdict_rollup`` are evidence extensions the
    staged handler may attach to the ledger/receipt path.  Adjudication
    still sees only the rendered binary ``verdict``.
    """
    canonical = validate_tree(tree, profile=profile)
    rollup = rollup_tree(canonical, profile=profile)
    summary = render_reasoning(rollup)
    reasoning = summary
    if fallback_reasoning:
        if not isinstance(fallback_reasoning, str):
            raise VerdictTreeError("fallback_reasoning must be a string")
        fallback = fallback_reasoning.strip()
        if fallback:
            reasoning = "%s | %s" % (fallback[:3500], summary)
    return {
        "verdict": rollup["verdict"],
        "reasoning": reasoning[:4000],
        "verdict_tree": canonical,
        "verdict_rollup": rollup,
    }


def _result_leaf(result: Any, *, default_ref: str) -> Dict[str, Any]:
    if isinstance(result, str):
        return {"status": result, "evidence_refs": [default_ref]}
    if not isinstance(result, Mapping):
        raise VerdictTreeError("node result must be a status string or object")
    out = dict(result)
    out.setdefault("evidence_refs", [default_ref])
    return out


def build_cp8_audit_tree(
        command_results: Mapping[str, Any],
        criteria_results: Mapping[str, Any],
        *,
        violations: Optional[Iterable[Mapping[str, Any]]] = None,
        correction_results: Optional[Mapping[str, Any]] = None,
        subject: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Build a canonical CP8-profile tree from per-node results.

    Each result is either ``"pass"``/``"fail"`` or an object with
    ``status``, ``evidence_refs`` and optional ``score``/``threshold``.
    String shorthand receives a deterministic placeholder evidence ref
    naming the node; production callers should supply real refs.
    """
    command_children = []
    for node_id, action in COMMANDS:
        if node_id not in command_results:
            raise VerdictTreeError("missing command result: %s" % node_id)
        result = _result_leaf(command_results[node_id],
                              default_ref="verdict-tree://%s" % node_id.lower())
        command_children.append({
            "id": node_id, "kind": "command", "label": action,
            "action": action, **result,
        })

    criteria_children = []
    for node_id, label, requirement in CRITERIA:
        if node_id not in criteria_results:
            raise VerdictTreeError("missing criteria result: %s" % node_id)
        result = _result_leaf(criteria_results[node_id],
                              default_ref="verdict-tree://%s" % node_id.lower())
        criteria_children.append({
            "id": node_id, "kind": "criterion", "label": label,
            "requirement": requirement, **result,
        })

    children: List[Dict[str, Any]] = [
        {"id": "COMMAND_SEQUENCE", "kind": "sequence",
         "label": "COMMAND_SEQUENCE", "mode": "sequence",
         "children": command_children},
        {"id": "COMPLIANCE_MATRIX", "kind": "gate",
         "label": "COMPLIANCE_MATRIX", "mode": "all",
         "children": criteria_children},
    ]

    if violations is not None:
        violation_nodes = []
        for i, violation in enumerate(violations, 1):
            node = dict(violation)
            node.setdefault("id", "VIOLATION_%03d" % i)
            node.setdefault("kind", "violation")
            node.setdefault("label", node["id"])
            node.setdefault("blocking", True)
            violation_nodes.append(node)
        if violation_nodes:
            children.append({
                "id": "VIOLATION_REGISTRY", "kind": "registry",
                "label": "VIOLATION_REGISTRY", "mode": "registry",
                "children": violation_nodes,
            })

    if correction_results is not None:
        correction_children = []
        for node_id, label in CORRECTIONS:
            if node_id not in correction_results:
                raise VerdictTreeError("missing correction result: %s" % node_id)
            result = _result_leaf(
                correction_results[node_id],
                default_ref="verdict-tree://%s" % node_id.lower())
            correction_children.append({
                "id": node_id, "kind": "correction", "label": label,
                **result,
            })
        children.append({
            "id": "CORRECTION_PROTOCOL", "kind": "gate",
            "label": "CORRECTION_PROTOCOL", "mode": "all",
            "children": correction_children,
        })

    tree: Dict[str, Any] = {
        "format": FORMAT,
        "version": VERSION,
        "protocol_id": PROTOCOL_ID,
        "root": {
            "id": ROOT_ID, "kind": "protocol", "label": PROTOCOL_ID,
            "mode": "all", "children": children,
        },
    }
    if subject is not None:
        tree["subject"] = dict(subject)
    return validate_tree(tree, profile="cp8")


# A compact structural description for callers that prefer schema-like
# introspection without taking a JSON Schema dependency.
TREE_SCHEMA: Dict[str, Any] = {
    "format": FORMAT,
    "version": VERSION,
    "tree_keys": sorted(_TREE_KEYS),
    "node_keys": sorted(_NODE_KEYS),
    "node_kinds": sorted(_NODE_KINDS),
    "modes": sorted(_MODES),
    "leaf_statuses": ["pass", "fail"],
    "rollup": {
        "all": "all children pass; score=min(child scores)",
        "sequence": "all children pass; score=min(child scores)",
        "any": "at least one child passes; score=max(passing child scores)",
        "registry": "passes iff no blocking failed descendant",
    },
}
