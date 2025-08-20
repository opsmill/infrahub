from collections import defaultdict
from dataclasses import dataclass
from typing import Generator

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query.node import NodeGetKindQuery
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

from ..model.path import (
    CalculatedDiffs,
    EnrichedDiffConflict,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
)
from ..payload_builder import get_display_labels
from .interface import DiffEnricherInterface

log = get_logger()

PROPERTY_TYPES_WITH_LABELS = {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_SOURCE}


@dataclass
class DisplayLabelRequest:
    node_id: str
    branch_name: str

    def __hash__(self) -> int:
        return hash(f"{self.node_id}-{self.branch_name}")


class DiffLabelsEnricher(DiffEnricherInterface):
    """Add display labels for nodes and labels for relationships"""

    def __init__(self, db: InfrahubDatabase):
        self.db = db
        self._base_branch_name: str | None = None
        self._diff_branch_name: str | None = None
        self._conflicts_only = False

    @property
    def base_branch_name(self) -> str:
        if not self._base_branch_name:
            raise RuntimeError("could not identify base branch")
        return self._base_branch_name

    @property
    def diff_branch_name(self) -> str:
        if not self._diff_branch_name:
            raise RuntimeError("could not identify diff branch")
        return self._diff_branch_name

    def _get_branch_for_action(self, action: DiffAction) -> str:
        if action is DiffAction.REMOVED:
            return self.base_branch_name
        return self.diff_branch_name

    def _nodes_iterator(self, enriched_diff_root: EnrichedDiffRoot) -> Generator[DisplayLabelRequest, str | None, None]:
        for node in enriched_diff_root.nodes:
            if not self._conflicts_only:
                branch_name = self._get_branch_for_action(action=node.action)
                label = yield DisplayLabelRequest(node_id=node.uuid, branch_name=branch_name)
                if label:
                    node.label = label
            for attribute_diff in node.attributes:
                for property_diff in attribute_diff.properties:
                    property_iterator = self._property_iterator(property_diff=property_diff)
                    try:
                        label = None
                        while True:
                            display_label_request = property_iterator.send(label)
                            label = yield display_label_request
                    except StopIteration:
                        ...
            for relationship_diff in node.relationships:
                relationship_iterator = self._relationship_iterator(relationship_diff=relationship_diff)
                try:
                    label = None
                    while True:
                        display_label_request = relationship_iterator.send(label)
                        label = yield display_label_request
                except StopIteration:
                    ...

    def _relationship_iterator(
        self, relationship_diff: EnrichedDiffRelationship
    ) -> Generator[DisplayLabelRequest, str | None, None]:
        for element_diff in relationship_diff.relationships:
            if not self._conflicts_only:
                branch_name = self._get_branch_for_action(action=element_diff.action)
                peer_label = yield DisplayLabelRequest(node_id=element_diff.peer_id, branch_name=branch_name)
                if peer_label:
                    element_diff.peer_label = peer_label
            if element_diff.conflict:
                conflict_iterator = self._conflict_iterator(conflict_diff=element_diff.conflict)
                label = None
                try:
                    while True:
                        display_label_request = conflict_iterator.send(label)
                        label = yield display_label_request
                except StopIteration:
                    ...
            for property_diff in element_diff.properties:
                property_iterator = self._property_iterator(property_diff=property_diff)
                label = None
                try:
                    while True:
                        display_label_request = property_iterator.send(label)
                        label = yield display_label_request
                except StopIteration:
                    ...

    def _property_iterator(
        self, property_diff: EnrichedDiffProperty
    ) -> Generator[DisplayLabelRequest, str | None, None]:
        if property_diff.property_type in PROPERTY_TYPES_WITH_LABELS:
            if property_diff.previous_value and not self._conflicts_only:
                label = yield DisplayLabelRequest(
                    node_id=property_diff.previous_value, branch_name=self.base_branch_name
                )
                if label:
                    property_diff.previous_label = label
            if property_diff.new_value and not self._conflicts_only:
                label = yield DisplayLabelRequest(node_id=property_diff.new_value, branch_name=self.diff_branch_name)
                if label:
                    property_diff.new_label = label
            if property_diff.conflict:
                conflict_iterator = self._conflict_iterator(conflict_diff=property_diff.conflict)
                label = None
                try:
                    while True:
                        display_label_request = conflict_iterator.send(label)
                        label = yield display_label_request
                except StopIteration:
                    ...

    def _conflict_iterator(
        self, conflict_diff: EnrichedDiffConflict
    ) -> Generator[DisplayLabelRequest, str | None, None]:
        if conflict_diff.base_branch_value:
            label = yield DisplayLabelRequest(
                node_id=conflict_diff.base_branch_value, branch_name=self.base_branch_name
            )
            if label:
                conflict_diff.base_branch_label = label
        if conflict_diff.diff_branch_value:
            label = yield DisplayLabelRequest(
                node_id=conflict_diff.diff_branch_value, branch_name=self.diff_branch_name
            )
            if label:
                conflict_diff.diff_branch_label = label

    def _update_relationship_labels(self, enriched_diff: EnrichedDiffRoot) -> None:
        for node in enriched_diff.nodes:
            if not node.relationships:
                continue

            node_schema = self.db.schema.get(name=node.kind, branch=enriched_diff.diff_branch_name, duplicate=False)
            alternate_node_schema = None
            if enriched_diff.diff_branch_name != enriched_diff.base_branch_name and self.db.schema.has(
                name=node.kind, branch=enriched_diff.base_branch_name
            ):
                alternate_node_schema = self.db.schema.get(
                    name=node.kind, branch=enriched_diff.base_branch_name, duplicate=False
                )
            for relationship_diff in node.relationships:
                relationship_schema = node_schema.get_relationship_or_none(name=relationship_diff.name)
                if not relationship_schema and alternate_node_schema:
                    relationship_schema = alternate_node_schema.get_relationship_or_none(name=relationship_diff.name)
                relationship_diff.label = relationship_schema.label or "" if relationship_schema else ""

    async def _get_display_label_map(
        self, display_label_requests: set[DisplayLabelRequest]
    ) -> dict[str, dict[str, str]]:
        node_ids = [dlr.node_id for dlr in display_label_requests]
        query = await NodeGetKindQuery.init(db=self.db, ids=node_ids)
        await query.execute(db=self.db)
        node_kind_map = await query.get_node_kind_map()
        display_label_request_map: dict[str, dict[str, list[str]]] = defaultdict(dict)
        for dlr in display_label_requests:
            try:
                node_kind = node_kind_map[dlr.node_id]
            except KeyError:
                continue
            branch_map = display_label_request_map[dlr.branch_name]
            if node_kind not in branch_map:
                branch_map[node_kind] = []
            branch_map[node_kind].append(dlr.node_id)
        return await get_display_labels(db=self.db, nodes=display_label_request_map)

    async def enrich(
        self,
        enriched_diff_root: EnrichedDiffRoot,
        calculated_diffs: CalculatedDiffs | None = None,  # noqa: ARG002
        conflicts_only: bool = False,
    ) -> None:
        log.info("Beginning display labels diff enrichment...")
        self._base_branch_name = enriched_diff_root.base_branch_name
        self._diff_branch_name = enriched_diff_root.diff_branch_name
        self._conflicts_only = conflicts_only
        display_label_requests = set(self._nodes_iterator(enriched_diff_root=enriched_diff_root))
        display_label_map = await self._get_display_label_map(display_label_requests=display_label_requests)

        # iterate through all the labels in this diff again and set them, if possible
        nodes_iterator = self._nodes_iterator(enriched_diff_root=enriched_diff_root)
        try:
            display_label_request = next(nodes_iterator)
            while display_label_request:
                try:
                    display_label = display_label_map[display_label_request.branch_name][display_label_request.node_id]
                except KeyError:
                    display_label = None
                display_label_request = nodes_iterator.send(display_label)
        except StopIteration:
            ...

        self._update_relationship_labels(enriched_diff=enriched_diff_root)
        log.info("Display labels diff enrichment complete.")
