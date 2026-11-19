from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.changelog.models import AttributeChangelog
from infrahub.core.timestamp import Timestamp

from .fields import OWNERS_CHANGELOG_KIND, attribute_owners_change, owner_list_value, stored_holder_field_name
from .models import INHERIT, NODE_HOLDER, HolderKind, StoredOwnerState
from .repository import OwnershipRepository

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from .models import HolderKey, StoredNodeOwnership


class OwnershipWriter:
    """Store the owner state that a mutation gives to a holder of a saved node."""

    def __init__(self, repository: OwnershipRepository) -> None:
        """Give a repository on the transaction of the mutation, because the writer opens none."""
        self.repository = repository

    async def apply(
        self,
        node: Node,
        holder: HolderKey,
        state: StoredOwnerState,
        at: Timestamp,
        user_id: str,
        stored: Mapping[str, StoredNodeOwnership] | None = None,
        keep_deleted_owners: bool = False,
    ) -> bool:
        """Store the state, and record the update in the audit metadata and in the changelog of the node.

        The changelog gets the old and the new owner IDs when the node was saved before the call.

        Args:
            node: The saved node that has the holder.
            holder: The holder to write.
            state: The state to store.
            at: The time of the write.
            user_id: The author of the write.
            stored: The states that the node stores, with the states of its attributes for the holder of an
                attribute. Without it, the call reads them.
            keep_deleted_owners: True to also write an owner that is deleted, for a copy of a stored state.

        Returns:
            False when the holder already stores this state. Nothing is written then.

        """
        node_id = node.get_id()
        if stored is None:
            stored = await self.repository.read(node_ids=[node_id], attributes=holder.kind == HolderKind.ATTRIBUTE)
        previous = stored[node_id].get(holder) if node_id in stored else INHERIT
        if node_id in stored and _same_state(previous, state):
            return False
        write_branch = _write_branch(node=node, holder=holder)
        await self.repository.write(
            node_id=node_id,
            holder=holder,
            state=state,
            write_branch=write_branch,
            at=at,
            user_id=user_id,
            keep_deleted_owners=keep_deleted_owners,
        )
        await self.repository.record_node_update(node_id=node_id, write_branch=write_branch, at=at, user_id=user_id)
        await self._add_to_changelog(node=node, holder=holder, state=state, previous=previous)
        return True

    async def copy_from_template(
        self,
        node: Node,
        template_id: str,
        owner_ids: tuple[str, ...],
        at: Timestamp,
        user_id: str,
        holder: HolderKey = NODE_HOLDER,
    ) -> None:
        """Give a holder of a new node a copy of the owners that its object template gives, with the template as origin.

        The holder must store no owner state, so that the copy costs no read. The save of the node already recorded
        the audit metadata.
        """
        state = StoredOwnerState(owner_ids=owner_ids, template_id=template_id)
        await self.repository.write(
            node_id=node.get_id(),
            holder=holder,
            state=state,
            write_branch=_write_branch(node=node, holder=holder),
            at=at,
            user_id=user_id,
            keep_deleted_owners=True,
        )
        await self._add_to_changelog(node=node, holder=holder, state=state, previous=INHERIT)

    async def _add_to_changelog(
        self, node: Node, holder: HolderKey, state: StoredOwnerState, previous: StoredOwnerState
    ) -> None:
        if not node.has_changelog:
            return
        if holder.kind == HolderKind.ATTRIBUTE:
            attribute = node.get_attribute(name=str(holder.attribute))
            changelog = node.node_changelog.attributes.get(attribute.name) or AttributeChangelog(
                name=attribute.name, kind=attribute.schema.kind, value=attribute.value, value_previous=attribute.value
            )
            prop_name, value, value_previous = attribute_owners_change(
                owner_ids=state.owner_ids, previous_owner_ids=previous.owner_ids
            )
            changelog.add_property(name=prop_name, value_current=value, value_previous=value_previous)
            await node.add_changelog_attribute(db=self.repository.db, attribute=changelog)
            return
        name = stored_holder_field_name(
            holder=holder,
            schema=node.get_schema(),
            schema_branch=self.repository.db.schema.get_schema_branch(name=self.repository.branch.name),
        )
        if name is None:
            return
        await node.add_changelog_attribute(
            db=self.repository.db,
            attribute=AttributeChangelog(
                name=name,
                kind=OWNERS_CHANGELOG_KIND,
                value=owner_list_value(owner_ids=state.owner_ids),
                value_previous=owner_list_value(owner_ids=previous.owner_ids),
            ),
        )


async def store_owner_states(
    db: InfrahubDatabase, branch: Branch, node: Node, owner_states: Mapping[HolderKey, StoredOwnerState], user_id: str
) -> None:
    """Store a copy of stored owner states on a saved node, deleted owners included. Give the transaction of the save."""
    if not owner_states:
        return
    repository = OwnershipRepository(db=db, branch=branch, at=None)
    writer = OwnershipWriter(repository=repository)
    at = Timestamp()
    stored = await repository.read(
        node_ids=[node.get_id()], attributes=any(holder.kind == HolderKind.ATTRIBUTE for holder in owner_states)
    )
    for holder, state in owner_states.items():
        await writer.apply(
            node=node, holder=holder, state=state, at=at, user_id=user_id, stored=stored, keep_deleted_owners=True
        )


def _write_branch(node: Node, holder: HolderKey) -> Branch:
    # The owner edges of an attribute follow the branch support of the attribute, as its other edges do.
    if holder.kind == HolderKind.ATTRIBUTE:
        return node.get_attribute(name=str(holder.attribute)).get_branch_based_on_support_type()
    return node.get_branch_based_on_support_type()


def _same_state(left: StoredOwnerState, right: StoredOwnerState) -> bool:
    # A write of the owners that a holder got from its template still closes the "from template" mark.
    if left.template_id != right.template_id:
        return False
    if left.owner_ids is None or right.owner_ids is None:
        return left.owner_ids is right.owner_ids
    return set(left.owner_ids) == set(right.owner_ids)
