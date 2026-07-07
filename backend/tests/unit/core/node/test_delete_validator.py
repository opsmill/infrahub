from dataclasses import dataclass

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node.delete_validator import DeleteRelationshipType, NodeDeleteIndex
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.definitions.core import core_models
from infrahub.core.schema.schema_branch import SchemaBranch


def _cascade_closure(index: NodeDeleteIndex, root_kind: str) -> set[str]:
    """All kinds reachable from root_kind by following CASCADE_DELETE edges."""
    reachable: set[str] = set()
    stack = [root_kind]
    while stack:
        kind = stack.pop()
        # _dependency_graph is accessed directly on purpose: there is no public
        # traversal API, and the closure is exactly what this test needs to prove.
        edges = index._dependency_graph.get(kind, {}).get(DeleteRelationshipType.CASCADE_DELETE, {})
        for peer_kinds in edges.values():
            for peer in peer_kinds:
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
        InfrahubKind.USERVALIDATOR,
    }
    assert expected_leaves <= reachable
