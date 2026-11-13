"""GENA subscriptions and evented property change notifications (UDA 2.0 eventing).

UPnP Device Architecture 2.0 (2020-04-17), clause 4.1 (unicast subscription, renewal and cancellation,
Tables 4-4 to 4-6) and clause 4.3.2 (NOTIFY event messages, the SEQ event key). This module is the state
and message layer: it validates a subscriber's CALLBACK header, keeps the subscription table with its
timeouts and per-subscription event key, and writes the NOTIFY message. It opens no connection; delivery
with timeouts and backoff belongs to ``notify``, which is not implemented yet.

A subscriber names a URL that the device then connects to, so the CALLBACK header is hostile input. The
specification requires an ``http://`` URL, no truncation, and that at least one URL be reachable; it says
nothing about where the URL may point. :func:`validate_callback` therefore applies this project's own
policy (design, not UDA): the host must be an IP literal, never a name; credentials are refused; the
address must be on the local network (``lan``) or exactly the subscriber's own address (``same-host``).
"""

from __future__ import annotations

import ipaddress
import re
import time
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "MAX_CALLBACK_LENGTH",
    "MAX_SEQ",
    "CallbackRejected",
    "SubscribeError",
    "Subscription",
    "SubscriptionTable",
    "notify",
    "notify_message",
    "parse_timeout",
    "renew",
    "validate_callback",
]

#: Clause 4.1.2: the device does not truncate a CALLBACK URL and rejects the subscription instead.
MAX_CALLBACK_LENGTH = 1024
MAX_SEQ = 4294967295  # clause 4.3.2: SEQ is a 32-bit unsigned value
_MIN_TIMEOUT = 1800  # clause 4.1.2: TIMEOUT should be at least 1800 seconds
_DEFAULT_MAX_TIMEOUT = 86400
_ANGLE = re.compile(r"\s*<([^<>\s]+)>")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
_BAD_XML = re.compile("[^\t\n\r -퟿-�\U00010000-\U0010ffff]")
_TIMEOUT = re.compile(r"Second-([0-9]{1,10})", re.IGNORECASE)
_SID = re.compile(r"uuid:[0-9A-Fa-f-]{8,64}")


class SubscribeError(Exception):
    """A subscription request is refused; ``status`` is the HTTP status to answer with (Tables 4-4 to
    4-6: 400 incompatible header fields, 412 precondition failed, a 5xx when unable to accept)."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


class CallbackRejected(SubscribeError):  # noqa: N818 - a refusal, named for what the publisher answers
    """The CALLBACK header is missing, malformed, too long, or names a place this device will not call."""

    def __init__(self, reason: str) -> None:
        super().__init__(412, reason)


def _is_lan(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_loopback: bool
) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if address.is_unspecified or address.is_multicast:
        return False
    if address.is_loopback:
        return allow_loopback
    return address.is_private or address.is_link_local


def validate_callback(
    header: str,
    *,
    peer: str | None = None,
    policy: str = "lan",
    allow_loopback: bool = False,
    max_urls: int = 4,
) -> tuple[str, ...]:
    """The URLs of a CALLBACK header value (``<http://192.168.1.5:49152/e>``, one or more), or
    :class:`CallbackRejected`.

    Clause 4.1.2 requires each URL to be an ``http://`` URL, bracketed in angle brackets, and forbids
    truncation, so a value over ``MAX_CALLBACK_LENGTH`` is rejected whole. Beyond that (design, see the
    module docstring) every URL must have an IP-literal host, no user information, a port within 1 to
    65535, and, per ``policy``, ``lan`` (a private or link-local address, loopback only with
    ``allow_loopback``) or ``same-host`` (exactly ``peer``, the subscriber's source address). Any URL
    failing the policy fails the header: the device never keeps a URL it would not call.
    """
    if policy not in {"lan", "same-host"}:
        raise ValueError("policy is lan or same-host")
    if not header or len(header) > MAX_CALLBACK_LENGTH:
        raise CallbackRejected("CALLBACK is missing or longer than this device stores")
    urls: list[str] = []
    position = 0
    while position < len(header):
        found = _ANGLE.match(header, position)
        if found is None:
            if header[position:].strip() == "":
                break
            raise CallbackRejected("CALLBACK is one or more URLs, each in angle brackets")
        urls.append(found.group(1))
        position = found.end()
    if not urls or len(urls) > max_urls:
        raise CallbackRejected(f"CALLBACK needs between 1 and {max_urls} URLs")
    peer_address = None
    if policy == "same-host":
        try:
            peer_address = ipaddress.ip_address(peer or "")
        except ValueError:
            raise CallbackRejected("same-host policy needs the subscriber's address") from None
    for url in urls:
        _check_url(url, peer_address, policy, allow_loopback)
    return tuple(urls)


def _check_url(
    url: str,
    peer: ipaddress.IPv4Address | ipaddress.IPv6Address | None,
    policy: str,
    allow_loopback: bool,
) -> None:
    if any(ord(c) < 0x21 or ord(c) > 0x7E for c in url):
        raise CallbackRejected("a CALLBACK URL holds a space, control or non-ASCII character")
    parts = urlsplit(url)
    if parts.scheme != "http":
        raise CallbackRejected("a CALLBACK URL is an http:// URL (clause 4.1.2)")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise CallbackRejected("a CALLBACK URL carries no user information")
    host = parts.hostname or ""
    if "%" in host:
        raise CallbackRejected("a CALLBACK host has no zone identifier")
    try:
        port = parts.port
        address = ipaddress.ip_address(host)
    except ValueError:
        raise CallbackRejected(
            "a CALLBACK host is an IP address literal, never a name, and its port a number"
        ) from None
    if port is not None and not 1 <= port <= 65535:
        raise CallbackRejected("a CALLBACK port is 1 to 65535")
    if policy == "same-host":
        if peer is None or address != peer:
            raise CallbackRejected("a CALLBACK URL names the subscriber's own address only")
    elif not _is_lan(address, allow_loopback=allow_loopback):
        raise CallbackRejected("a CALLBACK URL names a local-network address only")


def parse_timeout(value: str | None, *, default: int = _MIN_TIMEOUT) -> int:
    """The seconds a TIMEOUT header asks for: ``Second-N``. Clause 4.1.2 deprecates ``infinite`` for
    UPnP 2.0 control points; it is read as no preference (``default``), so the device still assigns a
    finite duration. Anything else is a 400 (design: the text does not say)."""
    if value is None or value.strip() == "" or value.strip().lower() == "infinite":
        return default
    found = _TIMEOUT.fullmatch(value.strip())
    if found is None:
        raise SubscribeError(400, "TIMEOUT is Second- followed by an integer")
    return int(found.group(1))


@dataclass(frozen=True)
class Subscription:
    """One subscriber: its SID, the validated callback URLs, when it expires (on the table's clock), the
    event key the next NOTIFY carries (``seq``, 0 for the initial event) and the state variables it asked
    for, if it said."""

    sid: str
    callbacks: tuple[str, ...]
    expires_at: float
    seq: int = 0
    statevars: tuple[str, ...] | None = None


def _grant(requested: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(requested, maximum))


def renew(
    subscription: Subscription,
    requested: int,
    *,
    now: float | None = None,
    min_timeout: int = _MIN_TIMEOUT,
    max_timeout: int = _DEFAULT_MAX_TIMEOUT,
) -> Subscription:
    """The subscription with a new duration assigned (UDA 2.0 eventing, clause 4.1.3): the publisher
    reassigns a duration from ``now``, within ``min_timeout`` (clause 4.1.2: at least 1800 s) and
    ``max_timeout``."""
    start = time.monotonic() if now is None else now
    return replace(subscription, expires_at=start + _grant(requested, min_timeout, max_timeout))


class SubscriptionTable:
    """The publisher's subscriptions for one service.

    ``clock`` returns seconds (``time.monotonic`` by default, a fake in tests). ``policy`` and
    ``allow_loopback`` go to :func:`validate_callback`. The table holds at most ``max_subscriptions``;
    a further subscriber is answered 503, a 5xx as Tables 4-4 and 4-5 allow.
    """

    def __init__(
        self,
        *,
        max_subscriptions: int = 64,
        min_timeout: int = _MIN_TIMEOUT,
        max_timeout: int = _DEFAULT_MAX_TIMEOUT,
        policy: str = "lan",
        allow_loopback: bool = False,
        clock: Callable[[], float] = time.monotonic,
        new_sid: Callable[[], str] | None = None,
    ) -> None:
        self.max_subscriptions = max_subscriptions
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        self.policy = policy
        self.allow_loopback = allow_loopback
        self._clock = clock
        self._new_sid = new_sid or (lambda: f"uuid:{uuid.uuid4()}")
        self._table: dict[str, Subscription] = {}

    def __len__(self) -> int:
        self.sweep()
        return len(self._table)

    def get(self, sid: str) -> Subscription | None:
        self.sweep()
        return self._table.get(sid)

    def sweep(self) -> list[str]:
        """Remove expired subscriptions and return their SIDs."""
        now = self._clock()
        gone = [sid for sid, sub in self._table.items() if sub.expires_at <= now]
        for sid in gone:
            del self._table[sid]
        return gone

    def subscribe(
        self,
        *,
        callback: str | None,
        nt: str | None,
        sid: str | None = None,
        timeout: str | None = None,
        statevar: str | None = None,
        peer: str | None = None,
    ) -> Subscription:
        """Accept a SUBSCRIBE with NT and CALLBACK (clause 4.1.2). A SID with NT or CALLBACK is 400; a missing
        or invalid CALLBACK or an NT other than ``upnp:event`` is 412; a full table is 503. The new
        subscription's ``seq`` is 0, the key of the initial event."""
        if sid is not None:
            raise SubscribeError(400, "SID and NT or CALLBACK are incompatible header fields")
        if nt != "upnp:event":
            raise SubscribeError(412, "NT must be upnp:event")
        urls = validate_callback(
            callback or "", peer=peer, policy=self.policy, allow_loopback=self.allow_loopback
        )
        self.sweep()
        if len(self._table) >= self.max_subscriptions:
            raise SubscribeError(503, "no resources for another subscription")
        granted = _grant(
            parse_timeout(timeout, default=self.min_timeout), self.min_timeout, self.max_timeout
        )
        names = tuple(n.strip() for n in statevar.split(",") if n.strip()) if statevar else None
        new = self._new_sid()
        while new in self._table:
            new = self._new_sid()
        sub = Subscription(new, urls, self._clock() + granted, 0, names)
        self._table[new] = sub
        return sub

    def renew(
        self,
        *,
        sid: str | None,
        timeout: str | None = None,
        nt: str | None = None,
        callback: str | None = None,
    ) -> Subscription:
        """Renew with SID only (clause 4.1.3): SID with NT or CALLBACK is 400; a missing, empty, unknown or
        expired SID is 412 (Table 4-5)."""
        if sid is not None and (nt is not None or callback is not None):
            raise SubscribeError(400, "SID and NT or CALLBACK are incompatible header fields")
        known = self._lookup(sid)
        updated = renew(
            known,
            parse_timeout(timeout, default=self.min_timeout),
            now=self._clock(),
            min_timeout=self.min_timeout,
            max_timeout=self.max_timeout,
        )
        self._table[known.sid] = updated
        return updated

    def cancel(
        self, *, sid: str | None, nt: str | None = None, callback: str | None = None
    ) -> None:
        """UNSUBSCRIBE (clause 4.1.4, Table 4-6): the same 400 and 412 rules as a renewal."""
        if sid is not None and (nt is not None or callback is not None):
            raise SubscribeError(400, "SID and NT or CALLBACK are incompatible header fields")
        del self._table[self._lookup(sid).sid]

    def _lookup(self, sid: str | None) -> Subscription:
        if not sid or _SID.fullmatch(sid) is None:
            raise SubscribeError(412, "SID is missing, empty or malformed")
        self.sweep()
        found = self._table.get(sid)
        if found is None:
            raise SubscribeError(412, "SID does not match a known, unexpired subscription")
        return found

    def next_event_key(self, sid: str) -> int:
        """The SEQ for the next NOTIFY to ``sid``, advancing the key: 0 for the initial event, then +1
        each time, wrapped from 4294967295 to 1 (clause 4.3.2)."""
        found = self._lookup(sid)
        following = 1 if found.seq >= MAX_SEQ else found.seq + 1
        self._table[sid] = replace(found, seq=following)
        return found.seq


def notify_message(callback_url: str, sid: str, seq: int, properties: Mapping[str, str]) -> bytes:
    """The NOTIFY event message (clause 4.3.2) for one subscriber: NOTIFY to the URL's path, HOST,
    CONTENT-TYPE ``text/xml; charset="utf-8"``, NT ``upnp:event``, NTS ``upnp:propchange``, SID, SEQ and
    CONTENT-LENGTH, with a ``propertyset`` of one ``property`` per variable. Values are escaped; a name
    must be an unqualified XML name (the mapping already keeps each variable once, as the text requires);
    SEQ is a 32-bit unsigned integer."""
    if not 0 <= seq <= MAX_SEQ:
        raise ValueError("SEQ is a 32-bit unsigned integer (clause 4.3.2)")
    if _SID.fullmatch(sid) is None:
        raise ValueError("SID is uuid: followed by a UUID")
    if any(ord(c) < 0x21 or ord(c) > 0x7E for c in callback_url):
        raise ValueError("the delivery URL holds a space, control or non-ASCII character")
    parts = urlsplit(callback_url)
    if parts.scheme != "http" or not parts.netloc:
        raise ValueError("the delivery URL is an http:// URL")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    props = []
    for name, value in properties.items():
        if _NAME.fullmatch(name) is None:
            raise ValueError(f"{name[:40]!r} is not an unqualified XML name")
        if _BAD_XML.search(value):
            raise ValueError(f"the value of {name} holds a character XML 1.0 cannot carry")
        escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        props.append(f"<e:property><{name}>{escaped}</{name}></e:property>")
    body = (
        '<?xml version="1.0"?>\r\n<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
        + "".join(props)
        + "</e:propertyset>"
    ).encode()
    head = (
        f"NOTIFY {path} HTTP/1.1\r\nHOST: {parts.netloc}\r\n"
        'CONTENT-TYPE: text/xml; charset="utf-8"\r\n'
        f"NT: upnp:event\r\nNTS: upnp:propchange\r\nSID: {sid}\r\nSEQ: {seq}\r\n"
        f"CONTENT-LENGTH: {len(body)}\r\n\r\n"
    )
    return head.encode("ascii") + body


async def notify(subscription: Subscription, props: dict) -> None:
    """Pending behaviour defined by UDA 2.0 eventing.

    Not implemented yet. See the ``events.notify()`` row in ROADMAP.md; this stub raises
    on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("notify() is not implemented: UDA 2.0 eventing")
