"""service control protocol definition: actions, state variables, allowed values.

``coerce_argument`` types an action argument from the ``dataType`` its state variable declares, using the
list in UPnP Device Architecture 2.0 (2020-04-17), clause 2.5 (the ``dataType`` element of a state
variable): ui1, ui2, ui4, ui8, i1, i2, i4, i8, int, r4, r8, number, fixed.14.4, float, char, string, date,
dateTime, dateTime.tz, time, time.tz, boolean, bin.base64, bin.hex, uri, uuid. A value that does not fit
raises :class:`ArgumentError` carrying the UPnP error code clause 3.2.5 (Table 3-3) assigns: 402 for a
value of the wrong data type and 601 for one outside the allowed range or list.

The ISO 8601 subset that the date and time types use is not spelled out in the text read so far; this module
accepts the common extended forms (``2026-11-13``, ``2026-11-13T06:30:00``, an optional ``Z`` or
``+hh:mm``) and nothing looser. ``parse_scpd`` (the service description document) is not implemented yet.
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    ServiceDescription = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "DATA_TYPES",
    "ArgumentError",
    "coerce_argument",
    "parse_scpd",
]

_MAX_ARGUMENT = 1_000_000
_INT = re.compile(r"[+-]?[0-9]+")
_UINT = re.compile(r"[0-9]+")
_FLOAT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:E[+-]?[0-9]+)?", re.IGNORECASE)
_FIXED = re.compile(r"[+-]?([0-9]{1,14})(?:\.([0-9]{1,4}))?")
_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_TIME = re.compile(r"([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?")
_ZONE = re.compile(r"(Z|[+-][0-9]{2}:[0-9]{2})")
_UUID = re.compile(
    r"(?:[0-9A-Fa-f]{2}){4,}-(?:[0-9A-Fa-f]{2}){2,}-(?:[0-9A-Fa-f]{2}){2,}-(?:[0-9A-Fa-f]{2}){2,}-(?:[0-9A-Fa-f]{2}){6,}"
)
_BOOLEANS = {"0": False, "1": True, "true": True, "yes": True, "false": False, "no": False}
_INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "ui1": (0, 2**8 - 1),
    "ui2": (0, 2**16 - 1),
    "ui4": (0, 2**32 - 1),
    "ui8": (0, 2**64 - 1),
    "i1": (-(2**7), 2**7 - 1),
    "i2": (-(2**15), 2**15 - 1),
    "i4": (-(2**31), 2**31 - 1),
    "i8": (-(2**63), 2**63 - 1),
}
_FLOAT_LIMITS = {"r4": 3.40282347e38, "r8": 1.79769313486232e308, "number": 1.79769313486232e308}
DATA_TYPES = frozenset(
    {
        *_INTEGER_RANGES,
        "int",
        "r4",
        "r8",
        "number",
        "fixed.14.4",
        "float",
        "char",
        "string",
        "date",
        "dateTime",
        "dateTime.tz",
        "time",
        "time.tz",
        "boolean",
        "bin.base64",
        "bin.hex",
        "uri",
        "uuid",
    }
)


class ArgumentError(ValueError):
    """An argument does not fit its declared type; ``code`` is the UPnP error code to answer with."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _wrong(reason: str) -> ArgumentError:
    return ArgumentError(402, reason)


def _time_of(text: str, zone_allowed: bool) -> tuple[time, timezone | None]:
    zone = None
    body = text
    found = re.search(_ZONE.pattern + r"$", text)
    if found is not None:
        if not zone_allowed:
            raise _wrong("this type has no time zone")
        body = text[: found.start()]
        label = found.group(1)
        if label == "Z":
            zone = UTC
        else:
            sign = -1 if label[0] == "-" else 1
            zone = timezone(sign * timedelta(hours=int(label[1:3]), minutes=int(label[4:6])))
    parsed = _TIME.fullmatch(body)
    if parsed is None:
        raise _wrong("not an ISO 8601 time")
    try:
        return time(int(parsed.group(1)), int(parsed.group(2)), int(parsed.group(3))), zone
    except ValueError:
        raise _wrong("not a valid time of day") from None


def _date_of(text: str) -> date:
    parsed = _DATE.fullmatch(text)
    if parsed is None:
        raise _wrong("not an ISO 8601 date")
    try:
        return date(int(parsed.group(1)), int(parsed.group(2)), int(parsed.group(3)))
    except ValueError:
        raise _wrong("not a valid calendar date") from None


def coerce_argument(
    data_type: str,
    text: str,
    *,
    allowed_values: Sequence[str] | None = None,
    value_range: tuple[float | None, float | None] | None = None,
) -> object:
    """Parse ``text`` as ``data_type`` (UDA 2.0, clause 2.5) and apply the state variable's constraints.

    ``allowed_values`` is the ``allowedValueList`` (string variables only; a value outside it is error
    601) and ``value_range`` the ``(minimum, maximum)`` of ``allowedValueRange`` for a numeric one
    (outside it, 601). Returns an int, float, bool, str, bytes, date, time or datetime. An unknown type
    name is a ``ValueError``, since that is a fault in the service description and not in the argument.
    """
    if data_type not in DATA_TYPES:
        raise ValueError(f"{data_type!r} is not a UDA 2.0 data type")
    if len(text) > _MAX_ARGUMENT:
        raise _wrong("argument too large")
    value = _parse(data_type, text)
    if allowed_values is not None:
        if data_type != "string":
            raise ValueError("allowedValueList is for string variables only (clause 2.5)")
        if text not in allowed_values:
            raise ArgumentError(601, "not in the allowed value list")
    if value_range is not None and isinstance(value, int | float) and not isinstance(value, bool):
        low, high = value_range
        if (low is not None and value < low) or (high is not None and value > high):
            raise ArgumentError(601, "outside the allowed value range")
    return value


def _parse(data_type: str, text: str) -> object:
    if data_type in _INTEGER_RANGES:
        low, high = _INTEGER_RANGES[data_type]
        pattern = _UINT if low == 0 else _INT
        if pattern.fullmatch(text) is None:
            raise _wrong(f"not an {data_type} integer")
        number = int(text)
        if not low <= number <= high:
            raise ArgumentError(601, f"outside the {data_type} range")
        return number
    if data_type == "int":
        if _INT.fullmatch(text) is None:
            raise _wrong("not an integer")
        return int(text)
    if data_type in _FLOAT_LIMITS or data_type == "float":
        if _FLOAT.fullmatch(text) is None:
            raise _wrong("not a floating point number")
        real = float(text)
        if real in {float("inf"), float("-inf")} or (
            data_type in _FLOAT_LIMITS and abs(real) > _FLOAT_LIMITS[data_type]
        ):
            raise ArgumentError(601, f"outside the {data_type} range")
        return real
    if data_type == "fixed.14.4":
        if _FIXED.fullmatch(text) is None:
            raise _wrong("fixed.14.4 has at most 14 digits before and 4 after the point")
        return float(text)
    if data_type == "char":
        if len(text) != 1:
            raise _wrong("char is exactly one character")
        return text
    if data_type == "string":
        return text
    if data_type == "boolean":
        found = _BOOLEANS.get(text.lower())
        if found is None:
            raise _wrong('boolean is "0", "1", "true", "yes", "false" or "no"')
        return found
    if data_type == "date":
        return _date_of(text)
    if data_type in {"dateTime", "dateTime.tz"}:
        day, sep, clock = text.partition("T")
        parsed_day = _date_of(day)
        if not sep:
            return datetime(parsed_day.year, parsed_day.month, parsed_day.day)
        moment, zone = _time_of(clock, data_type == "dateTime.tz")
        return datetime.combine(parsed_day, moment, tzinfo=zone)
    if data_type in {"time", "time.tz"}:
        moment, zone = _time_of(text, data_type == "time.tz")
        return moment.replace(tzinfo=zone)
    if data_type == "bin.base64":
        try:
            return base64.b64decode(text, validate=True)
        except (binascii.Error, ValueError):
            raise _wrong("not Base64") from None
    if data_type == "bin.hex":
        if len(text) % 2 or re.fullmatch(r"[0-9A-Fa-f]*", text) is None:
            raise _wrong("bin.hex is an even number of hexadecimal digits")
        return bytes.fromhex(text)
    if data_type == "uri":
        if not text or any(ord(c) <= 0x20 or ord(c) == 0x7F for c in text):
            raise _wrong("not a URI")
        urlsplit(text)
        return text
    if _UUID.fullmatch(text.removeprefix("uuid:")) is None:
        raise _wrong("not a UUID in the clause 1.1.4 format")
    return text


def parse_scpd(raw: bytes) -> ServiceDescription:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``scpd.parse_scpd()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("parse_scpd() is not implemented: UDA 2.0")
