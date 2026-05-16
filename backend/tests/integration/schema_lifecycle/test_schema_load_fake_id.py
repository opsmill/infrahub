"""Loading a schema with a fabricated ``id`` must always be rejected without mutating the
database — both when the ``(namespace, name)`` is previously unknown and when it already
exists on the branch.
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


def _widget_schema(name: str, fake_id: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {
        "name": name,
        "namespace": "Faketest",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "color", "kind": "Text", "optional": True},
        ],
    }
    if fake_id is not None:
        node["id"] = fake_id
    return {"version": "1.0", "nodes": [node]}


class TestSchemaLoadWithFakeId(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def reload_fake_id(self) -> str:
        return str(uuid.uuid4())

    @pytest.fixture(scope="class")
    async def pre_existing_widget_id(self, client: InfrahubClient, db: InfrahubDatabase) -> str:
        """Load ``FaketestRepeatWidget`` with the normal id-less flow and return its DB-assigned uuid."""
        response = await client.schema.load(schemas=[_widget_schema(name="RepeatWidget")])
        assert not response.errors
        rows = await NodeManager.query(
            db=db,
            schema="SchemaNode",
            filters={"name__value": "RepeatWidget", "namespace__value": "Faketest"},
        )
        assert len(rows) == 1
        return rows[0].id

    async def test_reload_with_fake_id_for_existing_schema_is_rejected(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        pre_existing_widget_id: str,
        reload_fake_id: str,
    ) -> None:
        """Re-loading an existing ``(namespace, name)`` with a fabricated id is rejected; the
        existing DB row keeps its original uuid."""
        response = await client.schema.load(schemas=[_widget_schema(name="RepeatWidget", fake_id=reload_fake_id)])
        assert response.errors

        rows = await NodeManager.query(
            db=db,
            schema="SchemaNode",
            filters={"name__value": "RepeatWidget", "namespace__value": "Faketest"},
        )
        assert len(rows) == 1
        assert rows[0].id == pre_existing_widget_id
