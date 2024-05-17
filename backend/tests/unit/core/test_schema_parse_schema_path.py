import pytest

from infrahub.core import registry
from infrahub.core.schema import AttributePathParsingError, SchemaAttributePath
from infrahub.core.schema_manager import SchemaBranch


class TestSchemaParseSchemaPath:
    def test_property_only_is_invalid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"value is invalid on schema"):
            car_schema.parse_schema_path(path="value")

    @pytest.mark.parametrize("bad_path", ["blork", "person", "__", "__dunder__"])
    def test_invalid_paths(self, car_person_schema, bad_path):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=rf"{bad_path} is invalid on schema"):
            car_schema.parse_schema_path(path=bad_path)

    def test_invalid_attribute_of_relationship_path(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid attribute of TestPerson"):
            car_schema.parse_schema_path(path="owner__blork", schema=car_person_schema)

    def test_invalid_property_of_attribute_path(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid property of nbr_seats"):
            car_schema.parse_schema_path(path="nbr_seats__blork")

    def test_invalid_path_with_map_override(self, car_person_schema: SchemaBranch):
        car_schema = car_person_schema.get("TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid attribute of TestPerson"):
            car_schema.parse_schema_path(path="owner__blork", schema=car_person_schema)

    def test_attribute_only_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_schema_path(path="nbr_seats")

        assert schema_path == SchemaAttributePath(attribute_schema=car_schema.get_attribute("nbr_seats"))

    def test_relationship_only_is_valid(self, car_person_schema: SchemaBranch):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_schema_path(path="owner", schema=car_person_schema)

        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=registry.schema.get(name="TestPerson"),
        )

    def test_relationship_and_attribute_is_valid(self, car_person_schema: SchemaBranch):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_schema_path(path="owner__name", schema=car_person_schema)

        owner_schema = registry.schema.get(name="TestPerson")
        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
        )

    def test_relationship_attribute_and_property_is_valid(self, car_person_schema: SchemaBranch):
        car_schema = car_person_schema.get("TestCar")
        owner_schema = car_person_schema.get("TestPerson")

        schema_path = car_schema.parse_schema_path(path="owner__name__value", schema=car_person_schema)

        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
            attribute_property_name="value",
        )
