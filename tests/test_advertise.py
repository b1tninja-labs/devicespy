"""SSDP message layer against UPnP Device Architecture 2.0 (2020-04-17), clauses 1.1.4, 1.2.2 to 1.2.4 and
1.3.2 to 1.3.3. The messages are built by the code under test and checked field by field; none is copied
from the specification."""

from __future__ import annotations

import pytest

from devicespy.advertise import (
    Advertisement,
    BootIds,
    Device,
    SsdpConfig,
    SsdpError,
    advertisement_set,
    alive_message,
    byebye_message,
    matching_advertisements,
    mx_delay,
    parse_search_request,
    refresh_interval,
    search_response,
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
