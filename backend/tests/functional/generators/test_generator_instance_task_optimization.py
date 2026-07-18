from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.generators.graphql_queries.queries import GeneratorInstanceQuery
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestGeneratorInstanceTaskOptimization(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def setup(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
        bus_simulator: BusSimulator,
    ) -> None:
        pass

    async def test_generator_instance_query_returns_empty_for_nonexistent_ids(
        self,
        db: InfrahubDatabase,
        setup: None,
        default_branch: Branch,
        client: InfrahubClient,
        prefect_test_fixture: None,
    ) -> None:
        gen_query = GeneratorInstanceQuery(
            definition_id="00000000-0000-0000-0000-000000000001",
            object_id="00000000-0000-0000-0000-000000000002",
        )
        response = await client.execute_graphql(query=gen_query.render_query(), branch_name=default_branch.name)
        result = gen_query.parse_response(response=response)
        assert result == []
