from collections import defaultdict
from dataclasses import dataclass

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node.delete_validator import DeleteRelationshipType, NodeDeleteIndex
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.definitions.core import core_models
from infrahub.core.schema.schema_branch import SchemaBranch


def _cascade_closure(index: NodeDeleteIndex, root_kind: str) -> set[str]:
    """All kinds reachable from root_kind by following CASCADE_DELETE edges.

    Built from the public interface only (the same methods the delete path uses to
    resolve cascades), rather than reaching into the index's internal graph.
    """
    cascade_edges: dict[str, set[str]] = defaultdict(set)
    for full_identifier in index.get_relationship_identifiers():
        relationship_types = index.get_relationship_types(
            src_kind=full_identifier.source_kind, relationship_identifier=full_identifier.identifier
        )
        if DeleteRelationshipType.CASCADE_DELETE in relationship_types:
            cascade_edges[full_identifier.source_kind].add(full_identifier.destination_kind)

    reachable: set[str] = set()
    stack = [root_kind]
    while stack:
        for peer in cascade_edges[stack.pop()]:
            if peer not in reachable:
                reachable.add(peer)
                stack.append(peer)
    return reachable


@dataclass
class RepositoryCase:
    name: str
    kind: str


REPOSITORY_CASES = [
    RepositoryCase(name="read-only-repository", kind=InfrahubKind.READONLYREPOSITORY),
    RepositoryCase(name="read-write-repository", kind=InfrahubKind.REPOSITORY),
]


@pytest.mark.parametrize("case", REPOSITORY_CASES, ids=[case.name for case in REPOSITORY_CASES])
def test_repository_cascade_reaches_all_managed_leaves(case: RepositoryCase) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    all_schemas = schema_branch.get_all(duplicate=False)

    index = NodeDeleteIndex(all_schemas_map=all_schemas)
    repo_schema = all_schemas[case.kind]
    assert isinstance(repo_schema, NodeSchema)
    index.index(start_schemas=[repo_schema])

    reachable = _cascade_closure(index, case.kind)

    expected_leaves = {
        InfrahubKind.ARTIFACT,
        InfrahubKind.ARTIFACTVALIDATOR,
        InfrahubKind.GENERATORINSTANCE,
        InfrahubKind.GENERATORVALIDATOR,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.REPOSITORYGROUP,
        InfrahubKind.USERVALIDATOR,
    }
    assert expected_leaves <= reachable
