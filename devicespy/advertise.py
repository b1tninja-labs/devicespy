"""SSDP alive, byebye, update and search responses (UPnP Device Architecture 2.0, 2020-04-17).

This module is the message layer: it decides which NT and USN values a device owes (clause 1.2.2,
Tables 1-1 to 1-3), writes the NOTIFY and search-response messages (clauses 1.2.2 to 1.2.4 and 1.3.3),
tracks BOOTID.UPNP.ORG and CONFIGID.UPNP.ORG, reads and answers an M-SEARCH (clauses 1.3.2 and 1.3.3)
including the random delay bounded by MX, and refuses hostile datagrams. It opens no socket: sending
and the multicast group belong to ``announce``, which is not implemented yet.

Clause numbers are those of the PDF's own headings (read 2026-11-13; see docs/rfc-map.md). The text of
the specification is not reproduced here.

IPv6 (Annex A of the same document): :func:`address_scope` and :func:`ssdp_host_for` decide which multicast
group an address may announce on (Table A-1, A.2.3), and a :class:`SsdpConfig` whose ``host`` is an IPv6
group adds the OPT and NLS header fields every IPv6 message carries (A.4.1 to A.4.6) and refuses a LOCATION
that is an IPv4 literal or outside the group's scope (A.4.2). A search over TCP (``TCPPORT.UPNP.ORG``) is
answered with :func:`tcp_search_reply` (clause 1.3.3). Device protection is only its headers here:
``SECURELOCATION.UPNP.ORG`` on a config, ``CPFN.UPNP.ORG`` and ``CPUUID.UPNP.ORG`` read from a search.
"""

from __future__ import annotations

import ipaddress
import random
import re
from dataclasses import dataclass
from email.utils import formatdate
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "MAX_DATAGRAM",
    "SSDP_HOST",
    "SSDP_HOST_V6_LINK",
    "SSDP_HOST_V6_SITE",
    "Advertisement",
    "BootIds",
    "Device",
    "SearchRequest",
    "SsdpConfig",
    "SsdpError",
    "address_scope",
    "advertisement_set",
    "alive_message",
    "announce",
    "byebye_message",
    "matching_advertisements",
    "mx_delay",
    "parse_search_request",
    "refresh_interval",
    "search_response",
    "ssdp_host_for",
    "tcp_search_reply",
    "update_message",
]

#: Clause 1.2.2: the host and port reserved for SSDP by IANA (IPv4).
SSDP_HOST = "239.255.255.250:1900"
#: Annex A.2.3, A.4.2: FF0X::C with scope 2 (link-local) or 5 (site-local), port 1900.
SSDP_HOST_V6_LINK = "[FF02::C]:1900"
SSDP_HOST_V6_SITE = "[FF05::C]:1900"
_V6_GROUPS = {SSDP_HOST_V6_LINK.lower(): "link", SSDP_HOST_V6_SITE.lower(): "site"}
#: Annex A.4.1: the OPT field every IPv6 message carries, with its namespace prefix 01 for the NLS field.
_OPT = '"http://schemas.upnp.org/upnp/1/0/"; ns=01'
#: A datagram larger than this is refused unread: UDP carries at most 65507 payload octets over IPv4.
MAX_DATAGRAM = 8192
_MAX_HEADERS = 64
_MAX_BOOTID = 2**31 - 1  # clause 1.2.2: a non-negative 31-bit integer
_MAX_CONFIGID = 2**24 - 1  # clause 1.2.2: UPnP 2.0 devices assign 0 to 16777215
_MAX_MX_ASSUMED = 5  # clause 1.3.3: a larger MX is treated as 5 or less
_SEARCHPORT_RANGE = range(49152, 65536)
_UUID = re.compile(
    r"uuid:(?:[0-9A-Fa-f]{2}){4,}-(?:[0-9A-Fa-f]{2}){2,}-(?:[0-9A-Fa-f]{2}){2,}"
    r"-(?:[0-9A-Fa-f]{2}){2,}-(?:[0-9A-Fa-f]{2}){6,}"
)  # clause 1.1.4 grammar
_TYPE_URN = re.compile(
    r"urn:[A-Za-z0-9-]+(?::[A-Za-z0-9._-]+){2}:[0-9]+"
)  # urn:domain:device|service:type:ver
_SERVER = re.compile(
    r"[^\s/]+/\S+ UPnP/2\.0 [^\s/]+/\S+"
)  # clause 1.2.2: OS/ver UPnP/2.0 product/ver


class SsdpError(ValueError):
    """A message cannot be built or was refused; the datagram is to be discarded (clause 1.1.5)."""


_ISATAP_IID = (0x00005EFE, 0x02005EFE)  # the 32 bits before an embedded IPv4 address (RFC 5214)


def address_scope(address: str, *, temporary: bool = False) -> str | None:
    """The multicast scope an IPv6 unicast address may be used with (Annex A, Table A-1 and A.2.3).

    ``"link"`` for a link-local address (fe80::/10), which goes with FF02::C and nothing else;
    ``"site"`` for a Unique Local Address (fc00::/7) or a Globally Unique Address (2000::/3), which go with
    FF05::C; ``None`` for what the Annex keeps off UPnP discovery: a temporary address (the caller says,
    RFC 4941 addresses cannot be told from the bytes), the addresses of the IPv4 transition technologies
    6to4 (2002::/16), Teredo (2001::/32) and ISATAP, and every address that is not unicast. Raises
    :class:`SsdpError` for text that is not an IPv6 address; an IPv4 address has no IPv6 scope, so it too is
    an error. A zone suffix (``fe80::1%eth0``) is accepted and ignored.
    """
    text = address.split("%", 1)[0]
    try:
        ip = ipaddress.IPv6Address(text)
    except ValueError:
        raise SsdpError(f"{address[:60]!r} is not an IPv6 address") from None
    if temporary or ip.is_multicast or ip.is_loopback or ip.is_unspecified or ip.ipv4_mapped:
        return None
    if ip in ipaddress.IPv6Network("2002::/16") or ip in ipaddress.IPv6Network("2001::/32"):
        return None  # 6to4 and Teredo (A.2.3)
    if (int(ip) >> 32) & 0xFFFFFFFF in _ISATAP_IID:
        return None  # ISATAP (A.2.3)
    if ip.is_link_local:
        return "link"
    if ip in ipaddress.IPv6Network("fc00::/7") or ip in ipaddress.IPv6Network("2000::/3"):
        return "site"
    return None


def ssdp_host_for(address: str, *, temporary: bool = False) -> str:
    """The SSDP group host field for announcements sent from ``address``: ``[FF02::C]:1900`` for a link-local
    source, ``[FF05::C]:1900`` for a ULA or GUA (Table A-1; A.2.3 items a and f). Raises :class:`SsdpError`
    for an address Annex A keeps off discovery."""
    scope = address_scope(address, temporary=temporary)
    if scope is None:
        raise SsdpError(f"{address[:60]!r} is not used for UPnP discovery (Annex A.2.3, Table A-1)")
    return SSDP_HOST_V6_LINK if scope == "link" else SSDP_HOST_V6_SITE


@dataclass(frozen=True)
class Device:
    """A device as advertised: its UUID (``uuid:...``), its type URN, the service type URNs it holds, and
    its embedded devices. Versions in the URNs are the highest supported (clause 1.2.2)."""

    uuid: str
    device_type: str
    services: tuple[str, ...] = ()
    embedded: tuple[Device, ...] = ()


@dataclass(frozen=True)
class Advertisement:
    """One NT and its USN, as a row of Tables 1-1, 1-2 or 1-3."""

    nt: str
    usn: str


@dataclass(frozen=True)
class SsdpConfig:
    """The values every message carries. ``server`` has the three product tokens of clause 1.2.2.
    ``max_age`` is the CACHE-CONTROL max-age in seconds (the text says it should be at least 1800)."""

    location: str
    server: str
    bootid: int
    configid: int
    max_age: int = 1800
    searchport: int | None = None
    host: str = SSDP_HOST
    securelocation: str | None = None
    nls: str | None = None

    @property
    def ipv6(self) -> bool:
        """True when ``host`` is an IPv6 group, so the messages carry OPT and NLS (A.4.1)."""
        return self.host.startswith("[")

    @property
    def nls_value(self) -> str:
        """The NLS value: ``nls`` when given, else the BOOTID, which A.4.1 allows as the value."""
        return self.nls if self.nls is not None else str(self.bootid)

    def __post_init__(self) -> None:
        for name, value in (
            ("location", self.location),
            ("server", self.server),
            ("host", self.host),
            ("securelocation", self.securelocation or ""),
            ("nls", self.nls or ""),
        ):
            _no_newline(value, name)
        if self.securelocation is not None and not self.securelocation.startswith("https://"):
            raise SsdpError(
                "SECURELOCATION.UPNP.ORG is a base URL with the https scheme (clause 1.2.2)"
            )
        if self.nls is not None and not 1 <= len(self.nls) <= 64:
            raise SsdpError("the NLS value is 1 to 64 characters (Annex A.4.1)")
        if self.ipv6:
            self._check_ipv6()
        if not _SERVER.fullmatch(self.server):
            raise SsdpError(
                "SERVER needs the tokens OS/version UPnP/2.0 product/version (clause 1.2.2)"
            )
        if not self.location.startswith(("http://", "https://")):
            raise SsdpError("LOCATION is a single absolute URL (clause 1.2.2)")
        if not 0 <= self.bootid <= _MAX_BOOTID:
            raise SsdpError("BOOTID.UPNP.ORG is a non-negative 31-bit integer (clause 1.2.2)")
        if not 0 <= self.configid <= _MAX_CONFIGID:
            raise SsdpError(
                "CONFIGID.UPNP.ORG is 0 to 16777215 for a UPnP 2.0 device (clause 1.2.2)"
            )
        if self.max_age < 1:
            raise SsdpError("max-age is a positive number of seconds")
        if self.searchport is not None and self.searchport not in _SEARCHPORT_RANGE:
            raise SsdpError("SEARCHPORT.UPNP.ORG is 49152 to 65535 (clause 1.2.2)")

    def _check_ipv6(self) -> None:
        """Annex A.4.2: an IPv6 advertisement never carries an IPv4 literal in LOCATION, and a literal IPv6
        address in it is valid in the scope of the group it is sent to (A.2.3 items a and f)."""
        scope = _V6_GROUPS.get(self.host.lower())
        if scope is None:
            raise SsdpError("an IPv6 host is [FF02::C]:1900 or [FF05::C]:1900 (Annex A.2.3)")
        for what, url in (("LOCATION", self.location), ("SECURELOCATION", self.securelocation)):
            if url is None:
                continue
            name = (urlsplit(url).hostname or "").split("%", 1)[0]
            try:
                literal = ipaddress.ip_address(name)
            except ValueError:
                continue  # a fully qualified name: its resolution is the device's business (A.2.3 j)
            if isinstance(literal, ipaddress.IPv4Address):
                raise SsdpError(f"{what} is not an IPv4 address in an IPv6 message (Annex A.4.2)")
            if address_scope(name) != scope:
                raise SsdpError(
                    f"the {what} address is not valid in the {scope} scope (Annex A.2.3)"
                )


@dataclass(frozen=True)
class BootIds:
    """BOOTID and CONFIGID of a device, and the moves clause 1.2.2 and 1.2.4 allow.

    ``after_reboot`` is the increase on each initial announce; ``update`` yields the two values an
    ssdp:update carries (the BOOTID already used, and a NEXTBOOTID greater than it) and the state after
    the update, whose BOOTID is the NEXTBOOTID.
    """

    bootid: int
    configid: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.bootid <= _MAX_BOOTID or not 0 <= self.configid <= _MAX_CONFIGID:
            raise SsdpError("BOOTID is 31-bit and CONFIGID at most 16777215 (clause 1.2.2)")

    def after_reboot(self) -> BootIds:
        if self.bootid >= _MAX_BOOTID:
            raise SsdpError("BOOTID.UPNP.ORG has no larger 31-bit value")
        return BootIds(self.bootid + 1, self.configid)

    def update(self, nextbootid: int | None = None) -> tuple[int, int, BootIds]:
        """``(bootid, nextbootid, state_after)``; NEXTBOOTID must exceed the BOOTID (clause 1.2.4)."""
        following = self.bootid + 1 if nextbootid is None else nextbootid
        if following <= self.bootid or following > _MAX_BOOTID:
            raise SsdpError(
                "NEXTBOOTID.UPNP.ORG is a 31-bit integer greater than BOOTID (clause 1.2.4)"
            )
        return self.bootid, following, BootIds(following, self.configid)

    def with_configuration_change(self) -> BootIds:
        """CONFIGID changes whenever the description or any SCPD changes (clause 1.2.2)."""
        if self.configid >= _MAX_CONFIGID:
            raise SsdpError(
                "no CONFIGID.UPNP.ORG value above 16777215 is available to a UPnP 2.0 device"
            )
        return BootIds(self.bootid, self.configid + 1)


def _no_newline(value: str, what: str) -> None:
    if "\r" in value or "\n" in value or "\x00" in value:
        raise SsdpError(f"{what} holds a line break or NUL")


def _check_device(device: Device) -> None:
    if not _UUID.fullmatch(device.uuid):
        raise SsdpError(
            f"{device.uuid[:50]!r} is not uuid: followed by the clause 1.1.4 UUID format"
        )
    if not _TYPE_URN.fullmatch(device.device_type) or ":device:" not in device.device_type:
        raise SsdpError(f"{device.device_type[:60]!r} is not a device type URN")
    for service in device.services:
        if not _TYPE_URN.fullmatch(service) or ":service:" not in service:
            raise SsdpError(f"{service[:60]!r} is not a service type URN")


def advertisement_set(root: Device) -> list[Advertisement]:
    """The NT/USN rows a root device owes: three for the root (Table 1-1), two for each embedded device
    (Table 1-2) and one per distinct service type in each device (Table 1-3), 3+2d+k in all (clause 1.2.2).

    Two embedded devices holding the same service type each announce it; a repeated type within one
    device is announced once.
    """
    rows = [
        Advertisement("upnp:rootdevice", f"{root.uuid}::upnp:rootdevice"),
        Advertisement(root.uuid, root.uuid),
        Advertisement(root.device_type, f"{root.uuid}::{root.device_type}"),
    ]
    _check_device(root)

    def services(device: Device) -> None:
        for service in dict.fromkeys(device.services):
            rows.append(Advertisement(service, f"{device.uuid}::{service}"))

    def embedded(device: Device, depth: int) -> None:
        if depth > 16:
            raise SsdpError("devices are nested too deeply")
        for child in device.embedded:
            _check_device(child)
            rows.append(Advertisement(child.uuid, child.uuid))
            rows.append(Advertisement(child.device_type, f"{child.uuid}::{child.device_type}"))
            services(child)
            embedded(child, depth + 1)

    services(root)
    embedded(root, 0)
    return rows


def _message(start: str, fields: list[tuple[str, str]]) -> bytes:
    for name, value in fields:
        _no_newline(name, "header name")
        _no_newline(value, name)
    lines = [start, *(f"{name}: {value}" if value else f"{name}:" for name, value in fields)]
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


def _ids(config: SsdpConfig) -> list[tuple[str, str]]:
    ids = [("BOOTID.UPNP.ORG", str(config.bootid)), ("CONFIGID.UPNP.ORG", str(config.configid))]
    if config.searchport is not None:
        ids.append(("SEARCHPORT.UPNP.ORG", str(config.searchport)))
    return ids


def _v6(config: SsdpConfig) -> list[tuple[str, str]]:
    """OPT and NLS, which every IPv6 message carries (Annex A.4.1 to A.4.6); nothing for IPv4."""
    return [("OPT", _OPT), ("01-NLS", config.nls_value)] if config.ipv6 else []


def _secure(config: SsdpConfig) -> list[tuple[str, str]]:
    return [("SECURELOCATION.UPNP.ORG", config.securelocation)] if config.securelocation else []


def alive_message(ad: Advertisement, config: SsdpConfig) -> bytes:
    """NOTIFY with ssdp:alive (clause 1.2.2): HOST, CACHE-CONTROL, LOCATION, NT, NTS, SERVER, USN, then
    BOOTID, CONFIGID and, if set, SEARCHPORT."""
    return _message(
        "NOTIFY * HTTP/1.1",
        [
            ("HOST", config.host),
            ("CACHE-CONTROL", f"max-age={config.max_age}"),
            ("LOCATION", config.location),
            *_secure(config),
            *_v6(config),
            ("NT", ad.nt),
            ("NTS", "ssdp:alive"),
            ("SERVER", config.server),
            ("USN", ad.usn),
            *_ids(config),
        ],
    )


def byebye_message(ad: Advertisement, config: SsdpConfig) -> bytes:
    """NOTIFY with ssdp:byebye (clause 1.2.3): HOST, NT, NTS, USN, BOOTID and CONFIGID, and no
    CACHE-CONTROL, LOCATION or SERVER. A device revokes each ssdp:alive it sent, so the caller passes the
    same ``advertisement_set`` rows; the BOOTID is the one the alives used."""
    return _message(
        "NOTIFY * HTTP/1.1",
        [
            ("HOST", config.host),
            *_v6(config),
            ("NT", ad.nt),
            ("NTS", "ssdp:byebye"),
            ("USN", ad.usn),
            ("BOOTID.UPNP.ORG", str(config.bootid)),
            ("CONFIGID.UPNP.ORG", str(config.configid)),
        ],
    )


def update_message(ad: Advertisement, config: SsdpConfig, nextbootid: int) -> bytes:
    """NOTIFY with ssdp:update (clause 1.2.4): the BOOTID of ``config`` is the one used so far and
    NEXTBOOTID.UPNP.ORG is the new one, which must exceed it. HOST, LOCATION, NT, NTS, USN, BOOTID,
    CONFIGID, NEXTBOOTID and, if set, SEARCHPORT."""
    if not config.bootid < nextbootid <= _MAX_BOOTID:
        raise SsdpError(
            "NEXTBOOTID.UPNP.ORG is a 31-bit integer greater than BOOTID (clause 1.2.4)"
        )
    fields = [
        ("HOST", config.host),
        ("LOCATION", config.location),
        *_secure(config),
        *_v6(config),
        ("NT", ad.nt),
        ("NTS", "ssdp:update"),
        ("USN", ad.usn),
        ("BOOTID.UPNP.ORG", str(config.bootid)),
        ("CONFIGID.UPNP.ORG", str(config.configid)),
        ("NEXTBOOTID.UPNP.ORG", str(nextbootid)),
    ]
    if config.searchport is not None:
        fields.append(("SEARCHPORT.UPNP.ORG", str(config.searchport)))
    return _message("NOTIFY * HTTP/1.1", fields)


@dataclass(frozen=True)
class SearchRequest:
    """A parsed M-SEARCH. ``mx`` is the delay bound in seconds, None when absent."""

    st: str
    mx: int | None
    multicast: bool
    host: str
    tcpport: int | None = None
    cpfn: str | None = None
    cpuuid: str | None = None


def parse_search_request(data: bytes) -> SearchRequest:
    """Read an M-SEARCH datagram (clause 1.3.2), refusing anything malformed with :class:`SsdpError`.

    Refused: a datagram over ``MAX_DATAGRAM``, a start line other than ``M-SEARCH * HTTP/1.1``, more
    than 64 header lines, a header without a colon, a repeated MAN, ST, MX or HOST, a MAN other than
    ``"ssdp:discover"`` with its quotes, a missing ST or HOST, an MX that is not a plain decimal, and a
    multicast request (HOST is the SSDP group) with no MX, which clause 1.3.3 says to discard silently.
    A unicast request needs no MX. Field names are case-insensitive, values are not.
    """
    if len(data) > MAX_DATAGRAM:
        raise SsdpError("datagram too large")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise SsdpError("not ASCII") from None
    head, blank, _body = text.partition("\r\n\r\n")
    if not blank:
        raise SsdpError("no blank line ends the header")
    lines = head.split("\r\n")
    if lines[0] != "M-SEARCH * HTTP/1.1":
        raise SsdpError("not an M-SEARCH * HTTP/1.1 request")
    if len(lines) - 1 > _MAX_HEADERS:
        raise SsdpError("too many header fields")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        name, sep, value = line.partition(":")
        if not sep or not name or name != name.strip():
            raise SsdpError("a header line has no field name and colon")
        key = name.upper()
        if key in fields and key in {
            "MAN",
            "ST",
            "MX",
            "HOST",
            "TCPPORT.UPNP.ORG",
            "CPFN.UPNP.ORG",
            "CPUUID.UPNP.ORG",
        }:
            raise SsdpError(f"{key} appears twice")
        fields.setdefault(key, value.strip())
    if fields.get("MAN") != '"ssdp:discover"':
        raise SsdpError('MAN must be "ssdp:discover" in double quotes (clause 1.3.2)')
    st = fields.get("ST", "")
    host = fields.get("HOST", "")
    if not st or not host:
        raise SsdpError("ST and HOST are required (clause 1.3.2)")
    multicast = _is_ssdp_group(host)
    mx_text = fields.get("MX")
    mx = None
    if mx_text is not None:
        if not (mx_text.isascii() and mx_text.isdigit()) or len(mx_text) > 6:
            raise SsdpError("MX is a decimal integer number of seconds")
        mx = int(mx_text)
        if mx < 1:
            raise SsdpError("MX shall be at least 1 (clause 1.3.2)")
    if multicast and mx is None:
        raise SsdpError("a multicast M-SEARCH without MX is discarded (clause 1.3.3)")
    tcp = fields.get("TCPPORT.UPNP.ORG")
    tcpport = None
    if tcp is not None:
        if not (tcp.isascii() and tcp.isdigit()) or int(tcp) not in _SEARCHPORT_RANGE:
            raise SsdpError("TCPPORT.UPNP.ORG is 49152 to 65535 (clause 1.3.2)")
        tcpport = int(tcp)
    cpuuid = fields.get("CPUUID.UPNP.ORG")
    if cpuuid is not None and not _UUID.fullmatch(cpuuid):
        raise SsdpError("CPUUID.UPNP.ORG is uuid: followed by the clause 1.1.4 format")
    return SearchRequest(st, mx, multicast, host, tcpport, fields.get("CPFN.UPNP.ORG"), cpuuid)


def _is_ssdp_group(host: str) -> bool:
    """Whether a HOST field names an SSDP multicast group: 239.255.255.250 on any port as before, or the
    IPv6 groups FF02::C and FF05::C (Annex A.4.5), in any letter case."""
    if host.startswith("["):
        group, _, _ = host[1:].partition("]")
        return group.upper() in ("FF02::C", "FF05::C")
    return host.split(":")[0] == SSDP_HOST.split(":")[0]


def mx_delay(mx: int, rng: Callable[[], float] = random.random) -> float:
    """The random wait before answering a multicast M-SEARCH: between 0 and MX seconds, with an MX above 5
    taken as 5 (clause 1.3.3). ``rng`` returns a float in [0, 1)."""
    if mx < 1:
        raise SsdpError("MX shall be at least 1 (clause 1.3.2)")
    return rng() * min(mx, _MAX_MX_ASSUMED)


def refresh_interval(max_age: int, rng: Callable[[], float] = random.random) -> float:
    """When to re-advertise: a randomly distributed interval of less than half the max-age (clause 1.2.2)."""
    if max_age < 1:
        raise SsdpError("max-age is a positive number of seconds")
    return rng() * (max_age / 2)


def matching_advertisements(root: Device, st: str) -> list[Advertisement]:
    """What a device answers for search target ``st`` (clause 1.3.3), as (ST, USN) pairs held in
    :class:`Advertisement` (``nt`` carries the ST).

    ``ssdp:all`` matches every row of the advertisement set; ``upnp:rootdevice`` the root only; ``uuid:``
    a device with exactly that UUID; a type URN any device or service of that name whose highest supported
    version is at least the requested one, answered with the requested version (clause 1.3.2).
    """
    rows = advertisement_set(root)
    if st == "ssdp:all":
        return rows
    if st == "upnp:rootdevice":
        return [rows[0]]
    if st.startswith("uuid:"):
        return [Advertisement(st, st)] if any(r.nt == st for r in rows) else []
    match = _TYPE_URN.fullmatch(st)
    if match is None:
        return []
    name, _, wanted = st.rpartition(":")
    found: list[Advertisement] = []
    for row in rows:
        if not row.nt.startswith("urn:"):
            continue
        have_name, _, have = row.nt.rpartition(":")
        if have_name == name and int(wanted) <= int(have):
            prefix = row.usn.split("::", 1)[0]
            found.append(Advertisement(st, f"{prefix}::{st}"))
    return found


def search_response(
    device: Device, st: str, *, config: SsdpConfig, now: float | None = None
) -> list[bytes]:
    """The unicast 200 OK messages answering an M-SEARCH for ``st`` (UDA 2.0, clause 1.3.3), one per matching
    advertisement: CACHE-CONTROL, DATE, an empty EXT, LOCATION, SERVER, ST, USN, BOOTID, CONFIGID and, if
    set, SEARCHPORT. An empty list means the device does not answer. The caller applies ``mx_delay`` and
    sends on the interface the request arrived on, using that interface's LOCATION."""
    messages = []
    for ad in matching_advertisements(device, st):
        fields = [
            ("CACHE-CONTROL", f"max-age={config.max_age}"),
            ("DATE", formatdate(now, usegmt=True)),
            ("EXT", ""),
            ("LOCATION", config.location),
            *_secure(config),
            ("SERVER", config.server),
            *_v6(config),
            ("ST", ad.nt),
            ("USN", ad.usn),
            *_ids(config),
        ]
        messages.append(_message("HTTP/1.1 200 OK", fields))
    return messages


def tcp_search_reply(
    device: Device, st: str, *, config: SsdpConfig, now: float | None = None
) -> list[bytes]:
    """The reply to an M-SEARCH that carries ``TCPPORT.UPNP.ORG`` (clause 1.3.3): the same 200 OK as
    :func:`search_response`, sent over TCP to that port, "formatted as 1 message replying to all applicable
    USN" with the USNs "conveyed by a comma separated list". Over TCP the device need not spread or repeat
    the messages, so MX is ignored and there is no delay.

    One message is built for each distinct ST among the matches, since the ST field holds one search target:
    a search for ``ssdp:all`` answers each type and uuid separately (so a device list of 3+2d+k rows comes
    back as that many messages, fewer where two embedded devices share a service type), and any other
    search answers in exactly one message listing every USN. An empty list means the device does not
    answer. The clause says nothing about ST under ``ssdp:all``; grouping by ST is this library's reading.
    """
    grouped: dict[str, list[str]] = {}
    for ad in matching_advertisements(device, st):
        grouped.setdefault(ad.nt, []).append(ad.usn)
    messages = []
    for target, usns in grouped.items():
        fields = [
            ("CACHE-CONTROL", f"max-age={config.max_age}"),
            ("DATE", formatdate(now, usegmt=True)),
            ("EXT", ""),
            ("LOCATION", config.location),
            *_secure(config),
            ("SERVER", config.server),
            *_v6(config),
            ("ST", target),
            ("USN", ", ".join(usns)),
            *_ids(config),
        ]
        messages.append(_message("HTTP/1.1 200 OK", fields))
    return messages


async def announce(device: Device, interfaces: list) -> None:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``advertise.announce()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("announce() is not implemented: UDA 2.0")
