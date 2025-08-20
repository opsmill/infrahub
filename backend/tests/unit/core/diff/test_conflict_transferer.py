from dataclasses import replace

import pytest

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.combiner import DiffCombiner
from infrahub.core.diff.conflict_transferer import DiffConflictTransferer
from infrahub.core.diff.model.path import ConflictSelection

from .factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestDiffConflictsTransferer:
    @pytest.fixture
    async def conflict_transferer(self):
        return DiffConflictTransferer(diff_combiner=DiffCombiner())

    async def test_node_conflicts(self, conflict_transferer: DiffConflictTransferer):
        conflict_early_only = EnrichedConflictFactory.build()
        node_early_only_1 = EnrichedNodeFactory.build(conflict=conflict_early_only)
        node_early_only_2 = EnrichedNodeFactory.build(
            uuid=node_early_only_1.uuid, action=node_early_only_1.action, conflict=None
        )
        conflict_later_only = EnrichedConflictFactory.build()
        node_later_only_1 = EnrichedNodeFactory.build(conflict=None)
        node_later_only_2 = EnrichedNodeFactory.build(
            uuid=node_later_only_1.uuid, action=node_later_only_1.action, conflict=conflict_later_only
        )
        conflict_transfer_1 = EnrichedConflictFactory.build(selected_branch=ConflictSelection.DIFF_BRANCH)
        conflict_transfer_2 = replace(conflict_transfer_1, selected_branch=None)
        node_transfer_1 = EnrichedNodeFactory.build(conflict=conflict_transfer_1)
        node_transfer_2 = EnrichedNodeFactory.build(
            uuid=node_transfer_1.uuid, action=node_transfer_1.action, conflict=conflict_transfer_2
        )
        node_later_only_1 = EnrichedNodeFactory.build(conflict=None)
        node_later_only_2 = EnrichedNodeFactory.build(uuid=node_later_only_1.uuid, conflict=conflict_later_only)
        diff_1 = EnrichedRootFactory.build(nodes={node_later_only_1, node_early_only_1, node_transfer_1})
        diff_2 = EnrichedRootFactory.build(nodes={node_later_only_2, node_early_only_2, node_transfer_2})

        await conflict_transferer.transfer(earlier=diff_1, later=diff_2)

        assert node_early_only_2.conflict is None
        assert node_later_only_2.conflict == conflict_later_only
        assert node_transfer_2.conflict == conflict_transfer_1

    async def test_attr_conflicts(self, conflict_transferer: DiffConflictTransferer):
        conflict_early_only = EnrichedConflictFactory.build()
        prop_early_only_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED, conflict=conflict_early_only
        )
        prop_early_only_2 = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_RELATED, conflict=None)
        conflict_later_only = EnrichedConflictFactory.build()
        prop_later_only_1 = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_PROTECTED, conflict=None)
        prop_later_only_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED, conflict=conflict_later_only
        )
        conflict_transfer_1 = EnrichedConflictFactory.build(selected_branch=ConflictSelection.DIFF_BRANCH)
        conflict_transfer_2 = replace(conflict_transfer_1, selected_branch=None)
        prop_transfer_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE, conflict=conflict_transfer_1
        )
        prop_transfer_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE, conflict=conflict_transfer_2
        )

        attr_early = EnrichedAttributeFactory.build(properties={prop_early_only_1, prop_later_only_1, prop_transfer_1})
        attr_later = EnrichedAttributeFactory.build(
            name=attr_early.name, properties={prop_early_only_2, prop_later_only_2, prop_transfer_2}
        )
        node_early = EnrichedNodeFactory.build(attributes={attr_early})
        node_later = EnrichedNodeFactory.build(uuid=node_early.uuid, attributes={attr_later})
        diff_1 = EnrichedRootFactory.build(nodes={node_early})
        diff_2 = EnrichedRootFactory.build(nodes={node_later})

        await conflict_transferer.transfer(earlier=diff_1, later=diff_2)

        assert prop_early_only_2.conflict is None
        assert prop_later_only_2.conflict == conflict_later_only
        assert prop_transfer_2.conflict == conflict_transfer_1

    async def test_rel_conflicts(self, conflict_transferer: DiffConflictTransferer):
        conflict_early_only = EnrichedConflictFactory.build()
        element_early_only_1 = EnrichedRelationshipElementFactory.build(conflict=conflict_early_only)
        element_early_only_2 = EnrichedRelationshipElementFactory.build(
            peer_id=element_early_only_1.peer_id, conflict=None
        )
        conflict_later_only = EnrichedConflictFactory.build()
        element_later_only_1 = EnrichedRelationshipElementFactory.build(conflict=None)
        element_later_only_2 = EnrichedRelationshipElementFactory.build(
            peer_id=element_later_only_1.peer_id, conflict=conflict_later_only
        )
        conflict_transfer_1 = EnrichedConflictFactory.build(selected_branch=ConflictSelection.DIFF_BRANCH)
        conflict_transfer_2 = replace(conflict_transfer_1, selected_branch=None)
        element_transfer_1 = EnrichedRelationshipElementFactory.build(conflict=conflict_transfer_1)
        element_transfer_2 = EnrichedRelationshipElementFactory.build(
            peer_id=element_transfer_1.peer_id, conflict=conflict_transfer_2
        )

        rel_early = EnrichedRelationshipGroupFactory.build(
            relationships={element_early_only_1, element_later_only_1, element_transfer_1}
        )
        rel_later = EnrichedRelationshipGroupFactory.build(
            name=rel_early.name, relationships={element_early_only_2, element_later_only_2, element_transfer_2}
        )
        node_early = EnrichedNodeFactory.build(relationships={rel_early})
        node_later = EnrichedNodeFactory.build(uuid=node_early.uuid, relationships={rel_later})
        diff_1 = EnrichedRootFactory.build(nodes={node_early})
        diff_2 = EnrichedRootFactory.build(nodes={node_later})

        await conflict_transferer.transfer(earlier=diff_1, later=diff_2)

        assert element_early_only_2.conflict is None
        assert element_later_only_2.conflict == conflict_later_only
        assert element_transfer_2.conflict == conflict_transfer_1

    async def test_rel_prop_conflicts(self, conflict_transferer: DiffConflictTransferer):
        conflict_early_only = EnrichedConflictFactory.build()
        prop_early_only_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED, conflict=conflict_early_only
        )
        prop_early_only_2 = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_RELATED, conflict=None)
        conflict_later_only = EnrichedConflictFactory.build()
        prop_later_only_1 = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_PROTECTED, conflict=None)
        prop_later_only_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED, conflict=conflict_later_only
        )
        conflict_transfer_1 = EnrichedConflictFactory.build(selected_branch=ConflictSelection.DIFF_BRANCH)
        conflict_transfer_2 = replace(conflict_transfer_1, selected_branch=None)
        prop_transfer_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE, conflict=conflict_transfer_1
        )
        prop_transfer_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE, conflict=conflict_transfer_2
        )

        element_early = EnrichedRelationshipElementFactory.build(
            properties={prop_early_only_1, prop_later_only_1, prop_transfer_1}
        )
        element_later = EnrichedRelationshipElementFactory.build(
            peer_id=element_early.peer_id, properties={prop_early_only_2, prop_later_only_2, prop_transfer_2}
        )
        rel_early = EnrichedRelationshipGroupFactory.build(relationships={element_early})
        rel_later = EnrichedRelationshipGroupFactory.build(name=rel_early.name, relationships={element_later})
        node_early = EnrichedNodeFactory.build(relationships={rel_early})
        node_later = EnrichedNodeFactory.build(uuid=node_early.uuid, relationships={rel_later})
        diff_1 = EnrichedRootFactory.build(nodes={node_early})
        diff_2 = EnrichedRootFactory.build(nodes={node_later})

        await conflict_transferer.transfer(earlier=diff_1, later=diff_2)

        assert prop_early_only_2.conflict is None
        assert prop_later_only_2.conflict == conflict_later_only
        assert prop_transfer_2.conflict == conflict_transfer_1
