import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core.branch.models import Branch
from infrahub.core.constants import HashableModelState
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp


class TestTemplateAttributeLifecycle(TestInfrahubApp):
    """Test that schema updates correctly add and remove attributes from existing Template instances."""

    @pytest.fixture(scope="class")
    def person_schema_base(self) -> NodeSchema:
        return NodeSchema(
            name="Person",
            namespace="Lifecycle",
            generate_template=True,
            label="Person",
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                # height is optional so it will appear on templates (support_templates=True)
                AttributeSchema(name="height", kind="Number", optional=True),
                # description is optional so it will appear on templates
                AttributeSchema(name="description", kind="TextArea", optional=True, default_value="placeholder"),
                # eye_color is read_only=True, so support_templates=False initially
                # changing to read_only=False later should ADD it to templates
                AttributeSchema(name="eye_color", kind="Text", optional=True, read_only=True),
                # lifespan is optional, support_templates=True initially
                # changing to read_only=True later should REMOVE it from templates
                AttributeSchema(name="lifespan", kind="Number", optional=True),
                # hobby will be removed from schema later to test attribute removal from templates
                AttributeSchema(name="hobby", kind="Text", optional=True),
            ],
        )

    @pytest.fixture(scope="class")
    async def schema_step_01(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_schema_base: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        schema_root = SchemaRoot(version="1.0", nodes=[person_schema_base])
        await load_schema(db=db, schema=schema_root, branch_name=default_branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def template_1(self, db: InfrahubDatabase, default_branch: Branch, schema_step_01: None) -> Node:
        template = await Node.init(db=db, schema="TemplateLifecyclePerson", branch=default_branch)
        await template.new(
            db=db,
            template_name="person-template-1",
            height=180,
            description="A tall person",
            lifespan=80,
            hobby="reading",
        )
        await template.save(db=db)
        return template

    @pytest.fixture(scope="class")
    async def person_schema_add_attributes(self, person_schema_base: NodeSchema) -> NodeSchema:
        """Schema update that adds attributes to templates:
        - eye_color: read_only=False (was True) -> support_templates becomes True -> ADD to templates
        - new attribute 'weight': optional=True -> support_templates=True -> ADD to templates
        - new attribute 'not_for_templates': read_only=True -> support_templates=False -> NOT added
        """
        updated = person_schema_base.model_copy(deep=True)
        eye_color_attr = updated.get_attribute("eye_color")
        eye_color_attr.read_only = False
        updated.attributes.append(AttributeSchema(name="weight", kind="Number", optional=True))
        updated.attributes.append(AttributeSchema(name="not_for_templates", kind="Text", optional=True, read_only=True))
        return updated

    @pytest.fixture(scope="class")
    async def schema_step_02(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_schema_add_attributes: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        schema_root = SchemaRoot(version="1.0", nodes=[person_schema_add_attributes])
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=default_branch.name)
        assert response.schema_updated
        assert not response.errors

    @pytest.fixture(scope="class")
    async def person_schema_remove_attributes(
        self,
        default_branch: Branch,
        person_schema_add_attributes: NodeSchema,
        client: InfrahubClient,
    ) -> NodeSchema:
        """Schema update that removes attributes from templates:
        - lifespan: read_only=True (was False) -> support_templates becomes False -> REMOVE from templates
        - hobby: state=ABSENT -> attribute removed entirely -> REMOVE from templates
        """
        current_template_schema = await client.schema.get(
            kind="LifecyclePerson", branch=default_branch.name, refresh=True
        )
        current_hobby_attr = current_template_schema.get_attribute("hobby")

        updated = person_schema_add_attributes.model_copy(deep=True)
        lifespan_attr = updated.get_attribute("lifespan")
        lifespan_attr.read_only = True
        hobby_attr = updated.get_attribute("hobby")
        hobby_attr.state = HashableModelState.ABSENT
        hobby_attr.id = current_hobby_attr.id
        return updated

    @pytest.fixture(scope="class")
    async def schema_step_03(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_schema_remove_attributes: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        schema_root = SchemaRoot(version="1.0", nodes=[person_schema_remove_attributes])
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=default_branch.name)
        assert response.schema_updated
        assert not response.errors

    async def test_step_01_initial_template(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schema_step_01: None,
        template_1: Node,
        client: InfrahubClient,
    ) -> None:
        """Verify initial template has the expected attributes."""
        template_schema = await client.schema.get(
            kind="TemplateLifecyclePerson", branch=default_branch.name, refresh=True
        )
        # Template should have attributes where support_templates=True
        # height, description, lifespan, hobby should be present
        # eye_color should NOT (read_only=True)
        assert "height" in template_schema.attribute_names
        assert "description" in template_schema.attribute_names
        assert "lifespan" in template_schema.attribute_names
        assert "hobby" in template_schema.attribute_names
        assert "eye_color" not in template_schema.attribute_names

        retrieved = await client.get(kind="TemplateLifecyclePerson", id=template_1.id)
        assert retrieved.height.value == 180
        assert retrieved.description.value == "A tall person"
        assert retrieved.lifespan.value == 80
        assert retrieved.hobby.value == "reading"
        with pytest.raises(AttributeError):
            _ = retrieved.eye_color

    async def test_step_02_add_attributes_to_template(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schema_step_02: None,
        template_1: Node,
        client: InfrahubClient,
    ) -> None:
        """After schema update, verify attributes were added to existing template.

        - eye_color: read_only changed True->False, so support_templates becomes True -> added
        - weight: new optional attribute -> added with None value
        - not_for_templates: read_only=True -> NOT added
        """
        template_schema = await client.schema.get(
            kind="TemplateLifecyclePerson", branch=default_branch.name, refresh=True
        )
        assert "eye_color" in template_schema.attribute_names
        assert "weight" in template_schema.attribute_names
        assert "not_for_templates" not in template_schema.attribute_names

        retrieved = await client.get(kind="TemplateLifecyclePerson", id=template_1.id)
        # Original values preserved
        assert retrieved.height.value == 180
        assert retrieved.description.value == "A tall person"
        assert retrieved.lifespan.value == 80
        assert retrieved.hobby.value == "reading"
        # Newly added attributes
        assert retrieved.eye_color.value is None
        assert retrieved.weight.value is None
        with pytest.raises(AttributeError):
            _ = retrieved.not_for_templates

    async def test_step_03_set_values_on_new_attributes(
        self,
        default_branch: Branch,
        template_1: Node,
        client: InfrahubClient,
    ) -> None:
        """Update the template to set values on newly added attributes."""
        retrieved = await client.get(kind="TemplateLifecyclePerson", id=template_1.id)
        retrieved.eye_color.value = "green"
        retrieved.weight.value = 75
        await retrieved.save()

        updated = await client.get(kind="TemplateLifecyclePerson", id=template_1.id)
        assert updated.eye_color.value == "green"
        assert updated.weight.value == 75

    async def test_step_04_remove_attributes_from_template(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schema_step_03: None,
        template_1: Node,
        client: InfrahubClient,
    ) -> None:
        """After schema update, verify attributes were removed from existing template.

        - lifespan: read_only changed False->True, so support_templates becomes False -> removed
        - hobby: attribute removed from schema entirely -> removed from template
        """
        template_schema = await client.schema.get(
            kind="TemplateLifecyclePerson", branch=default_branch.name, refresh=True
        )
        assert "lifespan" not in template_schema.attribute_names
        assert "hobby" not in template_schema.attribute_names
        # These should still be present
        assert "height" in template_schema.attribute_names
        assert "description" in template_schema.attribute_names
        assert "eye_color" in template_schema.attribute_names
        assert "weight" in template_schema.attribute_names

        retrieved = await client.get(kind="TemplateLifecyclePerson", id=template_1.id)
        # Preserved attributes
        assert retrieved.height.value == 180
        assert retrieved.description.value == "A tall person"
        assert retrieved.eye_color.value == "green"
        assert retrieved.weight.value == 75
        # Removed attributes
        with pytest.raises(AttributeError):
            _ = retrieved.lifespan
        with pytest.raises(AttributeError):
            _ = retrieved.hobby
