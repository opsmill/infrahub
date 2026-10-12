"""Checks on a worker that has not loaded the schema of the request's branch."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.exceptions import InitializationError
from tests.unit.core.validators.number_pool_scope.helpers import (
    BRANCH,
    DEVICE,
    DEVICE_POOL_BY_SITE,
    RecordingPoolSource,
    build_checker,
    build_schema_branch,
    device_site_optional,
    saved_schema,
)

if TYPE_CHECKING:
    from infrahub.core.validators.pool.scope import NumberPoolScopeChecker
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool


class TestUnloadedBranch:
    """A worker that has not loaded the schema of the request's branch cannot tell which pools a change breaks."""

    @staticmethod
    def _checker(pools: tuple[ScopedNumberPool, ...]) -> tuple[NumberPoolScopeChecker, SchemaManager]:
        schema_manager = SchemaManager()
        schema_manager.set_schema_branch(
            name=registry.default_branch, schema=build_schema_branch(saved_schema(), name=registry.default_branch)
        )
        checker = build_checker(
            pool_source=RecordingPoolSource(pools=pools),
            schema_source=schema_manager,
        )
        return checker, schema_manager

    @staticmethod
    def _site_made_optional_request() -> SchemaConstraintValidatorRequest:
        candidate_schema = saved_schema()
        device_site_optional(candidate_schema)
        candidate = build_schema_branch(candidate_schema)
        node_schema = candidate.get(name=DEVICE, duplicate=False)
        assert isinstance(node_schema, NodeSchema)
        return SchemaConstraintValidatorRequest(
            branch=BRANCH,
            constraint_name="relationship.optional.update",
            node_schema=node_schema,
            schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=DEVICE, field_name="site"),
            schema_branch=candidate,
        )

    async def test_refuses_to_check_a_field_a_pool_may_depend_on_without_registering_the_branch(self) -> None:
        checker, schema_manager = self._checker(pools=(DEVICE_POOL_BY_SITE,))

        with pytest.raises(
            InitializationError,
            match=r"^The schema of branch feature is not loaded; the change to ScopeDevice\.site cannot be checked"
            r" against the number pools$",
        ):
            await checker.check(self._site_made_optional_request())
        assert not schema_manager.has_schema_branch(name=BRANCH.name)

    async def test_accepts_a_change_no_pool_depends_on_without_registering_the_branch(self) -> None:
        checker, schema_manager = self._checker(pools=())

        assert await checker.check(self._site_made_optional_request()) == []
        assert not schema_manager.has_schema_branch(name=BRANCH.name)
