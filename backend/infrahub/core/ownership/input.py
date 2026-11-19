from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

OWNER_KINDS = frozenset({InfrahubKind.GENERICACCOUNT, InfrahubKind.ACCOUNTGROUP})


@dataclass(frozen=True)
class ReferenceRule:
    """The kinds of node that an input can refer to, and the words that the errors use."""

    kinds: frozenset[str]
    name: str
    a_name: str
    allowed: str

    @property
    def refusal(self) -> str:
        return f"Only {self.allowed} can be {self.a_name}"


OWNER_RULE = ReferenceRule(kinds=OWNER_KINDS, name="owner", a_name="an owner", allowed="an account or an account group")


class OwnerLookup(Protocol):
    async def read_labels(self, node_ids: list[str]) -> dict[str, set[str]]:
        """Return the labels of each node that is active."""
        ...


async def check_owner_kinds(
    lookup: OwnerLookup, owner_ids: list[str], path: str, rule: ReferenceRule = OWNER_RULE
) -> None:
    """Refuse an owner that is not an active account or account group, or a node that the given rule refuses.

    Raises:
        ValidationError: When a node is not found, or is not of a kind of the rule.

    """
    await check_field_owner_kinds(lookup=lookup, owner_ids={path: owner_ids}, rule=rule)


async def check_field_owner_kinds(
    lookup: OwnerLookup, owner_ids: Mapping[str, list[str]], rule: ReferenceRule = OWNER_RULE
) -> None:
    """Refuse the nodes that several fields give with one read, and name the path of the field in the error.

    Args:
        lookup: The reader of the labels of the nodes.
        owner_ids: The IDs of the nodes that each path gives.
        rule: The kinds of node that the fields can refer to.

    Raises:
        ValidationError: When a node is not found, or is not of a kind of the rule.

    """
    all_ids = list(dict.fromkeys(owner_id for ids in owner_ids.values() for owner_id in ids))
    labels = await lookup.read_labels(node_ids=all_ids) if all_ids else {}
    for path, ids in owner_ids.items():
        for owner_id in ids:
            if owner_id not in labels:
                raise ValidationError({path: f"{rule.name.capitalize()} not found: {owner_id}"})
            if not rule.kinds & labels[owner_id]:
                raise ValidationError({path: f"{rule.refusal}, not: {owner_id}"})
