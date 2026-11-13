"""Eventing against UPnP Device Architecture 2.0 (2020-04-17), clauses 4.1.2 to 4.1.4 (Tables 4-4 to 4-6)
and 4.3.2 (NOTIFY and the SEQ event key). The CALLBACK validation rows are this project's design: the
specification names no place a callback may not point (see devicespy/events.py)."""

from __future__ import annotations

import pytest

from devicespy import xmlsafe
from devicespy.events import (
    MAX_CALLBACK_LENGTH,
    MAX_SEQ,
    CallbackRejected,
    SubscribeError,
    SubscriptionTable,
    notify_message,
    parse_timeout,
    renew,
    validate_callback,
)

PEER = "192.168.1.20"
CALLBACK = f"<http://{PEER}:49152/event>"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def table(**kw):
    clock = Clock()
    sids = iter(f"uuid:00000000-0000-0000-0000-{n:012d}" for n in range(1, 1000))
    return SubscriptionTable(clock=clock, new_sid=lambda: next(sids), **kw), clock


def test_callback_accepts_lan_urls_in_order():
    assert validate_callback(CALLBACK) == (f"http://{PEER}:49152/event",)
    two = "<http://10.0.0.5/a> <http://[fe80::1]:8080/b>"
    assert validate_callback(two) == ("http://10.0.0.5/a", "http://[fe80::1]:8080/b")
    assert validate_callback("<http://[fd00::5]/x>") == ("http://[fd00::5]/x",)
    assert validate_callback("<http://169.254.1.1/x>")  # link-local


@pytest.mark.parametrize(
    "header",
    [
        "",
        "http://192.168.1.20/e",  # no angle brackets
        "<https://192.168.1.20/e>",  # not http
        "<ftp://192.168.1.20/e>",
        "<http://example.com/e>",  # a name, never an IP literal
        "<http://localhost/e>",
        "<http://8.8.8.8/e>",  # not local
        "<http://127.0.0.1/e>",  # loopback unless allowed
        "<http://[::1]/e>",
        "<http://0.0.0.0/e>",
        "<http://224.0.0.1/e>",  # multicast
        "<http://[::ffff:8.8.8.8]/e>",  # IPv4-mapped public address
        "<http://[::ffff:127.0.0.1]/e>",  # IPv4-mapped loopback
        "<http://127.1/e>",  # shorthand is a name to urllib, not an IP literal
        "<http://0x7f000001/e>",
        "<http://2130706433/e>",
        "<http://user:pw@192.168.1.20/e>",
        "<http://192.168.1.20@8.8.8.8/e>",
        "<http://[fe80::1%25eth0]/e>",
        "<http://192.168.1.20:0/e>",
        "<http://192.168.1.20:70000/e>",
        "<http://192.168.1.20:abc/e>",
        "<http://192.168.1.20/e> <http://8.8.8.8/e>",  # one bad URL fails the header
        "<http://192.168.1.20/e> junk",
        "<http://192.168.1.20/e\r\nX: y>",
        "<http://192.168.1.20/a b>",
        "<>",
        "<http://192.168.1.20/e>" * 5,
    ],
)
def test_hostile_callbacks_are_rejected_with_412(header):
    with pytest.raises(CallbackRejected) as info:
        validate_callback(header)
    assert info.value.status == 412


def test_callback_is_never_truncated_only_rejected():
    long = "<http://192.168.1.20/" + "a" * MAX_CALLBACK_LENGTH + ">"
    with pytest.raises(CallbackRejected, match="longer"):
        validate_callback(long)


def test_loopback_is_allowed_only_on_request():
    assert validate_callback("<http://127.0.0.1:9/e>", allow_loopback=True)
    assert validate_callback("<http://[::1]:9/e>", allow_loopback=True)
    with pytest.raises(CallbackRejected):
        validate_callback("<http://0.0.0.0/e>", allow_loopback=True)


def test_same_host_policy_names_the_subscriber_only():
    assert validate_callback(CALLBACK, peer=PEER, policy="same-host")
    with pytest.raises(CallbackRejected, match="own address"):
        validate_callback("<http://192.168.1.99/e>", peer=PEER, policy="same-host")
    with pytest.raises(CallbackRejected, match="needs the subscriber"):
        validate_callback(CALLBACK, policy="same-host")
    with pytest.raises(ValueError, match="policy"):
        validate_callback(CALLBACK, policy="anywhere")


def test_subscribe_assigns_sid_timeout_and_initial_event_key():
    t, clock = table()
    sub = t.subscribe(callback=CALLBACK, nt="upnp:event", timeout="Second-300", statevar="A, B")
    assert sub.sid == "uuid:00000000-0000-0000-0000-000000000001"
    assert sub.seq == 0
    assert sub.expires_at == clock.now + 1800  # clause 4.1.2: TIMEOUT should be at least 1800
    assert sub.statevars == ("A", "B")
    assert len(t) == 1
    longer = t.subscribe(callback=CALLBACK, nt="upnp:event", timeout="Second-7200")
    assert longer.expires_at == clock.now + 7200
    capped = t.subscribe(callback=CALLBACK, nt="upnp:event", timeout="Second-99999999")
    assert capped.expires_at == clock.now + 86400


def test_subscribe_errors_follow_table_4_4():
    t, _ = table()
    with pytest.raises(SubscribeError) as info:
        t.subscribe(
            callback=CALLBACK, nt="upnp:event", sid="uuid:00000000-0000-0000-0000-000000000009"
        )
    assert info.value.status == 400
    for callback, nt in (
        (None, "upnp:event"),
        (CALLBACK, "upnp:other"),
        (CALLBACK, None),
        ("junk", "upnp:event"),
    ):
        with pytest.raises(SubscribeError) as info:
            t.subscribe(callback=callback, nt=nt)
        assert info.value.status == 412


def test_a_full_table_answers_503():
    t, _ = table(max_subscriptions=2)
    t.subscribe(callback=CALLBACK, nt="upnp:event")
    t.subscribe(callback=CALLBACK, nt="upnp:event")
    with pytest.raises(SubscribeError) as info:
        t.subscribe(callback=CALLBACK, nt="upnp:event")
    assert info.value.status == 503


def test_timeout_header_forms():
    assert parse_timeout("Second-1800") == 1800
    assert parse_timeout("second-60") == 60
    assert parse_timeout(None) == 1800
    assert parse_timeout("infinite") == 1800
    for bad in ("Seconds-5", "Second-", "Second--5", "5", "Second-99999999999"):
        with pytest.raises(SubscribeError) as info:
            parse_timeout(bad)
        assert info.value.status == 400


def test_renewal_and_cancellation_follow_tables_4_5_and_4_6():
    t, clock = table()
    sub = t.subscribe(callback=CALLBACK, nt="upnp:event")
    clock.now += 100
    renewed = t.renew(sid=sub.sid, timeout="Second-3600")
    assert renewed.expires_at == clock.now + 3600
    assert t.get(sub.sid) == renewed
    for kwargs in ({"nt": "upnp:event"}, {"callback": CALLBACK}):
        with pytest.raises(SubscribeError) as info:
            t.renew(sid=sub.sid, **kwargs)
        assert info.value.status == 400
        with pytest.raises(SubscribeError) as info:
            t.cancel(sid=sub.sid, **kwargs)
        assert info.value.status == 400
    for sid in (None, "", "uuid:", "uuid:00000000-0000-0000-0000-0000000000ff", "nonsense"):
        with pytest.raises(SubscribeError) as info:
            t.renew(sid=sid)
        assert info.value.status == 412
        with pytest.raises(SubscribeError) as info:
            t.cancel(sid=sid)
        assert info.value.status == 412
    t.cancel(sid=sub.sid)
    assert len(t) == 0
    with pytest.raises(SubscribeError):
        t.cancel(sid=sub.sid)


def test_expired_subscriptions_are_swept_and_cannot_be_renewed():
    t, clock = table()
    sub = t.subscribe(callback=CALLBACK, nt="upnp:event", timeout="Second-1800")
    clock.now += 1799
    assert t.get(sub.sid) is not None
    clock.now += 1
    assert t.sweep() == [sub.sid] or t.get(sub.sid) is None
    with pytest.raises(SubscribeError) as info:
        t.renew(sid=sub.sid)
    assert info.value.status == 412


def test_module_renew_reassigns_a_duration():
    t, clock = table()
    sub = t.subscribe(callback=CALLBACK, nt="upnp:event")
    assert renew(sub, 5000, now=0).expires_at == 5000
    assert renew(sub, 10, now=0).expires_at == 1800
    assert renew(sub, 10**9, now=0).expires_at == 86400
    assert clock.now == 1000.0


def test_event_key_starts_at_zero_increments_and_wraps_to_one():
    t, _ = table()
    sub = t.subscribe(callback=CALLBACK, nt="upnp:event")
    assert [t.next_event_key(sub.sid) for _ in range(3)] == [0, 1, 2]
    other = t.subscribe(callback=CALLBACK, nt="upnp:event")
    assert t.next_event_key(other.sid) == 0  # a key per subscription
    t._table[sub.sid] = t._table[sub.sid].__class__(sub.sid, sub.callbacks, sub.expires_at, MAX_SEQ)
    assert t.next_event_key(sub.sid) == MAX_SEQ
    assert t.next_event_key(sub.sid) == 1  # wrapped from 4294967295 to 1, never back to 0
    assert t.next_event_key(sub.sid) == 2


def test_notify_message_layout_and_seq():
    sid = "uuid:00000000-0000-0000-0000-000000000001"
    raw = notify_message(
        f"http://{PEER}:49152/event?x=1", sid, 5, {"Status": "1", "Name": "a<b & c"}
    )
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("ascii").split("\r\n")
    assert lines[0] == "NOTIFY /event?x=1 HTTP/1.1"
    fields = dict(line.split(": ", 1) for line in lines[1:])
    assert fields["HOST"] == f"{PEER}:49152"
    assert fields["NT"] == "upnp:event"
    assert fields["NTS"] == "upnp:propchange"
    assert fields["SID"] == sid
    assert fields["SEQ"] == "5"
    assert fields["CONTENT-TYPE"] == 'text/xml; charset="utf-8"'
    assert int(fields["CONTENT-LENGTH"]) == len(body)
    root = xmlsafe.parse(body, 10_000)
    assert xmlsafe.localname(root.tag) == ("urn:schemas-upnp-org:event-1-0", "propertyset")
    values = {
        xmlsafe.localname(p[0].tag)[1]: p[0].text
        for p in root
        if xmlsafe.localname(p.tag)[1] == "property"
    }
    assert values == {"Status": "1", "Name": "a<b & c"}
    assert all(xmlsafe.localname(p[0].tag)[0] == "" for p in root)  # variableName is unqualified


def test_notify_message_refuses_bad_input():
    sid = "uuid:00000000-0000-0000-0000-000000000001"
    url = f"http://{PEER}/e"
    with pytest.raises(ValueError, match="SEQ"):
        notify_message(url, sid, MAX_SEQ + 1, {})
    with pytest.raises(ValueError, match="SEQ"):
        notify_message(url, sid, -1, {})
    with pytest.raises(ValueError, match="SID"):
        notify_message(url, "x", 0, {})
    with pytest.raises(ValueError, match="XML name"):
        notify_message(url, sid, 0, {"a b": "1"})
    with pytest.raises(ValueError, match="XML name"):
        notify_message(url, sid, 0, {"x><y": "1"})
    with pytest.raises(ValueError, match="cannot carry"):
        notify_message(url, sid, 0, {"a": "\x00"})
    with pytest.raises(ValueError, match="http://"):
        notify_message("https://h/e", sid, 0, {})
    with pytest.raises(ValueError, match="space"):
        notify_message("http://h/e\r\nX: y", sid, 0, {})
