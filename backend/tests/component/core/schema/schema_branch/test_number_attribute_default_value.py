import pytest

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.test_app import TestInfrahubApp


class TestNumberAttrForbidsBool(TestInfrahubApp):
    async def test_number_attr_forbids_bool(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
    ) -> None:
        schema = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Node",
                    "namespace": "Testing",
                    "attributes": [{"name": "number", "kind": "Number", "default_value": True, "optional": False}],
                }
            ],
        }

        schema_root = SchemaRoot(**schema)  # type: ignore
        schema_branch = registry.schema.get_schema_branch(default_branch.name)
        schema_branch.load_schema(schema=schema_root)
        with pytest.raises(ValidationError, match="TestingNode: default value True is not a valid Number"):
            schema_branch.process()
