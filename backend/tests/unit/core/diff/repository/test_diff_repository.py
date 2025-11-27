import random
from collections import defaultdict
from collections.abc import Generator
from dataclasses import replace
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    EnrichedDiffRoot,
    EnrichedDiffs,
    NameTrackingId,
    NodeDiffFieldSummary,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ResourceNotFoundError

from ..factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)
from ..get_one_node import get_one_diff_node
from .base import DiffRepositoryTestBase


class TestDiffRepositorySaveAndLoad(DiffRepositoryTestBase):
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

    async def test_get_non_existent_diff(self, diff_repository: DiffRepository, reset_database) -> None:
        right_now = Timestamp()
        enriched_diffs = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=right_now,
            to_time=right_now.add(hours=1),
        )
        assert len(enriched_diffs) == 0

    async def test_save_and_retrieve(self, diff_repository: DiffRepository, reset_database) -> None:
        enriched_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=self._build_nodes(num_nodes=5, num_sub_fields=2),
            tracking_id=NameTrackingId(name="the-best-diff"),
        )

        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
        )

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
        )
        assert len(retrieved) == 1
        diff_root = retrieved[0]
        assert diff_root.exists_on_database is True
        diff_root.exists_on_database = False
        assert diff_root == enriched_diff

    async def test_save_and_retrieve_large_diff(self, diff_repository: DiffRepository, reset_database) -> None:
        enriched_branch_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=self._build_nodes(num_nodes=20, num_sub_fields=2),
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        enriched_base_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.base_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=self._build_nodes(num_nodes=18, num_sub_fields=1),
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        enriched_base_diff.partner_uuid = enriched_branch_diff.uuid
        enriched_branch_diff.partner_uuid = enriched_base_diff.uuid
        enriched_diffs = EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            base_branch_diff=enriched_base_diff,
            diff_branch_diff=enriched_branch_diff,
        )

        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        retrieved = await diff_repository.get_pairs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
        )
        assert len(retrieved) == 1
        retrieved_pair = retrieved[0]
        assert retrieved_pair.diff_branch_diff.exists_on_database is True
        assert retrieved_pair.base_branch_diff.exists_on_database is True
        retrieved_pair.diff_branch_diff.exists_on_database = False
        retrieved_pair.base_branch_diff.exists_on_database = False
        assert retrieved_pair == enriched_diffs

    async def test_base_branch_name_filter(self, diff_repository: DiffRepository, reset_database) -> None:
        name_uuid_map = {name: str(uuid4()) for name in (self.base_branch_name, "more-main", "most-main")}
        for base_branch_name, root_uuid in name_uuid_map.items():
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=self.diff_from_time,
                to_time=self.diff_to_time,
                uuid=root_uuid,
                nodes={EnrichedNodeFactory.build(relationships={})},
            )
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
        )
        assert len(retrieved) == 1
        assert retrieved[0].base_branch_name == self.base_branch_name
        assert retrieved[0].uuid == name_uuid_map[self.base_branch_name]

    async def test_diff_branch_name_filter(self, diff_repository: DiffRepository, reset_database) -> None:
        diff_branch_1, diff_branch_2, diff_branch_3 = "diff1", "diff2", "diff3"
        diff_uuids_by_name = {diff_branch_1: set(), diff_branch_2: set(), diff_branch_3: set()}
        for diff_branch_name in (diff_branch_1, diff_branch_2, diff_branch_3):
            start_time = Timestamp("2024-06-15T18:35:20Z")
            for _ in range(5):
                start_time = start_time.add(seconds=random.randint(150_000, 300_000))
                end_time = start_time.add(seconds=random.randint(25_000, 100_000))
                root_uuid = str(uuid4())
                diff_uuids_by_name[diff_branch_name].add(root_uuid)
                enriched_diff = EnrichedRootFactory.build(
                    base_branch_name=self.base_branch_name,
                    diff_branch_name=diff_branch_name,
                    from_time=start_time,
                    to_time=end_time,
                    uuid=root_uuid,
                    nodes={EnrichedNodeFactory.build(relationships={})},
                )
                await self._save_single_diff(
                    diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
                )

        start_time = Timestamp("2024-06-15T18:35:20Z")
        end_time = start_time.add(months=1)
        for diff_name, expected_uuids in diff_uuids_by_name.items():
            retrieved = await diff_repository.get(
                base_branch_name=self.base_branch_name,
                diff_branch_names=[diff_name],
                from_time=start_time,
                to_time=end_time,
            )
            retrieved_uuids = {root_diff.uuid for root_diff in retrieved}
            assert retrieved_uuids == expected_uuids

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[diff_branch_1, diff_branch_2],
            from_time=start_time,
            to_time=end_time,
        )
        expected_uuids = diff_uuids_by_name[diff_branch_1] | diff_uuids_by_name[diff_branch_2]
        retrieved_uuids = {root_diff.uuid for root_diff in retrieved}
        assert retrieved_uuids == expected_uuids

    async def test_filter_time_ranges(self, diff_repository: DiffRepository, reset_database) -> None:
        root_uuid = str(uuid4())
        enriched_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            uuid=root_uuid,
            nodes={EnrichedNodeFactory.build(relationships={})},
        )
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
        )

        # both before
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time.subtract(minutes=100),
            to_time=self.diff_from_time.subtract(minutes=50),
        )
        assert len(retrieved) == 0
        # one before, one during
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time.subtract(minutes=100),
            to_time=self.diff_to_time.subtract(minutes=1),
        )
        assert len(retrieved) == 0
        # one before, one after
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time.subtract(minutes=100),
            to_time=self.diff_to_time.add(minutes=100),
        )
        assert len(retrieved) == 1
        assert retrieved[0].uuid == root_uuid
        # both during
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time.add(minutes=1),
            to_time=self.diff_to_time.subtract(minutes=1),
        )
        assert len(retrieved) == 0
        # one during, one after
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time.add(minutes=1),
            to_time=self.diff_to_time.add(minutes=1),
        )
        assert len(retrieved) == 0
        # both after
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_to_time.add(minutes=1),
            to_time=self.diff_to_time.add(minutes=10),
        )
        assert len(retrieved) == 0

    async def test_filter_root_node_uuids(self, diff_repository: DiffRepository, reset_database) -> None:
        enriched_diffs: list[EnrichedDiffRoot] = []
        for i in range(5):
            nodes = self._build_nodes(num_nodes=4, num_sub_fields=3)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=f"branch{i}",
                from_time=self.diff_from_time,
                to_time=self.diff_to_time,
                nodes=nodes,
            )
            enriched_diffs.append(enriched_diff)
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )

        parent_node = EnrichedNodeFactory.build(
            is_node_kind_migration=False,
        )
        middle_parent_rel = EnrichedRelationshipGroupFactory.build(nodes={parent_node})
        other_middle_rels = {EnrichedRelationshipGroupFactory.build() for _ in range(2)}
        middle_node = EnrichedNodeFactory.build(
            is_node_kind_migration=False, relationships={middle_parent_rel} | other_middle_rels
        )
        leaf_middle_rel = EnrichedRelationshipGroupFactory.build(nodes={middle_node})
        other_leaf_rels = {EnrichedRelationshipGroupFactory.build() for _ in range(2)}
        leaf_node = EnrichedNodeFactory.build(
            is_node_kind_migration=False, relationships={leaf_middle_rel} | other_leaf_rels
        )
        other_nodes = {EnrichedNodeFactory.build(is_node_kind_migration=False) for _ in range(2)}
        this_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name="diff",
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=other_nodes | {parent_node, middle_node, leaf_node},
        )
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=this_diff, do_summary_counts=False)
        diff_branch_names = [e.diff_branch_name for e in enriched_diffs] + ["diff"]

        # get parent node
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            filters={"ids": [parent_node.uuid]},
        )
        assert len(retrieved) == 1
        assert retrieved[0].exists_on_database is True
        retrieved[0].exists_on_database = False
        assert retrieved[0] == replace(this_diff, nodes={parent_node})

        # get middle node
        thin_parent_node = replace(
            parent_node,
            conflict=None,
            attributes=set(),
            relationships=set(),
            action=DiffAction.UNCHANGED,
            changed_at=None,
            path_identifier="",
        )
        expected_middle_parent_rel = replace(middle_parent_rel, nodes={thin_parent_node})
        expected_middle_node = replace(middle_node, relationships=other_middle_rels | {expected_middle_parent_rel})
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            filters={"ids": [middle_node.uuid]},
        )
        assert len(retrieved) == 1
        assert retrieved[0].exists_on_database is True
        retrieved[0].exists_on_database = False
        assert retrieved[0] == replace(this_diff, nodes={thin_parent_node, expected_middle_node})

        # get leaf node
        thin_middle_parent_rel = replace(
            middle_parent_rel,
            nodes={thin_parent_node},
            relationships=set(),
            changed_at=None,
            action=DiffAction.UNCHANGED,
            path_identifier="",
        )
        thin_middle_node = replace(
            middle_node,
            conflict=None,
            attributes=set(),
            relationships={thin_middle_parent_rel},
            action=DiffAction.UNCHANGED,
            changed_at=None,
            path_identifier="",
        )
        expected_leaf_middle_rel = replace(leaf_middle_rel, nodes={thin_middle_node})
        expected_leaf_node = replace(leaf_node, relationships=other_leaf_rels | {expected_leaf_middle_rel})
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            filters={"ids": [leaf_node.uuid]},
        )
        assert len(retrieved) == 1
        assert retrieved[0].exists_on_database is True
        retrieved[0].exists_on_database = False
        assert retrieved[0] == replace(this_diff, nodes={thin_parent_node, thin_middle_node, expected_leaf_node})

        # get middle and parent nodes
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            filters={"ids": [parent_node.uuid, middle_node.uuid]},
        )
        assert len(retrieved) == 1
        assert retrieved[0].exists_on_database is True
        retrieved[0].exists_on_database = False
        assert retrieved[0] == replace(this_diff, nodes={parent_node, middle_node})

        # get leaf and parent nodes
        thin_middle_parent_rel = replace(
            middle_parent_rel,
            nodes={parent_node},
            relationships=set(),
            changed_at=None,
            action=DiffAction.UNCHANGED,
            path_identifier="",
        )
        thin_middle_node = replace(
            middle_node,
            conflict=None,
            attributes=set(),
            relationships={thin_middle_parent_rel},
            action=DiffAction.UNCHANGED,
            changed_at=None,
            path_identifier="",
        )
        expected_leaf_middle_rel = replace(leaf_middle_rel, nodes={thin_middle_node})
        expected_leaf_node = replace(leaf_node, relationships=other_leaf_rels | {expected_leaf_middle_rel})
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            filters={"ids": [parent_node.uuid, leaf_node.uuid]},
        )
        assert len(retrieved) == 1
        assert retrieved[0].exists_on_database is True
        retrieved[0].exists_on_database = False
        assert retrieved[0] == replace(this_diff, nodes={parent_node, thin_middle_node, expected_leaf_node})

    async def test_save_and_retrieve_many_diffs(self, diff_repository: DiffRepository, reset_database) -> None:
        diffs_to_retrieve: list[EnrichedDiffRoot] = []
        start_time = self.diff_from_time.add(seconds=1)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=start_time.add(minutes=i * 30),
                to_time=start_time.add(minutes=(i * 30) + 29),
                nodes=nodes,
            )
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )
            diffs_to_retrieve.append(enriched_diff)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=start_time.add(days=3, minutes=(i * 30)),
                to_time=start_time.add(days=3, minutes=(i * 30) + 29),
                nodes=nodes,
            )
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=start_time,
            to_time=start_time.add(minutes=150),
        )
        assert len(retrieved) == 5
        for r in retrieved:
            assert r.exists_on_database is True
            r.exists_on_database = False
        assert set(retrieved) == set(diffs_to_retrieve)

    async def test_delete_diff_by_uuid(self, diff_repository: DiffRepository, reset_database) -> None:
        diffs: list[EnrichedDiffRoot] = []
        start_time = self.diff_from_time.add(seconds=1)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=start_time.add(minutes=i * 30),
                to_time=start_time.add(minutes=(i * 30) + 29),
                nodes=nodes,
            )
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )
            diffs.append(enriched_diff)

        diff_to_delete = diffs.pop()
        await diff_repository.delete_diff_roots(diff_root_uuids=[diff_to_delete.uuid])
        diffs_to_delete = [diffs.pop(), diffs.pop()]
        await diff_repository.delete_diff_roots(diff_root_uuids=[diff.uuid for diff in diffs_to_delete])

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_from_time.add(minutes=(4 * 30) + 29),
        )
        assert len(retrieved) == len(diffs)
        for r in retrieved:
            assert r.exists_on_database is True
            r.exists_on_database = False
        assert set(retrieved) == set(diffs)

    async def test_delete_all_diffs(self, diff_repository: DiffRepository, reset_database) -> None:
        diffs: list[EnrichedDiffRoot] = []
        for _ in range(5):
            nodes = self._build_nodes(num_nodes=2, num_sub_fields=1)
            enriched_diff = EnrichedRootFactory.build(nodes=nodes)
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )
            diffs.append(enriched_diff)

        await diff_repository.delete_all_diff_roots()

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
        )
        assert len(retrieved) == 0

    async def test_get_by_tracking_id(self, diff_repository: DiffRepository, reset_database) -> None:
        branch_tracking_id = BranchTrackingId(name=self.diff_branch_name)
        name_tracking_id = NameTrackingId(name="an very cool diff")
        end_time = self.diff_from_time.add(minutes=5)
        for i in range(4):
            nodes = self._build_nodes(num_nodes=2, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=self.diff_from_time.add(minutes=i * 30),
                to_time=end_time.add(minutes=(i * 30) + 29),
                nodes=nodes,
            )
            await self._save_single_diff(
                diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
            )
        nodes = self._build_nodes(num_nodes=2, num_sub_fields=2)
        branch_tracked_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time.add(minutes=i * 30),
            to_time=end_time.add(minutes=(i * 30) + 29),
            nodes=nodes,
            tracking_id=branch_tracking_id,
        )
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=branch_tracked_diff, do_summary_counts=False
        )
        name_tracked_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time.add(minutes=i * 30),
            to_time=end_time.add(minutes=(i * 30) + 29),
            nodes=nodes,
            tracking_id=name_tracking_id,
        )
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=name_tracked_diff, do_summary_counts=False
        )

        retrieved_branch_diff = await diff_repository.get_one(
            tracking_id=branch_tracking_id,
            diff_branch_name=self.diff_branch_name,
        )
        assert retrieved_branch_diff.exists_on_database is True
        retrieved_branch_diff.exists_on_database = False
        assert retrieved_branch_diff == branch_tracked_diff
        retrieved_name_diff = await diff_repository.get_one(
            tracking_id=name_tracking_id,
            diff_branch_name=self.diff_branch_name,
        )
        assert retrieved_name_diff.exists_on_database is True
        retrieved_name_diff.exists_on_database = False
        assert retrieved_name_diff == name_tracked_diff

        with pytest.raises(ResourceNotFoundError):
            await diff_repository.get_one(
                tracking_id=BranchTrackingId(name="not a branch"),
                diff_branch_name=self.diff_branch_name,
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

    async def test_merge_tracking_ids(self, diff_repository: DiffRepository, reset_database) -> None:
        base_branch_name = "main"
        tracking_id_diff_1 = EnrichedRootFactory.build(base_branch_name=base_branch_name)
        tracking_id_1 = BranchTrackingId(name=tracking_id_diff_1.diff_branch_name)
        tracking_id_diff_1.tracking_id = tracking_id_1
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=tracking_id_diff_1, do_summary_counts=False
        )
        tracking_id_diff_2 = EnrichedRootFactory.build(base_branch_name=base_branch_name)
        tracking_id_2 = BranchTrackingId(name=tracking_id_diff_2.diff_branch_name)
        tracking_id_diff_2.tracking_id = tracking_id_2
        await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=tracking_id_diff_2, do_summary_counts=False
        )

        await diff_repository.mark_tracking_ids_merged(tracking_ids=[tracking_id_1])

        # verify tracking ID 1 diff cannot be retrieved by tracking ID
        with pytest.raises(ResourceNotFoundError, match="Cannot find diff"):
            await diff_repository.get_one(
                diff_branch_name=tracking_id_diff_1.diff_branch_name, tracking_id=tracking_id_1
            )
        # verify tracking ID 2 diff can be retrieved by tracking ID
        diff_2 = await diff_repository.get_one(
            diff_branch_name=tracking_id_diff_2.diff_branch_name, tracking_id=tracking_id_2
        )
        assert diff_2.tracking_id == tracking_id_2
        # verify tracking ID 1 diff is not retrievable
        diffs = await diff_repository.get(
            diff_branch_names=[tracking_id_diff_1.diff_branch_name],
            base_branch_name=tracking_id_diff_1.base_branch_name,
        )
        diff_uuids = {d.uuid for d in diffs}
        assert tracking_id_diff_1.uuid not in diff_uuids

    async def test_limit_and_offset(self, diff_repository: DiffRepository, reset_database) -> None:
        nodes_by_kind = defaultdict(list)
        all_nodes = set()
        for kind in ("KindOne", "KindTwo", "KindThree"):
            for _ in range(8):
                node = EnrichedNodeFactory.build(kind=kind, relationships=set())
                nodes_by_kind[kind].append(node)
                all_nodes.add(node)
        sorted_uuids = sorted(all_nodes, key=lambda i: i.uuid)
        enriched_branch_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=all_nodes,
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        enriched_base_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.base_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=set(),
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        enriched_base_diff.partner_uuid = enriched_branch_diff.uuid
        enriched_branch_diff.partner_uuid = enriched_base_diff.uuid
        enriched_diffs = EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            base_branch_diff=enriched_base_diff,
            diff_branch_diff=enriched_branch_diff,
        )

        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        # validate limit
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            limit=7,
        )
        assert len(retrieved) == 1
        retrieved_diff = retrieved[0]
        assert len(retrieved_diff.nodes) == 7
        assert {n.uuid for n in retrieved_diff.nodes} == {n.uuid for n in sorted_uuids[:7]}

        # validate limit with offset
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            limit=7,
            offset=7,
        )
        assert len(retrieved) == 1
        retrieved_diff = retrieved[0]
        assert len(retrieved_diff.nodes) == 7
        assert {n.uuid for n in retrieved_diff.nodes} == {n.uuid for n in sorted_uuids[7:14]}

        # validate limit with filter
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            limit=7,
            filters={"kind": {"includes": ["KindOne"]}},
        )
        assert len(retrieved) == 1
        retrieved_diff = retrieved[0]
        assert len(retrieved_diff.nodes) == 7
        assert {n.uuid for n in retrieved_diff.nodes} == {
            n.uuid for n in sorted(nodes_by_kind["KindOne"], key=lambda x: x.uuid)[:7]
        }

        # validate limit with offset and filter
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            limit=7,
            offset=7,
            filters={"kind": {"includes": ["KindOne"]}},
        )
        assert len(retrieved) == 1
        retrieved_diff = retrieved[0]
        assert len(retrieved_diff.nodes) == 1
        assert {n.uuid for n in retrieved_diff.nodes} == {
            n.uuid for n in sorted(nodes_by_kind["KindOne"], key=lambda x: x.uuid)[7:]
        }

    async def test_update_existing(self, db: InfrahubDatabase, diff_repository: DiffRepository, reset_database) -> None:
        node_with_removes = self.build_diff_node(no_recurse=True, num_sub_fields=3)
        node_with_updates = self.build_diff_node(no_recurse=True, num_sub_fields=3)
        # there are no conflicts by default
        node_with_adds = self.build_diff_node(no_recurse=True, num_sub_fields=3)
        # set conflicts on every node/rel/prop in update and remove nodes
        for node in (node_with_removes, node_with_updates):
            node.conflict = EnrichedConflictFactory.build()
            for attr in node.attributes:
                for prop in attr.properties:
                    prop.conflict = EnrichedConflictFactory.build()
            for rel_group in node.relationships:
                for rel_elem in rel_group.relationships:
                    rel_elem.conflict = EnrichedConflictFactory.build()
                    for prop in rel_elem.properties:
                        prop.conflict = EnrichedConflictFactory.build()
        enriched_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes={node_with_removes, node_with_updates, node_with_adds},
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        base_diff = EnrichedRootFactory.build(
            base_branch_name=enriched_diff.base_branch_name,
            diff_branch_name=enriched_diff.base_branch_name,
            from_time=enriched_diff.from_time,
            to_time=enriched_diff.to_time,
            nodes=set(),
            tracking_id=enriched_diff.tracking_id,
            partner_uuid=enriched_diff.uuid,
        )
        enriched_diff.partner_uuid = base_diff.uuid
        enriched_diffs = EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            diff_branch_diff=enriched_diff,
            base_branch_diff=base_diff,
        )
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        # removed node conflict
        node_with_removes.conflict = None
        # add node conflict
        node_with_adds.conflict = EnrichedConflictFactory.build()

        # remove attribute
        removed_attr = node_with_removes.attributes.pop()
        # remove attribute property
        attr_with_removed_prop = next(iter(node_with_removes.attributes))
        removed_prop_from_attr = attr_with_removed_prop.properties.pop()
        # remove attribute property conflict
        attr_prop_with_removed_conflict = next(iter(attr_with_removed_prop.properties))
        attr_prop_with_removed_conflict.conflict = None
        # add attribute
        added_attr = EnrichedAttributeFactory.build()
        node_with_adds.attributes.add(added_attr)
        # add attribute property conflict
        attr_with_added_prop = next(iter(node_with_adds.attributes))
        attr_prop_with_added_conflict = next(iter(attr_with_added_prop.properties))
        attr_prop_with_added_conflict.conflict = EnrichedConflictFactory.build()
        # add attribute property
        added_prop_type = [
            d for d in DatabaseEdgeType if d not in [p.property_type for p in attr_with_added_prop.properties]
        ][0]
        added_prop_to_attr = EnrichedPropertyFactory.build(property_type=added_prop_type)
        attr_with_added_prop.properties.add(added_prop_to_attr)
        # update attribute and property
        attr_to_update = node_with_updates.attributes.pop()
        attr_with_property_updates = next(iter(node_with_updates.attributes))
        updated_attr = EnrichedAttributeFactory.build(name=attr_to_update.name)
        node_with_updates.attributes.add(updated_attr)
        attr_prop_to_update = attr_with_property_updates.properties.pop()
        updated_attr_prop = EnrichedPropertyFactory.build(property_type=attr_prop_to_update.property_type)
        attr_with_property_updates.properties.add(updated_attr_prop)

        # remove relationship
        removed_relationship = node_with_removes.relationships.pop()
        # remove relationship element
        relationship_with_removes = next(iter(node_with_removes.relationships))
        removed_element = relationship_with_removes.relationships.pop()
        # remove relationship element conflict
        element_with_removes = next(iter(relationship_with_removes.relationships))
        element_with_removes.conflict = None
        # remove relationship element property
        removed_element_property = element_with_removes.properties.pop()
        # remove relationship element property conflict
        element_property_with_removes = next(iter(element_with_removes.properties))
        element_property_with_removes.conflict = None
        # add relationship
        relationship_with_adds = next(iter(node_with_adds.relationships))
        added_relationship = EnrichedRelationshipGroupFactory.build()
        node_with_adds.relationships.add(added_relationship)
        # add relationship element
        element_with_adds = next(iter(relationship_with_adds.relationships))
        added_element = EnrichedRelationshipElementFactory.build()
        relationship_with_adds.relationships.add(added_element)
        # add relationship element conflict
        added_element_conflict = EnrichedConflictFactory.build()
        element_with_adds.conflict = added_element_conflict
        # add relationship element property
        element_property_with_adds = next(iter(element_with_adds.properties))
        added_prop_type = [
            d for d in DatabaseEdgeType if d not in [p.property_type for p in element_with_adds.properties]
        ][0]
        added_element_property = EnrichedPropertyFactory.build(property_type=added_prop_type)
        element_with_adds.properties.add(added_element_property)
        # add relationship element property conflict
        added_element_property_conflict = EnrichedConflictFactory.build()
        element_property_with_adds.conflict = added_element_property_conflict
        # update relationship
        updated_relationship = next(iter(node_with_updates.relationships))
        updated_relationship.label += "_new"
        # update relationship element
        updated_relationship_element = next(iter(updated_relationship.relationships))
        updated_relationship_element.peer_label = "fresh_label"
        # update relationship element conflict
        updated_relationship_element.conflict.base_branch_value = "BASE SOMETHING"
        # update relationship element property
        updated_element_property = next(iter(updated_relationship_element.properties))
        updated_element_property.previous_value = "PREVIOUS SOMETHING"
        # update relationship element property conflict
        updated_element_property.conflict.diff_branch_value = "DIFF SOMETHING"

        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
        )
        assert len(retrieved) == 1
        retrieved_diff_root = retrieved[0]
        assert len(retrieved_diff_root.nodes) == 3
        nodes_by_uuid = {n.uuid: n for n in retrieved_diff_root.nodes}
        # verify removed conflict
        retrieved_node_with_removes = nodes_by_uuid[node_with_removes.uuid]
        assert retrieved_node_with_removes.conflict is None
        # verify added conflict
        retrieved_node_with_adds = nodes_by_uuid[node_with_adds.uuid]
        assert retrieved_node_with_adds.conflict == node_with_adds.conflict

        # verify removed attribute
        assert len(retrieved_node_with_removes.attributes) == 2
        attrs_by_name = {a.name: a for a in retrieved_node_with_removes.attributes}
        assert removed_attr.name not in attrs_by_name
        # verify removed attribute property
        retrieved_attr_with_removed_prop = attrs_by_name[attr_with_removed_prop.name]
        props_by_type = {p.property_type: p for p in retrieved_attr_with_removed_prop.properties}
        assert removed_prop_from_attr.property_type not in props_by_type
        # verify removed attribute property conflict
        attr_prop_with_removed_conflict = props_by_type[attr_prop_with_removed_conflict.property_type]
        assert attr_prop_with_removed_conflict.conflict is None
        # verify added attr
        assert len(retrieved_node_with_adds.attributes) == 4
        attrs_by_name = {a.name: a for a in retrieved_node_with_adds.attributes}
        assert added_attr.name in attrs_by_name
        assert added_attr == attrs_by_name[added_attr.name]
        # verify added property to attribute
        retrieved_attr_with_added_prop = attrs_by_name[attr_with_added_prop.name]
        props_by_type = {p.property_type: p for p in retrieved_attr_with_added_prop.properties}
        retrieved_added_prop_to_attr = props_by_type[added_prop_to_attr.property_type]
        assert retrieved_added_prop_to_attr == added_prop_to_attr
        # verify added conflict to attribute property
        retrieved_attr_prop_with_added_conflict = props_by_type[attr_prop_with_added_conflict.property_type]
        assert retrieved_attr_prop_with_added_conflict.conflict == attr_prop_with_added_conflict.conflict
        # verify updated attr
        retrieved_node_with_updates = nodes_by_uuid[node_with_updates.uuid]
        assert len(retrieved_node_with_updates.attributes) == 3
        attrs_by_name = {a.name: a for a in retrieved_node_with_updates.attributes}
        assert updated_attr.name in attrs_by_name
        assert updated_attr == attrs_by_name[updated_attr.name]
        # verify updated attr property
        retrieved_attr_with_property_update = attrs_by_name[attr_with_property_updates.name]
        props_by_type = {p.property_type: p for p in retrieved_attr_with_property_update.properties}
        assert updated_attr_prop == props_by_type[updated_attr_prop.property_type]

        # verify relationship removed
        rels_by_name = {r.name: r for r in retrieved_node_with_removes.relationships}
        assert removed_relationship.name not in rels_by_name
        # verify relationship element removed
        retrieved_rel_with_removes = rels_by_name[relationship_with_removes.name]
        elements_by_peer_id = {e.peer_id: e for e in retrieved_rel_with_removes.relationships}
        assert removed_element.peer_id not in elements_by_peer_id
        # verify relationship element conflict removed
        retrieved_element_with_removes = elements_by_peer_id[element_with_removes.peer_id]
        assert retrieved_element_with_removes.conflict is None
        # verify relationship element property removed
        props_by_type = {p.property_type: p for p in retrieved_element_with_removes.properties}
        assert removed_element_property.property_type not in props_by_type
        # verify relationship element property conflict removed
        retrieved_element_property_with_removes = props_by_type[element_property_with_removes.property_type]
        assert retrieved_element_property_with_removes.conflict is None
        # verify relationship added
        rels_by_name = {r.name: r for r in retrieved_node_with_adds.relationships}
        assert added_relationship == rels_by_name[added_relationship.name]
        # verify relationship element added
        retrieved_rel_with_adds = rels_by_name[relationship_with_adds.name]
        elements_by_peer_id = {e.peer_id: e for e in retrieved_rel_with_adds.relationships}
        assert added_element == elements_by_peer_id[added_element.peer_id]
        # verify relationship element conflict added
        retrieved_element_with_adds = elements_by_peer_id[element_with_adds.peer_id]
        assert retrieved_element_with_adds.conflict == added_element_conflict
        # verify relationship element property added
        props_by_type = {p.property_type: p for p in retrieved_element_with_adds.properties}
        assert added_element_property == props_by_type[added_element_property.property_type]
        # verify relationship element property conflict added
        retrieved_element_property_with_adds = props_by_type[element_property_with_adds.property_type]
        assert retrieved_element_property_with_adds.conflict == element_property_with_adds.conflict
        # verify relationship updated
        rels_by_name = {r.name: r for r in retrieved_node_with_updates.relationships}
        retrieved_updated_relationship = rels_by_name[updated_relationship.name]
        assert retrieved_updated_relationship == updated_relationship
        # verify relationship element updated
        elements_by_peer_id = {e.peer_id: e for e in retrieved_updated_relationship.relationships}
        retrieved_updated_element = elements_by_peer_id[updated_relationship_element.peer_id]
        assert retrieved_updated_element == updated_relationship_element
        # verify relationship element conflict updated
        assert retrieved_updated_element.conflict == updated_relationship_element.conflict
        # verify relationship element property updated
        props_by_type = {p.property_type: p for p in retrieved_updated_element.properties}
        retrieved_updated_element_property = props_by_type[updated_element_property.property_type]
        assert retrieved_updated_element_property == updated_element_property
        # verify relationship element property conflict updated
        assert retrieved_updated_element_property.conflict == updated_element_property.conflict

        assert retrieved_diff_root.exists_on_database is True
        retrieved_diff_root.exists_on_database = False
        assert retrieved_diff_root == enriched_diff
        await verify_no_orphaned_nodes(db=db)

    async def test_update_existing_hierarchy(
        self, db: InfrahubDatabase, diff_repository: DiffRepository, reset_database
    ) -> None:
        nodes = self._build_nodes(num_nodes=2, num_sub_fields=3)
        for n in nodes:
            for r in n.relationships:
                if r.nodes:
                    child_node, parent_rel = n, r
                    break
        enriched_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=nodes,
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        saved_diffs = await self._save_single_diff(
            diff_repository=diff_repository, enriched_diff=enriched_diff, do_summary_counts=False
        )

        # replace a parent
        new_parent = self.build_diff_node(num_sub_fields=2, no_recurse=True)
        removed_parent = parent_rel.nodes.pop()
        parent_rel.nodes.add(new_parent)
        saved_diffs.diff_branch_diff.nodes.add(new_parent)

        # the update includes some nodes in the existing diff, but not all
        updated_base_branch_diff = replace(saved_diffs.base_branch_diff, nodes=set())
        updated_diff_branch_diff = replace(saved_diffs.diff_branch_diff, nodes={child_node, new_parent, removed_parent})
        updated_diffs = replace(
            saved_diffs, base_branch_diff=updated_base_branch_diff, diff_branch_diff=updated_diff_branch_diff
        )
        await diff_repository.save(enriched_diffs=updated_diffs, do_summary_counts=False)

        # retrieving the diff still gets all the nodes for the whole diff
        retrieved_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff.diff_branch_name, diff_id=enriched_diff.uuid
        )

        retrieved_child = get_one_diff_node(diff_root=retrieved_diff, node_uuid=child_node.uuid)
        retrieved_parent_rel = retrieved_child.get_relationship(name=parent_rel.name)
        assert {n.uuid for n in retrieved_parent_rel.nodes} == {n.uuid for n in parent_rel.nodes}
        assert retrieved_child == child_node
        retrieved_removed_parent = get_one_diff_node(diff_root=retrieved_diff, node_uuid=removed_parent.uuid)
        assert retrieved_removed_parent == removed_parent

        assert retrieved_diff.exists_on_database is True
        retrieved_diff.exists_on_database = False
        assert retrieved_diff == saved_diffs.diff_branch_diff
        await verify_no_orphaned_nodes(db=db)


async def verify_no_orphaned_nodes(db: InfrahubDatabase) -> None:
    """Verify that no diff elements have been orphaned"""
    query = """
CALL () {
    MATCH (d:DiffNode)
    WHERE not exists((:DiffRoot)-[]->(d))
    RETURN d
    UNION
    MATCH (d:DiffAttribute)
    WHERE not exists((:DiffNode)-[]->(d))
    RETURN d
    UNION
    MATCH (d:DiffRelationship)
    WHERE not exists((:DiffNode)-[]->(d))
    RETURN d
    UNION
    MATCH (d:DiffRelationshipElement)
    WHERE not exists((:DiffRelationship)-[]->(d))
    RETURN d
    UNION
    MATCH (d:DiffProperty)
    WHERE not exists(()-[]->(d))
    RETURN d
    UNION
    MATCH (d:DiffConflict)
    WHERE not exists(()-[]->(d))
    RETURN d
}
RETURN labels(d)[0] AS node_label, %(id_func)s(d) AS database_id
    """ % {"id_func": db.get_id_function_name()}
    records = await db.execute_query(query=query)
    orphaned_nodes = []
    for record in records:
        node_label = record.get("node_label")
        database_id = record.get("database_id")
        orphaned_nodes.append(f"{node_label}({database_id})")
    if orphaned_nodes:
        raise ValueError(f"The following nodes are orphaned: {orphaned_nodes}")
