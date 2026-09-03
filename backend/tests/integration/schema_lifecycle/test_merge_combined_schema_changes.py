"""One merge carrying every kind of schema divergence at once, refused first and then accepted.

Each concern has its own single-purpose component test; this scenario checks that they hold together
when one merge has to deal with all of them: a regex the destination tightened, an attribute the
branch made unique, a rename on each side, a kind renamed on the branch and one removed on the
destination, and two properties of one element changed one per side.

Resolved conflicts are deliberately absent: a direct ``BranchMerge`` refuses any conflict, resolved or
not (``graphql/mutations/tasks.py``), since only a proposed change can carry a resolution. The
component tests in ``constraint_validators/test_merge_resolved_schema_conflicts.py`` cover that path.

Phase one asserts the merge is refused with every offender named in a single report and that nothing
moved on either side. Phase two repairs the offending data on the branch, merges, and inspects the
merged schema and data for every concern.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.database.validation import verify_graph

from ..shared import load_schema
from .shared import CAR_KIND, MANUFACTURER_KIND_01, PERSON_KIND, TAG_KIND, TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase

MAKER_KIND = "TestingMaker"
INTERIOR_KIND = "TestingInterior"

PERMISSIVE_NAME_REGEX = r".*"
STRICT_NAME_REGEX = r"^[A-Z][a-z]+$"
ILLEGAL_NAME = "not a valid name"
ACCORD_COLOR = "#3443eb"
REPAIRED_COLOR = "#111111"
TAG_CARS_DESCRIPTION = "Cars carrying this tag"
TAG_CARS_ORDER_WEIGHT = 5000
NOTES_MAX_LENGTH = 100

BRANCH_MERGE_MUTATION = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""


def _attribute(node: dict[str, Any], name: str) -> dict[str, Any]:
    return next(attribute for attribute in node["attributes"] if attribute["name"] == name)


def _relationship(node: dict[str, Any], name: str) -> dict[str, Any]:
    return next(relationship for relationship in node["relationships"] if relationship["name"] == name)


def _root(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"version": "1.0", "nodes": list(nodes)}


class TestMergeCombinedSchemaChanges(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def base_nodes(
        self,
        schema_person_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
        schema_tag_base: dict[str, Any],
        schema_interior_base: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Deep copies of the shared base kinds as they stand at the fork; every load below copies again."""
        person = copy.deepcopy(schema_person_base)
        _attribute(person, "name")["regex"] = PERMISSIVE_NAME_REGEX
        manufacturer = copy.deepcopy(schema_manufacturer_base)
        manufacturer["generate_template"] = True
        return {
            "person": person,
            "car": copy.deepcopy(schema_car_base),
            "manufacturer": manufacturer,
            "tag": copy.deepcopy(schema_tag_base),
            "interior": copy.deepcopy(schema_interior_base),
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, base_nodes: dict[str, dict[str, Any]]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=_root(*(copy.deepcopy(node) for node in base_nodes.values())))

        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        jane = await Node.init(schema=PERSON_KIND, db=db)
        await jane.new(db=db, name="Jane", height=165, description="The famous Jane Doe")
        await jane.save(db=db)
        honda = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await honda.new(db=db, name="honda", description="Honda Motor Co., Ltd")
        await honda.save(db=db)
        renault = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await renault.new(db=db, name="renault", description="Groupe Renault")
        await renault.save(db=db)
        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(
            db=db, name="accord", description="Honda Accord", color=ACCORD_COLOR, manufacturer=honda, owner=jane
        )
        await accord.save(db=db)
        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(db=db, name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=john)
        await civic.save(db=db)
        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(
            db=db, name="Megane", description="Renault Megane", color="#c93420", manufacturer=renault, owner=john
        )
        await megane.save(db=db)
        blue = await Node.init(schema=TAG_KIND, db=db)
        await blue.new(db=db, name="blue", cars=[accord, civic], persons=[jane])
        await blue.save(db=db)
        return {
            "john": john.id,
            "jane": jane.id,
            "honda": honda.id,
            "renault": renault.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
            "blue": blue.id,
        }

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> Branch:
        """Forked only once the base dataset is in place."""
        return await create_branch(db=db, branch_name="combined_schema_changes")

    @pytest.fixture(scope="class")
    def schema_ids(self, branch_2: Branch) -> dict[str, str]:
        """Ids the renames are expressed with; identical on both sides since they were forked together."""
        car = registry.schema.get_node_schema(name=CAR_KIND, branch=branch_2)
        tag = registry.schema.get_node_schema(name=TAG_KIND, branch=branch_2)
        manufacturer = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01, branch=branch_2)
        ids = {
            "manufacturer": manufacturer.id,
            "car_description": car.get_attribute(name="description").id,
            "tag_name": tag.get_attribute(name="name").id,
        }
        assert all(ids.values())
        return {key: str(value) for key, value in ids.items()}

    @pytest.fixture(scope="class")
    async def branch_schema_loaded(
        self,
        client: InfrahubClient,
        branch_2: Branch,
        base_nodes: dict[str, dict[str, Any]],
        schema_ids: dict[str, str],
    ) -> None:
        """Everything the branch changes, in one load.

        Car: ``description`` renamed to ``notes``, ``color`` made unique, manufacturer peer follows the
        rename. Manufacturer: renamed to Maker. Tag: a harmless property on ``cars``. Person is re-sent
        unchanged, which must not register as a change of its own.
        """
        person = copy.deepcopy(base_nodes["person"])

        car = copy.deepcopy(base_nodes["car"])
        description = _attribute(car, "description")
        description["id"] = schema_ids["car_description"]
        description["name"] = "notes"
        _attribute(car, "color")["unique"] = True
        _relationship(car, "manufacturer")["peer"] = MAKER_KIND

        maker = copy.deepcopy(base_nodes["manufacturer"])
        maker["id"] = schema_ids["manufacturer"]
        maker["name"] = "Maker"
        maker["label"] = "Maker"

        tag = copy.deepcopy(base_nodes["tag"])
        _relationship(tag, "cars")["description"] = TAG_CARS_DESCRIPTION

        response = await client.schema.load(schemas=[_root(person, car, maker, tag)], branch=branch_2.name)
        assert not response.errors, response.errors

    @pytest.fixture(scope="class")
    async def main_schema_loaded(
        self,
        client: InfrahubClient,
        branch_schema_loaded: None,
        base_nodes: dict[str, dict[str, Any]],
        schema_ids: dict[str, str],
    ) -> None:
        """Everything main changes after the fork, in one load.

        Person: the name regex tightened. Car: ``description.max_length`` on the attribute the branch
        renamed. Tag: ``name`` renamed to ``label_text``, ``cars.order_weight`` on the relationship the
        branch described. Interior removed.
        """
        person = copy.deepcopy(base_nodes["person"])
        _attribute(person, "name")["regex"] = STRICT_NAME_REGEX

        car = copy.deepcopy(base_nodes["car"])
        _attribute(car, "description")["max_length"] = NOTES_MAX_LENGTH

        tag = copy.deepcopy(base_nodes["tag"])
        name = _attribute(tag, "name")
        name["id"] = schema_ids["tag_name"]
        name["name"] = "label_text"
        _relationship(tag, "cars")["order_weight"] = TAG_CARS_ORDER_WEIGHT

        interior = copy.deepcopy(base_nodes["interior"])
        interior["state"] = "absent"

        manufacturer = copy.deepcopy(base_nodes["manufacturer"])
        response = await client.schema.load(schemas=[_root(person, car, manufacturer, tag, interior)])
        assert not response.errors, response.errors

    @pytest.fixture(scope="class")
    async def data_changed_on_both_sides(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch_2: Branch,
        initial_dataset: dict[str, str],
        main_schema_loaded: None,
    ) -> dict[str, str]:
        """Main recolours a pre-fork car into a duplicate; the branch adds an illegal person and a tag."""
        civic = await NodeManager.get_one(
            db=db, id=initial_dataset["civic"], branch=default_branch, raise_on_error=True
        )
        civic.color.value = ACCORD_COLOR
        await civic.save(db=db)

        offender = await Node.init(schema=PERSON_KIND, db=db, branch=branch_2)
        await offender.new(db=db, name=ILLEGAL_NAME, height=160, description="Offender")
        await offender.save(db=db)
        green = await Node.init(schema=TAG_KIND, db=db, branch=branch_2)
        await green.new(db=db, name="green")
        await green.save(db=db)
        return {"offender": offender.id, "green": green.id}

    async def test_step01_the_merge_is_refused_with_every_offender_named(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        branch_2: Branch,
        initial_dataset: dict[str, str],
        data_changed_on_both_sides: dict[str, str],
    ) -> None:
        branched_from_before = (await Branch.get_by_name(db=db, name=branch_2.name)).branched_from

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch_2.name})

        message = exc.value.message
        # The person the strict regex refuses, and both cars sharing a colour once it is unique.
        assert data_changed_on_both_sides["offender"] in message
        assert initial_dataset["accord"] in message
        assert initial_dataset["civic"] in message
        assert "regex" in message
        assert "'unique'" in message

        persons = await NodeManager.query(db=db, schema=PERSON_KIND, branch=default_branch)
        assert sorted(str(person.name.value) for person in persons) == ["Jane", "John"]
        civic = await NodeManager.get_one(
            db=db, id=initial_dataset["civic"], branch=default_branch, raise_on_error=True
        )
        assert civic.color.value == ACCORD_COLOR, "a refused merge changes nothing on main"
        offender_count = await NodeManager.count(
            db=db, schema=PERSON_KIND, branch=branch_2, filters={"name__value": ILLEGAL_NAME}
        )
        assert offender_count == 1, "a refused merge leaves the offending object on the branch"
        refused_branch = await Branch.get_by_name(db=db, name=branch_2.name)
        assert refused_branch.status == BranchStatus.OPEN.value
        assert refused_branch.branched_from == branched_from_before

    async def test_step02_the_repaired_branch_merges(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        branch_2: Branch,
        initial_dataset: dict[str, str],
        data_changed_on_both_sides: dict[str, str],
    ) -> None:
        offender = await NodeManager.get_one(
            db=db, id=data_changed_on_both_sides["offender"], branch=branch_2, raise_on_error=True
        )
        offender.name.value = "Bob"
        await offender.save(db=db)
        # Main changed civic's colour after the fork, so the branch repairs the *other* duplicate: touching
        # civic here would be a data conflict, and a direct merge carries no resolutions.
        accord = await NodeManager.get_one(db=db, id=initial_dataset["accord"], branch=branch_2, raise_on_error=True)
        accord.color.value = REPAIRED_COLOR
        await accord.save(db=db)

        result = await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch_2.name})
        assert result["BranchMerge"]["ok"]

        merged = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        assert merged.get_hash() == registry.schema.get_schema_branch(name=default_branch.name).get_hash()

        # 1. main's tightened regex survived the merge
        person = merged.get(name=PERSON_KIND)
        name_parameters = person.get_attribute(name="name").parameters
        assert isinstance(name_parameters, TextAttributeParameters)
        assert name_parameters.regex == STRICT_NAME_REGEX

        # 2. the branch made colour unique; 3. renamed description, keeping main's max_length
        car = merged.get(name=CAR_KIND)
        assert car.get_attribute(name="color").unique is True
        assert sorted(attribute.name for attribute in car.attributes) == ["color", "name", "notes"]
        notes_parameters = car.get_attribute(name="notes").parameters
        assert isinstance(notes_parameters, TextAttributeParameters)
        assert notes_parameters.max_length == NOTES_MAX_LENGTH
        # 5. the kind rename, with the peer pointing at the new name and the generated kinds following
        assert car.get_relationship(name="manufacturer").peer == MAKER_KIND
        assert merged.has(name=MAKER_KIND)
        assert merged.has(name=f"Profile{MAKER_KIND}")
        assert merged.has(name=f"Template{MAKER_KIND}")
        for old_name in (MANUFACTURER_KIND_01, f"Profile{MANUFACTURER_KIND_01}", f"Template{MANUFACTURER_KIND_01}"):
            assert not merged.has(name=old_name), old_name

        # 4. two properties of one relationship, one per side; 6. main's rename of the tag attribute
        tag = merged.get(name=TAG_KIND)
        cars = tag.get_relationship(name="cars")
        assert cars.description == TAG_CARS_DESCRIPTION
        assert cars.order_weight == TAG_CARS_ORDER_WEIGHT
        assert [attribute.name for attribute in tag.attributes] == ["label_text"]
        # 7. the kind main removed stays removed
        assert not merged.has(name=INTERIOR_KIND)

    async def test_step03_the_merged_data_matches_the_merged_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        data_changed_on_both_sides: dict[str, str],
    ) -> None:
        persons = await NodeManager.query(db=db, schema=PERSON_KIND, branch=default_branch)
        assert sorted(str(person.name.value) for person in persons) == ["Bob", "Jane", "John"]

        accord = await NodeManager.get_one(
            db=db, id=initial_dataset["accord"], branch=default_branch, raise_on_error=True
        )
        assert accord.color.value == REPAIRED_COLOR
        civic = await NodeManager.get_one(
            db=db, id=initial_dataset["civic"], branch=default_branch, raise_on_error=True
        )
        assert civic.color.value == ACCORD_COLOR, "main's own post-fork edit is kept"
        assert civic.get_attribute("notes").value == "Honda Civic", "the branch's rename reached main's rows"

        makers = await NodeManager.query(db=db, schema=MAKER_KIND, branch=default_branch)
        assert {maker.id for maker in makers} == {initial_dataset["honda"], initial_dataset["renault"]}

        green = await NodeManager.get_one(
            db=db, id=data_changed_on_both_sides["green"], branch=default_branch, raise_on_error=True
        )
        assert green.get_attribute("label_text").value == "green", "main's rename reached the branch's rows"

    async def test_step04_the_graph_is_consistent(self, db: InfrahubDatabase) -> None:
        await verify_graph(db=db)
