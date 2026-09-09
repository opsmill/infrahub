from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m076_heal_missing_attribute_rows.queries import AttributeHealDetectionQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .conftest import (
    INHERITED_CAR_ATTRIBUTE_NAMES,
    create_damaged_car,
    create_healthy_car,
    delete_attribute_rows,
    tombstone_attribute,
)


async def create_deleted_damaged_car(db: InfrahubDatabase, branch: Branch, name: str) -> str:
    """Seed a damaged car whose node was deleted through the object layer."""
    car = await create_healthy_car(db=db, branch=branch, name=name, created_at=Timestamp().subtract(seconds=30))
    node = await NodeManager.get_one(db=db, branch=branch, id=car.get_id())
    assert node is not None
    await node.delete(db=db, at=Timestamp().subtract(seconds=10))
    await delete_attribute_rows(db=db, node_uuid=car.get_id(), attribute_names=["name", "status", "asset_tag"])
    return car.get_id()


async def run_detection(db: InfrahubDatabase, branch: Branch, attribute_names: list[str]) -> set[tuple[str, str]]:
    query = await AttributeHealDetectionQuery.init(
        db=db, branch=branch, node_kinds=["TestCar"], attribute_names=attribute_names
    )
    await query.execute(db=db)
    return {(pair.node_uuid, pair.attribute_name) for pair in query.get_data()}


@dataclass(frozen=True)
class DetectionSeed:
    user_branch: Branch
    default_damaged: tuple[str, str]
    default_tombstoned: str
    branch_damaged: str
    branch_tombstoned: str


class TestAttributeHealDetection:
    """One seed covering the default branch and a user branch; each test audits one scope."""

    @pytest.fixture(scope="class")
    async def seeded(self, db: InfrahubDatabase, asset_schema_class: Branch) -> DetectionSeed:
        default = asset_schema_class
        created_at = Timestamp().subtract(seconds=30)

        await create_healthy_car(db=db, branch=default, name="healthy-default", created_at=created_at)
        default_damaged_1 = await create_damaged_car(db=db, branch=default, created_at=created_at)
        default_damaged_2 = await create_damaged_car(db=db, branch=default, created_at=created_at)
        await create_deleted_damaged_car(db=db, branch=default, name="deleted-default")
        default_tombstoned = await create_healthy_car(
            db=db, branch=default, name="tombstoned-default", created_at=created_at
        )
        await tombstone_attribute(
            db=db,
            branch=default,
            node_uuid=default_tombstoned.get_id(),
            attribute_name="status",
            deleted_at=Timestamp().subtract(seconds=10),
        )

        user_branch = await create_branch(db=db, branch_name="detection-branch")
        await create_healthy_car(db=db, branch=user_branch, name="healthy-branch", created_at=Timestamp())
        branch_damaged = await create_damaged_car(db=db, branch=user_branch, created_at=Timestamp())
        await create_deleted_damaged_car(db=db, branch=user_branch, name="deleted-branch")
        branch_tombstoned = await create_healthy_car(
            db=db, branch=user_branch, name="tombstoned-branch", created_at=Timestamp()
        )
        await tombstone_attribute(
            db=db,
            branch=user_branch,
            node_uuid=branch_tombstoned.get_id(),
            attribute_name="status",
            deleted_at=Timestamp(),
        )

        return DetectionSeed(
            user_branch=user_branch,
            default_damaged=(default_damaged_1, default_damaged_2),
            default_tombstoned=default_tombstoned.get_id(),
            branch_damaged=branch_damaged,
            branch_tombstoned=branch_tombstoned.get_id(),
        )

    async def test_default_branch_missing_and_tombstoned_detected(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: DetectionSeed
    ) -> None:
        # Healthy and deleted nodes are skipped; a tombstone-only attribute counts as damaged.
        # Branch-created nodes are invisible from the default branch.
        pairs = await run_detection(db=db, branch=asset_schema_class, attribute_names=["status"])
        assert pairs == {
            (seeded.default_damaged[0], "status"),
            (seeded.default_damaged[1], "status"),
            (seeded.default_tombstoned, "status"),
        }

    async def test_default_branch_batches_all_attribute_names(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: DetectionSeed
    ) -> None:
        pairs = await run_detection(
            db=db, branch=asset_schema_class, attribute_names=list(INHERITED_CAR_ATTRIBUTE_NAMES)
        )
        assert pairs == {
            (seeded.default_damaged[0], "asset_tag"),
            (seeded.default_damaged[0], "status"),
            (seeded.default_damaged[1], "asset_tag"),
            (seeded.default_damaged[1], "status"),
            (seeded.default_tombstoned, "status"),
        }

    async def test_user_branch_sees_visible_and_branch_local_damage(
        self, db: InfrahubDatabase, seeded: DetectionSeed
    ) -> None:
        # The branch audit reports default-branch damage the branch can see plus the
        # damage on its own branch-created nodes.
        pairs = await run_detection(
            db=db, branch=seeded.user_branch, attribute_names=list(INHERITED_CAR_ATTRIBUTE_NAMES)
        )
        assert pairs == {
            (seeded.default_damaged[0], "asset_tag"),
            (seeded.default_damaged[0], "status"),
            (seeded.default_damaged[1], "asset_tag"),
            (seeded.default_damaged[1], "status"),
            (seeded.default_tombstoned, "status"),
            (seeded.branch_damaged, "asset_tag"),
            (seeded.branch_damaged, "status"),
            (seeded.branch_tombstoned, "status"),
        }
