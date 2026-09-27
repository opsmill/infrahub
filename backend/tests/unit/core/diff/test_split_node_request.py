from unittest.mock import MagicMock

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot, EnrichedDiffs
from infrahub.core.diff.repository.repository import DiffRepository
from tests.helpers.diff_factories import (
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)

PROPERTY_TYPES = [DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.IS_PROTECTED]


def build_node(elements_per_relationship: list[int]) -> EnrichedDiffNode:
    return EnrichedNodeFactory.build(
        attributes=set(),
        relationships={
            EnrichedRelationshipGroupFactory.build(
                name=f"rel{index}",
                nodes=set(),
                relationships={
                    EnrichedRelationshipElementFactory.build(
                        properties={EnrichedPropertyFactory.build(property_type=ptype) for ptype in PROPERTY_TYPES}
                    )
                    for _ in range(count)
                },
            )
            for index, count in enumerate(elements_per_relationship)
        },
    )


def build_repository(max_save_batch_size: int) -> DiffRepository:
    return DiffRepository(db=MagicMock(), deserializer=MagicMock(), max_save_batch_size=max_save_batch_size)


def test_split_covers_every_element_once_within_budget() -> None:
    node = build_node(elements_per_relationship=[37, 5, 20])
    repository = build_repository(max_save_batch_size=10)

    chunks = list(repository._split_node_request(node=node, root_uuid="root"))

    assert len(chunks) > 1
    assert [chunk.is_first_chunk for chunk in chunks] == [True] + [False] * (len(chunks) - 1)
    seen: dict[str, list[str]] = {}
    for chunk in chunks:
        assert chunk.node is node
        assert chunk.is_chunk
        assert chunk.relationship_elements is not None
        assert sum(e.num_properties for elements in chunk.relationship_elements.values() for e in elements) <= 10
        for rel_name, elements in chunk.relationship_elements.items():
            seen.setdefault(rel_name, []).extend(e.peer_id for e in elements)
    for relationship in node.relationships:
        expected = sorted(e.peer_id for e in relationship.relationships)
        assert sorted(seen[relationship.name]) == expected


def test_oversized_nodes_are_split_and_small_nodes_batched_as_before() -> None:
    small_nodes = {build_node(elements_per_relationship=[1]) for _ in range(3)}
    big_node = build_node(elements_per_relationship=[50])
    diff_root: EnrichedDiffRoot = EnrichedRootFactory.build(nodes=small_nodes | {big_node})
    base_root: EnrichedDiffRoot = EnrichedRootFactory.build(nodes=set())
    enriched_diffs = EnrichedDiffs(
        base_branch_name="main",
        diff_branch_name="branch",
        base_branch_diff=base_root,
        diff_branch_diff=diff_root,
    )
    repository = build_repository(max_save_batch_size=20)

    batches = list(repository._get_node_create_request_batch(enriched_diffs=enriched_diffs))

    chunk_batches = [b for b in batches if any(r.is_chunk for r in b)]
    plain_requests = [r for b in batches for r in b if not r.is_chunk]
    assert all(len(b) == 1 for b in chunk_batches)
    assert {r.node for b in chunk_batches for r in b} == {big_node}
    assert {r.node for r in plain_requests} == small_nodes
    assert sum(1 for b in chunk_batches if b[0].is_first_chunk) == 1


def test_node_under_budget_is_not_split() -> None:
    node = build_node(elements_per_relationship=[3])
    diff_root: EnrichedDiffRoot = EnrichedRootFactory.build(nodes={node})
    enriched_diffs = EnrichedDiffs(
        base_branch_name="main",
        diff_branch_name="branch",
        base_branch_diff=EnrichedRootFactory.build(nodes=set()),
        diff_branch_diff=diff_root,
    )

    batches = list(
        build_repository(max_save_batch_size=100)._get_node_create_request_batch(enriched_diffs=enriched_diffs)
    )

    assert len(batches) == 1
    assert [r.is_chunk for r in batches[0]] == [False]
