from typing import Generator

import pytest

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    EnrichedDiffNode,
    NameTrackingId,
    NodeDiffFieldSummary,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.diff_factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)

from .base import DiffRepositoryTestBase


class TestDiffNodeFieldSummaries(DiffRepositoryTestBase):
    base_branch_name: str = "main"
    diff_branch_name: str = "diff"
    diff_from_time = Timestamp("2024-06-15T18:35:20Z")
    diff_to_time = Timestamp("2024-06-15T18:49:40Z")

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> Generator[DiffRepository, None, None]:
        original_depth = config.SETTINGS.database.max_depth_search_hierarchy
        original_size = config.SETTINGS.database.query_size_limit
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        config.SETTINGS.database.query_size_limit = 50
        diff_repository = DiffRepository(
            db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()), max_save_batch_size=30
        )
        yield diff_repository
        config.SETTINGS.database.max_depth_search_hierarchy = original_depth
        config.SETTINGS.database.query_size_limit = original_size

    def _build_named_field_node(
        self,
        kind: str,
        node_action: DiffAction,
        attribute_actions: dict[str, DiffAction],
        relationship_actions: dict[str, DiffAction],
    ) -> EnrichedDiffNode:
        return EnrichedNodeFactory.build(
            kind=kind,
            action=node_action,
            attributes={
                EnrichedAttributeFactory.build(name=name, action=action, properties=set())
                for name, action in attribute_actions.items()
            },
            relationships={
                EnrichedRelationshipGroupFactory.build(name=name, action=action, relationships=set(), nodes=set())
                for name, action in relationship_actions.items()
            },
        )

    async def test_get_node_field_summaries_excludes_other_diffs(
        self, diff_repository: DiffRepository, reset_database: None
    ) -> None:
        """Only the changed fields of the requested diff are summarized.

        Other diffs covering the same node kind must not contribute field names, and must not make a field
        name that is unchanged in the requested diff look changed.
        """
        shared_kind = "TestingSharedKind"
        requested_branch_name = "requested-branch"
        requested_tracking_id = BranchTrackingId(name=requested_branch_name)

        changed_node = self._build_named_field_node(
            kind=shared_kind,
            node_action=DiffAction.UPDATED,
            attribute_actions={"changed_attr": DiffAction.UPDATED, "quiet_attr": DiffAction.UNCHANGED},
            relationship_actions={"changed_rel": DiffAction.ADDED, "quiet_rel": DiffAction.UNCHANGED},
        )
        requested_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=requested_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes={
                changed_node,
                # an unchanged node of the same kind contributes nothing, even with changed fields of its own
                self._build_named_field_node(
                    kind=shared_kind,
                    node_action=DiffAction.UNCHANGED,
                    attribute_actions={"quiet_node_attr": DiffAction.UPDATED},
                    relationship_actions={"quiet_node_rel": DiffAction.REMOVED},
                ),
            },
            tracking_id=requested_tracking_id,
        )
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=requested_diff, do_summary_counts=False
        )

        other_branch_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name="other-branch",
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes={
                self._build_named_field_node(
                    kind=shared_kind,
                    node_action=DiffAction.UPDATED,
                    attribute_actions={
                        # changed here, unchanged in the requested diff
                        "quiet_attr": DiffAction.REMOVED,
                        # unchanged here, changed in the requested diff
                        "changed_attr": DiffAction.UNCHANGED,
                        "other_branch_attr": DiffAction.ADDED,
                    },
                    relationship_actions={
                        "quiet_rel": DiffAction.UPDATED,
                        "changed_rel": DiffAction.UNCHANGED,
                        "other_branch_rel": DiffAction.ADDED,
                    },
                )
            },
            tracking_id=BranchTrackingId(name="other-branch"),
        )
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=other_branch_diff, do_summary_counts=False
        )

        merged_tracking_id = NameTrackingId(name="already-merged")
        merged_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=requested_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes={
                self._build_named_field_node(
                    kind=shared_kind,
                    node_action=DiffAction.UPDATED,
                    attribute_actions={
                        "quiet_node_attr": DiffAction.UPDATED,
                        "merged_attr": DiffAction.UPDATED,
                    },
                    relationship_actions={
                        "quiet_node_rel": DiffAction.UPDATED,
                        "merged_rel": DiffAction.UPDATED,
                    },
                )
            },
            tracking_id=merged_tracking_id,
        )
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=merged_diff, do_summary_counts=False
        )
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[merged_tracking_id])

        expected_summaries = [
            NodeDiffFieldSummary(
                kind=shared_kind,
                attribute_node_uuids={"changed_attr": {changed_node.uuid}},
                relationship_node_uuids={"changed_rel": {changed_node.uuid}},
            )
        ]

        retrieved_by_tracking_id = await diff_repository.get_node_field_summaries(
            diff_branch_name=requested_branch_name, tracking_id=requested_tracking_id
        )
        assert retrieved_by_tracking_id == expected_summaries

        retrieved_by_diff_id = await diff_repository.get_node_field_summaries(
            diff_branch_name=requested_branch_name, diff_id=requested_diff.uuid
        )
        assert retrieved_by_diff_id == expected_summaries
