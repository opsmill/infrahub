from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase

WIDGET_KIND = "TestingWidget"
GADGET_KIND = "TestingGadget"
BRANCH_NAME = "remove-template-node"


class TestLoadRemoveTemplateNodeOnBranch(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
    ) -> None:
        schema: dict[str, Any] = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Widget",
                    "namespace": "Testing",
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                },
                {
                    "name": "Gadget",
                    "namespace": "Testing",
                    "generate_template": True,
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                },
            ],
        }
        response = await client.schema.load(schemas=[schema])
        assert response.schema_updated
        assert not response.errors

    async def test_registry_refresh_after_removing_template_node_on_branch(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        load_schema: None,
    ) -> None:
        """Reloading a branch schema after a template-generating node was removed must succeed.

        The reloaded schema must drop the node together with its generated template
        and profile. A registry holding the pre-removal schema stands in for another
        worker that has not yet seen the update and refreshes the branch from the
        database.
        """
        await client.branch.create(branch_name=BRANCH_NAME)

        stale_schema = registry.schema.get_schema_branch(name=BRANCH_NAME).duplicate()
        assert GADGET_KIND in stale_schema.node_names
        assert f"Template{GADGET_KIND}" in stale_schema.template_names

        removal: dict[str, Any] = {
            "version": "1.0",
            "nodes": [{"name": "Gadget", "namespace": "Testing", "state": "absent"}],
        }
        response = await client.schema.load(schemas=[removal], branch=BRANCH_NAME)
        assert response.schema_updated
        assert not response.errors

        registry.schema.set_schema_branch(name=BRANCH_NAME, schema=stale_schema)
        fresh_branch = await Branch.get_by_name(db=db, name=BRANCH_NAME)
        await registry.schema.load_schema(db=db, branch=fresh_branch)

        refreshed = registry.schema.get_schema_branch(name=BRANCH_NAME)
        assert GADGET_KIND not in refreshed.node_names
        assert f"Template{GADGET_KIND}" not in refreshed.template_names
        assert f"Profile{GADGET_KIND}" not in refreshed.profile_names
        assert WIDGET_KIND in refreshed.node_names
