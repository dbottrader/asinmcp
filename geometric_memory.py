#!/usr/bin/env python3
"""geometric_memory.py — CP-0023 deep pass: per-document binding records.

Method (see GEOMETRIC-MEMORY.md): STORE is immutable and untouched; this
script writes BINDINGS only — metadata + provenance, never document bodies.

Outputs ~/workspace/asinmcp/geometric-index-docs.jsonl with two sections:

1. archive-index — one binding per document in the multi-AI conversation
   archive (~/workspace/archive-index/index.db, FTS5 table `conv`,
   3,531 docs). Only the metadata columns (source, title, date, url, path,
   sha256) are read; the `body` column is never selected.

   Stable id: no single metadata column is unique across all sources —
   `path` is shared by all 1,757 X docs (one tweets.js), `sha256` is
   absent for all 367 CodePen docs and duplicated for 3 OAI docs — so the
   binding id is `archive/<source>/<rowid>`, the rowid being the index's
   own primary key, with the underlying store path and the store's
   SHA-256 (where the index carries one) cited as provenance fields.

2. research_notes — one binding per file under ~/workspace/research_notes/
   (path, size, SHA-256 of the file bytes, bundle dir as link).

Private-never material (voice-source, screenshot-archive raw) is excluded
by a path guard and is never read or hashed.

Stdlib only. Deterministic output; safe to re-run (overwrites the jsonl).
"""

import hashlib
import json
import os
import sqlite3
import sys

HOME = os.path.expanduser("~")
ARCHIVE_DB = os.path.join(HOME, "workspace", "archive-index", "index.db")
RESEARCH_DIR = os.path.join(HOME, "workspace", "research_notes")
OUT_PATH = os.path.join(HOME, "workspace", "asinmcp", "geometric-index-docs.jsonl")

BINDING_VERSION = 2
STATUS = "bound_v2"

# Private-never path components: never read, never hashed, never bound.
EXCLUDED_MARKERS = ("voice-source", "screenshot-archive")


def is_excluded(path):
    low = path.lower()
    return any(marker in low for marker in EXCLUDED_MARKERS)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_bindings(db_path=ARCHIVE_DB):
    """One binding per doc in the archive index. Metadata columns only."""
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        rows = con.execute(
            "SELECT rowid, source, title, date, url, path, sha256 "
            "FROM conv ORDER BY source, rowid"
        ).fetchall()
    finally:
        con.close()
    records = []
    for rowid, source, title, date, url, path, sha256 in rows:
        rec = {
            "doc": "archive/%s/%d" % (source, rowid),
            "collection": "archive-index",
            "source": source,
            "title": title,
        }
        if date:
            rec["date"] = date
        rec["store_ref"] = "archive-index/index.db#conv:%d" % rowid
        rec["path"] = path
        if url:
            rec["url"] = url
        if sha256:
            rec["sha256"] = sha256
        rec["binding_version"] = BINDING_VERSION
        rec["status"] = STATUS
        records.append(rec)
    return records


def research_bindings(root=RESEARCH_DIR):
    """One binding per file under research_notes (bytes hashed, not read
    into the index — only the digest is stored)."""
    records = []
    skipped = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if is_excluded(full):
                skipped.append(full)
                continue
            rel = os.path.relpath(full, root)
            parts = rel.split(os.sep)
            bundle = parts[0] if len(parts) > 1 else "."
            rec = {
                "doc": "research/" + rel.replace(os.sep, "/"),
                "collection": "research_notes",
                "source": "research_notes",
                "title": name,
                "path": full,
                "size": os.path.getsize(full),
                "sha256": sha256_file(full),
                "bundle": bundle,
                "links": ["research_notes" if bundle == "."
                          else "research_notes/" + bundle],
                "binding_version": BINDING_VERSION,
                "status": STATUS,
            }
            records.append(rec)
    records.sort(key=lambda r: r["doc"])
    return records, skipped


def main():
    archive = archive_bindings()
    research, skipped = research_bindings()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for rec in archive + research:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    by_source = {}
    for rec in archive:
        by_source[rec["source"]] = by_source.get(rec["source"], 0) + 1
    print("archive-index bindings: %d" % len(archive))
    for src in sorted(by_source):
        print("  %-10s %d" % (src, by_source[src]))
    print("research_notes bindings: %d" % len(research))
    print("excluded (private-never guard): %d" % len(skipped))
    print("total written: %d -> %s" % (len(archive) + len(research), OUT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
