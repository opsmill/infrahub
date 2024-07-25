import random
import string
from datetime import UTC
from random import randint
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime
from polyfactory.factories import DataclassFactory

from infrahub import config
from infrahub.core.diff.model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase


class PropertyFactory(DataclassFactory[EnrichedDiffProperty]): ...


class AttributeFactory(DataclassFactory[EnrichedDiffAttribute]): ...


class RelationshipGroupFactory(DataclassFactory[EnrichedDiffRelationship]): ...


class RelationshipElementFactory(DataclassFactory[EnrichedDiffSingleRelationship]): ...


class NodeFactory(DataclassFactory[EnrichedDiffNode]): ...


class RootFactory(DataclassFactory[EnrichedDiffRoot]): ...


class TestDiffRepositorySaveAndLoad:
    @pytest.fixture
    async def reset_database(self, db: InfrahubDatabase):
        await delete_all_nodes(db=db)

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        return DiffRepository(db=db)

    def build_diff_node(self, num_sub_fields=2) -> EnrichedDiffNode:
        enriched_node = NodeFactory.build(
            attributes={
                AttributeFactory.build(properties={PropertyFactory.build() for _ in range(num_sub_fields)})
                for _ in range(num_sub_fields)
            },
            relationships={
                RelationshipGroupFactory.build(
                    relationships={
                        RelationshipElementFactory.build(
                            properties={PropertyFactory.build() for _ in range(num_sub_fields)},
                        )
                        for _ in range(num_sub_fields)
                    },
                    nodes=set(),
                )
                for _ in range(num_sub_fields)
            },
        )
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
        enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=self._build_nodes(num_nodes=5, num_sub_fields=3),
        )

        await diff_repository.save(enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
        )
        assert len(retrieved) == 1
        diff_root = retrieved[0]
        assert diff_root == enriched_diff

    async def test_base_branch_name_filter(self, diff_repository: DiffRepository, reset_database):
        name_uuid_map = {name: str(uuid4()) for name in (self.base_branch_name, "more-main", "most-main")}
        for base_branch_name, root_uuid in name_uuid_map.items():
            enriched_diff = RootFactory.build(
                base_branch_name=base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(self.diff_from_time),
                to_time=Timestamp(self.diff_to_time),
                uuid=root_uuid,
                nodes=[],
            )
            await diff_repository.save(enriched_diff=enriched_diff)

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
                start_time = start_time.add(seconds=randint(150_000, 300_000))
                end_time = start_time.add(seconds=randint(25_000, 100_000))
                root_uuid = str(uuid4())
                diff_uuids_by_name[diff_branch_name].add(root_uuid)
                enriched_diff = RootFactory.build(
                    base_branch_name=self.base_branch_name,
                    diff_branch_name=diff_branch_name,
                    from_time=Timestamp(start_time),
                    to_time=Timestamp(end_time),
                    uuid=root_uuid,
                    nodes=[],
                )
                await diff_repository.save(enriched_diff=enriched_diff)

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
        enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            uuid=root_uuid,
            nodes=set(),
        )
        await diff_repository.save(enriched_diff=enriched_diff)

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
            enriched_diff = RootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=f"branch{i}",
                from_time=Timestamp(self.diff_from_time),
                to_time=Timestamp(self.diff_to_time),
                nodes=nodes,
            )
            enriched_diffs.append(enriched_diff)
            await diff_repository.save(enriched_diff=enriched_diff)

        one_diff = enriched_diffs[0]
        nodes_without_parents = one_diff.get_nodes_without_parents()
        nodes_without_children = set()
        for node in one_diff.nodes:
            if any(rel.nodes for rel in node.relationships):
                continue
            nodes_without_children.add(node)
        nodes_with_parents_and_children = one_diff.nodes - nodes_without_parents - nodes_without_children

        # just root nodes
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[rd.diff_branch_name for rd in enriched_diffs],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            root_node_uuids=[n.uuid for n in nodes_without_parents],
        )
        assert len(retrieved) == 1
        assert retrieved[0] == one_diff
        # just leaf nodes
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[rd.diff_branch_name for rd in enriched_diffs],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            root_node_uuids=[n.uuid for n in nodes_without_children],
        )
        assert len(retrieved) == 1
        assert retrieved[0].nodes == nodes_without_children
        # just middle nodes
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[rd.diff_branch_name for rd in enriched_diffs],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            root_node_uuids=[n.uuid for n in nodes_with_parents_and_children],
        )
        assert len(retrieved) == 1
        assert retrieved[0].nodes == one_diff.nodes - nodes_without_parents
        # one node from each diff
        first_nodes_map = {diff.uuid: diff.nodes.pop() for diff in enriched_diffs}
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[rd.diff_branch_name for rd in enriched_diffs],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            root_node_uuids=[n.uuid for n in first_nodes_map.values()],
        )
        assert len(retrieved) == 5
        for retrieved_root in retrieved:
            expected_first_node = first_nodes_map[retrieved_root.uuid]
            node_with_children = expected_first_node.get_all_child_nodes() | {expected_first_node}
            assert retrieved_root.nodes == node_with_children

    async def test_filter_max_depth(self, diff_repository: DiffRepository, reset_database):
        nodes_by_depth_of_children: dict[int, EnrichedDiffNode] = {}
        previous_node = None
        depth = 0
        while depth < 4:
            node = NodeFactory.build(relationships=set())
            if previous_node:
                relationship_group = RelationshipGroupFactory.build(nodes={previous_node})
                node.relationships.add(relationship_group)
            nodes_by_depth_of_children[depth] = node
            previous_node = node
            depth += 1
        three_deep_node = nodes_by_depth_of_children[3]
        two_deep_node = nodes_by_depth_of_children[2]
        one_deep_node = nodes_by_depth_of_children[1]
        zero_deep_node = nodes_by_depth_of_children[0]

        enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=set(nodes_by_depth_of_children.values()),
        )
        await diff_repository.save(enriched_diff=enriched_diff)

        # depth 1, no node filters
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            max_depth=1,
        )
        assert len(retrieved) == 1
        expected_nodes = {three_deep_node.get_trimmed_node(max_depth=1), two_deep_node.get_trimmed_node(max_depth=0)}
        assert retrieved[0].nodes == expected_nodes

        # depth 1, with node filters
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            root_node_uuids=[three_deep_node.uuid, zero_deep_node.uuid],
            max_depth=1,
        )
        assert len(retrieved) == 1
        expected_nodes = {
            three_deep_node.get_trimmed_node(max_depth=1),
            two_deep_node.get_trimmed_node(max_depth=0),
            zero_deep_node.get_trimmed_node(max_depth=1),
        }
        assert retrieved[0].nodes == expected_nodes

        # depth 2, with node filters
        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            root_node_uuids=[two_deep_node.uuid],
            max_depth=2,
        )
        assert len(retrieved) == 1
        expected_nodes = {
            two_deep_node.get_trimmed_node(max_depth=2),
            one_deep_node.get_trimmed_node(max_depth=1),
            zero_deep_node.get_trimmed_node(max_depth=0),
        }
        assert retrieved[0].nodes == expected_nodes

    async def test_filter_limit_and_offset_flat(self, diff_repository: DiffRepository, reset_database):
        ordered_nodes = []
        for kind, label in (("A", "a"), ("A", "b"), ("B", "a"), ("B", "b")):
            ordered_nodes.append(NodeFactory.build(kind=kind, label=label, relationships=set()))
        enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=set(ordered_nodes),
        )
        await diff_repository.save(enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            limit=2,
        )
        assert len(retrieved) == 1
        assert retrieved[0].nodes == set(ordered_nodes[:2])

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            limit=2,
            offset=2,
        )
        assert len(retrieved) == 1
        assert retrieved[0].nodes == set(ordered_nodes[2:])

    async def test_filter_limit_and_offset_with_nested_nodes(self, diff_repository: DiffRepository, reset_database):
        nodes = self._build_nodes(num_nodes=10, num_sub_fields=3)
        enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=nodes,
        )
        root_nodes = enriched_diff.get_nodes_without_parents()
        ordered_nodes = list(root_nodes)
        kinds = sorted(random.choices(string.ascii_uppercase, k=5))
        for i in range(5):
            kind = kinds[i]
            labels = sorted(random.choices(string.ascii_lowercase, k=2))
            ordered_nodes[2 * i].kind = kind
            ordered_nodes[2 * i + 1].kind = kind
            ordered_nodes[2 * i].label = labels[0]
            ordered_nodes[2 * i + 1].label = labels[1]
        await diff_repository.save(enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            limit=2,
        )
        expected_root_nodes = set(ordered_nodes[:2])
        all_expected_nodes = set(expected_root_nodes)
        for n in expected_root_nodes:
            all_expected_nodes |= n.get_all_child_nodes()
        assert len(retrieved) == 1
        assert retrieved[0].get_nodes_without_parents() == expected_root_nodes
        assert retrieved[0].nodes == all_expected_nodes

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            limit=4,
            offset=2,
        )
        expected_root_nodes = set(ordered_nodes[2:6])
        all_expected_nodes = set(expected_root_nodes)
        for n in expected_root_nodes:
            all_expected_nodes |= n.get_all_child_nodes()
        assert len(retrieved) == 1
        assert retrieved[0].get_nodes_without_parents() == set(ordered_nodes[2:6])
        assert retrieved[0].nodes == all_expected_nodes

    async def test_filter_limit_and_offset_across_multiple_roots(self, diff_repository: DiffRepository, reset_database):
        enriched_diffs = []
        node_uuids = [str(uuid4()) for _ in range(3)]
        first_nodes = []
        second_nodes = []
        third_nodes = []
        start_time = self.diff_from_time.add(minutes=1)
        for i in range(3):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = RootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(start_time.add(minutes=i * 30)),
                to_time=Timestamp(start_time.add(minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            enriched_diffs.append(enriched_diff)
            root_nodes = enriched_diff.get_nodes_without_parents()
            ordered_nodes = list(root_nodes)
            first_node, second_node, third_node = ordered_nodes
            first_node.kind = "A"
            first_node.label = "a"
            first_node.uuid = node_uuids[0]
            first_nodes.append(first_node)
            second_node.kind = "B"
            second_node.label = "b"
            second_node.uuid = node_uuids[1]
            second_nodes.append(second_node)
            third_node.kind = "C"
            third_node.label = "c"
            third_node.uuid = node_uuids[2]
            third_nodes.append(third_node)
            await diff_repository.save(enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(start_time),
            to_time=Timestamp(start_time.add(minutes=100)),
            limit=1,
        )
        assert len(retrieved) == 3
        for index, retrieved_root in enumerate(retrieved):
            root_nodes = retrieved_root.get_nodes_without_parents()
            assert len(root_nodes) == 1
            assert root_nodes == {first_nodes[index]}

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(start_time),
            to_time=Timestamp(start_time.add(minutes=100)),
            limit=1,
            offset=1,
        )
        assert len(retrieved) == 3
        for index, retrieved_root in enumerate(retrieved):
            root_nodes = retrieved_root.get_nodes_without_parents()
            assert len(root_nodes) == 1
            assert root_nodes == {second_nodes[index]}

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(start_time),
            to_time=Timestamp(start_time.add(minutes=100)),
            limit=1,
            offset=2,
        )
        assert len(retrieved) == 3
        for index, retrieved_root in enumerate(retrieved):
            root_nodes = retrieved_root.get_nodes_without_parents()
            assert len(root_nodes) == 1
            assert root_nodes == {third_nodes[index]}

    async def test_save_and_retrieve_many_diffs(self, diff_repository: DiffRepository, reset_database):
        diffs_to_retrieve: list[EnrichedDiffRoot] = []
        start_time = self.diff_from_time.add(seconds=1)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = RootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(start_time.add(minutes=i * 30)),
                to_time=Timestamp(start_time.add(minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await diff_repository.save(enriched_diff=enriched_diff)
            diffs_to_retrieve.append(enriched_diff)
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            enriched_diff = RootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(start_time.add(days=3, minutes=(i * 30))),
                to_time=Timestamp(start_time.add(days=3, minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await diff_repository.save(enriched_diff=enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(start_time),
            to_time=Timestamp(start_time.add(minutes=150)),
        )
        assert len(retrieved) == 5
        assert set(retrieved) == set(diffs_to_retrieve)

    async def test_retrieve_overlapping_diffs_excludes_duplicates(
        self, diff_repository: DiffRepository, reset_database
    ):
        for i in range(5):
            nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
            incremental_enriched_diff = RootFactory.build(
                base_branch_name=self.base_branch_name,
                diff_branch_name=self.diff_branch_name,
                from_time=Timestamp(self.diff_from_time.add(minutes=i * 30)),
                to_time=Timestamp(self.diff_from_time.add(minutes=(i * 30) + 29)),
                nodes=nodes,
            )
            await diff_repository.save(enriched_diff=incremental_enriched_diff)
        nodes = self._build_nodes(num_nodes=3, num_sub_fields=2)
        super_enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_from_time.add(minutes=(4 * 30) + 29)),
            nodes=nodes,
        )
        await diff_repository.save(enriched_diff=super_enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_from_time.add(minutes=(4 * 30) + 29)),
        )
        assert len(retrieved) == 1
        assert retrieved[0] == super_enriched_diff
