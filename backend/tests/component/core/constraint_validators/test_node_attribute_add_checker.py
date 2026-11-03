from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality, SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.attribute import NodeAttributeAddChecker
from tests.helpers.number_pool import SCOPED_SITE, save_schema_kinds, scoped_site

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SWITCH = NodeSchema(
    name="Switch",
    namespace="Scope",
    label="Switch",
    human_friendly_id=["name__value"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="site",
            peer=SCOPED_SITE.kind,
            identifier="scope_switch__site",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)


def _switch_with_vlan_id(allocation_scope: list[str] | None) -> NodeSchema:
    switch = SWITCH.duplicate()
    switch.attributes.append(
        AttributeSchema(
            name="vlan_id",
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(start_range=1, end_range=10, allocation_scope=allocation_scope),
        )
    )
    return switch


class TestNodeAttributeAddCheckerOnNumberPool:
    """A required NumberPool attribute added to a kind holding 50 switches over 10 sites, with a range of 10 numbers."""

    @pytest.fixture(scope="class")
    async def fifty_switches(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await save_schema_kinds(db=db, schema=SchemaRoot(nodes=[SCOPED_SITE, SWITCH]))
        for site_index in range(1, 11):
            site = await scoped_site(db=db, branch=default_branch_scope_class, name=f"site-{site_index}")
            for switch_index in range(1, 6):
                switch = await Node.init(db=db, schema=SWITCH.kind, branch=default_branch_scope_class)
                await switch.new(db=db, name=f"switch-{site_index}-{switch_index}", site=site)
                await switch.save(db=db)

    @staticmethod
    async def _check(db: InfrahubDatabase, branch: Branch, allocation_scope: list[str] | None) -> int:
        """Run the check for the switch kind with `vlan_id` added and return the number of nodes it reports."""
        request = SchemaConstraintValidatorRequest(
            branch=branch,
            constraint_name="node.attribute.add",
            node_schema=_switch_with_vlan_id(allocation_scope=allocation_scope),
            schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=SWITCH.kind, field_name="vlan_id"),
            schema_branch=registry.schema.get_schema_branch(name=branch.name),
        )
        grouped_data_paths = await NodeAttributeAddChecker(db=db, branch=branch).check(request=request)
        return sum(len(paths.get_all_data_paths()) for paths in grouped_data_paths)

    async def test_scoped_pool_is_not_refused_on_the_count_of_the_kind(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, fifty_switches: None
    ) -> None:
        assert await self._check(db=db, branch=default_branch_scope_class, allocation_scope=["site"]) == 0

    async def test_unscoped_pool_smaller_than_the_kind_is_refused(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, fifty_switches: None
    ) -> None:
        with pytest.raises(
            ValueError, match=r"^The size of the NumberPool is smaller than the number of existing nodes 10 < 50\.$"
        ):
            await self._check(db=db, branch=default_branch_scope_class, allocation_scope=None)
