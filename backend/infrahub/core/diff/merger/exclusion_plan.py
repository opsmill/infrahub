from dataclasses import dataclass, field
from typing import NamedTuple

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType

from ..model.path import (
    ConflictSelection,
    EnrichedDiffNode,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class AttributePropertyPath(NamedTuple):
    node_uuid: str
    attribute_name: str
    edge_type: str


class RelationshipPath(NamedTuple):
    node_uuid: str
    relationship_identifier: str
    peer_uuid: str


class RelationshipPropertyPath(NamedTuple):
    node_uuid: str
    relationship_identifier: str
    peer_uuid: str
    edge_type: str


class CardinalityOneDiffResolution(NamedTuple):
    """Identifies a cardinality-one rel where DIFF won — the bulk merge should keep the selected
    peer's edges and close any other peer edges on the target branch."""

    node_uuid: str
    relationship_identifier: str
    selected_peer_uuid: str


class CarryOverBaseRelProperty(NamedTuple):
    """A property under a cardinality-one rel-element where the element resolved to DIFF
    (selected peer = source's) but the property resolved to BASE. Base's property edge lives
    on the displaced rel-vertex and would otherwise be lost when that vertex is closed —
    the bulk merge copies the property edge onto the selected rel-vertex instead.
    """

    node_uuid: str
    relationship_identifier: str
    selected_peer_uuid: str
    edge_type: str


class CarryOverDiffRelProperty(NamedTuple):
    """A property under a cardinality-one rel-element where the element resolved to BASE
    (kept peer = base's) but the property resolved to DIFF. Source's property edge lives on
    the source-side rel-vertex (which is excluded from the merge). The bulk merge applies
    source's value to the kept (base-side) rel-vertex on target.
    """

    node_uuid: str
    relationship_identifier: str
    kept_peer_uuid: str
    source_peer_uuid: str
    edge_type: str


@dataclass
class MergeExclusionPlan:
    """Path-level exclusions and explicit closes derived from EnrichedDiff conflicts.

    BASE-resolved conflicts produce exclusions: bulk merge skips those paths and the target
    branch keeps its existing value. DIFF-resolved cardinality-one rel-element conflicts where
    the base branch had set its own peer produce extra closes: the bulk merge can't see the
    base-only peer's IS_RELATED edges (they don't appear on the source branch), so they must be
    closed explicitly.
    """

    excluded_node_uuids: list[str] = field(default_factory=list)
    excluded_attribute_property_paths: list[AttributePropertyPath] = field(default_factory=list)
    excluded_relationship_paths: list[RelationshipPath] = field(default_factory=list)
    excluded_relationship_property_paths: list[RelationshipPropertyPath] = field(default_factory=list)
    cardinality_one_diff_resolutions: list[CardinalityOneDiffResolution] = field(default_factory=list)
    carry_over_base_relationship_properties: list[CarryOverBaseRelProperty] = field(default_factory=list)
    carry_over_diff_relationship_properties: list[CarryOverDiffRelProperty] = field(default_factory=list)


class MergeExclusionPlanBuilder:
    def __init__(self) -> None:
        self._plan = MergeExclusionPlan()

    def build(self, diff: EnrichedDiffRoot) -> MergeExclusionPlan:
        self._plan = MergeExclusionPlan()
        for node in diff.nodes:
            self._process_node(node=node)
        return self._plan

    def _process_node(self, node: EnrichedDiffNode) -> None:
        node_conflict = node.conflict
        if node_conflict and node_conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            self._plan.excluded_node_uuids.append(node.uuid)
            return

        for attribute in node.attributes:
            for prop in attribute.properties:
                conflict = prop.conflict
                if not conflict or not conflict.resolvable:
                    continue
                if conflict.selected_branch is ConflictSelection.BASE_BRANCH:
                    self._plan.excluded_attribute_property_paths.append(
                        AttributePropertyPath(
                            node_uuid=node.uuid,
                            attribute_name=attribute.name,
                            edge_type=prop.property_type.value,
                        )
                    )

        for relationship in node.relationships:
            self._process_relationship(node=node, relationship=relationship)

    def _process_relationship(self, node: EnrichedDiffNode, relationship: EnrichedDiffRelationship) -> None:
        is_cardinality_one = relationship.cardinality is RelationshipCardinality.ONE
        for element in relationship.relationships:
            if is_cardinality_one:
                self._process_cardinality_one_element(node=node, relationship=relationship, element=element)
            self._process_element_properties(node=node, relationship=relationship, element=element)

    def _process_cardinality_one_element(
        self,
        node: EnrichedDiffNode,
        relationship: EnrichedDiffRelationship,
        element: EnrichedDiffSingleRelationship,
    ) -> None:
        conflict = element.conflict
        if not conflict:
            return
        if conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            # The whole rel-element is excluded — IS_RELATED edge and every property edge under it.
            self._plan.excluded_relationship_paths.append(
                RelationshipPath(
                    node_uuid=node.uuid,
                    relationship_identifier=relationship.identifier,
                    peer_uuid=element.peer_id,
                )
            )
            return
        if conflict.selected_branch is ConflictSelection.DIFF_BRANCH:
            self._plan.cardinality_one_diff_resolutions.append(
                CardinalityOneDiffResolution(
                    node_uuid=node.uuid,
                    relationship_identifier=relationship.identifier,
                    selected_peer_uuid=element.peer_id,
                )
            )

    def _process_element_properties(
        self,
        node: EnrichedDiffNode,
        relationship: EnrichedDiffRelationship,
        element: EnrichedDiffSingleRelationship,
    ) -> None:
        # Carry-overs apply when the element-level resolution and a property-level resolution
        # disagree — the chosen value lives on a different rel-vertex than the kept one.
        is_cardinality_one = relationship.cardinality is RelationshipCardinality.ONE
        element_conflict = element.conflict
        is_cardinality_one_diff_wins = (
            is_cardinality_one
            and element_conflict is not None
            and element_conflict.selected_branch is ConflictSelection.DIFF_BRANCH
        )
        is_cardinality_one_base_wins = (
            is_cardinality_one
            and element_conflict is not None
            and element_conflict.selected_branch is ConflictSelection.BASE_BRANCH
        )
        for prop in element.properties:
            conflict = prop.conflict
            if not conflict:
                continue
            if (
                conflict.selected_branch is ConflictSelection.DIFF_BRANCH
                and is_cardinality_one_base_wins
                and prop.property_type is not DatabaseEdgeType.IS_RELATED
                and element_conflict is not None
                and element_conflict.base_branch_value
            ):
                # Inverse carry-over: BASE element kept its peer; DIFF property wants source's
                # value applied to that kept rel-vertex.
                self._plan.carry_over_diff_relationship_properties.append(
                    CarryOverDiffRelProperty(
                        node_uuid=node.uuid,
                        relationship_identifier=relationship.identifier,
                        kept_peer_uuid=element_conflict.base_branch_value,
                        source_peer_uuid=element.peer_id,
                        edge_type=prop.property_type.value,
                    )
                )
                continue
            if conflict.selected_branch is not ConflictSelection.BASE_BRANCH:
                continue
            if prop.property_type is DatabaseEdgeType.IS_RELATED:
                self._plan.excluded_relationship_paths.append(
                    RelationshipPath(
                        node_uuid=node.uuid,
                        relationship_identifier=relationship.identifier,
                        peer_uuid=element.peer_id,
                    )
                )
                continue
            self._plan.excluded_relationship_property_paths.append(
                RelationshipPropertyPath(
                    node_uuid=node.uuid,
                    relationship_identifier=relationship.identifier,
                    peer_uuid=element.peer_id,
                    edge_type=prop.property_type.value,
                )
            )
            if is_cardinality_one_diff_wins:
                self._plan.carry_over_base_relationship_properties.append(
                    CarryOverBaseRelProperty(
                        node_uuid=node.uuid,
                        relationship_identifier=relationship.identifier,
                        selected_peer_uuid=element.peer_id,
                        edge_type=prop.property_type.value,
                    )
                )
