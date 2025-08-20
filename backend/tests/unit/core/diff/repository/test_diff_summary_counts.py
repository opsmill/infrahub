import random
from collections import Counter, defaultdict

import pytest

from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import (
    EnrichedDiffNode,
    EnrichedDiffRoot,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.database import InfrahubDatabase

from ..factories import (
    EnrichedConflictFactory,
    EnrichedRootFactory,
)
from .base import DiffRepositoryTestBase


class TestDiffSummaryCountsQuery(DiffRepositoryTestBase):
    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()))

    async def __save_and_update_diff(
        self, diff_repository: DiffRepository, enriched_diff: EnrichedDiffRoot
    ) -> EnrichedDiffRoot:
        await self._save_single_diff(diff_repository=diff_repository, enriched_diff=enriched_diff)
        return await diff_repository.get_one(
            diff_branch_name=enriched_diff.diff_branch_name, diff_id=enriched_diff.uuid
        )

    def _set_conflicts(self, diff_node: EnrichedDiffNode, conflict_chance: float = 1.0) -> None:
        if random.random() < conflict_chance:
            diff_node.conflict = EnrichedConflictFactory.build()
        else:
            diff_node.conflict = None
        for a in diff_node.attributes:
            for p in a.properties:
                if random.random() < conflict_chance:
                    p.conflict = EnrichedConflictFactory.build()
                else:
                    p.conflict = None
        for r in diff_node.relationships:
            for e in r.relationships:
                if random.random() < conflict_chance:
                    e.conflict = EnrichedConflictFactory.build()
                else:
                    e.conflict = None
                for p in e.properties:
                    if random.random() < conflict_chance:
                        p.conflict = EnrichedConflictFactory.build()
                    else:
                        p.conflict = None

    def _validate_counts(self, updated_diff: EnrichedDiffRoot) -> None:
        node_num_conflicts_map = defaultdict(lambda: 0)
        for n in updated_diff.nodes:
            # ATTRIBUTE-LEVEL
            for a in n.attributes:
                actions = [p.action for p in a.properties]
                summary_count = Counter(actions)
                assert a.num_added == summary_count.get(DiffAction.ADDED, 0)
                assert a.num_updated == summary_count.get(DiffAction.UPDATED, 0)
                assert a.num_removed == summary_count.get(DiffAction.REMOVED, 0)
                expected_num_conflicts = sum(1 for p in a.properties if p.conflict)
                assert a.num_conflicts == expected_num_conflicts
                assert a.contains_conflict == (a.num_conflicts > 0)

            for r in n.relationships:
                # RELATIONSHIP ELEMENT-LEVEL
                for e in r.relationships:
                    actions = [p.action for p in e.properties]
                    summary_count = Counter(actions)
                    assert e.num_added == summary_count.get(DiffAction.ADDED, 0)
                    assert e.num_updated == summary_count.get(DiffAction.UPDATED, 0)
                    assert e.num_removed == summary_count.get(DiffAction.REMOVED, 0)
                    expected_num_conflicts = sum(1 for p in e.properties if p.conflict)
                    expected_num_conflicts += 1 if e.conflict else 0
                    assert e.num_conflicts == expected_num_conflicts
                    assert e.contains_conflict == (e.num_conflicts > 0)

                # RELATIONSHIP-LEVEL
                actions = [e.action for e in r.relationships]
                summary_count = Counter(actions)
                assert r.num_added == summary_count.get(DiffAction.ADDED, 0)
                assert r.num_updated == summary_count.get(DiffAction.UPDATED, 0)
                assert r.num_removed == summary_count.get(DiffAction.REMOVED, 0)
                expected_num_conflicts = sum(e.num_conflicts for e in r.relationships)
                assert r.num_conflicts == expected_num_conflicts
                assert r.contains_conflict == (r.num_conflicts > 0)

            # NODE-LEVEL
            actions = [f.action for f in n.relationships | n.attributes]
            summary_count = Counter(actions)
            assert n.num_added == summary_count.get(DiffAction.ADDED, 0)
            assert n.num_updated == summary_count.get(DiffAction.UPDATED, 0)
            assert n.num_removed == summary_count.get(DiffAction.REMOVED, 0)
            # accumulate conflicts here to account for bubbling up conflict counts from child nodes
            expected_num_conflicts = 1 if n.conflict else 0
            expected_num_conflicts += sum(a.num_conflicts for a in n.attributes)
            expected_num_conflicts += sum(r.num_conflicts for r in n.relationships)
            node_num_conflicts_map[n.uuid] += expected_num_conflicts
            for r in n.relationships:
                for parent_n in r.nodes:
                    node_num_conflicts_map[parent_n.uuid] += expected_num_conflicts

        # NODE-LEVEL CONFLICTS COUNT
        for n in updated_diff.nodes:
            expected_num_conflicts = node_num_conflicts_map[n.uuid]
            assert n.num_conflicts == expected_num_conflicts
            assert n.contains_conflict == (n.num_conflicts > 0)

        # ROOT LEVEL
        actions = [n.action for n in updated_diff.nodes]
        summary_count = Counter(actions)
        assert updated_diff.num_added == summary_count.get(DiffAction.ADDED, 0)
        assert updated_diff.num_updated == summary_count.get(DiffAction.UPDATED, 0)
        assert updated_diff.num_removed == summary_count.get(DiffAction.REMOVED, 0)
        # need to add these up at the relationship/attribute level to avoid double-counting
        # conflicts in child nodes of a hierarchy
        expected_num_conflicts = 0
        for n in updated_diff.nodes:
            expected_num_conflicts += 1 if n.conflict else 0
            expected_num_conflicts += sum(a.num_conflicts for a in n.attributes)
            for r in n.relationships:
                expected_num_conflicts += sum(e.num_conflicts for e in r.relationships)
        assert updated_diff.num_conflicts == expected_num_conflicts
        assert updated_diff.contains_conflict == (updated_diff.num_conflicts > 0)

    async def test_no_nodes(self, diff_repository: DiffRepository) -> None:
        diff_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name, diff_branch_name=self.diff_branch_name, nodes=set()
        )
        updated_diff = await self.__save_and_update_diff(diff_repository=diff_repository, enriched_diff=diff_root)

        self._validate_counts(updated_diff=updated_diff)

    async def test_one_node_with_conflicts(self, diff_repository: DiffRepository) -> None:
        diff_node = self.build_diff_node(no_recurse=True)
        self._set_conflicts(diff_node=diff_node)
        diff_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name, diff_branch_name=self.diff_branch_name, nodes={diff_node}
        )
        updated_diff = await self.__save_and_update_diff(diff_repository=diff_repository, enriched_diff=diff_root)

        self._validate_counts(updated_diff=updated_diff)

    async def test_multiple_nodes_some_conflicts(self, diff_repository: DiffRepository) -> None:
        diff_nodes = set()
        for _ in range(2):
            diff_node = self.build_diff_node(no_recurse=True)
            self._set_conflicts(diff_node=diff_node, conflict_chance=0.5)
            diff_nodes.add(diff_node)
        diff_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name, diff_branch_name=self.diff_branch_name, nodes=diff_nodes
        )
        updated_diff = await self.__save_and_update_diff(diff_repository=diff_repository, enriched_diff=diff_root)

        self._validate_counts(updated_diff=updated_diff)

    async def test_existing_node_with_changes(self, diff_repository: DiffRepository) -> None:
        diff_nodes = {self.build_diff_node(no_recurse=True) for _ in range(2)}
        node_uuids = {n.uuid for n in diff_nodes}
        for dn in diff_nodes:
            self._set_conflicts(diff_node=dn, conflict_chance=0.5)
        diff_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name, diff_branch_name=self.diff_branch_name, nodes=diff_nodes
        )
        enriched_diffs = await self._save_single_diff(diff_repository=diff_repository, enriched_diff=diff_root)
        # set the counts for this diff
        await diff_repository.add_summary_counts(diff_branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid)
        # make a change
        node_to_update = enriched_diffs.diff_branch_diff.nodes.pop()
        updated_node = self.build_diff_node(no_recurse=True)
        updated_node.identifier = node_to_update.identifier
        self._set_conflicts(diff_node=updated_node, conflict_chance=0.5)
        enriched_diffs.diff_branch_diff.nodes = {updated_node}
        # set the counts again
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)
        await diff_repository.add_summary_counts(
            diff_branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid, node_uuids=[node_to_update.uuid]
        )
        # validate the updated counts
        updated_diff = await diff_repository.get_one(
            diff_branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid
        )
        assert {n.uuid for n in updated_diff.nodes} == node_uuids
        self._validate_counts(updated_diff=updated_diff)

    async def test_multiple_nodes_with_hierarchy(self, diff_repository: DiffRepository) -> None:
        diff_nodes = self._build_nodes(num_nodes=2, num_sub_fields=2)
        for dn in diff_nodes:
            self._set_conflicts(diff_node=dn, conflict_chance=0.5)
        diff_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name, diff_branch_name=self.diff_branch_name, nodes=diff_nodes
        )
        updated_diff = await self.__save_and_update_diff(diff_repository=diff_repository, enriched_diff=diff_root)

        self._validate_counts(updated_diff=updated_diff)

    async def test_existing_node_with_changes_and_parents(self, diff_repository: DiffRepository) -> None:
        diff_nodes = self._build_nodes(num_nodes=2, num_sub_fields=2)
        for dn in diff_nodes:
            self._set_conflicts(diff_node=dn, conflict_chance=0.5)
        node_uuids = {n.uuid for n in diff_nodes}
        diff_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name, diff_branch_name=self.diff_branch_name, nodes=diff_nodes
        )
        enriched_diffs = await self._save_single_diff(diff_repository=diff_repository, enriched_diff=diff_root)
        # make some changes to nodes with parents
        nodes_to_update = set()
        action_choices = list(DiffAction)
        for dn in diff_nodes:
            if all(not r.nodes for r in dn.relationships):
                continue
            self._set_conflicts(diff_node=dn, conflict_chance=0.5)

            for a in dn.attributes:
                a.action = random.choice(action_choices)
                for p in a.properties:
                    p.action = random.choice(action_choices)
            for r in dn.relationships:
                r.action = random.choice(action_choices)
                for e in r.relationships:
                    e.action = random.choice(action_choices)
                    for p in e.properties:
                        p.action = random.choice(action_choices)
            nodes_to_update.add(dn)

        enriched_diffs.diff_branch_diff.nodes = nodes_to_update
        # set the counts again
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)
        await diff_repository.add_summary_counts(
            diff_branch_name=diff_root.diff_branch_name,
            diff_id=diff_root.uuid,
            node_uuids=[n.uuid for n in nodes_to_update],
        )
        # validate the updated counts
        updated_diff = await diff_repository.get_one(
            diff_branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid
        )
        assert {n.uuid for n in updated_diff.nodes} == node_uuids
        self._validate_counts(updated_diff=updated_diff)
