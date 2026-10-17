#!/usr/bin/env python3
"""The anti-staleness gate: the post's numbers vs the live ledger.

Parses the four counts and the two rates out of the post, runs the classifier
on the ledger, and exits 1 naming every mismatch. A number typed into a post is
a claim, and a claim about a live table has a shelf life — this is the re-check.

It ignores the post's stated as-of date except to warn when the snapshot is
more than 14 days old.
"""
import argparse
import datetime
import re
import sys

from ledger_reconcile import load_rows, reconcile, rates

FIELDS = [
    "delivered", "sent_then_mislabelled", "transport_dead",
    "target_invalid", "ledger_failure_rate", "real_failure_rate",
]


def parse_post_numbers(text):
    """Extract counts + rates from a clean block, or from the draft's prose.

    Returns a dict; missing fields are None.
    """
    result = {k: None for k in
              ["delivered", "sent_then_mislabelled", "transport_dead",
               "target_invalid", "ledger_failure_rate", "real_failure_rate",
               "as_of", "rows"]}

    # 1) clean block (the `--format block` shape pasted into the final post)
    for label in ["delivered", "sent_then_mislabelled", "transport_dead",
                  "target_invalid"]:
        m = re.search(rf"^{label}\s+(\d+)\s*$", text, re.MULTILINE)
        if m:
            result[label] = int(m.group(1))
    for label in ["ledger_failure_rate", "real_failure_rate"]:
        m = re.search(rf"^{label}\s+(\d+)%\s*$", text, re.MULTILINE)
        if m:
            result[label] = int(m.group(1))
    m = re.search(r"^as-of (\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if m:
        result["as_of"] = m.group(1)
    m = re.search(r"· rows (\d+)", text)
    if m:
        result["rows"] = int(m.group(1))

    if all(result[f] is not None for f in FIELDS):
        return result  # clean block fully present

    # 2) draft prose fallback (the 6 Oct snapshot wording)
    m = re.search(r"\*\*(\d+)\*\* rows: `?delivered`?", text)
    if m and result["delivered"] is None:
        result["delivered"] = int(m.group(1))
    m = re.search(r"\*\*(\d+)\*\* rows: `?failed`?, with error text", text)
    if m and result["sent_then_mislabelled"] is None:
        result["sent_then_mislabelled"] = int(m.group(1))
    m = re.search(r"(\d+) rows whose send died", text)
    if m and result["transport_dead"] is None:
        result["transport_dead"] = int(m.group(1))
    m = re.search(r"and (\d+) rows for one job", text)
    if m and result["target_invalid"] is None:
        result["target_invalid"] = int(m.group(1))
    m = re.search(r"headline failure rate is \*\*(\d+)%", text)
    if m and result["ledger_failure_rate"] is None:
        result["ledger_failure_rate"] = int(m.group(1))
    m = re.search(r"real one is \*\*(\d+)%", text)
    if m and result["real_failure_rate"] is None:
        result["real_failure_rate"] = int(m.group(1))

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", required=True)
    ap.add_argument("--ledger", required=True)
    args = ap.parse_args()

    text = open(args.post).read()
    claimed = parse_post_numbers(text)
    rows = load_rows(args.ledger)
    counts = reconcile(rows)
    ledger_rate, real_rate = rates(counts)
    total = len(rows)

    actual = {
        "delivered": counts["delivered"],
        "sent_then_mislabelled": counts["sent_then_mislabelled"],
        "transport_dead": counts["transport_dead"],
        "target_invalid": counts["target_invalid"],
        "ledger_failure_rate": ledger_rate,
        "real_failure_rate": real_rate,
        "rows": total,
    }

    mismatches = []
    for field in FIELDS:
        c = claimed[field]
        a = actual[field]
        if c is None:
            mismatches.append(f"post has no parseable {field}")
        elif c != a:
            mismatches.append(f"post says {field}={c}, ledger says {a}")

    warn = ""
    as_of = claimed.get("as_of")
    if as_of:
        try:
            d = datetime.date.fromisoformat(as_of)
            age = (datetime.date.today() - d).days
            if age > 14:
                warn = f"⚠️ post snapshot is {age} days old"
        except ValueError:
            pass

    if mismatches:
        print(f"RED — {len(mismatches)} mismatch(es) against {args.ledger} (rows {total}):")
        for m in mismatches:
            print(f"  - {m}")
        if warn:
            print(warn)
        return 1

    print(f"GREEN — post numbers match {args.ledger} (rows {total})")
    if warn:
        print(warn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
