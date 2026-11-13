"""GENA subscriptions and evented property change notifications (UDA 2.0 eventing).

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    Subscription = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "notify",
    "renew",
]


async def notify(subscription: Subscription, props: dict) -> None:
    """Pending behaviour defined by UDA 2.0 eventing.

    Not implemented yet. See the ``events.notify()`` row in ROADMAP.md; this stub raises
    on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("notify() is not implemented: UDA 2.0 eventing")


def renew(subscription: Subscription, requested: int) -> Subscription:
    """Pending behaviour defined by UDA 2.0 eventing.

    Not implemented yet. See the ``events.renew()`` row in ROADMAP.md; this stub raises
    on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("renew() is not implemented: UDA 2.0 eventing")
