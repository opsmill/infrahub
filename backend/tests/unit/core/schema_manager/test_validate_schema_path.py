import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SchemaElementPathType,
)
from infrahub.core.schema import (
    SchemaRoot,
)
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


class TestValidateSchemaPath:
    @pytest.fixture
    async def schema(db: InfrahubDatabase, reset_registry, default_branch: Branch) -> SchemaBranch:
        FULL_SCHEMA = {
            "nodes": [
                {
                    "name": "Criticality",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "label": "Criticality",
                    "attributes": [
                        {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                        {"name": "level", "kind": "Number", "label": "Level"},
                        {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                        {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                    ],
                    "relationships": [
                        {
                            "name": "tags",
                            "peer": "TestTag",
                            "label": "Tags",
                            "optional": True,
                            "cardinality": "many",
                        },
                        {
                            "name": "primary_tag",
                            "peer": "TestTag",
                            "label": "Primary Tag",
                            "identifier": "primary_tag__criticality",
                            "optional": True,
                            "cardinality": "one",
                        },
                    ],
                },
                {
                    "name": "Tag",
                    "namespace": "Test",
                    "label": "Tag",
                    "default_filter": "name__value",
                    "attributes": [
                        {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                        {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                    ],
                },
            ]
        }
        schema = SchemaRoot(**FULL_SCHEMA)
        schema.generate_uuid()
        schema_branch = SchemaBranch(cache={}, name="test")
        schema_branch.load_schema(schema=schema)
        return schema_branch

    def test_attr_only(self, schema: SchemaBranch):
        criticality_schema = schema.get(name="TestCriticality")

        allowed_types = SchemaElementPathType.ATTR
        schema_path = schema.validate_schema_path(
            node_schema=criticality_schema, path="name__value", allowed_path_types=allowed_types
        )
        assert schema_path.is_type_attribute

        with pytest.raises(ValueError) as exc:
            schema.validate_schema_path(node_schema=criticality_schema, path="tags", allowed_path_types=allowed_types)
        assert "only supports attributes" in str(exc.value)

    @pytest.mark.parametrize(
        "path,allowed_types",
        [
            # standalone
            ("primary_tag", SchemaElementPathType.REL_ONE),
            ("primary_tag__name__value", SchemaElementPathType.REL_ONE),
            ("primary_tag__name__value", SchemaElementPathType.REL_ONE_ATTR),
            ("primary_tag", SchemaElementPathType.REL_ONE_NO_ATTR),
            # with another flag (attr)
            ("primary_tag", SchemaElementPathType.REL_ONE | SchemaElementPathType.ATTR),
            ("primary_tag__name__value", SchemaElementPathType.REL_ONE | SchemaElementPathType.ATTR),
            ("primary_tag__name__value", SchemaElementPathType.REL_ONE_ATTR | SchemaElementPathType.ATTR),
            ("primary_tag", SchemaElementPathType.REL_ONE_NO_ATTR | SchemaElementPathType.ATTR),
            # with another flag (rel)
            ("primary_tag", SchemaElementPathType.REL_ONE | SchemaElementPathType.REL_MANY_NO_ATTR),
            ("primary_tag__name__value", SchemaElementPathType.REL_ONE | SchemaElementPathType.REL_MANY_NO_ATTR),
            ("primary_tag__name__value", SchemaElementPathType.REL_ONE_ATTR | SchemaElementPathType.REL_MANY_NO_ATTR),
            ("primary_tag", SchemaElementPathType.REL_ONE_NO_ATTR | SchemaElementPathType.REL_MANY_NO_ATTR),
        ],
    )
    def test_rel_one_valid(self, schema: SchemaBranch, path, allowed_types):
        criticality_schema = schema.get(name="TestCriticality")
        schema_path = schema.validate_schema_path(
            node_schema=criticality_schema, path=path, allowed_path_types=allowed_types
        )
        assert schema_path.is_type_relationship

    def test_rel_one_fail(self, schema: SchemaBranch):
        criticality_schema = schema.get(name="TestCriticality")

        with pytest.raises(ValueError) as exc:
            allowed_types = SchemaElementPathType.REL_ONE_NO_ATTR
            schema.validate_schema_path(
                node_schema=criticality_schema, path="primary_tag__name__value", allowed_path_types=allowed_types
            )
        assert "cannot use attributes of related node" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            allowed_types = SchemaElementPathType.REL_ONE_ATTR
            schema.validate_schema_path(
                node_schema=criticality_schema, path="primary_tag", allowed_path_types=allowed_types
            )
        assert "Must use attributes of related node" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            allowed_types = SchemaElementPathType.REL_ONE
            schema.validate_schema_path(
                node_schema=criticality_schema, path="name__value", allowed_path_types=allowed_types
            )
        assert "this property only supports relationships" in str(exc.value)

    @pytest.mark.parametrize(
        "path,allowed_types",
        [
            # standalone
            ("tags", SchemaElementPathType.REL_MANY),
            ("tags__name__value", SchemaElementPathType.REL_MANY),
            ("tags__name__value", SchemaElementPathType.REL_MANY_ATTR),
            ("tags", SchemaElementPathType.REL_MANY_NO_ATTR),
            # with another flag (attr)
            ("tags", SchemaElementPathType.REL_MANY | SchemaElementPathType.ATTR),
            ("tags__name__value", SchemaElementPathType.REL_MANY | SchemaElementPathType.ATTR),
            ("tags__name__value", SchemaElementPathType.REL_MANY_ATTR | SchemaElementPathType.ATTR),
            ("tags", SchemaElementPathType.REL_MANY_NO_ATTR | SchemaElementPathType.ATTR),
            # with another flag (rel)
            ("tags", SchemaElementPathType.REL_MANY | SchemaElementPathType.REL_ONE_NO_ATTR),
            ("tags__name__value", SchemaElementPathType.REL_MANY | SchemaElementPathType.REL_ONE_NO_ATTR),
            ("tags__name__value", SchemaElementPathType.REL_MANY_ATTR | SchemaElementPathType.REL_ONE_NO_ATTR),
            ("tags", SchemaElementPathType.REL_MANY_NO_ATTR | SchemaElementPathType.REL_ONE_NO_ATTR),
        ],
    )
    def test_rel_many_valid(self, schema: SchemaBranch, path, allowed_types):
        criticality_schema = schema.get(name="TestCriticality")
        schema_path = schema.validate_schema_path(
            node_schema=criticality_schema, path=path, allowed_path_types=allowed_types
        )
        assert schema_path.is_type_relationship

    def test_rel_many_fail(self, schema: SchemaBranch):
        criticality_schema = schema.get(name="TestCriticality")

        with pytest.raises(ValueError) as exc:
            allowed_types = SchemaElementPathType.REL_MANY_NO_ATTR
            schema.validate_schema_path(
                node_schema=criticality_schema, path="tags__name__value", allowed_path_types=allowed_types
            )
        assert "cannot use attributes of related node" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            allowed_types = SchemaElementPathType.REL_MANY_ATTR
            schema.validate_schema_path(node_schema=criticality_schema, path="tags", allowed_path_types=allowed_types)
        assert "Must use attributes of related node" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            allowed_types = SchemaElementPathType.REL_MANY
            schema.validate_schema_path(
                node_schema=criticality_schema, path="name__value", allowed_path_types=allowed_types
            )
        assert "this property only supports relationships" in str(exc.value)
