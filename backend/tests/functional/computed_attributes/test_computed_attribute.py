from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.computed_attribute.gather import gather_trigger_computed_attribute_python
from infrahub.computed_attribute.tasks import query_transform_targets
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import COLOR, TSHIRT, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


RECOMPUTE_COMPUTED_ATTRIBUTE_MUTATION = """
mutation Recompute($kind: String!, $attribute: String!, $node_ids: [String!]) {
  InfrahubRecomputeComputedAttribute(data: {kind: $kind, attribute: $attribute, node_ids: $node_ids}) {
    ok
  }
}
"""


class TestComputedAttribute(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def context(self, db: InfrahubDatabase, initialize_registry: None, default_branch: Branch) -> InfrahubContext:
        """Context with a real account from the database for computed attribute workflows"""
        admin_account = await NodeManager.get_one_by_hfid(
            db=db, kind=InfrahubKind.ACCOUNT, hfid=["admin"], raise_on_error=True
        )
        return InfrahubContext(
            account=AccountSession(authenticated=True, account_id=admin_account.id, auth_type=AuthType.API),
            branch=BranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        )

    @pytest.fixture(scope="class")
    async def data(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        default_branch: Branch,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
        git_repos_source_dir_module_scope: Path,
    ) -> dict[str, Node]:
        await load_schema(db, schema=SchemaRoot(nodes=[COLOR, TSHIRT]), update_db=True)

        c1 = await Node.init(db=db, schema="TestingColor")
        await c1.new(
            db=db, name="Sunset", description="A bold, vibrant orange that captures the warmth of the setting sun."
        )
        await c1.save(db=db)
        c2 = await Node.init(db=db, schema="TestingColor")
        await c2.new(db=db, name="Ocean", description="Deep and calming, like the endless expanse of the ocean.")
        await c2.save(db=db)

        c3 = await Node.init(db=db, schema="TestingColor")
        await c3.new(db=db, name="Ivory", description="A soft off-white, smooth and classic.")
        await c3.save(db=db)

        t1 = await Node.init(db=db, schema="TestingTShirt")
        await t1.new(db=db, name="Explorer", color=c1)
        await t1.save(db=db)

        t2 = await Node.init(db=db, schema="TestingTShirt")
        await t2.new(db=db, name="Rouge", color=c3)
        await t2.save(db=db)

        FileRepo(name="computed-attributes-functional", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={
                "name": "computed-attributes-functional",
                "location": f"{git_repos_source_dir_module_scope}/computed-attributes-functional",
            },
            branch=default_branch.name,
        )
        await client_repository.save()

        return {"c1": c1, "c2": c2, "c3": c3, "t1": t1, "t2": t2}

    async def test_gather_trigger_computed_attribute_python_main(
        self,
        db: InfrahubDatabase,
        data: dict[str, Node],
        client: InfrahubClient,
        default_branch: Branch,
    ) -> None:
        triggers_python, triggers_python_query = await gather_trigger_computed_attribute_python(db=db)
        assert len(triggers_python) == 1
        assert triggers_python[0].generate_name() == "computed_attr_python::main::TestingTShirt_pitch"
        assert len(triggers_python_query) == 2
        assert (
            triggers_python_query[0].generate_name()
            == "computed_attr_python_query::main::TestingTShirt_pitch::kind::TestingTShirt"
        )
        assert (
            triggers_python_query[1].generate_name()
            == "computed_attr_python_query::main::TestingTShirt_pitch::kind::TestingColor"
        )

    async def test_gather_trigger_computed_attribute_python_branch(
        self,
        db: InfrahubDatabase,
        data: dict[str, Node],
        client: InfrahubClient,
        default_branch: Branch,
    ) -> None:
        await client.branch.create(branch_name="branch2")

        repo = await client.get(kind="CoreRepository", name__value="computed-attributes-functional", branch="branch2")
        repo.commit.value = "decc6d49679404b201c54bbe7b0c788e268e25b7"
        await repo.save()

        triggers_python, triggers_python_query = await gather_trigger_computed_attribute_python(db=db)
        assert len(triggers_python) == 2
        assert len(triggers_python_query) == 4

    async def test_description_after_color_change_jinja2(
        self,
        data: dict[str, Node],
        client: InfrahubClient,
        default_branch: Branch,
        context: InfrahubContext,
    ) -> None:
        tshirt_1 = await client.get(kind="TestingTShirt", id=data["t1"].id)
        assert (
            tshirt_1.description.value
            == "A Sunset Explorer t-shirt. A bold, vibrant orange that captures the warmth of the setting sun."
        )

        tshirt_1.color = data["c2"].id
        await tshirt_1.save()

        response = await client.execute_graphql(
            query=RECOMPUTE_COMPUTED_ATTRIBUTE_MUTATION,
            variables={"kind": TSHIRT.kind, "attribute": "description", "node_ids": [tshirt_1.id]},
        )
        assert "InfrahubRecomputeComputedAttribute" in response
        assert response["InfrahubRecomputeComputedAttribute"]["ok"]

        tshirt_updated = await client.get(kind="TestingTShirt", id=data["t1"].id)
        assert (
            tshirt_updated.description.value
            == "A Ocean Explorer t-shirt. Deep and calming, like the endless expanse of the ocean."
        )

    async def test_description_after_chainging_color_description_transform(
        self,
        data: dict[str, Node],
        client: InfrahubClient,
        default_branch: Branch,
        context: InfrahubContext,
    ) -> None:
        tshirt_obj = data["t2"]
        color_obj = data["c3"]

        tshirt_initial = await client.get(kind="TestingTShirt", id=tshirt_obj.id)

        response = await client.execute_graphql(
            query=RECOMPUTE_COMPUTED_ATTRIBUTE_MUTATION,
            variables={"kind": TSHIRT.kind, "attribute": "pitch", "node_ids": [tshirt_obj.id]},
        )
        assert "InfrahubRecomputeComputedAttribute" in response
        assert response["InfrahubRecomputeComputedAttribute"]["ok"]

        tshirt_first_pitch_allocation = await client.get(kind="TestingTShirt", id=tshirt_obj.id)

        color = await client.get(kind="TestingColor", id=color_obj.id)
        color.description.value = "A soft off-white, smooth and timeless."
        await color.save()

        await query_transform_targets(
            branch_name=default_branch.name,
            node_kind="TestingColor",
            object_id=color_obj.id,
            context=context,
        )

        tshirt_altered_pitch_allocation = await client.get(kind="TestingTShirt", id=tshirt_obj.id)
        assert not tshirt_initial.pitch.value
        assert (
            tshirt_first_pitch_allocation.pitch.value
            == "Buy your Rouge t-shirt today. Look great in a soft off-white, smooth and classic."
        )
        assert (
            tshirt_altered_pitch_allocation.pitch.value
            == "Buy your Rouge t-shirt today. Look great in a soft off-white, smooth and timeless."
        )
