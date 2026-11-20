from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import load_extra_core_schemas
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.workers.dependencies import build_extra_core_schemas, get_extra_core_schemas
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from fast_depends import Provider

EXTRA_SCHEMA = SchemaRoot(
    nodes=[{"name": "ExtraNode", "namespace": "Testing", "attributes": [{"name": "name", "kind": "Text"}]}]
)


def test_community_has_no_extra_core_schemas() -> None:
    assert get_extra_core_schemas() == []


def test_extra_core_schemas_come_from_the_override(dependency_provider: Provider) -> None:
    with override_dependency(build_extra_core_schemas, lambda: [EXTRA_SCHEMA], dependency_provider=dependency_provider):
        assert get_extra_core_schemas() == [EXTRA_SCHEMA]


def test_load_extra_core_schemas_adds_the_nodes(dependency_provider: Provider) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")

    with override_dependency(build_extra_core_schemas, lambda: [EXTRA_SCHEMA], dependency_provider=dependency_provider):
        load_extra_core_schemas(schema_branch=schema_branch)

    assert schema_branch.has(name="TestingExtraNode")


def test_load_extra_core_schemas_adds_nothing_by_default() -> None:
    schema_branch = SchemaBranch(cache={}, name="test")

    load_extra_core_schemas(schema_branch=schema_branch)

    assert schema_branch.node_names == []
