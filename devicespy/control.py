"""SOAP action dispatch with argument coercion (UDA 2.0).

``upnp_error_envelope`` writes the action error response body and ``parse_upnp_error`` reads one, both
following UPnP Device Architecture 2.0 (2020-04-17), clause 3.2.5 (action error response, Table 3-3, the
UPnP defined action error codes) and clause 3.2.6. The HTTP status of such a response is 500 and the caller
sets it with the CONTENT-TYPE ``text/xml; charset="utf-8"``. ``dispatch`` is not implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import xmlsafe

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET
    from typing import Any

    ActionResult = Any  # placeholder: give it a real type in the milestone that needs it
    Service = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "CONTROL_NS",
    "SOAP_ENCODING_NS",
    "SOAP_ENVELOPE_NS",
    "UPNP_ERRORS",
    "UpnpError",
    "dispatch",
    "parse_upnp_error",
    "upnp_error_envelope",
]

SOAP_ENVELOPE_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_ENCODING_NS = "http://schemas.xmlsoap.org/soap/encoding/"
CONTROL_NS = "urn:schemas-upnp-org:control-1-0"
MAX_BYTES = 262_144
_MAX_DESCRIPTION = 255  # clause 3.2.5: errorDescription is recommended under 256 characters

#: Table 3-3, the codes with a defined description. 403 is deprecated ("Do Not Use") and 606 to 612
#: are reserved for UPnP DeviceSecurity, so neither is offered for use; 613 to 699 are common action errors
#: defined by the UPnP Forum Technical Committee, 700 to 799 action-specific errors of a working committee
#: and 800 to 899 action-specific errors of non-standard actions, defined by the vendor.
UPNP_ERRORS: dict[int, str] = {
    401: "Invalid Action",
    402: "Invalid Args",
    501: "Action Failed",
    600: "Argument Value Invalid",
    601: "Argument Value Out of Range",
    602: "Optional Action Not Implemented",
    603: "Out of Memory",
    604: "Human Intervention Required",
    605: "String Argument Too Long",
}
_BAD_XML = "".join(chr(c) for c in [*range(0, 9), 11, 12, *range(14, 32)])


@dataclass(frozen=True)
class UpnpError:
    """A decoded action error: the numeric ``code`` and the ``description`` ('' when absent)."""

    code: int
    description: str = ""


def _usable(code: int) -> bool:
    return code in UPNP_ERRORS or 613 <= code <= 899


def upnp_error_envelope(code: int, description: str | None = None) -> bytes:
    """The SOAP Fault body for an action error (clause 3.2.5): ``s:Client`` faultcode, faultstring
    ``UPnPError``, and a ``UPnPError`` detail in the control namespace with errorCode and errorDescription.

    ``description`` defaults to Table 3-3's text for the code. Raises ``ValueError`` for a code that Table 3-3
    deprecates, reserves or does not define, and for a description of 256 characters or more or holding a
    control character XML 1.0 cannot carry.
    """
    if not _usable(code):
        raise ValueError(f"{code} is not a usable UPnP action error code (Table 3-3)")
    text = UPNP_ERRORS.get(code, "") if description is None else description
    if len(text) > _MAX_DESCRIPTION or any(c in _BAD_XML for c in text):
        raise ValueError("errorDescription is under 256 characters and plain text")
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<?xml version="1.0"?>\r\n'
        f'<s:Envelope xmlns:s="{SOAP_ENVELOPE_NS}" s:encodingStyle="{SOAP_ENCODING_NS}">'
        "<s:Body><s:Fault><faultcode>s:Client</faultcode><faultstring>UPnPError</faultstring>"
        f'<detail><UPnPError xmlns="{CONTROL_NS}"><errorCode>{code}</errorCode>'
        f"<errorDescription>{escaped}</errorDescription></UPnPError></detail>"
        "</s:Fault></s:Body></s:Envelope>"
    ).encode()


def _child(element: ET.Element, uri: str, local: str) -> ET.Element | None:
    found = [c for c in element if xmlsafe.localname(c.tag) == (uri, local)]
    return found[0] if len(found) == 1 else None


def parse_upnp_error(raw: bytes) -> UpnpError:
    """Read an action error response (clause 3.2.5) through ``xmlsafe``.

    Raises ``xmlsafe.XmlRefused`` for a hostile document and ``ValueError`` for one that is not a SOAP 1.1
    envelope whose Body holds a Fault with a ``UPnPError`` detail and an integer errorCode. A faultcode must
    be ``Client`` (namespace-qualified or not) as the clause requires for errors specific to a service.
    """
    root = xmlsafe.parse(raw, MAX_BYTES, max_depth=16, max_elements=200)
    if xmlsafe.localname(root.tag) != (SOAP_ENVELOPE_NS, "Envelope"):
        raise ValueError("not a SOAP 1.1 Envelope (clause 3.2.5)")
    body = _child(root, SOAP_ENVELOPE_NS, "Body")
    fault = None if body is None else _child(body, SOAP_ENVELOPE_NS, "Fault")
    if fault is None:
        raise ValueError("no Fault in the Body")
    code_element = next((c for c in fault if c.tag == "faultcode"), None)
    if code_element is None or (code_element.text or "").strip().rsplit(":", 1)[-1] != "Client":
        raise ValueError("faultcode is not Client")
    detail = next((c for c in fault if c.tag == "detail"), None)
    error = None if detail is None else _child(detail, CONTROL_NS, "UPnPError")
    if error is None:
        raise ValueError("the detail holds no UPnPError")
    number = _child(error, CONTROL_NS, "errorCode")
    digits = (number.text or "").strip() if number is not None else ""
    if not digits.isascii() or not digits.isdigit() or len(digits) > 6:
        raise ValueError("errorCode is not an integer")
    description = _child(error, CONTROL_NS, "errorDescription")
    return UpnpError(
        int(digits), (description.text or "").strip() if description is not None else ""
    )


def dispatch(service: Service, action: str, args: dict) -> ActionResult:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``control.dispatch()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("dispatch() is not implemented: UDA 2.0")
