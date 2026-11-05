"""SOAP action dispatch with argument coercion (UDA 2.0).

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    ActionResult = Any  # placeholder: give it a real type in the milestone that needs it
    Service = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "dispatch",
]


def dispatch(service: Service, action: str, args: dict) -> ActionResult:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``control.dispatch()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("dispatch() is not implemented: UDA 2.0")
