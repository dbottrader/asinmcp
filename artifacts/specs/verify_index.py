#!/usr/bin/env python3
"""Verify provenance-index.json:
 1. recompute every entry's file sha256 (where a canonical file exists),
 2. cross-check corpus-block hashes against the corpus INDEX.json records,
 3. walk the index hash chain from the ledger-tip seed to the head hash.
Prints PASS/FAIL per entry and a summary. Exit 0 only if everything verifiable passes."""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = '/home/hatch/workspace'

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

doc = json.load(open(os.path.join(HERE, 'provenance-index.json')))
corpus_idx = {r['sha8']: r for r in json.load(open(f'{WS}/code-corpus/INDEX.json'))}
entries = doc['entries']
fails = 0

print(f"ASIN-HHC Public Provenance Index — verification")
print(f"entries: {doc['entry_count']} · ledger anchor: height {doc['ledger_anchor']['height']}, "
      f"tip {doc['ledger_anchor']['tip_hash'][:16]}…")
print(f"chain seed check: entry 0 prev_index_hash == ledger tip -> "
      f"{'PASS' if entries[0]['prev_index_hash'] == doc['ledger_anchor']['tip_hash'] else 'FAIL'}")
if entries[0]['prev_index_hash'] != doc['ledger_anchor']['tip_hash']:
    fails += 1
print('-' * 100)

prev = doc['ledger_anchor']['tip_hash']
for e in entries:
    problems = []
    # chain
    if e['prev_index_hash'] != prev:
        problems.append('prev_index_hash mismatch')
    canon = {k: e[k] for k in sorted(e) if k != 'index_hash'}
    recomputed = hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if recomputed != e['index_hash']:
        problems.append('index_hash mismatch (entry content altered)')
    prev = e['index_hash']
    # file hash
    fstat = 'no-file (URL/record anchor)'
    if e.get('local_path'):
        p = os.path.join(WS, e['local_path'])
        if not os.path.isfile(p):
            problems.append(f"canonical file missing: {e['local_path']}")
            fstat = 'FILE MISSING'
        elif e.get('file_sha256'):
            actual = sha256_file(p)
            if actual != e['file_sha256']:
                problems.append('file sha256 mismatch')
                fstat = 'FILE HASH FAIL'
            else:
                fstat = 'file sha256 OK'
        # corpus cross-check
        if e.get('corpus_sha8'):
            rec = corpus_idx.get(e['corpus_sha8'])
            if not rec or rec['sha256'] != e.get('corpus_block_sha256'):
                problems.append('corpus INDEX cross-check mismatch')
            elif e.get('file_sha256') and rec['sha256'] != e['file_sha256']:
                problems.append('file hash != corpus INDEX sha256')
    status = 'PASS' if not problems else 'FAIL'
    if problems:
        fails += 1
    print(f"[{status}] #{e['index']:>2} {e['name'][:62]:<62} {fstat:<26} {'; '.join(problems)}")

head_ok = prev == doc['head_hash']
print('-' * 100)
print(f"chain head: {'PASS' if head_ok else 'FAIL'} (head {doc['head_hash'][:16]}…)")
if not head_ok:
    fails += 1
print(f"RESULT: {'PASS' if fails == 0 else f'FAIL — {fails} problem(s)'} "
      f"({doc['entry_count']} entries, {sum(1 for e in entries if e.get('file_sha256'))} file fingerprints verified)")
sys.exit(0 if fails == 0 else 1)
