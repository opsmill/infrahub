from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.registry import registry
from infrahub.database.validation import verify_graph
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestHFIDPathValidation(TestInfrahubApp):
    async def test_rejected_hfid_can_be_corrected_and_schema_updated(
        self, client: InfrahubClient, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        contact_schema: dict[str, Any] = {
            "name": "Contact",
            "namespace": "Testing",
            "human_friendly_id": ["first_name__value__last_name__value"],
            "attributes": [
                {"name": "first_name", "kind": "Text"},
                {"name": "last_name", "kind": "Text"},
                {"name": "telephone_number", "kind": "Text", "optional": True},
            ],
        }
        schema = {"version": "1.0", "nodes": [contact_schema]}

        rejected = await client.schema.load(schemas=[schema])

        assert rejected.errors == {
            "data": None,
            "errors": [
                {
                    "extensions": {"code": 422},
                    "message": (
                        "TestingContact.human_friendly_id: first_name__value__last_name__value "
                        "has too many segments on schema TestingContact"
                    ),
                }
            ],
        }
        persisted = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        assert "TestingContact" not in persisted.node_names

        contact_schema["human_friendly_id"] = ["first_name__value", "last_name__value"]
        loaded = await client.schema.load(schemas=[schema])
        assert not loaded.errors

        contact = await client.create(kind="TestingContact", data={"first_name": "Ada", "last_name": "Lovelace"})
        await contact.save()

        contact_schema["attributes"][2]["state"] = "absent"
        updated = await client.schema.load(schemas=[schema])
        assert not updated.errors

        persisted = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        persisted_contact = persisted.get_node(name="TestingContact")
        assert persisted_contact.human_friendly_id == ["first_name__value", "last_name__value"]
        assert persisted_contact.uniqueness_constraints == [["first_name__value", "last_name__value"]]
        assert "telephone_number" not in persisted_contact.attribute_names

        await client.schema.all(refresh=True)
        reloaded = await client.get(kind="TestingContact", id=contact.id)
        assert reloaded.first_name.value == "Ada"
        assert reloaded.last_name.value == "Lovelace"
        await verify_graph(db=db)
