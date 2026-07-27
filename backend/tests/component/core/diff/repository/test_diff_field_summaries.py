import random
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

from ..factories import (
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

    async def test_get_node_field_summaries(self, diff_repository: DiffRepository) -> None:
        diff_nodes = self._build_nodes(num_nodes=5, num_sub_fields=2)
        for diff_node in list(diff_nodes)[:3]:
            same_kind_diff_node = self.build_diff_node(num_sub_fields=3, no_recurse=True)
            same_kind_diff_node.identifier.kind = diff_node.identifier.kind
            same_attr_names = random.sample([a.name for a in diff_node.attributes], k=min(len(diff_node.attributes), 2))
            for attr_diff, attr_name in zip(list(same_kind_diff_node.attributes)[:2], same_attr_names, strict=False):
                attr_diff.name = attr_name
            same_rel_names = random.sample(
                [r.name for r in diff_node.relationships], k=min(len(diff_node.relationships), 2)
            )
            for rel_diff, rel_name in zip(list(same_kind_diff_node.relationships)[:2], same_rel_names, strict=False):
                rel_diff.name = rel_name
            diff_nodes.add(same_kind_diff_node)
        diff_root = EnrichedRootFactory.build(nodes=diff_nodes)
        diff_root.tracking_id = BranchTrackingId(name=diff_root.diff_branch_name)
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=diff_root, do_summary_counts=False)

        expected_map: dict[str, NodeDiffFieldSummary] = {}
        for node in diff_root.nodes:
            if node.action is DiffAction.UNCHANGED:
                continue
            if node.kind not in expected_map:
                expected_map[node.kind] = NodeDiffFieldSummary(kind=node.kind)
            field_summary = expected_map[node.kind]
            attr_names = {a.name for a in node.attributes if a.action is not DiffAction.UNCHANGED}
            field_summary.attribute_names.update(attr_names)
            rel_names = {r.name for r in node.relationships if r.action is not DiffAction.UNCHANGED}
            field_summary.relationship_names.update(rel_names)
        expected_map = {k: v for k, v in expected_map.items() if v.relationship_names or v.attribute_names}

        retrieved_node_field_summaries = await diff_repository.get_node_field_summaries(
            diff_branch_name=diff_root.diff_branch_name, tracking_id=diff_root.tracking_id
        )
        retrieved_map = {summary.kind: summary for summary in retrieved_node_field_summaries}
        assert expected_map == retrieved_map

        retrieved_node_field_summaries = await diff_repository.get_node_field_summaries(
            diff_branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid
        )
        retrieved_map = {summary.kind: summary for summary in retrieved_node_field_summaries}
        assert expected_map == retrieved_map

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

        requested_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=requested_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes={
                self._build_named_field_node(
                    kind=shared_kind,
                    node_action=DiffAction.UPDATED,
                    attribute_actions={"changed_attr": DiffAction.UPDATED, "quiet_attr": DiffAction.UNCHANGED},
                    relationship_actions={"changed_rel": DiffAction.ADDED, "quiet_rel": DiffAction.UNCHANGED},
                ),
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
            NodeDiffFieldSummary(kind=shared_kind, attribute_names={"changed_attr"}, relationship_names={"changed_rel"})
        ]

        retrieved_by_tracking_id = await diff_repository.get_node_field_summaries(
            diff_branch_name=requested_branch_name, tracking_id=requested_tracking_id
        )
        assert retrieved_by_tracking_id == expected_summaries

        retrieved_by_diff_id = await diff_repository.get_node_field_summaries(
            diff_branch_name=requested_branch_name, diff_id=requested_diff.uuid
        )
        assert retrieved_by_diff_id == expected_summaries
