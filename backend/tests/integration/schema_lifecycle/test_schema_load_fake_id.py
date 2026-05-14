"""Loading a schema with a fabricated ``id`` for an already-existing ``(namespace, name)`` must
not insert a duplicate ``SchemaNode`` row — dedup is by ``(namespace, name)``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.manager import NodeManager
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestSchemaLoadWithFakeId(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def widget_schema(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Widget",
                    "namespace": "Faketest",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "color", "kind": "Text", "optional": True},
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    def widget_schema_with_fake_id(self, widget_schema: dict[str, Any]) -> dict[str, Any]:
        widget_node = {**widget_schema["nodes"][0], "id": str(uuid.uuid4())}
        return {"version": "1.0", "nodes": [widget_node]}

    async def test_step_01_load_initial(self, client: InfrahubClient, widget_schema: dict[str, Any]) -> None:
        response = await client.schema.load(schemas=[widget_schema])
        assert not response.errors

    async def test_step_02_only_one_db_row_after_initial_load(self, db: InfrahubDatabase) -> None:
        schema_nodes = await NodeManager.query(db=db, schema="SchemaNode", filters={"name__value": "Widget"})
        assert len(schema_nodes) == 1

    async def test_step_03_load_with_fake_id(
        self, client: InfrahubClient, widget_schema_with_fake_id: dict[str, Any]
    ) -> None:
        """Re-loading the same ``(namespace, name)`` with a fabricated ``id`` must be rejected:
        the load returns an error rather than silently mutating state, and DB rows are unchanged
        (asserted in ``test_step_04``)."""
        response = await client.schema.load(schemas=[widget_schema_with_fake_id])
        assert response.errors
        assert "Unable to find the Schema associated with" in str(response.errors)

    async def test_step_04_still_only_one_db_row(self, db: InfrahubDatabase) -> None:
        rows = await NodeManager.query(db=db, schema="SchemaNode", filters={"name__value": "Widget"})
        widget_rows = [r for r in rows if r.namespace.value == "Faketest"]
        assert len(widget_rows) == 1
