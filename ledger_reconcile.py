#!/usr/bin/env python3
"""Classify a delivery ledger honestly.

The real ledger records only strings — a status column and an error column —
so this is a string-based classifier, and it says so out loud. The whole point
of the post is that a routing note ("delivered without thread_id") and a dead
network ("Temporary failure in name resolution") both land in a status column
that the old code reduced to the single word "failed".

Rules, in order (first match wins — a row matching two signatures is counted
once, never twice):

  delivered              status == 'delivered' and error empty
  sent_then_mislabelled  'delivered without thread_id' in error   (sent, labelled failed)
  transport_dead         'Temporary failure in name resolution' in error (never sent)
                          or 'Timed out' in error                 (send failed — never sent)
  target_invalid         'Chat not found' in error                (never sent)
  unclassified           anything else — printed, never folded in

A new error shape is a finding, not a rounding error.
"""
import argparse
import json
import sqlite3
import sys

CLASS_ORDER = [
    "delivered",
    "sent_then_mislabelled",
    "transport_dead",
    "target_invalid",
    "unclassified",
]


def classify(status, error):
    error = error or ""
    if status == "delivered" and error.strip() == "":
        return "delivered"
    if "delivered without thread_id" in error:
        return "sent_then_mislabelled"
    if "Temporary failure in name resolution" in error:
        return "transport_dead"
    if "Timed out" in error:
        return "transport_dead"
    if "Chat not found" in error:
        return "target_invalid"
    return "unclassified"


def _job_name(job_json):
    try:
        data = json.loads(job_json or "{}")
    except (ValueError, TypeError):
        return None
    if isinstance(data, dict):
        return data.get("job") or data.get("name")
    return None


def load_rows(ledger_path, as_of=None, job=None):
    """Return [(execution_id, status, error, created_at), ...]."""
    db = sqlite3.connect(ledger_path)
    rows = db.execute(
        "SELECT execution_id, job_json, status, error, created_at FROM deliveries"
    ).fetchall()
    db.close()
    out = []
    for exec_id, job_json, status, error, created_at in rows:
        if as_of is not None and (created_at or "")[:10] > as_of:
            continue
        if job is not None and _job_name(job_json) != job:
            continue
        out.append((exec_id, status, error or "", created_at or ""))
    return out


def reconcile(rows):
    counts = {c: 0 for c in CLASS_ORDER}
    for exec_id, status, error, created_at in rows:
        counts[classify(status, error)] += 1
    return counts


def rates(counts):
    total = sum(counts.values())
    if total == 0:
        return 0, 0
    delivered = counts["delivered"]
    confirmed_dead = counts["transport_dead"] + counts["target_invalid"]
    ledger_rate = round((total - delivered) / total * 100)
    real_rate = round(confirmed_dead / total * 100)
    return ledger_rate, real_rate


def _max_date(rows):
    dates = [r[3][:10] for r in rows if r[3]]
    return max(dates) if dates else "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="fixtures/ledger-sample.db")
    ap.add_argument("--as-of")
    ap.add_argument("--job")
    ap.add_argument("--format", choices=["block", "json"], default="block")
    args = ap.parse_args()

    rows = load_rows(args.ledger, args.as_of, args.job)
    counts = reconcile(rows)
    ledger_rate, real_rate = rates(counts)
    total = len(rows)
    as_of = args.as_of or _max_date(rows)

    if args.format == "json":
        print(json.dumps({
            "as_of": as_of, "ledger": args.ledger, "rows": total,
            "delivered": counts["delivered"],
            "sent_then_mislabelled": counts["sent_then_mislabelled"],
            "transport_dead": counts["transport_dead"],
            "target_invalid": counts["target_invalid"],
            "unclassified": counts["unclassified"],
            "ledger_failure_rate": ledger_rate,
            "real_failure_rate": real_rate,
        }))
        return 0

    print(f"as-of {as_of} · ledger {args.ledger} · rows {total}")
    print(f"delivered             {counts['delivered']}")
    print(f"sent_then_mislabelled {counts['sent_then_mislabelled']}")
    print(f"transport_dead        {counts['transport_dead']}")
    print(f"target_invalid        {counts['target_invalid']}")
    print(f"unclassified          {counts['unclassified']}")
    print(f"ledger_failure_rate  {ledger_rate}%")
    print(f"real_failure_rate    {real_rate}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
