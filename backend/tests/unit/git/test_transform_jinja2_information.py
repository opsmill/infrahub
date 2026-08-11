from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import CoreTransformJinja2
from infrahub_sdk.schema import NodeSchemaAPI

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.git.integrator import InfrahubRepositoryIntegrator, InfrahubRepositoryJinja2


def _load_core_node_schema(kind: str) -> NodeSchemaAPI:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    # Flatten inherited attributes/relationships so the node schema carries the full field set.
    schema_branch.process_inheritance()
    return NodeSchemaAPI(**schema_branch.get(name=kind, duplicate=False).model_dump())


TRANSFORM_JINJA2_SCHEMA = _load_core_node_schema("CoreTransformJinja2")
EXISTING_TRANSFORM_ID = "a0d4c22a-5f60-4bf9-a53f-f9a335420492"


def _make_existing_transform(
    query_id: str = "query-id",
    template_path: str = "templates/test.j2",
    description: str | None = None,
    dependencies: list[str] | None = None,
    dependencies_complete: bool = False,
) -> CoreTransformJinja2:
    client = InfrahubClient(config=Config(address="http://mock"))
    data = {
        "id": EXISTING_TRANSFORM_ID,
        "__typename": "CoreTransformJinja2",
        "display_label": "test-transform",
        "name": {"value": "test", "__typename": "Text"},
        "label": {"value": "Test", "__typename": "Text"},
        "description": {"value": description, "__typename": "Text"},
        "template_path": {"value": template_path, "__typename": "Text"},
        "dependencies": {"value": dependencies if dependencies is not None else [], "__typename": "List"},
        "dependencies_complete": {"value": dependencies_complete, "__typename": "Boolean"},
        "query": {
            "node": {"id": query_id, "display_label": "test-query", "__typename": "CoreGraphQLQuery"},
            "__typename": "NestedEdgedCoreGraphQLQuery",
        },
    }
    # Round-trip through the client store so the returned node is typed as the generated
    # protocol rather than the bare InfrahubNode the constructor yields.
    client.store.set(InfrahubNode(client=client, schema=TRANSFORM_JINJA2_SCHEMA, data=data))
    return client.store.get(kind=CoreTransformJinja2, key=EXISTING_TRANSFORM_ID)


def _make_local_transform(
    template_path: str = "templates/test.j2",
    description: str | None = None,
    dependencies: list[str] | None = None,
    dependencies_complete: bool = False,
) -> InfrahubRepositoryJinja2:
    return InfrahubRepositoryJinja2(
        name="test",
        repository="repo-id",
        query="query-id",
        template_path=Path(template_path),
        description=description,
        dependencies=dependencies if dependencies is not None else [],
        dependencies_complete=dependencies_complete,
    )


@dataclass
class CompareJinja2Case:
    name: str
    """Descriptive name for the test scenario (used as test ID)."""

    expected: bool
    """Expected result of the comparison: True when the stored and local transform match."""

    existing_kwargs: dict[str, Any] = field(default_factory=dict)
    """Overrides for the stored transform node."""

    local_kwargs: dict[str, Any] = field(default_factory=dict)
    """Overrides for the local transform parsed from the repository config."""


COMPARE_JINJA2_TEST_CASES: list[CompareJinja2Case] = [
    # Identical inputs: the local template_path is a Path while the stored value is a str, so an
    # unchanged transform must compare equal across the type boundary rather than look changed.
    CompareJinja2Case(name="identical", expected=True),
    CompareJinja2Case(
        name="template_path_changed",
        expected=False,
        existing_kwargs={"template_path": "templates/old.j2"},
        local_kwargs={"template_path": "templates/new.j2"},
    ),
    CompareJinja2Case(
        name="description_changed",
        expected=False,
        local_kwargs={"description": "New description"},
    ),
    CompareJinja2Case(
        name="description_removed",
        expected=False,
        existing_kwargs={"description": "Old description"},
    ),
    CompareJinja2Case(
        name="description_same",
        expected=True,
        existing_kwargs={"description": "Same"},
        local_kwargs={"description": "Same"},
    ),
    CompareJinja2Case(
        name="query_changed",
        expected=False,
        existing_kwargs={"query_id": "old-query-id"},
    ),
    CompareJinja2Case(
        name="dependencies_changed",
        expected=False,
        existing_kwargs={"dependencies": ["templates/test.j2"]},
        local_kwargs={"dependencies": ["templates/test.j2", "templates/partial.j2"]},
    ),
    CompareJinja2Case(
        name="dependencies_complete_changed",
        expected=False,
        local_kwargs={"dependencies_complete": True},
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in COMPARE_JINJA2_TEST_CASES],
)
async def test_compare_jinja2_transform(test_case: CompareJinja2Case) -> None:
    existing = _make_existing_transform(**test_case.existing_kwargs)
    local = _make_local_transform(**test_case.local_kwargs)
    assert await InfrahubRepositoryIntegrator.compare_jinja2_transform(existing, local) is test_case.expected
