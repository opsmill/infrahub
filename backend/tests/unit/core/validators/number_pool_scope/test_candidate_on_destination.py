"""Checks of a candidate built on the destination's schema for a change made on the source branch."""

from __future__ import annotations

from infrahub.core.constants import SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from tests.unit.core.validators.number_pool_scope.helpers import (
    ALL_POOLS,
    BRANCH,
    DEVICE,
    RecordingPoolSource,
    StaticSchemaSource,
    build_checker,
    build_schema_branch,
    device_site_removed,
    saved_schema,
)


class TestCandidateOnDestination:
    """A proposed change or a merge builds the candidate on the destination's schema and checks it for the source."""

    async def test_reports_a_pool_of_the_destination_scoped_by_a_field_the_source_removed(self) -> None:
        source_schema = saved_schema()
        device_site_removed(source_schema)
        candidate_schema = saved_schema()
        device_site_removed(candidate_schema)
        pool_source = RecordingPoolSource(pools=ALL_POOLS)
        checker = build_checker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(
                schema_branch=build_schema_branch(source_schema),
                default_branch_schema=build_schema_branch(saved_schema(), name=registry.default_branch),
            ),
        )
        candidate = build_schema_branch(candidate_schema, name=registry.default_branch)
        node_schema = candidate.get(name=DEVICE, duplicate=False)
        assert isinstance(node_schema, NodeSchema)
        request = SchemaConstraintValidatorRequest(
            branch=BRANCH,
            constraint_name="node.relationship.remove",
            node_schema=node_schema,
            schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=DEVICE, field_name="site"),
            schema_branch=candidate,
        )

        grouped_data_paths = await checker.check(request)

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == [
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site;"
                " a scope element cannot be removed while the pool exists",
            )
        ]
