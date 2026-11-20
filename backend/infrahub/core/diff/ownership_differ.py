from __future__ import annotations

from dataclasses import dataclass
from itertools import batched
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.ownership.fields import diff_field_name, list_property_type, owner_list_value
from infrahub.core.ownership.models import INHERIT
from infrahub.core.ownership.repository import OwnershipRepository

from .model.path import DiffAttribute, DiffNode, DiffProperty, DiffRoot, NodeIdentifier
from .query.ownership import DiffOwnerHoldersQuery, OwnerHolderChange

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.constants.database import DatabaseEdgeType
    from infrahub.core.ownership.models import HolderKey, StoredOwnerState
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .model.field_specifiers_map import NodeFieldSpecifierMap

OwnerStates = dict[tuple[str, "HolderKey"], "StoredOwnerState"]
FieldNames = dict[OwnerHolderChange, str]
"""The field name that the diff shows each changed holder under."""


@dataclass(frozen=True)
class OwnerDiffRequest:
    base_branch: Branch
    diff_branch: Branch
    branch_from_time: Timestamp
    from_time: Timestamp
    to_time: Timestamp
    include_unchanged: bool
    previous_node_specifiers: NodeFieldSpecifierMap | None
    node_kinds: list[str] | None
    node_uuids: set[str] | None


class OwnershipDiffer:
    """Add one HAS_OWNER property for each holder whose owners changed, with the whole owner list at both ends.

    A holder that loses the mark of a copy from an object template also changed, and both ends then hold the same
    list.

    The owner edges of a holder form a set, so the owners at each end of the time range are read from the graph and
    not replayed from the edges that changed. A holder that is not an attribute shows as an attribute with a
    reserved name, which the schema of the diff branch gives for the owners of a field. The sources of a node show
    in the same way, as one HAS_SOURCE property with the whole list of sources.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_branch_changes(self, request: OwnerDiffRequest) -> FieldNames:
        """Return the holders whose owners changed on the diff branch, with the field name of each."""
        return await self._get_changes(
            schema_branches=[self.db.schema.get_schema_branch(name=request.diff_branch.name)],
            branch=request.diff_branch,
            from_time=request.from_time,
            to_time=request.to_time,
            node_uuids=sorted(request.node_uuids) if request.node_uuids is not None else None,
            node_kinds=request.node_kinds,
        )

    async def add_owner_changes(
        self, request: OwnerDiffRequest, branch_root: DiffRoot, base_root: DiffRoot, branch_changes: FieldNames
    ) -> None:
        # A rebase moves the edges of the branch to the time that the branch starts from, so the owners that the
        # branch starts with are the owners of the base branch.
        is_full_diff = (
            request.from_time == request.branch_from_time and request.base_branch.name != request.diff_branch.name
        )
        # The time range of a diff includes its start, so the state before the range excludes an edge from then.
        start_time = request.from_time if is_full_diff else request.from_time.subtract(microseconds=1)
        await self._apply_changes(
            root=branch_root,
            start_branch=request.base_branch if is_full_diff else request.diff_branch,
            end_branch=request.diff_branch,
            start_times=dict.fromkeys(branch_changes, start_time),
            field_names=branch_changes,
            request=request,
        )
        if request.base_branch.name == request.diff_branch.name:
            return

        new_fields: dict[str, set[str]] = {}
        for change, field_name in branch_changes.items():
            new_fields.setdefault(change.node_uuid, set()).add(field_name)
        current_fields: dict[str, set[str]] = {}
        if request.previous_node_specifiers is not None:
            # Any attribute of the previous diff can hold owners.
            for node_uuid, field_names in request.previous_node_specifiers.get_uuid_field_names_map().items():
                if other_fields := set(field_names) - new_fields.get(node_uuid, set()):
                    current_fields[node_uuid] = other_fields
        candidate_uuids = sorted(new_fields.keys() | current_fields.keys())
        if not candidate_uuids:
            return
        # A kind migration on the base branch gives its holders a kind that only the base branch schema has.
        base_changes = await self._get_changes(
            schema_branches=[
                self.db.schema.get_schema_branch(name=request.diff_branch.name),
                self.db.schema.get_schema_branch(name=request.base_branch.name),
            ],
            branch=request.base_branch,
            from_time=request.branch_from_time,
            to_time=request.to_time,
            node_uuids=candidate_uuids,
            node_kinds=None,
        )
        # A field that the previous diff already covers only needs the base branch changes since that diff.
        start_times: dict[OwnerHolderChange, Timestamp] = {}
        for change, field_name in base_changes.items():
            if field_name in new_fields.get(change.node_uuid, set()):
                start_times[change] = request.branch_from_time
            elif field_name in current_fields.get(change.node_uuid, set()) and change.changed_at >= request.from_time:
                start_times[change] = start_time
        await self._apply_changes(
            root=base_root,
            start_branch=request.base_branch,
            end_branch=request.base_branch,
            start_times=start_times,
            field_names=base_changes,
            request=request,
        )

    async def _get_changes(
        self,
        schema_branches: list[SchemaBranch],
        branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        node_uuids: list[str] | None,
        node_kinds: list[str] | None,
    ) -> FieldNames:
        """Return the holders whose owner edges changed, without the holders of the fields that the schema lacks."""
        node_batches: list[list[str] | None] = (
            [None]
            if node_uuids is None
            else [list(batch) for batch in batched(node_uuids, config.SETTINGS.database.query_size_limit)]
        )
        changes: FieldNames = {}
        # The query groups its rows by node, so two batches never give the same holder.
        for node_batch in node_batches:
            query = await DiffOwnerHoldersQuery.init(
                db=self.db,
                branch=branch,
                from_time=from_time,
                to_time=to_time,
                node_uuids=node_batch,
                node_kinds=node_kinds,
            )
            await query.execute(db=self.db)
            for change in query.get_changes():
                if field_name := diff_field_name(
                    holder=change.holder, kind=change.node_kind, schema_branches=schema_branches
                ):
                    changes[change] = field_name
        return changes

    async def read_states(self, branch: Branch, at: Timestamp, node_ids: list[str]) -> OwnerStates:
        """Return the stored state of each holder of the nodes that does not inherit, as the branch reads it at `at`."""
        repository = OwnershipRepository(db=self.db, branch=branch, at=at)
        states: OwnerStates = {}
        for node_ids_chunk in batched(node_ids, config.SETTINGS.database.query_size_limit):
            stored = await repository.read(node_ids=list(node_ids_chunk), attributes=True)
            for node_id, node in stored.items():
                for holder, state in node.holders.items():
                    states[node_id, holder] = state
        return states

    async def _apply_changes(
        self,
        root: DiffRoot,
        start_branch: Branch,
        end_branch: Branch,
        start_times: dict[OwnerHolderChange, Timestamp],
        field_names: FieldNames,
        request: OwnerDiffRequest,
    ) -> None:
        if not start_times:
            return
        end_states = await self.read_states(
            branch=end_branch, at=request.to_time, node_ids=sorted({change.node_uuid for change in start_times})
        )
        start_states_by_time: dict[Timestamp, OwnerStates] = {}
        for at in set(start_times.values()):
            node_ids = sorted({change.node_uuid for change, start_time in start_times.items() if start_time == at})
            start_states_by_time[at] = await self.read_states(branch=start_branch, at=at, node_ids=node_ids)
        nodes_by_identifier = {node.identifier: node for node in root.nodes}
        for change, start_time in start_times.items():
            key = (change.node_uuid, change.holder)
            diff_property = self._build_property(
                previous=start_states_by_time[start_time].get(key, INHERIT),
                new=end_states.get(key, INHERIT),
                changed_at=change.changed_at,
                property_type=list_property_type(holder=change.holder),
            )
            if diff_property.action is DiffAction.UNCHANGED and not request.include_unchanged:
                continue
            identifier = NodeIdentifier(uuid=change.node_uuid, kind=change.node_kind, db_id=change.node_db_id)
            diff_node = nodes_by_identifier.get(identifier)
            if diff_node is None:
                diff_node = DiffNode(identifier=identifier, changed_at=change.changed_at, action=DiffAction.UNCHANGED)
                root.nodes.append(diff_node)
                nodes_by_identifier[identifier] = diff_node
            field_name = field_names[change]
            diff_attribute = next((attr for attr in diff_node.attributes if attr.name == field_name), None)
            if diff_attribute is None:
                diff_node.attributes.append(
                    DiffAttribute(
                        uuid=change.holder_uuid,
                        name=field_name,
                        changed_at=change.changed_at,
                        action=diff_property.action,
                        properties=[diff_property],
                    )
                )
            else:
                # The attribute is in the diff for another change, for example a new value.
                diff_attribute.properties.append(diff_property)
                if diff_attribute.action is DiffAction.UNCHANGED:
                    diff_attribute.action = diff_property.action
            if diff_property.action is not DiffAction.UNCHANGED:
                if diff_node.action is DiffAction.UNCHANGED:
                    diff_node.action = DiffAction.UPDATED
                diff_node.changed_at = max(diff_node.changed_at, change.changed_at)

    @staticmethod
    def _build_property(
        previous: StoredOwnerState, new: StoredOwnerState, changed_at: Timestamp, property_type: DatabaseEdgeType
    ) -> DiffProperty:
        previous_value, new_value = owner_list_value(previous.owner_ids), owner_list_value(new.owner_ids)
        if previous_value == new_value and previous.template_id == new.template_id:
            action = DiffAction.UNCHANGED
        elif previous_value is None:
            action = DiffAction.ADDED
        elif new_value is None:
            action = DiffAction.REMOVED
        else:
            action = DiffAction.UPDATED
        return DiffProperty(
            property_type=property_type,
            changed_at=changed_at,
            previous_value=previous_value,
            new_value=new_value,
            action=action,
        )
