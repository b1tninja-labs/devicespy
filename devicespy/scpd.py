"""service control protocol definition: actions, state variables, allowed values.

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    ServiceDescription = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "parse_scpd",
]


def parse_scpd(raw: bytes) -> ServiceDescription:
    """Pending behaviour defined by UDA 2.0.

    Not implemented yet. See the ``scpd.parse_scpd()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("parse_scpd() is not implemented: UDA 2.0")
