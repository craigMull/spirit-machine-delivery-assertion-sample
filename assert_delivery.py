#!/usr/bin/env python3
"""Assert delivery by reading a receipt back — not by trusting a status string.

The post's first fix, in order of durability: a send is not complete when the
API accepts it. Send, read the receipt back from the transport's durable
record, and fail loudly when it is missing.

A deliberately broken target is wired in so the check can be seen to fail —
a check that has never gone red is not a check.
"""
import argparse
import json
import os
import sys
import uuid
from abc import ABC, abstractmethod


class Undelivered(Exception):
    """The transport accepted the send but no receipt is on record."""


class Receipt:
    def __init__(self, target, message_id, accepted, note=""):
        self.target = target
        self.message_id = message_id
        self.accepted = accepted
        self.note = note


class Transport(ABC):
    @abstractmethod
    def send(self, target, text) -> Receipt:
        ...

    @abstractmethod
    def read_back(self, message_id) -> bool:
        """True iff a receipt for message_id exists in the durable record."""


def assert_delivered(transport, receipt):
    """Read the receipt back from the transport's durable record.

    `send` returning a Receipt is not a delivery. This is.
    """
    if receipt.message_id is None or not transport.read_back(receipt.message_id):
        raise Undelivered(
            f"no receipt for {receipt.target!r} — the send was not a delivery"
        )
    return receipt


class FakeTransport(Transport):
    """In-memory transport; per-target outcomes are scriptable."""

    def __init__(self, outcomes):
        self.outcomes = outcomes
        self._record = []
        self._n = 0

    def send(self, target, text):
        outcome = self.outcomes.get(target, "ok")
        self._n += 1
        mid = f"{target}:{self._n}"
        if outcome == "ok":
            self._record.append(mid)
            return Receipt(target, mid, True)
        if outcome == "thread_missing":
            # the fallback succeeds and lands in the durable record; the note
            # says *why*, but the old classifier read it as the failure signal
            self._record.append(mid)
            return Receipt(target, mid, True, note="delivered without thread_id")
        if outcome == "dns_failure":
            return Receipt(target, None, False,
                           note="Temporary failure in name resolution")
        if outcome == "chat_not_found":
            return Receipt(target, None, False, note="Chat not found")
        if outcome == "silent_drop":
            # the API accepts, but nothing ever lands in the durable record
            return Receipt(target, mid, True)
        raise ValueError(f"unknown outcome: {outcome}")

    def read_back(self, message_id):
        return message_id in self._record


class JsonlTransport(Transport):
    """Appends a receipt line per send — the 'receipt' ledger."""

    def __init__(self, path):
        self.path = path

    def send(self, target, text):
        mid = f"{target}:{uuid.uuid4().hex}"
        line = json.dumps({"message_id": mid, "target": target, "accepted": True})
        with open(self.path, "a") as f:
            f.write(line + "\n")
        return Receipt(target, mid, True)

    def read_back(self, message_id):
        if not os.path.exists(self.path):
            return False
        with open(self.path) as f:
            for line in f:
                if json.loads(line).get("message_id") == message_id:
                    return True
        return False


DEMO = [
    ("ok",             "ok",
     "delivered, receipt read back"),
    ("thread_missing", "thread_missing",
     "delivered after fallback (the note is a WARNING, not a failure)"),
    ("dns_failure",    "dns_failure",
     "no receipt — Undelivered"),
    ("chat_not_found", "chat_not_found",
     "no receipt — Undelivered"),
    ("silent_drop",    "silent_drop",
     'accepted by the API, no receipt — the row a status string calls "sent"'),
]


def run_demo(targets):
    fails = 0
    for name, outcome, note in targets:
        transport = FakeTransport({name: outcome})
        try:
            receipt = transport.send(name, "synthetic report")
            assert_delivered(transport, receipt)
            print(f"{name:<16} PASS  {note}")
        except Undelivered:
            fails += 1
            print(f"{name:<16} FAIL  {note}")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", choices=["all", "ok"], default="all")
    args = ap.parse_args()
    targets = DEMO if args.demo == "all" else [DEMO[0]]
    fails = run_demo(targets)
    print(f"--- {len(targets)} targets, {fails} failed ---")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
