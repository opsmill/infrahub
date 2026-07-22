import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.database import InfrahubDatabase


async def _run_checker(
    db: InfrahubDatabase, branch: Branch, schema: NodeSchema, node_uuids: list[str] | None
) -> set[tuple[str, str | None, str | None]]:
    checker = UniquenessChecker(db)
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.uniqueness_constraints.update",
        node_schema=schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=schema.kind),
        schema_branch=db.schema.get_schema_branch(name=branch.name),
        node_uuids=node_uuids,
    )
    grouped_data_paths = await checker.check(request)
    assert len(grouped_data_paths) == 1
    return {(path.node_id, path.field_name, str(path.value)) for path in grouped_data_paths[0].get_all_data_paths()}


def _make_nbr_seats_unique(branch: Branch) -> NodeSchema:
    schema = registry.schema.get_node_schema("TestCar", branch=branch)
    schema.get_attribute("nbr_seats").unique = True
    registry.schema.register_schema(schema=SchemaRoot(nodes=[schema]), branch=branch.name)
    return registry.schema.get_node_schema(name="TestCar", branch=branch, duplicate=False)


class TestUniquenessCheckerNodeScoped:
    async def test_targeted_change_finds_collision_with_untouched_peer(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_volt_main: Node,
        branch: Branch,
    ) -> None:
        # accord and prius share nbr_seats=5; only accord is "changed" (passed via node_uuids)
        schema = _make_nbr_seats_unique(branch)

        violations = await _run_checker(db, branch, schema, node_uuids=[car_accord_main.id])

        # volt is not included (nbr_seats=4)
        assert violations == {
            (car_accord_main.id, "nbr_seats", "5"),
            (car_prius_main.id, "nbr_seats", "5"),
        }

    async def test_targeted_change_without_collision_reports_nothing(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_volt_main: Node,
        branch: Branch,
    ) -> None:
        # volt's nbr_seats is unique among the fixtures, so validating only volt finds no collision
        schema = _make_nbr_seats_unique(branch)

        violations = await _run_checker(db, branch, schema, node_uuids=[car_volt_main.id])

        assert violations == set()

    async def test_targeted_mutual_collision_between_changed_nodes(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_volt_main: Node,
        car_yaris_main: Node,
        branch: Branch,
    ) -> None:
        # make two previously-distinct cars collide, then validate both as changed nodes
        yaris_main = await NodeManager.get_one(db=db, id=car_yaris_main.id)
        yaris_main.get_attribute("nbr_seats").value = 9
        await yaris_main.save(db=db)
        volt_branch = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
        volt_branch.get_attribute("nbr_seats").value = 9
        await volt_branch.save(db=db)

        schema = _make_nbr_seats_unique(branch)

        violations = await _run_checker(db, branch, schema, node_uuids=[car_volt_main.id, car_yaris_main.id])

        assert violations == {
            (car_volt_main.id, "nbr_seats", "9"),
            (car_yaris_main.id, "nbr_seats", "9"),
        }

    async def test_full_scan_when_node_uuids_is_none(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        branch: Branch,
    ) -> None:
        # node_uuids=None preserves the full-population scan used for a newly added/broadened constraint
        schema = _make_nbr_seats_unique(branch)

        violations = await _run_checker(db, branch, schema, node_uuids=None)

        assert violations == {
            (car_accord_main.id, "nbr_seats", "5"),
            (car_prius_main.id, "nbr_seats", "5"),
        }

    @pytest.mark.xfail(
        reason="peer-attribute uniqueness (owner__height) is not supported by the batched targeted "
        "query; such constraints are rejected at schema load, so this path is unreachable in a "
        "valid schema. Full-population validation still covers it.",
        raises=ValueError,
        strict=True,
    )
    async def test_targeted_cross_kind_peer_attribute_collision(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_camry_main: Node,
        person_john_main: Node,
        person_jane_main: Node,
        branch: Branch,
    ) -> None:
        # accord is owned by John and camry by Jane, but both owners have height 180. A
        # uniqueness on the peer's attribute value (not the peer's identity) must flag them as
        # colliding even though the changed node (accord) points at a different peer than camry.
        schema = registry.schema.get_node_schema("TestCar", branch=branch)
        schema.uniqueness_constraints = [["owner__height"]]
        registry.schema.register_schema(schema=SchemaRoot(nodes=[schema]), branch=branch.name)
        synced_schema = registry.schema.get_node_schema(name="TestCar", branch=branch, duplicate=False)

        violations = await _run_checker(db, branch, synced_schema, node_uuids=[car_accord_main.id])

        # the violation is reported against the relationship path, carrying the peer's value
        assert (car_accord_main.id, "owner", "180") in violations
        assert (car_camry_main.id, "owner", "180") in violations

    @pytest.mark.xfail(
        reason="peer-attribute uniqueness (owner__height) is not supported by the batched targeted "
        "query; the determiner still resolves the cross-kind change, but the checker rejects the "
        "peer-attribute constraint. Such constraints cannot exist in a valid schema.",
        raises=ValueError,
        strict=True,
    )
    async def test_cross_kind_peer_change_resolves_and_detects_end_to_end(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_camry_main: Node,
        person_john_main: Node,
        person_jane_main: Node,
        branch: Branch,
    ) -> None:
        # accord->john and camry->jane, both owners height 180, uniqueness on the peer's height.
        # A change to john's height (the peer) leaves accord itself absent from the diff; the whole
        # chain (determiner cross-kind descriptor -> real resolver -> checker) must still flag it.
        car_schema = registry.schema.get_node_schema("TestCar", branch=branch)
        car_schema.uniqueness_constraints = [["owner__height"]]
        registry.schema.register_schema(schema=SchemaRoot(nodes=[car_schema]), branch=branch.name)
        synced_schema = registry.schema.get_node_schema(name="TestCar", branch=branch, duplicate=False)

        determiner = build_constraint_validator_determiner(
            db=db, branch=branch, schema_branch=registry.schema.get_schema_branch(name=branch.name)
        )
        person_change = NodeDiffFieldSummary(
            kind="TestPerson", attribute_names={"height"}, node_uuids={person_john_main.id}
        )

        constraints = await determiner.get_constraints(node_diffs=[person_change])

        car_constraint = next(
            c
            for c in constraints
            if c.constraint_name == "node.uniqueness_constraints.update" and c.path.schema_kind == "TestCar"
        )
        # the resolver mapped the changed person to the car that owns it (accord), not camry
        assert car_constraint.node_uuids == [car_accord_main.id]

        violations = await _run_checker(db, branch, synced_schema, node_uuids=car_constraint.node_uuids)

        violating_ids = {node_id for node_id, _, _ in violations}
        assert car_accord_main.id in violating_ids
        # camry is untouched and points at a different owner, but shares the owner height value
        assert car_camry_main.id in violating_ids
