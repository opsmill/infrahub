from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.read_sets import transform_read_set_from_query_report
from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.schema.color import COLOR
from tests.helpers.schema.tshirt import TSHIRT

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

TSHIRT_KIND = "TestingTShirtHfid"


@dataclass
class HfidFilterCase:
    name: str
    human_friendly_id: list[str]
    depends_on_everything: bool


@pytest.mark.parametrize(
    "case",
    [
        HfidFilterCase(
            name="built_from_its_own_attribute", human_friendly_id=["name__value"], depends_on_everything=False
        ),
        HfidFilterCase(
            name="built_from_a_peer_attribute", human_friendly_id=["color__name__value"], depends_on_everything=True
        ),
    ],
    ids=lambda case: case.name,
)
async def test_a_filter_on_hfid_reads_the_fields_behind_it_as_unknown(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, case: HfidFilterCase
) -> None:
    """A filter on ``hfid`` is held like a read of it: any change to the kind, or to a peer it is built from, can move it."""
    tshirt_hfid = deepcopy(TSHIRT)
    tshirt_hfid.name = "TShirtHfid"
    tshirt_hfid.human_friendly_id = case.human_friendly_id
    registry.schema.register_schema(schema=SchemaRoot(nodes=[COLOR, tshirt_hfid]), branch=default_branch.name)
    default_branch.update_schema_hash()
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    analyzer = InfrahubGraphQLQueryAnalyzer(
        query=f'query {{ {TSHIRT_KIND}(hfid: ["blue"]) {{ edges {{ node {{ name {{ value }} }} }} }} }}',
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    read_set = transform_read_set_from_query_report(report=analyzer.query_report, schema_branch=schema_branch)

    assert read_set.depends_on_everything is case.depends_on_everything
    if not case.depends_on_everything:
        assert read_set.imprecise_kinds == frozenset({TSHIRT_KIND})
