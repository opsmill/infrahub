from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from graphql import GraphQLInputObjectType, GraphQLObjectType

from infrahub.graphql.initialization import prepare_graphql_params

from .conftest import DELIVERY_ATTRIBUTES

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@dataclass
class MutationInputTestCase:
    name: str
    input_type: str


MUTATION_INPUT_TEST_CASES: list[MutationInputTestCase] = [
    MutationInputTestCase(name="create", input_type="CoreRepositoryCreateInput"),
    MutationInputTestCase(name="update", input_type="CoreRepositoryUpdateInput"),
    MutationInputTestCase(name="upsert", input_type="CoreRepositoryUpsertInput"),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in MUTATION_INPUT_TEST_CASES])
async def test_the_repository_mutation_inputs_leave_out_every_delivery_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    test_case: MutationInputTestCase,
) -> None:
    default_branch.update_schema_hash()
    schema = (await prepare_graphql_params(db=db, branch=default_branch)).schema
    repository_type = schema.get_type("CoreRepository")
    repository_input = schema.get_type(test_case.input_type)
    assert isinstance(repository_type, GraphQLObjectType)
    assert isinstance(repository_input, GraphQLInputObjectType)

    assert set(DELIVERY_ATTRIBUTES) <= repository_type.fields.keys()
    assert repository_input.fields.keys() & set(DELIVERY_ATTRIBUTES) == set()
    assert {"name", "location", "commit"} <= repository_input.fields.keys()
