from collections import defaultdict
from dataclasses import dataclass

import pytest

from infrahub.core.constants import InfrahubKind, RelationshipDirection
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
    for pattern in index.get_link_patterns(relationship_type=DeleteRelationshipType.CASCADE_DELETE):
        cascade_edges[pattern.kind].add(pattern.peer_kind)

    reachable: set[str] = set()
    stack = [root_kind]
    while stack:
        for peer in cascade_edges[stack.pop()]:
            if peer not in reachable:
                reachable.add(peer)
                stack.append(peer)
    return reachable


def _index_for(kind: str) -> NodeDeleteIndex:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    all_schemas = schema_branch.get_all(duplicate=False)

    index = NodeDeleteIndex(all_schemas_map=all_schemas)
    schema = all_schemas[kind]
    assert isinstance(schema, NodeSchema)
    index.index(start_schemas=[schema])
    return index


@dataclass
class RepositoryCase:
    name: str
    kind: str


REPOSITORY_CASES = [
    RepositoryCase(name="read-only-repository", kind=InfrahubKind.READONLYREPOSITORY),
    RepositoryCase(name="read-write-repository", kind=InfrahubKind.REPOSITORY),
]


@pytest.mark.parametrize("case", REPOSITORY_CASES, ids=[case.name for case in REPOSITORY_CASES])
def test_repository_cascade_reaches_exactly_expected_kinds(case: RepositoryCase) -> None:
    reachable = _cascade_closure(_index_for(case.kind), case.kind)

    expected_cascade = {
        InfrahubKind.ARTIFACT,
        InfrahubKind.ARTIFACTCHECK,
        InfrahubKind.ARTIFACTDEFINITION,
        InfrahubKind.ARTIFACTVALIDATOR,
        InfrahubKind.CHECKDEFINITION,
        InfrahubKind.DATACHECK,
        InfrahubKind.FILECHECK,
        InfrahubKind.GENERATORCHECK,
        InfrahubKind.GENERATORDEFINITION,
        InfrahubKind.GENERATORINSTANCE,
        InfrahubKind.GENERATORVALIDATOR,
        InfrahubKind.GRAPHQLQUERY,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.REPOSITORYGROUP,
        InfrahubKind.SCHEMACHECK,
        InfrahubKind.STANDARDCHECK,
        InfrahubKind.TRANSFORMJINJA2,
        InfrahubKind.TRANSFORMPYTHON,
        InfrahubKind.USERVALIDATOR,
    }
    assert reachable == expected_cascade


def test_account_cascade_reaches_its_internal_children() -> None:
    index = _index_for(InfrahubKind.ACCOUNT)

    assert _cascade_closure(index, InfrahubKind.ACCOUNT) == {
        InfrahubKind.EXTERNALIDENTITY,
        InfrahubKind.ACCOUNTTOKEN,
        InfrahubKind.REFRESHTOKEN,
    }


def test_account_cascade_uses_the_paired_relationships() -> None:
    """The identifiers are asserted in full because each has to match the child's own side.

    The account side of `tokens` was generated rather than declared, so it resolved an identifier
    no edge in the graph uses and the cascade skipped tokens entirely.
    """
    index = _index_for(InfrahubKind.ACCOUNT)

    assert {
        pattern
        for relationship_type in DeleteRelationshipType
        for pattern in index.get_link_patterns(relationship_type=relationship_type)
        if pattern.peer_kind.startswith("Internal")
    } == {
        (
            InfrahubKind.ACCOUNT,
            "account__external_identity",
            RelationshipDirection.BIDIR,
            InfrahubKind.EXTERNALIDENTITY,
        ),
        (InfrahubKind.ACCOUNT, "account__token", RelationshipDirection.BIDIR, InfrahubKind.ACCOUNTTOKEN),
        (InfrahubKind.ACCOUNT, "account__refreshtoken", RelationshipDirection.BIDIR, InfrahubKind.REFRESHTOKEN),
    }


REPOSITORY_IMPORT_IDENTIFIERS = {
    "check_definition__repository",
    "generator_definition__repository",
    "repository__transformation",
}


def _dependent_patterns_of_repositories(skip_cascading: bool) -> set[tuple[str, str]]:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    index = NodeDeleteIndex(all_schemas_map=schema_branch.get_all(duplicate=False))

    index.index_dependent_links(
        deleted_kinds={InfrahubKind.REPOSITORY, InfrahubKind.READONLYREPOSITORY}, skip_cascading=skip_cascading
    )

    return {
        (pattern.kind, pattern.identifier)
        for pattern in index.get_link_patterns(relationship_type=DeleteRelationshipType.DEPENDENT_NODE)
        if pattern.identifier in REPOSITORY_IMPORT_IDENTIFIERS
    }


def test_repository_imported_nodes_require_their_repository() -> None:
    assert _dependent_patterns_of_repositories(skip_cascading=False) == {
        (kind, identifier)
        for kind in (InfrahubKind.REPOSITORY, InfrahubKind.READONLYREPOSITORY)
        for identifier in REPOSITORY_IMPORT_IDENTIFIERS
    }


def test_dependent_links_skip_the_relationships_a_repository_cascades_on() -> None:
    assert _dependent_patterns_of_repositories(skip_cascading=True) == set()
