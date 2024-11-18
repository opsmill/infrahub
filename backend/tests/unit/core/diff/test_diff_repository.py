import random
from dataclasses import replace
from datetime import UTC
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    EnrichedDiffNode,
    EnrichedDiffRoot,
    EnrichedDiffs,
    NameTrackingId,
    NodeDiffFieldSummary,
)
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ResourceNotFoundError

from .factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestDiffRepositorySaveAndLoad:
    @pytest.fixture
    async def reset_database(self, db: InfrahubDatabase, default_branch):
        await delete_all_nodes(db=db)

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer())

    def build_diff_node(self, num_sub_fields=2, no_recurse=False) -> EnrichedDiffNode:
        enriched_node = EnrichedNodeFactory.build(
            attributes={
                EnrichedAttributeFactory.build(
                    properties={
                        EnrichedPropertyFactory.build(property_type=det)
                        for det in random.sample(list(DatabaseEdgeType), num_sub_fields)
                    }
                )
                for _ in range(num_sub_fields)
            },
            relationships={
                EnrichedRelationshipGroupFactory.build(
                    relationships={
                        EnrichedRelationshipElementFactory.build(
                            properties={
                                EnrichedPropertyFactory.build(property_type=det)
                                for det in random.sample(list(DatabaseEdgeType), num_sub_fields)
                            }
                        )
                        for _ in range(num_sub_fields)
                    },
                    nodes=set(),
                )
                for _ in range(num_sub_fields)
            },
        )
        if no_recurse:
            return enriched_node
        if num_sub_fields > 1 and len(enriched_node.relationships) > 0:
            for relationship_group in enriched_node.relationships:
                relationship_group.nodes = {
                    self.build_diff_node(num_sub_fields=num_sub_fields - 1) for _ in range(num_sub_fields - 1)
                }
                break
        return enriched_node

    def setup_method(self):
        self.base_branch_name = "main"
        self.diff_branch_name = "diff"
        self.diff_from_time = DateTime.create(2024, 6, 15, 18, 35, 20, tz=UTC)
        self.diff_to_time = DateTime.create(2024, 6, 15, 18, 49, 40, tz=UTC)

    def _build_nodes(self, num_nodes: int, num_sub_fields: int) -> set[EnrichedDiffNode]:
        nodes = {self.build_diff_node(num_sub_fields=num_sub_fields) for _ in range(num_nodes)}

        # need to associate the generated child nodes with the DiffRoot directly
        # b/c that is how the data will actually be shaped
        nodes_to_check = list(nodes)
        all_nodes = set()
        while len(nodes_to_check) > 0:
            this_node = nodes_to_check.pop(0)
            all_nodes.add(this_node)
            for rel in this_node.relationships:
                for child_node in rel.nodes:
                    nodes_to_check.append(child_node)
        return all_nodes

    async def _save_single_diff(
        self, diff_repository: DiffRepository, enriched_diff: EnrichedDiffRoot
    ) -> EnrichedDiffs:
        base_diff = EnrichedRootFactory.build(
            base_branch_name=enriched_diff.base_branch_name,
            diff_branch_name=enriched_diff.base_branch_name,
            from_time=enriched_diff.from_time,
            to_time=enriched_diff.to_time,
            nodes=self._build_nodes(num_nodes=2, num_sub_fields=1),
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
        await diff_repository.save(enriched_diffs=enriched_diffs)
        return enriched_diffs

    async def test_get_non_existent_diff(self, diff_repository: DiffRepository, reset_database):
        right_now = Timestamp()
        enriched_diffs = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=right_now,
            to_time=right_now.add_delta(hours=1),
        )
        assert len(enriched_diffs) == 0

    async def test_save_and_retrieve(self, diff_repository: DiffRepository, reset_database):
        enriched_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=self._build_nodes(num_nodes=5, num_sub_fields=2),
            tracking_id=NameTrackingId(name="the-best-diff"),
        )

        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
        )
        assert len(retrieved) == 1
        diff_root = retrieved[0]
        assert diff_root == enriched_diff

    async def test_save_and_retrieve_large_diff(self, diff_repository: DiffRepository, reset_database):
        diff_repository.MAX_SAVE_BATCH_SIZE = 3
        enriched_branch_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=self._build_nodes(num_nodes=20, num_sub_fields=2),
            tracking_id=NameTrackingId(name="the-best-diff"),
        )
        enriched_base_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.base_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
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

        await diff_repository.save(enriched_diffs=enriched_diffs)

        retrieved = await diff_repository.get_pairs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
        )
        assert len(retrieved) == 1
        retrieved_pair = retrieved[0]
        assert retrieved_pair == enriched_diffs

    async def test_base_branch_name_filter(self, diff_repository: DiffRepository, reset_database):
        name_uuid_map = {name: str(uuid4()) for name in (self.base_branch_name, "more-main", "most-main")}
        for base_branch_name, root_uuid in name_uuid_map.items():
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(self.diff_from_time),
                to_time=Timestamp(self.diff_to_time),
                uuid=root_uuid,
                nodes={EnrichedNodeFactory.build(relationships={})},
            )
            await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
        )
        assert len(retrieved) == 1
        assert retrieved[0].base_branch_name == self.base_branch_name
        assert retrieved[0].uuid == name_uuid_map[self.base_branch_name]

    async def test_diff_branch_name_filter(self, diff_repository: DiffRepository, reset_database):
        diff_branch_1, diff_branch_2, diff_branch_3 = "diff1", "diff2", "diff3"
        diff_uuids_by_name = {diff_branch_1: set(), diff_branch_2: set(), diff_branch_3: set()}
        for diff_branch_name in (diff_branch_1, diff_branch_2, diff_branch_3):
            start_time = DateTime.create(2024, 6, 15, 18, 35, 20, tz=UTC)
            for _ in range(5):
                start_time = start_time.add(seconds=random.randint(150_000, 300_000))
                end_time = start_time.add(seconds=random.randint(25_000, 100_000))
                root_uuid = str(uuid4())
                diff_uuids_by_name[diff_branch_name].add(root_uuid)
                enriched_diff = EnrichedRootFactory.build(
                    base_branch_name=self.base_branch_name,
                    diff_branch_name=diff_branch_name,
                    from_time=Timestamp(start_time),
                    to_time=Timestamp(end_time),
                    uuid=root_uuid,
                    nodes={EnrichedNodeFactory.build(relationships={})},
                )
                await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)

        start_time = DateTime.create(2024, 6, 15, 18, 35, 20, tz=UTC)
        end_time = start_time.add(months=1)
        for diff_name, expected_uuids in diff_uuids_by_name.items():
            retrieved = await diff_repository.get(
                base_branch_name=self.base_branch_name,
                diff_branch_names=[diff_name],
                from_time=Timestamp(start_time),
                to_time=Timestamp(end_time),
            )
            retrieved_uuids = {root_diff.uuid for root_diff in retrieved}
            assert retrieved_uuids == expected_uuids

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[diff_branch_1, diff_branch_2],
            from_time=Timestamp(start_time),
            to_time=Timestamp(end_time),
        )
        expected_uuids = diff_uuids_by_name[diff_branch_1] | diff_uuids_by_name[diff_branch_2]
        retrieved_uuids = {root_diff.uuid for root_diff in retrieved}
        assert retrieved_uuids == expected_uuids

    async def test_filter_time_ranges(self, diff_repository: DiffRepository, reset_database):
        root_uuid = str(uuid4())
        enriched_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            uuid=root_uuid,
            nodes={EnrichedNodeFactory.build(relationships={})},
        )
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)

        # both before
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time.subtract(minutes=100)),
            to_time=Timestamp(self.diff_from_time.subtract(minutes=50)),
        )
        assert len(retrieved) == 0
        # one before, one during
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time.subtract(minutes=100)),
            to_time=Timestamp(self.diff_to_time.subtract(minutes=1)),
        )
        assert len(retrieved) == 0
        # one before, one after
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time.subtract(minutes=100)),
            to_time=Timestamp(self.diff_to_time.add(minutes=100)),
        )
        assert len(retrieved) == 1
        assert retrieved[0].uuid == root_uuid
        # both during
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time.add(minutes=1)),
            to_time=Timestamp(self.diff_to_time.subtract(minutes=1)),
        )
        assert len(retrieved) == 0
        # one during, one after
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time.add(minutes=1)),
            to_time=Timestamp(self.diff_to_time.add(minutes=1)),
        )
        assert len(retrieved) == 0
        # both after
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_to_time.add(minutes=1)),
            to_time=Timestamp(self.diff_to_time.add(minutes=10)),
        )
        assert len(retrieved) == 0

    async def test_filter_root_node_uuids(self, diff_repository: DiffRepository, reset_database):
        enriched_diffs: list[EnrichedDiffRoot] = []
        for i in range(5):
            nodes = self._build_nodes(num_nodes=4, num_sub_fields=3)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=f"branch{i}",
                from_time=Timestamp(self.diff_from_time),
                to_time=Timestamp(self.diff_to_time),
                nodes=nodes,
            )
            enriched_diffs.append(enriched_diff)
            await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)

        parent_node = EnrichedNodeFactory.build()
        middle_parent_rel = EnrichedRelationshipGroupFactory.build(nodes={parent_node})
        other_middle_rels = {EnrichedRelationshipGroupFactory.build() for _ in range(2)}
        middle_node = EnrichedNodeFactory.build(relationships={middle_parent_rel} | other_middle_rels)
        leaf_middle_rel = EnrichedRelationshipGroupFactory.build(nodes={middle_node})
        other_leaf_rels = {EnrichedRelationshipGroupFactory.build() for _ in range(2)}
        leaf_node = EnrichedNodeFactory.build(relationships={leaf_middle_rel} | other_leaf_rels)
        other_nodes = {EnrichedNodeFactory.build() for _ in range(2)}
        this_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name="diff",
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=other_nodes | {parent_node, middle_node, leaf_node},
        )
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=this_diff)
        diff_branch_names = [e.diff_branch_name for e in enriched_diffs] + ["diff"]

        # get parent node
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            filters={"ids": [parent_node.uuid]},
        )
        assert len(retrieved) == 1
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
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            filters={"ids": [middle_node.uuid]},
        )
        assert len(retrieved) == 1
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
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            filters={"ids": [leaf_node.uuid]},
        )
        assert len(retrieved) == 1
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
        assert retrieved[0] == replace(this_diff, nodes={parent_node, thin_middle_node, expected_leaf_node})

    async def test_save_and_retrieve_many_diffs(self, diff_repository: DiffRepository, reset_database):
        diffs_to_retrieve: list[EnrichedDiffRoot] = []
        start_time = self.diff_from_time.add(seconds=1)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(start_time.add(minutes=i * 30)),
                to_time=Timestamp(start_time.add(minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)
            diffs_to_retrieve.append(enriched_diff)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(start_time.add(days=3, minutes=(i * 30))),
                to_time=Timestamp(start_time.add(days=3, minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(start_time),
            to_time=Timestamp(start_time.add(minutes=150)),
        )
        assert len(retrieved) == 5
        assert set(retrieved) == set(diffs_to_retrieve)

    async def test_delete_diff_by_uuid(self, diff_repository: DiffRepository, reset_database):
        diffs: list[EnrichedDiffRoot] = []
        start_time = self.diff_from_time.add(seconds=1)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(start_time.add(minutes=i * 30)),
                to_time=Timestamp(start_time.add(minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)
            diffs.append(enriched_diff)

        diff_to_delete = diffs.pop()
        await diff_repository.delete_diff_roots(diff_root_uuids=[diff_to_delete.uuid])
        diffs_to_delete = [diffs.pop(), diffs.pop()]
        await diff_repository.delete_diff_roots(diff_root_uuids=[diff.uuid for diff in diffs_to_delete])

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_from_time.add(minutes=(4 * 30) + 29)),
        )
        assert len(retrieved) == len(diffs)
        assert set(retrieved) == set(diffs)

    async def test_get_by_tracking_id(self, diff_repository: DiffRepository, reset_database):
        branch_tracking_id = BranchTrackingId(name=self.diff_branch_name)
        name_tracking_id = NameTrackingId(name="an very cool diff")
        end_time = self.diff_from_time.add(minutes=5)
        for i in range(4):
            nodes = self._build_nodes(num_nodes=2, num_sub_fields=2)
            enriched_diff = EnrichedRootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(self.diff_from_time.add(minutes=i * 30)),
                to_time=Timestamp(end_time.add(minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)
        nodes = self._build_nodes(num_nodes=2, num_sub_fields=2)
        branch_tracked_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time.add(minutes=i * 30)),
            to_time=Timestamp(end_time.add(minutes=(i * 30) + 29)),
            nodes=nodes,
            tracking_id=branch_tracking_id,
        )
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=branch_tracked_diff)
        name_tracked_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time.add(minutes=i * 30)),
            to_time=Timestamp(end_time.add(minutes=(i * 30) + 29)),
            nodes=nodes,
            tracking_id=name_tracking_id,
        )
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=name_tracked_diff)

        retrieved_branch_diff = await diff_repository.get_one(
            tracking_id=branch_tracking_id,
            diff_branch_name=self.diff_branch_name,
        )
        assert retrieved_branch_diff == branch_tracked_diff
        retrieved_name_diff = await diff_repository.get_one(
            tracking_id=name_tracking_id,
            diff_branch_name=self.diff_branch_name,
        )
        assert retrieved_name_diff == name_tracked_diff

        with pytest.raises(ResourceNotFoundError):
            await diff_repository.get_one(
                tracking_id=BranchTrackingId(name="not a branch"),
                diff_branch_name=self.diff_branch_name,
            )

    async def test_get_node_field_summaries(self, diff_repository: DiffRepository):
        diff_nodes = self._build_nodes(num_nodes=5, num_sub_fields=2)
        for diff_node in list(diff_nodes)[:3]:
            same_kind_diff_node = self.build_diff_node(num_sub_fields=3, no_recurse=True)
            same_kind_diff_node.kind = diff_node.kind
            same_attr_names = random.sample([a.name for a in diff_node.attributes], k=min(len(diff_node.attributes), 2))
            for attr_diff, attr_name in zip(list(same_kind_diff_node.attributes)[:2], same_attr_names):
                attr_diff.name = attr_name
            same_rel_names = random.sample(
                [r.name for r in diff_node.relationships], k=min(len(diff_node.relationships), 2)
            )
            for rel_diff, rel_name in zip(list(same_kind_diff_node.relationships)[:2], same_rel_names):
                rel_diff.name = rel_name
            diff_nodes.add(same_kind_diff_node)
        diff_root = EnrichedRootFactory.build(nodes=diff_nodes)
        diff_root.tracking_id = BranchTrackingId(name=diff_root.diff_branch_name)
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=diff_root)

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
