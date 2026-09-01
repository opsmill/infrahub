"""Reading conflict resolutions out of an enriched diff, for the schema the merge will produce."""

from __future__ import annotations

import pytest

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    ConflictSelection,
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRoot,
    NodeIdentifier,
)
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.timestamp import Timestamp

CODE_ATTR_UUID = "11111111-1111-1111-1111-111111111111"
COLOR_ATTR_UUID = "22222222-2222-2222-2222-222222222222"


def _conflict(
    selected_branch: ConflictSelection | None = ConflictSelection.BASE_BRANCH, resolvable: bool = True
) -> EnrichedDiffConflict:
    return EnrichedDiffConflict(
        uuid="conflict-1",
        base_branch_action=DiffAction.UPDATED,
        base_branch_value="destination",
        diff_branch_action=DiffAction.UPDATED,
        diff_branch_value="source",
        selected_branch=selected_branch,
        resolvable=resolvable,
    )


def _property(
    property_type: DatabaseEdgeType = DatabaseEdgeType.HAS_VALUE,
    conflict: EnrichedDiffConflict | None = None,
) -> EnrichedDiffProperty:
    return EnrichedDiffProperty(
        property_type=property_type,
        changed_at=Timestamp(),
        previous_value="before",
        new_value="after",
        action=DiffAction.UPDATED,
        conflict=conflict,
    )


def _attribute(name: str, *properties: EnrichedDiffProperty) -> EnrichedDiffAttribute:
    return EnrichedDiffAttribute(
        name=name, changed_at=Timestamp(), action=DiffAction.UPDATED, properties=set(properties)
    )


def _node(uuid: str, *attributes: EnrichedDiffAttribute) -> EnrichedDiffNode:
    return EnrichedDiffNode(
        identifier=NodeIdentifier(uuid=uuid, kind="SchemaAttribute", db_id=f"db-{uuid}"),
        label=uuid,
        action=DiffAction.UPDATED,
        attributes=set(attributes),
    )


def _diff(*nodes: EnrichedDiffNode) -> EnrichedDiffRoot:
    return EnrichedDiffRoot(
        base_branch_name="main",
        diff_branch_name="branch",
        from_time=Timestamp(),
        to_time=Timestamp(),
        uuid="diff-1",
        tracking_id=BranchTrackingId(name="branch"),
        nodes=set(nodes),
    )


class TestPropertiesTheDestinationKeeps:
    def test_a_value_conflict_resolved_for_the_destination_is_collected(self) -> None:
        diff = _diff(_node(CODE_ATTR_UUID, _attribute("parameters", _property(conflict=_conflict()))))

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {CODE_ATTR_UUID: {"parameters"}}

    def test_several_properties_of_one_node_collapse_into_one_entry(self) -> None:
        diff = _diff(
            _node(
                CODE_ATTR_UUID,
                _attribute("parameters", _property(conflict=_conflict())),
                _attribute("optional", _property(conflict=_conflict())),
            )
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {
            CODE_ATTR_UUID: {"parameters", "optional"}
        }

    def test_several_nodes_are_kept_apart(self) -> None:
        diff = _diff(
            _node(CODE_ATTR_UUID, _attribute("parameters", _property(conflict=_conflict()))),
            _node(COLOR_ATTR_UUID, _attribute("kind", _property(conflict=_conflict()))),
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {
            CODE_ATTR_UUID: {"parameters"},
            COLOR_ATTR_UUID: {"kind"},
        }


class TestPropertiesTheDestinationDoesNotKeep:
    """Everything the graph merge would still write from the source must stay out of the map."""

    def test_an_unresolved_conflict_is_ignored(self) -> None:
        diff = _diff(
            _node(CODE_ATTR_UUID, _attribute("parameters", _property(conflict=_conflict(selected_branch=None))))
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {}

    def test_a_conflict_resolved_for_the_source_is_ignored(self) -> None:
        diff = _diff(
            _node(
                CODE_ATTR_UUID,
                _attribute("parameters", _property(conflict=_conflict(selected_branch=ConflictSelection.DIFF_BRANCH))),
            )
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {}

    def test_an_unresolvable_conflict_is_ignored(self) -> None:
        diff = _diff(_node(CODE_ATTR_UUID, _attribute("parameters", _property(conflict=_conflict(resolvable=False)))))

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {}

    def test_a_property_with_no_conflict_is_ignored(self) -> None:
        diff = _diff(_node(CODE_ATTR_UUID, _attribute("parameters", _property())))

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {}

    @pytest.mark.parametrize(
        "property_type", [DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_SOURCE, DatabaseEdgeType.IS_PROTECTED]
    )
    def test_a_metadata_conflict_is_ignored(self, property_type: DatabaseEdgeType) -> None:
        """Only the value decides what the schema holds; ownership and protection do not."""
        diff = _diff(
            _node(
                CODE_ATTR_UUID,
                _attribute("parameters", _property(property_type=property_type, conflict=_conflict())),
            )
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {}

    def test_a_diff_with_no_nodes_yields_nothing(self) -> None:
        assert MergeSchemaAnalyzer.properties_kept_from_destination(_diff()) == {}


class TestMixedResolutionsOnOneAttribute:
    def test_only_the_value_conflict_is_collected(self) -> None:
        diff = _diff(
            _node(
                CODE_ATTR_UUID,
                _attribute(
                    "parameters",
                    _property(conflict=_conflict()),
                    _property(property_type=DatabaseEdgeType.HAS_OWNER, conflict=_conflict()),
                ),
            )
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {CODE_ATTR_UUID: {"parameters"}}

    def test_one_resolved_attribute_does_not_carry_its_neighbour(self) -> None:
        diff = _diff(
            _node(
                CODE_ATTR_UUID,
                _attribute("parameters", _property(conflict=_conflict())),
                _attribute("kind", _property(conflict=_conflict(selected_branch=ConflictSelection.DIFF_BRANCH))),
            )
        )

        assert MergeSchemaAnalyzer.properties_kept_from_destination(diff) == {CODE_ATTR_UUID: {"parameters"}}
