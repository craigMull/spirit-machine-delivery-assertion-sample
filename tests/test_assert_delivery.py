"""The read-back harness: the good target MUST pass, the broken target MUST fail."""
import pytest

from assert_delivery import FakeTransport, Undelivered, assert_delivered

BROKEN = ["dns_failure", "chat_not_found", "silent_drop"]


@pytest.mark.parametrize("outcome", ["ok", "thread_missing"])
def test_good_target_passes(outcome):
    t = FakeTransport({"t": outcome})
    r = t.send("t", "hello")
    assert_delivered(t, r)  # must not raise


@pytest.mark.parametrize("outcome", BROKEN)
def test_broken_target_must_fail(outcome):
    t = FakeTransport({"t": outcome})
    r = t.send("t", "hello")
    with pytest.raises(Undelivered):
        assert_delivered(t, r)


def test_silent_drop_is_accepted_but_unreadable():
    # the crux: the API accepted it (accepted=True), yet no receipt exists —
    # the row a status string would call "sent"
    t = FakeTransport({"t": "silent_drop"})
    r = t.send("t", "hello")
    assert r.accepted is True
    assert t.read_back(r.message_id) is False
