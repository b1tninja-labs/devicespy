"""SSDP alive, byebye and search responses (UDA 2.0, SDDL 1.0).

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    Device = Any  # placeholder: give it a real type in the milestone that needs it
    Response = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "announce",
    "search_response",
]


async def announce(device: Device, interfaces: list) -> None:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``advertise.announce()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("announce() is not implemented: UDA 2.0")


def search_response(device: Device, stn: str) -> Response:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``advertise.search_response()`` row in ROADMAP.md; this
    stub raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("search_response() is not implemented: UDA 2.0")
