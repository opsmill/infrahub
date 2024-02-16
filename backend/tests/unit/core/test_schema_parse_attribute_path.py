import pytest

from infrahub.core import registry
from infrahub.core.schema import AttributePathParsingError, SchemaAttributePath


class TestSchemaParseAttributePath:
    def test_property_only_is_invalid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"value is invalid on schema"):
            car_schema.parse_attribute_path("value")

    @pytest.mark.parametrize("bad_path", ["blork", "person", "__", "__dunder__"])
    def test_invalid_paths(self, car_person_schema, bad_path):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=rf"{bad_path} is invalid on schema"):
            car_schema.parse_attribute_path(bad_path)

    def test_invalid_attribute_of_relationship_path(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid attribute of TestPerson"):
            car_schema.parse_attribute_path("owner__blork")

    def test_invalid_property_of_attribute_path(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid property of nbr_seats"):
            car_schema.parse_attribute_path("nbr_seats__blork")

    def test_invalid_path_with_map_override(self, car_person_schema_unregistered):
        schema_map = {
            sch.kind: sch for sch in car_person_schema_unregistered.nodes + car_person_schema_unregistered.generics
        }
        car_schema = schema_map.get("TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid attribute of TestPerson"):
            car_schema.parse_attribute_path("owner__blork", schema_map_override=schema_map)

    def test_attribute_only_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_attribute_path("nbr_seats")

        assert schema_path == SchemaAttributePath(attribute_schema=car_schema.get_attribute("nbr_seats"))

    def test_relationship_only_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_attribute_path("owner")

        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=registry.schema.get(name="TestPerson"),
        )

    def test_relationship_and_attribute_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_attribute_path("owner__name")

        owner_schema = registry.schema.get(name="TestPerson")
        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
        )

    def test_relationship_attribute_and_property_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = car_schema.parse_attribute_path("owner__name__value")

        owner_schema = registry.schema.get(name="TestPerson")
        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
            attribute_property_name="value",
        )

    def test_relationship_attribute_and_property_is_valid_map_override(self, car_person_schema_unregistered):
        schema_map = {
            sch.kind: sch for sch in car_person_schema_unregistered.nodes + car_person_schema_unregistered.generics
        }
        car_schema = schema_map.get("TestCar")
        owner_schema = schema_map.get("TestPerson")

        schema_path = car_schema.parse_attribute_path("owner__name__value", schema_map_override=schema_map)

        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
            attribute_property_name="value",
        )
