"""devicespy -- be the UPnP device, not the control point.

Every Python UPnP library is a control point. async-upnp-client 0.49.0 (2026-10-11),
upnpclient 2.0.3 (2026-04-07) and python-upnp 1.0.0 (2024-07-12) all talk to devices, and
ssdp 1.3.1 (2025-09-06) plus ssdpy 0.4.1 do discovery.
"""

from __future__ import annotations

from . import advertise, apps, cli, control, description, events, httpd, scpd, xmlsafe
from .advertise import announce, search_response
from .control import dispatch
from .description import render_device_xml
from .events import notify, renew
from .scpd import parse_scpd
from .xmlsafe import parse

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "advertise",
    "announce",
    "apps",
    "cli",
    "control",
    "description",
    "dispatch",
    "events",
    "httpd",
    "notify",
    "parse",
    "parse_scpd",
    "render_device_xml",
    "renew",
    "scpd",
    "search_response",
    "xmlsafe",
]
