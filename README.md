# spirit-machine-delivery-assertion-sample

A **sample** (not production code) that answers the two questions behind the post
*"My Agent Marked Every Report 'Failed.' Every One Arrived."*:

1. **What do the numbers actually say?** `ledger_reconcile.py` reads a delivery
   ledger and classifies every row honestly, instead of reducing it to a single
   `failed` status string. The four classes plus `unclassified` are printed —
   and a new error shape is a finding, never a rounding error.
2. **How do you know a send is a delivery?** `assert_delivery.py` shows that a
   send is not complete when the API accepts it: send, read a receipt back from
   the transport's durable record, and fail loudly when it's missing. A
   deliberately broken target is wired in so the check can be *seen to fail*.

`verify_post_numbers.py` is the anti-staleness gate: it parses the numbers out
of the post and re-checks them against the live ledger at publish time, so a
published number is the publish-day number, not a snapshot that has since rotted.

## The defect, in one line

A routing note and a dead network both land in a `status` column as `failed`:

```
status: failed
error:  configured thread_id 13528 for telegram:<chat> was not found;
        delivered without thread_id
```

The error text says *delivered*. The status says `failed`. They are the same row.

## Reproduce

```bash
python3 make_fixture.py                 # write fixtures/ledger-sample.db (synthetic)
python3 ledger_reconcile.py             # classify the fixture, block format
python3 ledger_reconcile.py --format json
python3 assert_delivery.py --demo all   # 5 targets, 3 deliberately broken -> exit 1
python3 assert_delivery.py --demo ok    # the good target only -> exit 0
pytest -q                               # 9 tests, all pass
```

Run the classifier against a real ledger (read-only; never committed):

```bash
python3 ledger_reconcile.py --ledger ~/.hermes/cron/deliveries.db
python3 verify_post_numbers.py \
  --post ~/Workspace/spirit-machine-pipeline/01-ideation/output/draft-failed-but-delivered.md \
  --ledger ~/.hermes/cron/deliveries.db
```

## Fixture

`fixtures/ledger-sample.db` is **generated, not copied** — synthetic targets
(`telegram:<sample-chat-x>`), synthetic job names, no real ids, no personal data.
`make_fixture.py --check` proves it is deterministic.

## Disclaimer

This is a sanitized sample for demonstration. It is not production code, and it
never touches a real Telegram token or a live chat — `FakeTransport` and
`JsonlTransport` only. See the post for the full argument:
*"a status is a claim about the system that produced it, not a measurement of the
system you care about."*
