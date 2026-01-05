from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.attribute_parameters import AttributeParameters, TextAttributeParameters
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchNotFoundError
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

THING_KIND = "TestingThing"
PROFILE_THING_KIND = "ProfileTestingThing"
TEMPLATE_THING_KIND = "TemplateTestingThing"


@dataclass
class AttributeIsIndexed:
    kind: str
    uuid: str
    attr_name: str
    is_indexed: bool

    def __hash__(self) -> int:
        return hash((self.kind, self.uuid, self.attr_name, self.is_indexed))


class TestMigrationAttributeKind(TestInfrahubApp):
    @pytest.fixture(params=[True, False])
    async def branch(self, request, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        if request.param:
            return default_branch
        branch_name = "branch-attr-kind-update"
        try:
            return await registry.get_branch(db=db, branch=branch_name)
        except BranchNotFoundError:
            return await create_branch(db=db, branch_name=branch_name)

    async def get_indexed_state_for_attributes(
        self, db: InfrahubDatabase, branch: Branch, kinds: list[str]
    ) -> list[AttributeIsIndexed]:
        branch_filter, branch_params = branch.get_query_filter_path()
        labels_filter = "|".join(kinds)
        query = """
MATCH (n:%(labels_filter)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)
WITH DISTINCT n, attr
CALL (n, attr) {
    MATCH (n)-[r1:HAS_ATTRIBUTE]->(attr:Attribute)-[r2:HAS_VALUE]->(av)
    WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
    WITH av, r1.status = "active" AND r2.status = "active" AS is_active
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status = "active" DESC, r1.branch_level DESC, r1.from DESC, r1.status = "active" DESC
    LIMIT 1
    WITH av
    WHERE is_active
    RETURN av
}
RETURN n.kind AS kind, n.uuid AS uuid, attr.name AS attr_name, "AttributeValueIndexed" IN labels(av) AS is_indexed
        """ % {"labels_filter": labels_filter, "branch_filter": branch_filter}
        results = await db.execute_query(query=query, params=branch_params)
        attr_is_indexeds = []
        for result in results:
            attr_is_indexeds.append(
                AttributeIsIndexed(
                    kind=result.get("kind"),
                    uuid=result.get("uuid"),
                    attr_name=result.get("attr_name"),
                    is_indexed=result.get("is_indexed"),
                )
            )
        return attr_is_indexeds

    async def validate_indexed_state(
        self, db: InfrahubDatabase, branch: Branch, kind_index_map: dict[tuple[str, str], dict[str, bool]]
    ) -> None:
        kinds = {kind_and_uuid[0] for kind_and_uuid in kind_index_map.keys()}
        num_expected_results = sum(len(attr_map) for attr_map in kind_index_map.values())
        attr_is_indexeds = await self.get_indexed_state_for_attributes(db=db, branch=branch, kinds=list(kinds))
        assert len(attr_is_indexeds) == num_expected_results
        for attr_is_indexed in attr_is_indexeds:
            kind_and_uuid = (attr_is_indexed.kind, attr_is_indexed.uuid)
            assert kind_and_uuid in kind_index_map
            assert attr_is_indexed.is_indexed == kind_index_map[kind_and_uuid][attr_is_indexed.attr_name]

    @pytest.fixture(scope="class")
    def schema_thing(self) -> dict[str, Any]:
        return {
            "name": "Thing",
            "namespace": "Testing",
            "generate_template": True,
            "generate_profile": True,
            "attributes": [
                {"name": "text_value", "kind": "Text", "optional": True},
                {"name": "text_area_value", "kind": "TextArea", "optional": True},
                {"name": "list_value", "kind": "List", "optional": True},
                {"name": "url_value", "kind": "URL", "optional": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step_01(
        self,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing],
        }

    @pytest.fixture(scope="class")
    def schema_thing_illegal_updates(self, schema_thing: dict[str, Any]) -> dict[str, Any]:
        updated_schema = deepcopy(schema_thing)
        updated_schema["attributes"][0]["kind"] = "JSON"
        updated_schema["attributes"][1]["kind"] = "List"
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_step_02(
        self,
        schema_thing_illegal_updates,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_illegal_updates],
        }

    @pytest.fixture(scope="class")
    def schema_thing_text_to_text_area(self, schema_thing: dict[str, Any]) -> dict[str, Any]:
        updated_schema = deepcopy(schema_thing)
        updated_schema["attributes"][0]["kind"] = "TextArea"
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_step_03(
        self,
        schema_thing_text_to_text_area,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_text_to_text_area],
        }

    @pytest.fixture(scope="class")
    def schema_thing_text_area_to_text(self, schema_thing_text_to_text_area: dict[str, Any]) -> dict[str, Any]:
        updated_schema = deepcopy(schema_thing_text_to_text_area)
        updated_schema["attributes"][1]["kind"] = "Text"
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_step_04(
        self,
        schema_thing_text_area_to_text,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_text_area_to_text],
        }

    @pytest.fixture(scope="class")
    def schema_thing_url_to_text(self, schema_thing_text_area_to_text: dict[str, Any]) -> dict[str, Any]:
        updated_schema = deepcopy(schema_thing_text_area_to_text)
        updated_schema["attributes"][3]["kind"] = "Text"
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_step_05(
        self,
        schema_thing_url_to_text,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_url_to_text],
        }

    @pytest.fixture(scope="class")
    def schema_thing_text_area_revert(self, schema_thing_url_to_text: dict[str, Any]) -> dict[str, Any]:
        updated_schema = deepcopy(schema_thing_url_to_text)
        updated_schema["attributes"][1]["kind"] = "TextArea"
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_step_06(
        self,
        schema_thing_text_area_revert,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_text_area_revert],
        }

    @pytest.fixture(scope="class")
    async def initial_objects(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initialize_registry,
        schema_step_01,
    ) -> dict[str, Node]:
        await load_schema(db=db, schema=schema_step_01)

        thing_one = await Node.init(schema=THING_KIND, db=db)
        await thing_one.new(
            db=db,
            text_value="ONE",
            text_area_value="a" * 5000,
            list_value=["a", "b"],
            url_value="https://infrahub.com",
        )
        await thing_one.save(db=db)

        thing_two = await Node.init(schema=THING_KIND, db=db)
        await thing_two.new(
            db=db,
            text_value="TWO",
            text_area_value="longer TWO",
            list_value=["c", "d"],
            url_value="https://opsmill.com",
        )
        await thing_two.save(db=db)

        profile_thing = await Node.init(db=db, schema=PROFILE_THING_KIND, branch=default_branch)
        await profile_thing.new(
            db=db,
            profile_name="test_profile",
            text_value="PROFILE_TEXT",
            text_area_value="profile area value",
            url_value="https://profile.example.com",
        )
        await profile_thing.save(db=db)

        template_thing = await Node.init(db=db, schema=TEMPLATE_THING_KIND, branch=default_branch)
        await template_thing.new(
            db=db,
            template_name="test_template",
            text_value="TEMPLATE_TEXT",
            text_area_value="template area value",
            url_value="https://template.example.com",
        )
        await template_thing.save(db=db)

        objs = {
            "thing_one": thing_one,
            "thing_two": thing_two,
            "profile_thing": profile_thing,
            "template_thing": template_thing,
        }

        return objs

    async def test_step01_baseline(
        self, db: InfrahubDatabase, initial_objects: dict[str, Node], branch: Branch
    ) -> None:
        object_ids = [obj.id for obj in initial_objects.values()]
        objects = await NodeManager.get_many(db=db, ids=object_ids)
        assert len(objects) == len(object_ids)

        kind_index_map = {
            (THING_KIND, initial_objects["thing_one"].id): {
                "text_value": True,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (THING_KIND, initial_objects["thing_two"].id): {
                "text_value": True,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (PROFILE_THING_KIND, initial_objects["profile_thing"].id): {
                "profile_name": True,
                "profile_priority": True,
                "text_value": True,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (TEMPLATE_THING_KIND, initial_objects["template_thing"].id): {
                "template_name": True,
                "text_value": True,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
        }
        await self.validate_indexed_state(db=db, branch=branch, kind_index_map=kind_index_map)

    async def test_step_02_illegal_kind_updates(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        branch: Branch,
        schema_step_02: dict[str, Any],
        client: InfrahubClient,
    ) -> None:
        response = await client.schema.load(schemas=[schema_step_02], branch=branch.name)
        assert response.errors
        error_messages: list[str] = response.errors["errors"][0]["message"].split("\n")
        assert len(error_messages) == 8
        assert all(
            em.startswith(
                (
                    ("Attribute-level 'kind' constraint violation on schema 'TestingThing"),
                    ("Attribute-level 'kind' constraint violation on schema 'ProfileTestingThing"),
                    ("Attribute-level 'kind' constraint violation on schema 'TemplateTestingThing"),
                )
            )
            for em in error_messages
        )

    async def test_step_03_text_to_text_area_update(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        branch: Branch,
        schema_step_03: dict[str, Any],
        client: InfrahubClient,
    ) -> None:
        response = await client.schema.load(schemas=[schema_step_03], branch=branch.name)
        assert not response.errors

        # Validate corresponding profile schema attribute has the correct kind and parameters
        profile_schema = registry.schema.get(name=PROFILE_THING_KIND, branch=branch)
        updated_profile_attr = profile_schema.get_attribute("text_value")
        assert updated_profile_attr.kind == "TextArea"
        assert isinstance(updated_profile_attr.parameters, TextAttributeParameters)

        # Validate corresponding template schema attribute has the correct kind and parameters
        template_schema = registry.schema.get(name=TEMPLATE_THING_KIND, branch=branch)
        updated_template_attr = template_schema.get_attribute("text_value")
        assert updated_template_attr.kind == "TextArea"
        assert isinstance(updated_template_attr.parameters, TextAttributeParameters)

        kind_index_map = {
            (THING_KIND, initial_objects["thing_one"].id): {
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (THING_KIND, initial_objects["thing_two"].id): {
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Profile instance text_value should now be non-indexed (TextArea)
            (PROFILE_THING_KIND, initial_objects["profile_thing"].id): {
                "profile_name": True,
                "profile_priority": True,
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Template instance text_value should now be non-indexed (TextArea)
            (TEMPLATE_THING_KIND, initial_objects["template_thing"].id): {
                "template_name": True,
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
        }
        await self.validate_indexed_state(db=db, branch=branch, kind_index_map=kind_index_map)

    async def test_step_04_text_area_to_text_update(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        branch: Branch,
        schema_step_04: dict[str, Any],
        client: InfrahubClient,
    ) -> None:
        # first attempt fails because thing_one.text_area_value is too long
        response = await client.schema.load(schemas=[schema_step_04], branch=branch.name)
        assert response.errors
        error_messages = response.errors["errors"][0]["message"].split("\n")
        assert len(error_messages) == 1
        error_message = error_messages[0]
        thing_one_id = initial_objects["thing_one"].id
        assert error_message.startswith("Attribute-level 'kind' constraint violation on schema 'TestingThing")
        assert f"Node (TestingThing(ID: {thing_one_id})) is not compliant." in error_message

        thing_one = await NodeManager.get_one(db=db, branch=branch, id=initial_objects["thing_one"].id)
        thing_one.text_area_value.value = "longer ONE"
        await thing_one.save(db=db)

        response = await client.schema.load(schemas=[schema_step_04], branch=branch.name)
        assert not response.errors

        # Validate corresponding profile schema attribute has the correct kind and parameters
        profile_schema = registry.schema.get(name=PROFILE_THING_KIND, branch=branch)
        updated_profile_attr = profile_schema.get_attribute("text_area_value")
        assert updated_profile_attr.kind == "Text"
        assert isinstance(updated_profile_attr.parameters, TextAttributeParameters)

        # Validate corresponding template schema attribute has the correct kind and parameters
        template_schema = registry.schema.get(name=TEMPLATE_THING_KIND, branch=branch)
        updated_template_attr = template_schema.get_attribute("text_area_value")
        assert updated_template_attr.kind == "Text"
        assert isinstance(updated_template_attr.parameters, TextAttributeParameters)

        kind_index_map = {
            (THING_KIND, initial_objects["thing_one"].id): {
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (THING_KIND, initial_objects["thing_two"].id): {
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Profile instance text_area_value should now be indexed (Text)
            (PROFILE_THING_KIND, initial_objects["profile_thing"].id): {
                "profile_name": True,
                "profile_priority": True,
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Template instance text_area_value should now be indexed (Text)
            (TEMPLATE_THING_KIND, initial_objects["template_thing"].id): {
                "template_name": True,
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
        }
        await self.validate_indexed_state(db=db, branch=branch, kind_index_map=kind_index_map)

    async def test_step_05_url_to_text_update(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        branch: Branch,
        schema_step_05: dict[str, Any],
        client: InfrahubClient,
    ) -> None:
        # First verify the url_value attribute has base AttributeParameters before the update
        profile_schema_before = registry.schema.get(name=PROFILE_THING_KIND, branch=branch)
        url_attr_before = profile_schema_before.get_attribute("url_value")
        assert url_attr_before.kind == "URL"
        assert type(url_attr_before.parameters) is AttributeParameters

        template_schema_before = registry.schema.get(name=TEMPLATE_THING_KIND, branch=branch)
        template_url_attr_before = template_schema_before.get_attribute("url_value")
        assert template_url_attr_before.kind == "URL"
        assert type(template_url_attr_before.parameters) is AttributeParameters

        response = await client.schema.load(schemas=[schema_step_05], branch=branch.name)
        assert not response.errors

        # Validate corresponding profile schema attribute has the correct kind and parameters
        profile_schema = registry.schema.get(name=PROFILE_THING_KIND, branch=branch)
        updated_profile_attr = profile_schema.get_attribute("url_value")
        assert updated_profile_attr.kind == "Text"
        assert isinstance(updated_profile_attr.parameters, TextAttributeParameters)

        # Validate corresponding template schema attribute has the correct kind and parameters
        template_schema = registry.schema.get(name=TEMPLATE_THING_KIND, branch=branch)
        updated_template_attr = template_schema.get_attribute("url_value")
        assert updated_template_attr.kind == "Text"
        assert isinstance(updated_template_attr.parameters, TextAttributeParameters)

        kind_index_map = {
            (THING_KIND, initial_objects["thing_one"].id): {
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (THING_KIND, initial_objects["thing_two"].id): {
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Profile instance url_value stays indexed (Text is also indexed)
            (PROFILE_THING_KIND, initial_objects["profile_thing"].id): {
                "profile_name": True,
                "profile_priority": True,
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Template instance url_value stays indexed (Text is also indexed)
            (TEMPLATE_THING_KIND, initial_objects["template_thing"].id): {
                "template_name": True,
                "text_value": False,
                "text_area_value": True,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
        }
        await self.validate_indexed_state(db=db, branch=branch, kind_index_map=kind_index_map)

    async def test_step_06_text_area_revert(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        branch: Branch,
        schema_step_06: dict[str, Any],
        client: InfrahubClient,
    ) -> None:
        response = await client.schema.load(schemas=[schema_step_06], branch=branch.name)
        assert not response.errors

        # Validate corresponding profile schema attribute has the correct kind and parameters
        profile_schema = registry.schema.get(name=PROFILE_THING_KIND, branch=branch)
        updated_profile_attr = profile_schema.get_attribute("text_area_value")
        assert updated_profile_attr.kind == "TextArea"
        assert isinstance(updated_profile_attr.parameters, TextAttributeParameters)

        # Validate corresponding template schema attribute has the correct kind and parameters
        template_schema = registry.schema.get(name=TEMPLATE_THING_KIND, branch=branch)
        updated_template_attr = template_schema.get_attribute("text_area_value")
        assert updated_template_attr.kind == "TextArea"
        assert isinstance(updated_template_attr.parameters, TextAttributeParameters)

        kind_index_map = {
            (THING_KIND, initial_objects["thing_one"].id): {
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            (THING_KIND, initial_objects["thing_two"].id): {
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Profile instance text_area_value should now be non-indexed (TextArea)
            (PROFILE_THING_KIND, initial_objects["profile_thing"].id): {
                "profile_name": True,
                "profile_priority": True,
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
            # Template instance text_area_value should now be non-indexed (TextArea)
            (TEMPLATE_THING_KIND, initial_objects["template_thing"].id): {
                "template_name": True,
                "text_value": False,
                "text_area_value": False,
                "list_value": False,
                "url_value": True,
                "display_label": True,
                "human_friendly_id": True,
            },
        }
        await self.validate_indexed_state(db=db, branch=branch, kind_index_map=kind_index_map)
