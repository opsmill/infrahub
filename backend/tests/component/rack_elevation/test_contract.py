from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp

from .dataset import (
    ACCEPTED_PLACEMENTS,
    EXPECTED_KINDS,
    REFUSED_PLACEMENTS,
    AcceptedPlacement,
    RackOptionFixture,
    RefusedPlacement,
    expected_elevation,
)
from .helpers import (
    ELEVATION_QUERY,
    KINDS_QUERY,
    PLACE_MUTATION,
    RACK_TOTALS_QUERY,
    RunGraphQL,
    formatted_errors,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

ELEVATION_ARGUMENTS = {"label_by": "name", "color_by": "role"}
CONSTRAINT_VIOLATION_CODE = "ATTRIBUTE_CONSTRAINT_VIOLATION"


def _place_variables(rack_ids: dict[str, str], item: str, rack: str, position: int | None, face: str | None) -> dict:
    return {
        "item": rack_ids[item],
        "rack": rack_ids[rack],
        "position": position,
        "face": face.upper() if face else None,
    }


async def _read_elevation(
    run_graphql: RunGraphQL, branch: Branch, rack_ids: dict[str, str], rack: str, **kwargs: Any
) -> dict[str, Any]:
    result = await run_graphql(
        branch=branch,
        document=ELEVATION_QUERY,
        variables={"rack": rack_ids[rack], **ELEVATION_ARGUMENTS},
        **kwargs,
    )
    assert result.errors is None
    assert result.data is not None
    return result.data["RackElevation"]


def _find_item(elevation: dict[str, Any], rack_ids: dict[str, str], name: str) -> dict[str, Any] | None:
    for item in elevation["items"]:
        if item["id"] == rack_ids[name]:
            return item
    return None


async def test_kinds_list_the_racks_the_items_and_the_types(
    rack_ids: dict[str, str], default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    result = await run_graphql(branch=default_branch, document=KINDS_QUERY)

    assert result.errors is None
    assert result.data is not None
    roles_by_kind = {entry["kind"]: entry["role"] for entry in result.data["RackElevationKinds"]}
    for kind, role in EXPECTED_KINDS.items():
        assert roles_by_kind[kind] == role


@pytest.mark.parametrize("rack", ["R1", "R2"])
async def test_elevation_of_a_rack(
    rack: str, rack_ids: dict[str, str], default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    elevation = await _read_elevation(run_graphql=run_graphql, branch=default_branch, rack_ids=rack_ids, rack=rack)

    assert elevation == expected_elevation(ids=rack_ids, rack_name=rack)


async def test_rack_nodes_expose_the_calculated_totals(
    rack_ids: dict[str, str], default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    result = await run_graphql(branch=default_branch, document=RACK_TOTALS_QUERY)

    assert result.errors is None
    assert result.data is not None
    totals_by_rack = {
        edge["node"]["name"]["value"]: (
            edge["node"]["rack_used_units"]["value"],
            edge["node"]["rack_utilization"]["value"],
            edge["node"]["rack_total_weight"]["value"],
        )
        for edge in result.data["LocationRack"]["edges"]
    }
    assert totals_by_rack == {"R1": (5, 41, 57), "R2": (0, 0, None)}


@pytest.mark.parametrize("case", REFUSED_PLACEMENTS, ids=lambda case: f"{case.item}-{case.rack}-{case.constraint}")
async def test_refused_placement_through_the_place_mutation(
    case: RefusedPlacement, rack_ids: dict[str, str], default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    result = await run_graphql(
        branch=default_branch,
        document=PLACE_MUTATION,
        variables=_place_variables(
            rack_ids=rack_ids, item=case.item, rack=case.rack, position=case.position, face=case.face
        ),
    )

    errors = formatted_errors(result)
    assert len(errors) == 1
    assert errors[0]["extensions"]["code"] == CONSTRAINT_VIOLATION_CODE
    assert errors[0]["extensions"]["data"]["constraint"] == case.constraint
    for rack in ("R1", "R2"):
        elevation = await _read_elevation(run_graphql=run_graphql, branch=default_branch, rack_ids=rack_ids, rack=rack)
        assert elevation == expected_elevation(ids=rack_ids, rack_name=rack)


@pytest.mark.parametrize(
    "case",
    [case for case in REFUSED_PLACEMENTS if case.through_standard_mutation],
    ids=lambda case: f"{case.item}-{case.rack}-{case.constraint}",
)
async def test_refused_placement_through_the_standard_update_mutation(
    case: RefusedPlacement,
    rack_ids: dict[str, str],
    rack_option: RackOptionFixture,
    default_branch: Branch,
    run_graphql: RunGraphQL,
) -> None:
    document, variables = rack_option.standard_update_mutation(
        item_name=case.item,
        item_id=rack_ids[case.item],
        rack_id=rack_ids[case.rack],
        position=case.position,
        face=case.face,
    )

    result = await run_graphql(branch=default_branch, document=document, variables=variables)

    errors = formatted_errors(result)
    assert len(errors) == 1
    assert errors[0]["extensions"]["code"] == CONSTRAINT_VIOLATION_CODE
    assert errors[0]["extensions"]["data"]["constraint"] == case.constraint


@pytest.mark.parametrize("case", ACCEPTED_PLACEMENTS, ids=lambda case: f"{case.item}-{case.rack}-{case.position}")
async def test_accepted_placement_shows_in_the_next_elevation(
    case: AcceptedPlacement, rack_ids: dict[str, str], default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    result = await run_graphql(
        branch=default_branch,
        document=PLACE_MUTATION,
        variables=_place_variables(
            rack_ids=rack_ids, item=case.item, rack=case.rack, position=case.position, face=case.face
        ),
    )

    assert result.errors is None
    assert result.data is not None
    assert result.data["RackElevationPlace"]["ok"] is True
    elevation = await _read_elevation(run_graphql=run_graphql, branch=default_branch, rack_ids=rack_ids, rack=case.rack)
    item = _find_item(elevation=elevation, rack_ids=rack_ids, name=case.item)
    assert item is not None
    assert item["position"] == case.position
    assert item["face"] == (case.face.upper() if case.face else None)
    assert item["placement"] == ("MOUNTED" if case.position is not None else "UNPOSITIONED")


async def test_moving_an_item_out_of_a_rack_updates_the_totals_of_both_racks(
    rack_ids: dict[str, str], default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    result = await run_graphql(
        branch=default_branch,
        document=PLACE_MUTATION,
        variables=_place_variables(rack_ids=rack_ids, item="leaf2", rack="R2", position=1, face="front"),
    )
    assert result.errors is None

    source = await _read_elevation(run_graphql=run_graphql, branch=default_branch, rack_ids=rack_ids, rack="R1")
    target = await _read_elevation(run_graphql=run_graphql, branch=default_branch, rack_ids=rack_ids, rack="R2")

    assert source["rack"]["used_units"] == 4
    assert source["rack"]["total_weight"] == 49
    assert _find_item(elevation=source, rack_ids=rack_ids, name="leaf2") is None
    assert target["rack"]["used_units"] == 1
    assert target["rack"]["total_weight"] == 8


async def test_a_move_on_a_branch_is_not_visible_on_the_default_branch(
    rack_ids: dict[str, str], db: InfrahubDatabase, default_branch: Branch, run_graphql: RunGraphQL
) -> None:
    branch = await create_branch(db=db, branch_name="rack-move")
    before_move = Timestamp()

    result = await run_graphql(
        branch=branch,
        document=PLACE_MUTATION,
        variables=_place_variables(rack_ids=rack_ids, item="spare1", rack="R1", position=5, face="front"),
    )
    assert result.errors is None

    on_branch = await _read_elevation(run_graphql=run_graphql, branch=branch, rack_ids=rack_ids, rack="R1")
    on_default = await _read_elevation(run_graphql=run_graphql, branch=default_branch, rack_ids=rack_ids, rack="R1")
    earlier_on_branch = await _read_elevation(
        run_graphql=run_graphql, branch=branch, rack_ids=rack_ids, rack="R1", at=before_move
    )

    moved = _find_item(elevation=on_branch, rack_ids=rack_ids, name="spare1")
    assert moved is not None
    assert (moved["position"], moved["face"], moved["placement"]) == (5, "FRONT", "MOUNTED")
    assert on_default == expected_elevation(ids=rack_ids, rack_name="R1")
    assert earlier_on_branch == expected_elevation(ids=rack_ids, rack_name="R1")
