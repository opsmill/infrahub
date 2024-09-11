from infrahub_sdk import InfrahubClient

from .shared import (
    TestSchemaLifecycleBase,
)


class TestSchemaMissingMenuPlacement(TestSchemaLifecycleBase):
    async def test_schema_missing_menu_placement(self, client: InfrahubClient):
        schema = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "BNode",
                    "namespace": "Infra",
                    "menu_placement": "UnexistingNode",
                    "label": "BNode",
                    "display_labels": ["name__value"],
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                }
            ],
        }

        response = await client.schema.load(schemas=[schema], branch="main")
        assert response.schema_updated is False
        assert response.errors["errors"][0]["extensions"]["code"] == 422
        assert (
            response.errors["errors"][0]["message"]
            == "InfraBNode refers an unexisting menu placement node: UnexistingNode."
        )
