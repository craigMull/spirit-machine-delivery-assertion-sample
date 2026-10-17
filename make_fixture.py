#!/usr/bin/env python3
"""Generate a deterministic, synthetic delivery ledger for the sample.

Writes fixtures/ledger-sample.db with the same schema as the real Hermes
deliveries ledger, but with synthetic targets and job names only — no real
chat ids, no real job names, no personal data.

`--check` re-generates to a temp file and diffs against the committed one:
the determinism test (a fixture that isn't byte-stable can't serve as a
canonical test input).
"""
import argparse
import datetime
import os
import random
import sqlite3
import sys

SCHEMA = """
CREATE TABLE deliveries (
    execution_id TEXT PRIMARY KEY,
    job_json TEXT NOT NULL,
    content TEXT NOT NULL,
    for_failure INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN
      ('pending','delivering','delivered','failed','unknown','suppressed')),
    owner_process_id TEXT,
    owner_pid INTEGER,
    owner_started_at INTEGER,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    error TEXT
);
"""

# class -> count, in the ~44% / 32% / 13% / 12% proportions of the 2026-10-07
# ledger, plus one unclassified row to exercise the "printed, never folded in"
# bucket. Every error string is synthetic: targets are "<sample-chat-x>".
CLASSES = [
    ("delivered",             26),
    ("sent_then_mislabelled", 19),
    ("transport_dead",         8),
    ("target_invalid",         6),
    ("unclassified",           1),
]

JOBS = ["weekday-writing", "daily-pulse", "weekly-review", "monthly-audit"]
TARGETS = ["<sample-chat-a>", "<sample-chat-b>", "<sample-chat-c>", "<sample-chat-d>"]


def _error_for(cls, target):
    if cls == "sent_then_mislabelled":
        return (f"configured thread_id 13528 for telegram:{target} was not found; "
                "delivered without thread_id")
    if cls == "transport_dead":
        return ("delivery error: Telegram send failed: httpx.ConnectError: "
                "[Errno -3] Temporary failure in name resolution "
                f"(target telegram:{target})")
    if cls == "target_invalid":
        return (f"live adapter send failed: Chat not found; live adapter delivery "
                f"to telegram:{target} failed: Chat not found")
    if cls == "unclassified":
        return (f"delivery error: Telegram send failed: Timed out "
                f"(target telegram:{target})")
    return ""


def build_rows(seed=20261007):
    rng = random.Random(seed)
    rows = []
    idx = 0
    base = datetime.datetime(2026, 9, 21, 8, 0, 0)
    for cls, count in CLASSES:
        for _ in range(count):
            idx += 1
            job = JOBS[(idx - 1) % len(JOBS)]
            target = TARGETS[(idx - 1) % len(TARGETS)]
            status = "delivered" if cls == "delivered" else "failed"
            ts = base + datetime.timedelta(minutes=(idx - 1) * 360)
            created_at = ts.isoformat() + "+02:00"
            rows.append({
                "execution_id": f"fixture-{idx:04d}",
                "job_json": '{"job": "' + job + '"}',
                "content": "synthetic sample report body",
                "for_failure": 0,
                "status": status,
                "created_at": created_at,
                "finished_at": created_at,
                "error": _error_for(cls, target),
            })
    return rows


def write_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for r in build_rows():
        db.execute(
            "INSERT INTO deliveries (execution_id, job_json, content, for_failure, "
            "status, created_at, finished_at, error) VALUES (?,?,?,?,?,?,?,?)",
            (r["execution_id"], r["job_json"], r["content"], r["for_failure"],
             r["status"], r["created_at"], r["finished_at"], r["error"]),
        )
    db.commit()
    db.close()


def all_rows(path):
    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT execution_id, job_json, status, error, created_at "
        "FROM deliveries ORDER BY execution_id"
    ).fetchall()
    db.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="regenerate to a temp file and diff against the committed one")
    ap.add_argument("--path", default="fixtures/ledger-sample.db")
    args = ap.parse_args()

    if args.check:
        import tempfile
        tmp = tempfile.mktemp(suffix=".db")
        write_db(tmp)
        committed = all_rows(args.path)
        regenerated = all_rows(tmp)
        os.remove(tmp)
        if committed == regenerated:
            print(f"OK: fixture deterministic ({len(committed)} rows identical)")
            return 0
        print("FAIL: fixture not deterministic")
        return 1

    write_db(args.path)
    print(f"wrote {args.path} ({len(build_rows())} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
