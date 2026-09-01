from collections import defaultdict
from dataclasses import dataclass

import pytest

from infrahub.core.constants import InfrahubKind, RelationshipDeleteBehavior
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
def test_repository_cascade_reaches_exactly_expected_kinds(case: RepositoryCase) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    all_schemas = schema_branch.get_all(duplicate=False)

    index = NodeDeleteIndex(all_schemas_map=all_schemas)
    repo_schema = all_schemas[case.kind]
    assert isinstance(repo_schema, NodeSchema)
    index.index(start_schemas=[repo_schema])

    reachable = _cascade_closure(index, case.kind)

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


def test_deleting_generator_target_cascades_to_generator_instance() -> None:
    """Deleting the object a generator instance targets must cascade to the generator instance.

    Artifacts already work this way: CoreArtifact.object peers to the CoreArtifactTarget generic,
    which carries an `artifacts` relationship with on_delete=CASCADE, so deleting an artifact target
    removes its artifacts. Generator instances have no equivalent: CoreGeneratorInstance.object peers
    to CoreNode, which carries no cascade relationship back to the instance. Deleting a target object
    therefore leaves an orphaned CoreGeneratorInstance whose mandatory `object` peer no longer exists.
    """
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    all_schemas = schema_branch.get_all(duplicate=False)

    instance_schema = all_schemas[InfrahubKind.GENERATORINSTANCE]
    target_kind = instance_schema.get_relationship(name="object").peer
    target_schema = all_schemas[target_kind]

    cascade_delete_peers = {
        relationship.peer
        for relationship in target_schema.relationships
        if relationship.on_delete == RelationshipDeleteBehavior.CASCADE
    }

    assert InfrahubKind.GENERATORINSTANCE in cascade_delete_peers
