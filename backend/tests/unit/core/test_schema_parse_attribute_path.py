import pytest

from infrahub.core import registry
from infrahub.core.schema import AttributePathParsingError, SchemaAttributePath


class TestSchemaParseAttributePath:
    async def test_property_only_is_invalid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"value is invalid on schema"):
            await car_schema.parse_attribute_path("value")

    @pytest.mark.parametrize("bad_path", ["blork", "person", "__", "__dunder__"])
    async def test_invalid_paths(self, car_person_schema, bad_path):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=rf"{bad_path} is invalid on schema"):
            await car_schema.parse_attribute_path(bad_path)

    async def test_invalid_attribute_of_relationship_path(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid attribute of TestPerson"):
            await car_schema.parse_attribute_path("owner__blork")

    async def test_invalid_property_of_attribute_path(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        with pytest.raises(AttributePathParsingError, match=r"blork is not a valid property of nbr_seats"):
            await car_schema.parse_attribute_path("nbr_seats__blork")

    async def test_attribute_only_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = await car_schema.parse_attribute_path("nbr_seats")

        assert schema_path == SchemaAttributePath(attribute_schema=car_schema.get_attribute("nbr_seats"))

    async def test_relationship_only_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = await car_schema.parse_attribute_path("owner")

        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=registry.schema.get(name="TestPerson"),
        )

    async def test_relationship_and_attribute_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = await car_schema.parse_attribute_path("owner__name")

        owner_schema = registry.schema.get(name="TestPerson")
        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
        )

    async def test_relationship_attribute_and_property_is_valid(self, car_person_schema):
        car_schema = registry.schema.get(name="TestCar")

        schema_path = await car_schema.parse_attribute_path("owner__name__value")

        owner_schema = registry.schema.get(name="TestPerson")
        assert schema_path == SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=owner_schema,
            attribute_schema=owner_schema.get_attribute("name"),
            attribute_property_name="value",
        )
