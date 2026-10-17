# TEST_RESULTS — spirit-machine-delivery-assertion-sample

**Built:** 2026-10-17 (Weekend Publish Block, Sat 08:00–09:00 SAST)
**Environment:** Linux, Python 3.11, pytest 9.1.1 (uv venv)
**Ledger measured:** `~/.hermes/cron/deliveries.db` — **156 rows** (the 2026-10-07 spec
snapshot was 103; it has moved, and that is the tool working)

## Acceptance tests (T1–T7)

| # | Command | Expected | Result |
|---|---------|----------|--------|
| T1 | `python3 make_fixture.py --check` | exit 0, byte-stable | ✅ `OK: fixture deterministic (60 rows identical)`, exit 0 |
| T2 | `pytest -q` | all pass incl. red-path | ✅ **10 passed**, exit 0 |
| T3 | `ledger_reconcile.py --ledger ~/.hermes/cron/deliveries.db` | re-measure at build time | ✅ 156 rows → delivered **85**, sent_then_mislabelled **36**, transport_dead **13**, target_invalid **12**, unclassified **10**, ledger_failure_rate **46%**, real_failure_rate **16%** |
| T4 | `ledger_reconcile.py --job weekday-writing` | 12 rows (spec's 10-07 value) | ⚠️ **0 rows on the real ledger** — see finding F1. Filter verified working on the fixture (15 rows) |
| T5 | `assert_delivery.py --demo all; echo $?` | exit 1, three FAIL lines | ✅ exit **1**, FAIL on dns_failure / chat_not_found / silent_drop |
| T6 | `assert_delivery.py --demo ok; echo $?` | exit 0 | ✅ exit **0** |
| T7 | `verify_post_numbers.py --post <draft> --ledger <real>` | RED (draft is a stale snapshot) | ✅ **RED, 5 mismatches, exit 1** — post says delivered=44/ledger 85, 31/36, 11/12, 56%/46%, 24%/16% (transport_dead 13 still matches by coincidence) |

## The red run (pasted, per spec §3)

```
$ python3 assert_delivery.py --demo all
ok               PASS  delivered, receipt read back
thread_missing   PASS  delivered after fallback (the note is a WARNING, not a failure)
dns_failure      FAIL  no receipt — Undelivered
chat_not_found   FAIL  no receipt — Undelivered
silent_drop      FAIL  accepted by the API, no receipt — the row a status string calls "sent"
--- 5 targets, 3 failed ---
```

Same harness, good target only:

```
$ python3 assert_delivery.py --demo ok
ok               PASS  delivered, receipt read back
--- 1 targets, 0 failed ---
```

## Findings surfaced by the build (the classifier doing its job)

**F1 — job identity has left the ledger.** Every row in the live ledger now has
`job_json = {}`. The spec's T4 (`--job weekday-writing` → 12 rows) was measured
2026-10-07 against a ledger that still carried job names. As of 2026-10-17 the
`--job` filter matches **0 rows** on the real ledger, because the job name is no
longer recorded. The filter itself is correct (verified against the fixture,
which carries synthetic job names). Consequence: the post's per-job claim
("13 rows for the blog pipeline job") can no longer be re-derived from the
ledger — the identity the claim needs is gone.

**F2 — two new error shapes, unclassified.** Since the 10-07 spec, the ledger
gained error shapes the classifier's vocabulary doesn't cover: `Timed out`
(9 rows) and `send_path_degraded`→`Timed out` (1 row). They land in
`unclassified` (10 total), which is the correct behaviour — a new error shape is
a finding, not a rounding error — but it means the post's "four classes" is now
incomplete against the live ledger. The publish-day refresh (§7 step 1) must
decide whether `Timed out` belongs in `transport_dead` or stays unclassified.

## What the numbers became

The 10-06 draft snapshot (99 rows: 44 / 31 / 24, 56% / 24%) is now 156 rows:
85 / 36 / 13 / 12 / 10, 46% / 16%. The headline-vs-real gap shrank from a
32-point spread to 30 points (46 vs 16) purely because delivered rows
accumulated — the mislabelling defect (36 rows) did not stop. The publish-day
run of `verify_post_numbers.py` will catch all of this; that is its purpose.

## Sanitization

`fixtures/ledger-sample.db` is generated, not copied: synthetic targets
(`telegram:<sample-chat-x>`), synthetic job names, seeded and byte-stable.
The real ledger is read only via the explicit `--ledger` flag and is never
committed. No real chat ids, job names, or personal data in this repo.
