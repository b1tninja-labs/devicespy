"""UPnPError responses and argument typing against UPnP Device Architecture 2.0 (2020-04-17): clause 3.2.5
(action error response, Table 3-3) and clause 2.5 (the dataType list of a state variable)."""

from __future__ import annotations

import datetime as dt

import pytest

from devicespy import xmlsafe
from devicespy.control import (
    CONTROL_NS,
    UPNP_ERRORS,
    UpnpError,
    parse_upnp_error,
    upnp_error_envelope,
)
from devicespy.scpd import DATA_TYPES, ArgumentError, coerce_argument


def test_upnp_error_envelope_round_trips():
    raw = upnp_error_envelope(402)
    assert parse_upnp_error(raw) == UpnpError(402, "Invalid Args")
    assert parse_upnp_error(upnp_error_envelope(501, "Busy & away")) == UpnpError(
        501, "Busy & away"
    )
    assert parse_upnp_error(upnp_error_envelope(718, "")) == UpnpError(718, "")
    assert b"<faultcode>s:Client</faultcode>" in raw
    assert b"<faultstring>UPnPError</faultstring>" in raw
    assert CONTROL_NS.encode() in raw
    assert b"s:encodingStyle=" in raw


def test_table_3_3_codes():
    assert UPNP_ERRORS[401] == "Invalid Action"
    assert UPNP_ERRORS[605] == "String Argument Too Long"
    assert sorted(UPNP_ERRORS) == [401, 402, 501, 600, 601, 602, 603, 604, 605]
    for usable in (613, 699, 700, 799, 800, 899):
        assert parse_upnp_error(upnp_error_envelope(usable, "x")).code == usable


@pytest.mark.parametrize("code", [0, 400, 403, 500, 606, 612, 900, -1])
def test_deprecated_reserved_and_unknown_codes_are_refused(code):
    with pytest.raises(ValueError, match="not a usable"):
        upnp_error_envelope(code)


def test_description_limits():
    with pytest.raises(ValueError, match="256"):
        upnp_error_envelope(501, "x" * 256)
    upnp_error_envelope(501, "x" * 255)
    with pytest.raises(ValueError, match="plain text"):
        upnp_error_envelope(501, "bell\x07")


def test_parse_upnp_error_refuses_what_is_not_an_action_error():
    ok = upnp_error_envelope(401)
    with pytest.raises(ValueError, match="Envelope"):
        parse_upnp_error(ok.replace(b"http://schemas.xmlsoap.org/soap/envelope/", b"urn:other"))
    with pytest.raises(ValueError, match="faultcode"):
        parse_upnp_error(ok.replace(b"s:Client", b"s:Server"))
    with pytest.raises(ValueError, match="UPnPError"):
        parse_upnp_error(ok.replace(b"urn:schemas-upnp-org:control-1-0", b"urn:other"))
    with pytest.raises(ValueError, match="errorCode"):
        parse_upnp_error(ok.replace(b"<errorCode>401", b"<errorCode>4x1"))
    with pytest.raises(ValueError, match="Fault"):
        parse_upnp_error(
            b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body/></s:Envelope>'
        )
    with pytest.raises(xmlsafe.XmlRefused):
        parse_upnp_error(b'<!DOCTYPE x [<!ENTITY a "b">]><x/>')


@pytest.mark.parametrize(
    ("data_type", "text", "expected"),
    [
        ("ui1", "255", 255),
        ("ui2", "65535", 65535),
        ("ui4", "4294967295", 4294967295),
        ("ui8", "18446744073709551615", 2**64 - 1),
        ("i1", "-128", -128),
        ("i2", "+32767", 32767),
        ("i4", "-2147483648", -(2**31)),
        ("i8", "9223372036854775807", 2**63 - 1),
        ("int", "-0042", -42),
        ("r4", "3.5E2", 350.0),
        ("r8", "-.5", -0.5),
        ("number", "1e3", 1000.0),
        ("float", "+1.25E-2", 0.0125),
        ("fixed.14.4", "12345678901234.1234", 12345678901234.1234),
        ("char", "x", "x"),
        ("string", "anything at all", "anything at all"),
        ("boolean", "1", True),
        ("boolean", "0", False),
        ("boolean", "Yes", True),
        ("boolean", "no", False),
        ("date", "2026-11-13", dt.date(2026, 11, 13)),
        ("dateTime", "2026-11-13T06:30:15", dt.datetime(2026, 11, 13, 6, 30, 15)),
        (
            "dateTime.tz",
            "2026-11-13T06:30:15Z",
            dt.datetime(2026, 11, 13, 6, 30, 15, tzinfo=dt.UTC),
        ),
        ("time", "06:30:15", dt.time(6, 30, 15)),
        (
            "time.tz",
            "06:30:15+01:00",
            dt.time(6, 30, 15, tzinfo=dt.timezone(dt.timedelta(hours=1))),
        ),
        ("bin.base64", "aGVsbG8=", b"hello"),
        ("bin.hex", "00ff10", b"\x00\xff\x10"),
        ("uri", "http://example.com/a?b=c", "http://example.com/a?b=c"),
        ("uuid", "2fac1234-31f8-11b4-a222-08002b34c003", "2fac1234-31f8-11b4-a222-08002b34c003"),
    ],
)
def test_argument_typing_accepts_the_clause_2_5_forms(data_type, text, expected):
    assert coerce_argument(data_type, text) == expected


@pytest.mark.parametrize(
    ("data_type", "text", "code"),
    [
        ("ui1", "256", 601),
        ("ui1", "-1", 402),  # no leading sign on an unsigned type
        ("ui1", "+1", 402),
        ("ui4", "4294967296", 601),
        ("i1", "128", 601),
        ("i4", "2147483648", 601),
        ("i4", "1.5", 402),
        ("i4", "", 402),
        ("i4", "0x10", 402),
        ("int", "1,000", 402),
        ("r4", "3.5E39", 601),
        ("r8", "1e999", 601),
        ("r8", "nan", 402),
        ("float", "1.2.3", 402),
        ("fixed.14.4", "123456789012345.1", 402),
        ("fixed.14.4", "1.12345", 402),
        ("char", "", 402),
        ("char", "ab", 402),
        ("boolean", "maybe", 402),
        ("date", "2026-13-01", 402),
        ("date", "13/11/2026", 402),
        ("dateTime", "2026-11-13T25:00:00", 402),
        ("dateTime", "2026-11-13T06:30:15Z", 402),  # no zone on the untimezoned type
        ("time", "06:30", 402),
        ("time.tz", "06:30:15+1", 402),
        ("bin.base64", "not base64!", 402),
        ("bin.hex", "abc", 402),
        ("bin.hex", "zz", 402),
        ("uri", "has space", 402),
        ("uri", "", 402),
        ("uuid", "not-a-uuid", 402),
    ],
)
def test_argument_typing_refuses_with_the_table_3_3_code(data_type, text, code):
    with pytest.raises(ArgumentError) as info:
        coerce_argument(data_type, text)
    assert info.value.code == code


def test_constraints_are_error_601_and_unknown_types_a_service_fault():
    assert coerce_argument("ui2", "50", value_range=(10, 100)) == 50
    for text in ("9", "101"):
        with pytest.raises(ArgumentError) as info:
            coerce_argument("ui2", text, value_range=(10, 100))
        assert info.value.code == 601
    assert coerce_argument("i4", "-5", value_range=(None, 0)) == -5
    assert coerce_argument("string", "Up", allowed_values=["Up", "Down"]) == "Up"
    with pytest.raises(ArgumentError) as info:
        coerce_argument("string", "Sideways", allowed_values=["Up", "Down"])
    assert info.value.code == 601
    with pytest.raises(ValueError, match="string variables only"):
        coerce_argument("ui1", "1", allowed_values=["1"])
    with pytest.raises(ValueError, match=r"not a UDA 2.0 data type"):
        coerce_argument("ui16", "1")
    assert (
        coerce_argument("boolean", "1", value_range=(0, 0)) is True
    )  # a bool is not a number here


def test_every_clause_2_5_type_is_covered_by_the_table():
    assert len(DATA_TYPES) == 26
    expected = {
        "ui1",
        "ui2",
        "ui4",
        "ui8",
        "i1",
        "i2",
        "i4",
        "i8",
        "int",
        "r4",
        "r8",
        "number",
        "fixed.14.4",
        "float",
    }
    expected |= {"char", "string", "date", "dateTime", "dateTime.tz", "time", "time.tz", "boolean"}
    expected |= {"bin.base64", "bin.hex", "uri", "uuid"}
    assert expected == DATA_TYPES
