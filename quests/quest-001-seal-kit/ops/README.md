# ops - NOT APPLIED

`QUEST-001-TEST` closed on Thu Nov 19, 2026, 11:59 PM CT, so the live service answers `410 quest_closed` to every test envelope and the kit's `--test-quest` flow cannot reach `201 accepted`.

`extend-test-quest.PROPOSAL.sql` would reopen the test quest (is_test, no reward) until Thu Nov 26, 2026, 11:59 PM CT, the same deadline as QUEST-001, using the same pattern as the QUEST-001 v2 extension: replace the manifest row with `manifest-test.v2.json` (sha256 `c22d7db6a392be5f80e72695a990e1c43b9d18335aac71be93be4961c46e401a`) and append a `manifest_superseded` chronicle record (seq 7, record_hash `ada62b25dd3db9542054f946adc97949d753b40b7765b4ea400628a9fc335593`). The chronicle is append-only, so applying it is permanent. It does not touch QUEST-001. It needs Dennis Christie's approval before anyone runs it. `seal_quest001.py` already accepts both the v1 and the proposed v2 test manifest hashes.
