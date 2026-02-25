import copy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from infrahub.exceptions import InitializationError
from tests.integration.profiles.validation import assert_no_virtual_schema_relationships_in_db

from ..shared import load_schema
from .shared import CAR_KIND, MANUFACTURER_KIND_01, PERSON_KIND, TAG_KIND, TestSchemaLifecycleBase

CATEGORY_KIND = "TestingCategory"
TEMPLATE_TAG_KIND = "TemplateTestingTag"
TEMPLATE_CATEGORY_KIND = "TemplateTestingCategory"
PROFILE_TAG_KIND = "ProfileTestingTag"


class BranchState:
    def __init__(self) -> None:
        self._branch: Branch | None = None

    @property
    def branch(self) -> Branch:
        if self._branch:
            return self._branch
        raise InitializationError

    @branch.setter
    def branch(self, value: Branch) -> None:
        self._branch = value


state = BranchState()


class TestSchemaLifecycleRelRemoveDefaultBranchTemplateProfile(TestSchemaLifecycleBase):
    """Remove relationships from a schema with generate_template=True and generate_profile=True
    on the default branch, then rebase a user branch, and confirm Template/Profile schemas
    and instances are correctly updated.

    Flow: load schema → create branch → create data on branch → remove rels on main → rebase → verify

    Removes both a Generic relationship (persons) that affects the Profile schema and a Component
    relationship (categories) that affects the Template schema. Verifies that:
    - Template instance linked to a sub-template instance (via categories) loses that relationship
    - Template instance linked to a regular node instance (via related_nodes) keeps that link
    - Profile instance loses the removed Generic relationship
    """

    @property
    def branch1(self) -> Branch:
        return state.branch

    @pytest.fixture(scope="class")
    def schema_category_base(self) -> dict[str, Any]:
        return {
            "name": "Category",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Testing Category",
            "generate_template": True,
            "attributes": [{"name": "name", "kind": "Text"}],
        }

    @pytest.fixture(scope="class")
    def schema_tag_base(self) -> dict[str, Any]:
        return {
            "name": "Tag",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Testing Tag",
            "generate_template": True,
            "generate_profile": True,
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": "TestingCar", "cardinality": "many"},
                {
                    "name": "persons",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingPerson",
                    "cardinality": "many",
                },
                {
                    "name": "categories",
                    "kind": "Component",
                    "optional": True,
                    "peer": "TestingCategory",
                    "cardinality": "many",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step01(
        self,
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
        schema_tag_base: dict[str, Any],
        schema_category_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_base,
                schema_car_base,
                schema_manufacturer_base,
                schema_tag_base,
                schema_category_base,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_tag_rels_removed(self, schema_tag_base: dict[str, Any]) -> dict[str, Any]:
        schema = copy.deepcopy(schema_tag_base)
        for rel in schema["relationships"]:
            if rel["name"] in ("persons", "categories"):
                rel["state"] = "absent"
        return schema

    @pytest.fixture(scope="class")
    def schema_main_rels_removed(
        self,
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
        schema_tag_rels_removed: dict[str, Any],
        schema_category_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_base,
                schema_car_base,
                schema_manufacturer_base,
                schema_tag_rels_removed,
                schema_category_base,
            ],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step01)

        # Create base entities on MAIN (visible to the branch)
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous John Doe")
        await john.save(db=db)

        renault = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await renault.new(db=db, name="renault", description="French manufacturer")
        await renault.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(
            db=db, name="Megane", description="Renault Megane", color="#c93420", manufacturer=renault, owner=john
        )
        await megane.save(db=db)

        electronics = await Node.init(schema=CATEGORY_KIND, db=db)
        await electronics.new(db=db, name="electronics")
        await electronics.save(db=db)

        # Create branch before adding Tag/Template/Profile data
        branch1 = await create_branch(db=db, branch_name="branch_tp")
        state.branch = branch1

        # Create Tag, Template, and Profile instances on the BRANCH
        red = await Node.init(schema=TAG_KIND, db=db, branch=branch1)
        await red.new(db=db, name="red", cars=[megane], persons=[john], categories=[electronics])
        await red.save(db=db)

        # Create sub-template: TemplateTestingCategory instance on the branch
        template_category_schema = registry.schema.get_template_schema(
            name=TEMPLATE_CATEGORY_KIND, branch=branch1, duplicate=False
        )
        template_category = await Node.init(db=db, schema=template_category_schema, branch=branch1)
        await template_category.new(db=db, template_name="cat_template", name="template_cat")
        await template_category.save(db=db)

        # Create TemplateTestingTag instance linked to sub-template via categories
        template_tag_schema = registry.schema.get_template_schema(
            name=TEMPLATE_TAG_KIND, branch=branch1, duplicate=False
        )
        tag_template = await Node.init(db=db, schema=template_tag_schema, branch=branch1)
        await tag_template.new(db=db, template_name="tag_template", name="template_tag", categories=[template_category])
        await tag_template.save(db=db)

        # Create a Tag from the template to establish related_nodes link
        tag_from_template = await Node.init(schema=TAG_KIND, db=db, branch=branch1)
        await tag_from_template.new(
            db=db,
            name="from_template",
            cars=[megane],
            persons=[john],
            categories=[electronics],
            object_template={"id": tag_template.id},
        )
        await tag_from_template.save(db=db)

        # Create Profile instance for Tag with persons relationship set
        profile_schema = registry.schema.get_profile_schema(name=PROFILE_TAG_KIND, branch=branch1, duplicate=False)
        tag_profile = await Node.init(db=db, schema=profile_schema, branch=branch1)
        await tag_profile.new(db=db, profile_name="tag_profile", persons=[john])
        await tag_profile.save(db=db)

        return {
            "john": john.id,
            "renault": renault.id,
            "megane": megane.id,
            "electronics": electronics.id,
            "red": red.id,
            "tag_from_template": tag_from_template.id,
            "tag_template": tag_template.id,
            "template_category": template_category.id,
            "tag_profile": tag_profile.id,
        }

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        """Verify baseline schemas and instances on the branch."""
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND, branch=self.branch1)
        assert "persons" in tag_schema.relationship_names
        assert "categories" in tag_schema.relationship_names

        profile_schema = registry.schema.get_profile_schema(name=PROFILE_TAG_KIND, branch=self.branch1)
        assert "persons" in profile_schema.relationship_names

        template_schema = registry.schema.get_template_schema(name=TEMPLATE_TAG_KIND, branch=self.branch1)
        assert template_schema is not None
        assert "categories" in template_schema.relationship_names

        # Verify Tag instance has persons and categories
        red = await registry.manager.get_one(db=db, id=initial_dataset["red"], branch=self.branch1)
        persons = await red.persons.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(persons) == 1
        categories = await red.categories.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(categories) == 1

        # Verify Template instance linked to sub-template (via categories)
        tag_template = await registry.manager.get_one(db=db, id=initial_dataset["tag_template"], branch=self.branch1)
        category_peers = await tag_template.categories.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(category_peers) == 1
        category_ids = {peer.id for peer in category_peers.values()}
        assert initial_dataset["template_category"] in category_ids

        # Verify Template instance linked to regular node (via related_nodes)
        related = await tag_template.related_nodes.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(related) == 1
        related_ids = {peer.id for peer in related.values()}
        assert initial_dataset["tag_from_template"] in related_ids

        # Verify node created from template has object_template set
        tag_from_template = await registry.manager.get_one(
            db=db, id=initial_dataset["tag_from_template"], branch=self.branch1
        )
        obj_template = await tag_from_template.object_template.get_peer(db=db)  # type: ignore[attr-defined]
        assert obj_template is not None
        assert obj_template.id == initial_dataset["tag_template"]

        # Verify Profile instance has persons
        tag_profile = await registry.manager.get_one(db=db, id=initial_dataset["tag_profile"], branch=self.branch1)
        persons = await tag_profile.persons.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(persons) == 1

    async def test_step02_remove_rels_on_main(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_main_rels_removed: dict[str, Any],
    ) -> None:
        """Remove persons (Generic) and categories (Component) from Tag on the default branch."""
        response = await client.schema.load(schemas=[schema_main_rels_removed])
        assert not response.errors

        # Tag schema on main: persons and categories removed
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND)
        assert "persons" not in tag_schema.relationship_names
        assert "categories" not in tag_schema.relationship_names
        assert "cars" in tag_schema.relationship_names

        # Profile schema on main: persons removed (Generic relationships support profiles)
        profile_schema = registry.schema.get_profile_schema(name=PROFILE_TAG_KIND)
        assert "persons" not in profile_schema.relationship_names

        # Template schema on main: categories removed (Component relationships are on templates)
        template_schema = registry.schema.get_template_schema(name=TEMPLATE_TAG_KIND)
        assert "categories" not in template_schema.relationship_names
        assert "related_nodes" in template_schema.relationship_names

        # Branch still has old schema
        tag_schema_branch = registry.schema.get_node_schema(name=TAG_KIND, branch=self.branch1)
        assert "persons" in tag_schema_branch.relationship_names
        assert "categories" in tag_schema_branch.relationship_names

    async def test_step03_rebase_and_verify(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset: dict[str, str]
    ) -> None:
        """Rebase the branch and verify all schemas and instances are correctly updated."""
        branch = await client.branch.rebase(branch_name=self.branch1.name)
        assert branch

        # --- Schema checks on branch ---

        # Tag schema: persons and categories removed
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND, branch=self.branch1)
        assert "persons" not in tag_schema.relationship_names
        assert "categories" not in tag_schema.relationship_names
        assert "cars" in tag_schema.relationship_names

        # Profile schema: persons removed
        profile_schema = registry.schema.get_profile_schema(name=PROFILE_TAG_KIND, branch=self.branch1)
        assert "persons" not in profile_schema.relationship_names

        # Template schema: categories removed, related_nodes and attributes still present
        template_schema = registry.schema.get_template_schema(name=TEMPLATE_TAG_KIND, branch=self.branch1)
        assert "categories" not in template_schema.relationship_names
        assert "related_nodes" in template_schema.relationship_names
        assert "template_name" in template_schema.attribute_names
        assert "name" in template_schema.attribute_names

        # Category template still exists
        template_category_schema = registry.schema.get_template_schema(name=TEMPLATE_CATEGORY_KIND, branch=self.branch1)
        assert template_category_schema is not None

        # --- Instance checks on branch ---

        # Tag instance: persons and categories no longer exposed, cars still works
        red = await registry.manager.get_one(db=db, id=initial_dataset["red"], branch=self.branch1)
        assert red is not None
        with pytest.raises(ValueError, match="persons"):
            red.get_relationship("persons")
        with pytest.raises(ValueError, match="categories"):
            red.get_relationship("categories")
        cars = await red.cars.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(cars) == 1

        # Node created from template: still accessible
        tag_from_template = await registry.manager.get_one(
            db=db, id=initial_dataset["tag_from_template"], branch=self.branch1
        )
        assert tag_from_template is not None
        with pytest.raises(ValueError, match="persons"):
            tag_from_template.get_relationship("persons")
        with pytest.raises(ValueError, match="categories"):
            tag_from_template.get_relationship("categories")

        # Template instance: accessible, categories removed, related_nodes still links to node
        tag_template = await registry.manager.get_one(db=db, id=initial_dataset["tag_template"], branch=self.branch1)
        assert tag_template is not None
        with pytest.raises(ValueError, match="categories"):
            tag_template.get_relationship("categories")
        related = await tag_template.related_nodes.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(related) == 1
        related_ids = {peer.id for peer in related.values()}
        assert initial_dataset["tag_from_template"] in related_ids

        # Category template instance: still accessible
        template_category = await registry.manager.get_one(
            db=db, id=initial_dataset["template_category"], branch=self.branch1
        )
        assert template_category is not None

        # Profile instance: accessible, persons no longer exposed
        tag_profile = await registry.manager.get_one(db=db, id=initial_dataset["tag_profile"], branch=self.branch1)
        assert tag_profile is not None
        with pytest.raises(ValueError, match="persons"):
            tag_profile.get_relationship("persons")

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
        await assert_no_virtual_schema_relationships_in_db(db=db)
