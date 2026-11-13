"""SSDP message layer against UPnP Device Architecture 2.0 (2020-04-17), clauses 1.1.4, 1.2.2 to 1.2.4 and
1.3.2 to 1.3.3. The messages are built by the code under test and checked field by field; none is copied
from the specification."""

from __future__ import annotations

import pytest

from devicespy.advertise import (
    SSDP_HOST_V6_LINK,
    SSDP_HOST_V6_SITE,
    Advertisement,
    BootIds,
    Device,
    SsdpConfig,
    SsdpError,
    address_scope,
    advertisement_set,
    alive_message,
    byebye_message,
    matching_advertisements,
    mx_delay,
    parse_search_request,
    refresh_interval,
    search_response,
    ssdp_host_for,
    tcp_search_reply,
    update_message,
)

ROOT_UUID = "uuid:2fac1234-31f8-11b4-a222-08002b34c003"
EMB_UUID = "uuid:2fac1234-31f8-11b4-a222-08002b34c004"
EMB2_UUID = "uuid:2fac1234-31f8-11b4-a222-08002b34c005"
SWITCH = "urn:schemas-upnp-org:service:SwitchPower:1"
DIMMING = "urn:schemas-upnp-org:service:Dimming:2"
ROOT = Device(
    ROOT_UUID,
    "urn:schemas-upnp-org:device:BinaryLight:1",
    (SWITCH, SWITCH),
    (
        Device(EMB_UUID, "urn:example-com:device:Sensor:1", (DIMMING,)),
        Device(EMB2_UUID, "urn:example-com:device:Sensor:1", (DIMMING,)),
    ),
)
CONFIG = SsdpConfig(
    "http://192.168.1.10:49152/desc.xml",
    "linux/6.1 UPnP/2.0 example/1.0",
    bootid=7,
    configid=3,
    searchport=49200,
)


def parse(message: bytes) -> tuple[str, dict[str, str]]:
    text = message.decode("ascii")
    assert text.endswith("\r\n\r\n")
    start, *lines = text[:-4].split("\r\n")
    return start, {k.upper(): v.strip() for k, _, v in (line.partition(":") for line in lines)}


def test_advertisement_set_is_3_plus_2d_plus_k():
    rows = advertisement_set(ROOT)
    # d = 2 embedded devices; k = 1 (SwitchPower, repeated within the root, once) + 1 + 1 (Dimming in
    # each embedded device, announced separately)
    assert len(rows) == 3 + 2 * 2 + 3
    assert rows[:3] == [
        Advertisement("upnp:rootdevice", f"{ROOT_UUID}::upnp:rootdevice"),
        Advertisement(ROOT_UUID, ROOT_UUID),
        Advertisement(ROOT.device_type, f"{ROOT_UUID}::{ROOT.device_type}"),
    ]
    assert Advertisement(SWITCH, f"{ROOT_UUID}::{SWITCH}") in rows
    assert sum(r.nt == DIMMING for r in rows) == 2
    assert Advertisement(EMB_UUID, EMB_UUID) in rows


@pytest.mark.parametrize(
    "bad",
    [
        Device("uuid:not-a-uuid", "urn:schemas-upnp-org:device:X:1"),
        Device(ROOT_UUID, "urn:schemas-upnp-org:service:X:1"),
        Device(ROOT_UUID, "urn:schemas-upnp-org:device:X:1", ("upnp:rootdevice",)),
        Device(ROOT_UUID, "urn:schemas-upnp-org:device:X"),
    ],
)
def test_malformed_identifiers_are_refused(bad):
    with pytest.raises(SsdpError):
        advertisement_set(bad)


def test_alive_message_fields_and_order():
    ad = advertisement_set(ROOT)[0]
    start, fields = parse(alive_message(ad, CONFIG))
    assert start == "NOTIFY * HTTP/1.1"
    assert fields["HOST"] == "239.255.255.250:1900"
    assert fields["NTS"] == "ssdp:alive"
    assert fields["CACHE-CONTROL"] == "max-age=1800"
    assert fields["NT"] == "upnp:rootdevice"
    assert fields["USN"] == f"{ROOT_UUID}::upnp:rootdevice"
    assert fields["LOCATION"].startswith("http://")
    assert fields["BOOTID.UPNP.ORG"] == "7"
    assert fields["CONFIGID.UPNP.ORG"] == "3"
    assert fields["SEARCHPORT.UPNP.ORG"] == "49200"
    assert "UPnP/2.0" in fields["SERVER"]


def test_byebye_message_has_no_cache_control_location_or_server():
    ad = advertisement_set(ROOT)[2]
    start, fields = parse(byebye_message(ad, CONFIG))
    assert start == "NOTIFY * HTTP/1.1"
    assert fields["NTS"] == "ssdp:byebye"
    assert set(fields) == {"HOST", "NT", "NTS", "USN", "BOOTID.UPNP.ORG", "CONFIGID.UPNP.ORG"}
    assert fields["NT"] == ROOT.device_type
    assert fields["BOOTID.UPNP.ORG"] == "7"


def test_every_alive_has_a_matching_byebye():
    rows = advertisement_set(ROOT)
    alive = [parse(alive_message(r, CONFIG))[1] for r in rows]
    bye = [parse(byebye_message(r, CONFIG))[1] for r in rows]
    assert [(a["NT"], a["USN"]) for a in alive] == [(b["NT"], b["USN"]) for b in bye]


def test_update_message_carries_old_and_next_bootid():
    ad = advertisement_set(ROOT)[0]
    start, fields = parse(update_message(ad, CONFIG, 8))
    assert start == "NOTIFY * HTTP/1.1"
    assert fields["NTS"] == "ssdp:update"
    assert fields["BOOTID.UPNP.ORG"] == "7"
    assert fields["NEXTBOOTID.UPNP.ORG"] == "8"
    assert "CACHE-CONTROL" not in fields
    assert "SERVER" not in fields
    for bad in (7, 6, 2**31):
        with pytest.raises(SsdpError, match="NEXTBOOTID"):
            update_message(ad, CONFIG, bad)


def test_boot_and_config_ids():
    ids = BootIds(7, 3)
    assert ids.after_reboot() == BootIds(8, 3)
    old, new, after = ids.update()
    assert (old, new, after) == (7, 8, BootIds(8, 3))
    assert ids.update(20)[1] == 20
    with pytest.raises(SsdpError):
        ids.update(7)
    assert ids.with_configuration_change() == BootIds(7, 4)
    with pytest.raises(SsdpError):
        BootIds(2**31 - 1).after_reboot()
    with pytest.raises(SsdpError):
        BootIds(1, 2**24 - 1).with_configuration_change()
    with pytest.raises(SsdpError):
        BootIds(2**31)
    with pytest.raises(SsdpError):
        SsdpConfig("http://h/d.xml", "a/1 UPnP/2.0 b/1", bootid=0, configid=2**24)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"server": "linux/6 UPnP/1.1 x/1"},
        {"server": "linux/6 x/1"},
        {"location": "/desc.xml"},
        {"location": "http://h/\r\nX: y"},
        {"searchport": 1900},
        {"max_age": 0},
    ],
)
def test_config_refuses_what_the_clauses_forbid(kwargs):
    base = {"location": "http://h/d.xml", "server": "a/1 UPnP/2.0 b/1", "bootid": 1, "configid": 1}
    with pytest.raises(SsdpError):
        SsdpConfig(**{**base, **kwargs})


MSEARCH = (
    b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\n'
    b"MX: 3\r\nST: ssdp:all\r\nUSER-AGENT: x/1 UPnP/2.0 y/1\r\n\r\n"
)


def test_parse_search_request():
    request = parse_search_request(MSEARCH)
    assert (request.st, request.mx, request.multicast) == ("ssdp:all", 3, True)
    lower = MSEARCH.replace(b"MX:", b"mx:").replace(b"ST:", b"st:")
    assert parse_search_request(lower).mx == 3
    unicast = MSEARCH.replace(b"239.255.255.250:1900", b"192.168.1.10:1900").replace(
        b"MX: 3\r\n", b""
    )
    request = parse_search_request(unicast)
    assert request.multicast is False
    assert request.mx is None
    tcp = MSEARCH.replace(b"MX: 3", b"MX: 3\r\nTCPPORT.UPNP.ORG: 50000")
    assert parse_search_request(tcp).tcpport == 50000


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b"MX: 3\r\n", b""),  # multicast without MX is discarded (1.3.3)
        (b"MX: 3", b"MX: 0"),
        (b"MX: 3", b"MX: -1"),
        (b"MX: 3", b"MX: 3.5"),
        (b"MX: 3", b"MX: 3\r\nMX: 4"),
        (b'MAN: "ssdp:discover"', b"MAN: ssdp:discover"),
        (b'MAN: "ssdp:discover"', b'MAN: "ssdp:other"'),
        (b"ST: ssdp:all\r\n", b""),
        (b"M-SEARCH * HTTP/1.1", b"M-SEARCH / HTTP/1.1"),
        (b"M-SEARCH * HTTP/1.1", b"NOTIFY * HTTP/1.1"),
        (b"MX: 3", b"BROKEN LINE"),
        (b"\r\n\r\n", b"\r\n"),
        (b"MX: 3", b"MX: 3\r\nTCPPORT.UPNP.ORG: 80"),
        (b"MX: 3", "MX: é".encode()),
    ],
)
def test_malformed_search_requests_are_refused(old, new):
    with pytest.raises(SsdpError):
        parse_search_request(MSEARCH.replace(old, new))


def test_search_datagram_bounds():
    with pytest.raises(SsdpError, match="too large"):
        parse_search_request(MSEARCH + b"X: " + b"a" * 9000)
    many = MSEARCH.replace(
        b"\r\n\r\n", b"".join(b"\r\nH%d: v" % i for i in range(70)) + b"\r\n\r\n"
    )
    with pytest.raises(SsdpError, match="too many"):
        parse_search_request(many)


def test_mx_random_delay_is_bounded_by_mx_and_capped_at_five():
    assert mx_delay(3, lambda: 0.0) == 0.0
    assert mx_delay(3, lambda: 0.5) == pytest.approx(1.5)
    assert mx_delay(3, lambda: 0.999999) < 3
    assert mx_delay(120, lambda: 0.999999) < 5  # an MX above 5 is taken as 5 (clause 1.3.3)
    assert 0 <= mx_delay(2) < 2
    with pytest.raises(SsdpError):
        mx_delay(0)


def test_refresh_interval_is_under_half_the_max_age():
    assert refresh_interval(1800, lambda: 0.0) == 0.0
    assert refresh_interval(1800, lambda: 0.999999) < 900
    with pytest.raises(SsdpError):
        refresh_interval(0)


def test_search_targets():
    assert len(matching_advertisements(ROOT, "ssdp:all")) == len(advertisement_set(ROOT))
    assert matching_advertisements(ROOT, "upnp:rootdevice") == [advertisement_set(ROOT)[0]]
    assert matching_advertisements(ROOT, EMB_UUID) == [Advertisement(EMB_UUID, EMB_UUID)]
    assert matching_advertisements(ROOT, "uuid:00000000-0000-0000-0000-000000000000") == []
    assert [a.usn for a in matching_advertisements(ROOT, SWITCH)] == [f"{ROOT_UUID}::{SWITCH}"]
    assert matching_advertisements(ROOT, "urn:schemas-upnp-org:service:Nothing:1") == []
    assert matching_advertisements(ROOT, "garbage") == []


def test_a_lower_version_is_answered_with_the_requested_version():
    # the device implements Dimming:2, so it answers a search for Dimming:1 naming version 1 (clause 1.3.2)
    lower = matching_advertisements(ROOT, "urn:schemas-upnp-org:service:Dimming:1")
    assert [a.nt for a in lower] == ["urn:schemas-upnp-org:service:Dimming:1"] * 2
    assert {a.usn for a in lower} == {
        f"{EMB_UUID}::urn:schemas-upnp-org:service:Dimming:1",
        f"{EMB2_UUID}::urn:schemas-upnp-org:service:Dimming:1",
    }
    assert matching_advertisements(ROOT, "urn:schemas-upnp-org:service:Dimming:3") == []


def test_search_response_message():
    (message,) = search_response(ROOT, "upnp:rootdevice", config=CONFIG, now=0)
    start, fields = parse(message)
    assert start == "HTTP/1.1 200 OK"
    assert fields["ST"] == "upnp:rootdevice"
    assert fields["EXT"] == ""
    assert fields["DATE"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert b"\r\nEXT:\r\n" in message
    assert b"NT:" not in message
    assert fields["BOOTID.UPNP.ORG"] == "7"
    assert fields["LOCATION"] == CONFIG.location
    assert search_response(ROOT, "urn:example:device:Nope:1", config=CONFIG) == []


# --- Annex A (IPv6), the TCP search reply, and the device-protection headers -------------------------------

V6_LINK_CONFIG = SsdpConfig(
    "http://[fe80::1234%25eth0]:49152/desc.xml",
    "linux/6.1 UPnP/2.0 example/1.0",
    bootid=7,
    configid=3,
    host=SSDP_HOST_V6_LINK,
)
V6_SITE_CONFIG = SsdpConfig(
    "http://[fd00:1::1234]:49152/desc.xml",
    "linux/6.1 UPnP/2.0 example/1.0",
    bootid=7,
    configid=3,
    host=SSDP_HOST_V6_SITE,
    nls="net-config-9",
)


@pytest.mark.parametrize(
    ("address", "scope"),
    [
        ("fe80::1", "link"),
        ("fe80::1%eth0", "link"),
        ("febf::1", "link"),  # the top of fe80::/10
        ("fd00::1", "site"),  # ULA
        ("fc00::1", "site"),
        ("2001:db8::1", "site"),  # GUA
        ("2a00:1450::1", "site"),
        ("2002:c000:204::1", None),  # 6to4
        ("2001:0:4136:e378:8000:63bf:3fff:fdd2", None),  # Teredo
        ("fe80::5efe:c000:204", None),  # ISATAP on a link-local prefix
        ("2001:db8::200:5efe:c000:204", None),  # ISATAP
        ("::1", None),
        ("::", None),
        ("ff02::c", None),  # multicast is not a source
        ("::ffff:192.0.2.1", None),
    ],
)
def test_ipv6_scope_selection(address, scope):
    # Annex A.2.3 and Table A-1: link-local address with FF02::C, ULA and GUA with FF05::C, never global
    assert address_scope(address) == scope


def test_ipv6_scope_selection_picks_the_group_and_refuses_the_rest():
    assert ssdp_host_for("fe80::1") == "[FF02::C]:1900"
    assert ssdp_host_for("fd12:3456::1") == "[FF05::C]:1900"
    assert ssdp_host_for("2001:db8::7") == "[FF05::C]:1900"
    # a temporary address (RFC 4941) cannot be told from its bytes: the caller says
    assert address_scope("2001:db8::7", temporary=True) is None
    with pytest.raises(SsdpError, match="not used"):
        ssdp_host_for("2002:c000:204::1")
    with pytest.raises(SsdpError, match="not an IPv6"):
        address_scope("192.0.2.1")
    with pytest.raises(SsdpError, match="not an IPv6"):
        address_scope("nonsense")


def test_ipv6_messages_carry_opt_and_nls():
    # A.4.1: OPT with ns=01 and the NLS field; A.4.2 to A.4.4 and A.4.6 put them in every message type
    ad = Advertisement("upnp:rootdevice", f"{ROOT_UUID}::upnp:rootdevice")
    first, fields = parse(alive_message(ad, V6_LINK_CONFIG))
    assert first == "NOTIFY * HTTP/1.1"
    assert fields["HOST"] == "[FF02::C]:1900"
    assert fields["OPT"] == '"http://schemas.upnp.org/upnp/1/0/"; ns=01'
    assert fields["01-NLS"] == "7"  # defaults to the BOOTID, which A.4.1 allows
    assert fields["LOCATION"].startswith("http://[fe80::1234%25eth0]:49152/")
    _, bye = parse(byebye_message(ad, V6_LINK_CONFIG))
    assert (bye["OPT"], bye["01-NLS"]) == (fields["OPT"], "7")
    assert "LOCATION" not in bye
    _, update = parse(update_message(ad, V6_SITE_CONFIG, 9))
    assert update["HOST"] == "[FF05::C]:1900"
    assert (update["OPT"], update["01-NLS"]) == (fields["OPT"], "net-config-9")
    (reply,) = search_response(ROOT, "upnp:rootdevice", config=V6_SITE_CONFIG, now=0)
    _, answer = parse(reply)
    assert (answer["OPT"], answer["01-NLS"]) == (fields["OPT"], "net-config-9")
    assert answer["ST"] == "upnp:rootdevice"
    # IPv4 messages do not
    _, v4 = parse(alive_message(ad, CONFIG))
    assert "OPT" not in v4
    assert "01-NLS" not in v4


def test_ipv6_config_refuses_ipv4_and_out_of_scope_locations():
    base = {"server": "linux/6.1 UPnP/2.0 example/1.0", "bootid": 1, "configid": 1}
    with pytest.raises(SsdpError, match="IPv4"):  # A.4.2: never an IPv4 address in an IPv6 LOCATION
        SsdpConfig("http://192.0.2.1/d.xml", host=SSDP_HOST_V6_LINK, **base)
    with pytest.raises(SsdpError, match="scope"):  # a ULA on the link-local group
        SsdpConfig("http://[fd00::1]/d.xml", host=SSDP_HOST_V6_LINK, **base)
    with pytest.raises(SsdpError, match="scope"):  # a link-local address on the site group
        SsdpConfig("http://[fe80::1]/d.xml", host=SSDP_HOST_V6_SITE, **base)
    with pytest.raises(SsdpError, match="scope"):  # a temporary-looking transition address
        SsdpConfig("http://[2002:c000:204::1]/d.xml", host=SSDP_HOST_V6_SITE, **base)
    with pytest.raises(SsdpError, match="IPv6 host"):
        SsdpConfig("http://[fd00::1]/d.xml", host="[FF08::C]:1900", **base)
    with pytest.raises(SsdpError, match="1 to 64"):
        SsdpConfig("http://[fd00::1]/d.xml", host=SSDP_HOST_V6_SITE, nls="x" * 65, **base)
    # a name is not judged: its resolution belongs to the device (A.2.3 item j)
    SsdpConfig("http://device.example.com/d.xml", host=SSDP_HOST_V6_SITE, **base)


def test_a_multicast_m_search_to_an_ipv6_group_needs_mx():
    # A.4.5: M-SEARCH to [FF0X::C]:1900 is a multicast search; clause 1.3.3 discards one without MX
    for group in ("[FF02::C]:1900", "[ff05::c]:1900", "[FF02::C]"):
        message = (
            f'M-SEARCH * HTTP/1.1\r\nHOST: {group}\r\nMAN: "ssdp:discover"\r\nST: ssdp:all\r\n\r\n'
        ).encode()
        with pytest.raises(SsdpError, match="without MX"):
            parse_search_request(message)
        request = parse_search_request(message.replace(b"\r\nST:", b"\r\nMX: 2\r\nST:"))
        assert request.multicast
        assert request.mx == 2
    unicast = b'M-SEARCH * HTTP/1.1\r\nHOST: [fe80::1]:1900\r\nMAN: "ssdp:discover"\r\nST: ssdp:all\r\n\r\n'
    assert not parse_search_request(
        unicast
    ).multicast  # a unicast M-SEARCH to an IPv6 device needs no MX


def test_tcp_search_reply_is_one_message_listing_every_usn():
    # clause 1.3.3: "1 message replying to all applicable USN", the USNs a comma separated list
    (one,) = tcp_search_reply(ROOT, "urn:example-com:device:Sensor:1", config=CONFIG, now=0)
    first, fields = parse(one)
    assert first == "HTTP/1.1 200 OK"
    assert fields["ST"] == "urn:example-com:device:Sensor:1"
    assert fields["USN"] == (
        f"{EMB_UUID}::urn:example-com:device:Sensor:1, {EMB2_UUID}::urn:example-com:device:Sensor:1"
    )
    assert fields["LOCATION"] == CONFIG.location
    assert fields["BOOTID.UPNP.ORG"] == "7"
    # the UDP answer is one message per USN
    assert len(search_response(ROOT, "urn:example-com:device:Sensor:1", config=CONFIG, now=0)) == 2
    # ssdp:all: one message per distinct ST, the USNs of a shared ST listed together
    everything = tcp_search_reply(ROOT, "ssdp:all", config=CONFIG, now=0)
    targets = [parse(m)[1]["ST"] for m in everything]
    assert len(targets) == len(set(targets))
    by_st = {parse(m)[1]["ST"]: parse(m)[1]["USN"] for m in everything}
    assert by_st[DIMMING] == f"{EMB_UUID}::{DIMMING}, {EMB2_UUID}::{DIMMING}"
    assert by_st["upnp:rootdevice"] == f"{ROOT_UUID}::upnp:rootdevice"
    assert len(everything) == len(
        {ad.nt for ad in advertisement_set(ROOT)}
    )  # shared STs share a message
    # a search target the device does not hold is not answered
    assert tcp_search_reply(ROOT, "urn:example-com:device:Nothing:1", config=CONFIG) == []


def test_search_request_reads_the_control_point_headers():
    message = MSEARCH.replace(
        b"MX: 3",
        b"MX: 3\r\nCPFN.UPNP.ORG: Living room\r\nCPUUID.UPNP.ORG: " + EMB_UUID.encode(),
    )
    request = parse_search_request(message)
    assert request.cpfn == "Living room"
    assert request.cpuuid == EMB_UUID
    plain = parse_search_request(MSEARCH)
    assert plain.cpfn is None
    assert plain.cpuuid is None
    with pytest.raises(SsdpError, match="CPUUID"):
        parse_search_request(message.replace(EMB_UUID.encode(), b"uuid:nope"))
    with pytest.raises(SsdpError, match="twice"):
        parse_search_request(message.replace(b"MX: 3", b"MX: 3\r\nCPFN.UPNP.ORG: again"))


def test_securelocation_is_an_https_base_url_in_alive_update_and_search_response():
    secure = SsdpConfig(
        "http://192.168.1.10:49152/desc.xml",
        "linux/6.1 UPnP/2.0 example/1.0",
        bootid=7,
        configid=3,
        securelocation="https://192.168.1.10:49153/desc.xml",
    )
    ad = Advertisement("upnp:rootdevice", f"{ROOT_UUID}::upnp:rootdevice")
    for message in (alive_message(ad, secure), update_message(ad, secure, 9)):
        assert parse(message)[1]["SECURELOCATION.UPNP.ORG"] == "https://192.168.1.10:49153/desc.xml"
    (reply,) = search_response(ROOT, "upnp:rootdevice", config=secure, now=0)
    assert parse(reply)[1]["SECURELOCATION.UPNP.ORG"] == "https://192.168.1.10:49153/desc.xml"
    assert "SECURELOCATION.UPNP.ORG" not in parse(byebye_message(ad, secure))[1]
    assert "SECURELOCATION.UPNP.ORG" not in parse(alive_message(ad, CONFIG))[1]
    with pytest.raises(SsdpError, match="https"):
        SsdpConfig(
            CONFIG.location, CONFIG.server, 1, 1, securelocation="http://192.168.1.10/desc.xml"
        )
