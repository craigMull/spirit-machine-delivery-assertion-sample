"""The four-class partition + the counterexamples, tested against the classifier."""
from ledger_reconcile import classify, reconcile


def test_four_class_partition():
    rows = [
        ("a", "delivered", "", ""),
        ("b", "failed",
         "configured thread_id 13528 for telegram:x was not found; delivered without thread_id",
         ""),
        ("c", "failed",
         "delivery error: Telegram send failed: httpx.ConnectError: "
         "[Errno -3] Temporary failure in name resolution (target telegram:x)",
         ""),
        ("d", "failed",
         "live adapter send failed: Chat not found; live adapter delivery to telegram:x",
         ""),
    ]
    counts = reconcile(rows)
    assert counts["delivered"] == 1
    assert counts["sent_then_mislabelled"] == 1
    assert counts["transport_dead"] == 1
    assert counts["target_invalid"] == 1
    assert counts["unclassified"] == 0


def test_compound_row_counted_once():
    # send_path_degraded *and* name resolution in one error -> transport_dead only
    cls = classify("failed",
                   "live adapter send failed: send_path_degraded; live adapter delivery "
                   "failed: send_path_degraded; delivery error: Telegram send failed: "
                   "httpx.ConnectError: [Errno -3] Temporary failure in name resolution")
    assert cls == "transport_dead"


def test_new_error_shape_is_unclassified_not_folded():
    # a shape the rules don't know must surface, not be rounded into "failed"
    assert classify("failed",
                    "delivery error: Telegram send failed: Timed out (target telegram:x)"
                    ) == "unclassified"


def test_delivered_requires_empty_error():
    # rule order: a 'delivered' row with a fallback note is *not* 'delivered' —
    # the note is what the classifier sees. Documented, literal rule behaviour.
    assert classify("delivered", "") == "delivered"
    assert classify("delivered",
                    "delivered without thread_id") == "sent_then_mislabelled"
