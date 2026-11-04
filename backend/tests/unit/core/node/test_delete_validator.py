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
        InfrahubKind.CHECK,
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
        InfrahubKind.TRANSFORM,
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
        (full_id.source_kind, full_id.identifier, full_id.destination_kind)
        for full_id in index.get_relationship_identifiers()
        if full_id.destination_kind.startswith("Internal")
    } == {
        (InfrahubKind.ACCOUNT, "account__external_identity", InfrahubKind.EXTERNALIDENTITY),
        (InfrahubKind.ACCOUNT, "account__token", InfrahubKind.ACCOUNTTOKEN),
        (InfrahubKind.ACCOUNT, "account__refreshtoken", InfrahubKind.REFRESHTOKEN),
    }
