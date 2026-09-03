"""A schema property changed on main after a branch forked, with the branch changing related data.

Test that schema changes on the destination branch are correctly evaluated against data changes on
the source branch during merge and rebase.
"""

from typing import Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from ..shared import load_schema
from .shared import PERSON_KIND, TestSchemaLifecycleBase

STRICT_NAME_REGEX = r"^[A-Z][a-z]+$"
PERMISSIVE_NAME_REGEX = r".*"
ILLEGAL_NAME = "not a valid name"

BRANCH_MERGE_MUTATION = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""


def _person_with_regex(person: dict[str, Any], regex: str | None) -> dict[str, Any]:
    updated = {**person, "attributes": [{**attr} for attr in person["attributes"]]}
    assert updated["attributes"][0]["name"] == "name"
    if regex is None:
        updated["attributes"][0].pop("regex", None)
    else:
        updated["attributes"][0]["regex"] = regex
    return updated


def _schema_root(person: dict[str, Any], others: list[dict[str, Any]]) -> dict[str, Any]:
    """Person relates to the car kind, so the whole base set has to load together."""
    return {"version": "1.0", "nodes": [person, *others]}


async def _person_names_on_main(db: InfrahubDatabase, default_branch: Branch) -> list[str]:
    people = await NodeManager.query(db=db, schema=PERSON_KIND, branch=default_branch)
    return sorted(str(node.get_attribute("name").value) for node in people)


class DestinationSchemaChangeBase(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_base_others(
        self,
        schema_car_base: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
        schema_tag_base: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [schema_car_base, schema_manufacturer_base, schema_tag_base]


class TestMergeWhenMainAddedTheProperty(DestinationSchemaChangeBase):
    """Regex updated on the default branch is evaluated against new data on the merging branch."""

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="main_added_property")

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_person_base: dict[str, Any],
        schema_base_others: list[dict[str, Any]],
    ) -> None:
        await load_schema(
            db=db,
            schema=_schema_root(_person_with_regex(schema_person_base, regex=None), others=schema_base_others),
        )
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)

    async def test_merge_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initial_dataset: None,
        schema_person_base: dict[str, Any],
        schema_base_others: list[dict[str, Any]],
        branch_2: Branch,
    ) -> None:
        response = await client.schema.load(
            schemas=[
                _schema_root(_person_with_regex(schema_person_base, regex=STRICT_NAME_REGEX), others=schema_base_others)
            ]
        )
        assert not response.errors

        offender = await Node.init(schema=PERSON_KIND, db=db, branch=branch_2)
        await offender.new(db=db, name=ILLEGAL_NAME, height=160)
        await offender.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch_2.name})

        assert "regex" in exc.value.message
        assert await _person_names_on_main(db=db, default_branch=default_branch) == ["John"]


class TestMergeWhenMainReplacedTheProperty(DestinationSchemaChangeBase):
    """Regex *replaced* on the default branch, not added to it, is still evaluated against the merge.

    The distinction is the whole point of the class: `HashableModel.update` skips a field the other
    side leaves as `None`, so a branch carrying no regex at all cannot overwrite one the destination
    added. A branch carrying the old permissive regex can, and does, unless the candidate schema
    takes back what only the destination changed.
    """

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="main_replaced_property_merge")

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_person_base: dict[str, Any],
        schema_base_others: list[dict[str, Any]],
    ) -> None:
        await load_schema(
            db=db,
            schema=_schema_root(
                _person_with_regex(schema_person_base, regex=PERMISSIVE_NAME_REGEX), others=schema_base_others
            ),
        )
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)

    async def test_merge_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initial_dataset: None,
        schema_person_base: dict[str, Any],
        schema_base_others: list[dict[str, Any]],
        branch_2: Branch,
    ) -> None:
        response = await client.schema.load(
            schemas=[
                _schema_root(_person_with_regex(schema_person_base, regex=STRICT_NAME_REGEX), others=schema_base_others)
            ]
        )
        assert not response.errors

        offender = await Node.init(schema=PERSON_KIND, db=db, branch=branch_2)
        await offender.new(db=db, name=ILLEGAL_NAME, height=160)
        await offender.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch_2.name})

        assert "regex" in exc.value.message
        assert await _person_names_on_main(db=db, default_branch=default_branch) == ["John"]


class TestRebaseWhenMainReplacedTheProperty(DestinationSchemaChangeBase):
    """Regex updated on the default branch is evaluated against new data on a branch during rebase."""

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="main_replaced_property")

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_person_base: dict[str, Any],
        schema_base_others: list[dict[str, Any]],
    ) -> None:
        await load_schema(
            db=db,
            schema=_schema_root(
                _person_with_regex(schema_person_base, regex=PERMISSIVE_NAME_REGEX), others=schema_base_others
            ),
        )
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)

    async def test_rebase_is_refused(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: None,
        schema_person_base: dict[str, Any],
        schema_base_others: list[dict[str, Any]],
        branch_2: Branch,
    ) -> None:
        response = await client.schema.load(
            schemas=[
                _schema_root(_person_with_regex(schema_person_base, regex=STRICT_NAME_REGEX), others=schema_base_others)
            ]
        )
        assert not response.errors

        offender = await Node.init(schema=PERSON_KIND, db=db, branch=branch_2)
        await offender.new(db=db, name=ILLEGAL_NAME, height=160)
        await offender.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.branch.rebase(branch_name=branch_2.name)

        assert "regex" in exc.value.message
        # Pins where the refusal comes from. The post-rebase diff refresh raises the same regex
        # message when it loads the offending node, so a rebase that ran to completion and only then
        # crashed downstream would satisfy the message check on its own.
        assert "for constraint" in exc.value.message, "the rebase is refused by constraint validation"
        # A refusal that dropped the object it refused over, or advanced the branch part way, would
        # also pass the message checks. Counted rather than loaded: the branch resolves the stricter
        # regex by now, and instantiating the node would raise the very error under test.
        assert (
            await NodeManager.count(db=db, schema=PERSON_KIND, branch=branch_2, filters={"name__value": ILLEGAL_NAME})
            == 1
        ), "the refused rebase left the offending object on the branch"
        refused_branch = await Branch.get_by_name(db=db, name=branch_2.name)
        assert refused_branch.branched_from == branch_2.branched_from, "a refused rebase moves no fork point"
