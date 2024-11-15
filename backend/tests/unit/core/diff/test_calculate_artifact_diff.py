from uuid import uuid4

import pytest

from infrahub.core.branch.models import Branch
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.diff.artifacts.calculator import ArtifactDiffCalculator
from infrahub.core.diff.model.diff import ArtifactTarget, BranchDiffArtifact, BranchDiffArtifactStorage
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def car_person_data_artifact_diff(
    db: InfrahubDatabase, default_branch: Branch, car_person_data_generic: dict[str, Node]
):
    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
    await g1.save(db=db)

    t1 = await Node.init(db=db, schema="CoreTransformPython")
    await t1.new(
        db=db,
        name="transform01",
        query=car_person_data_generic["q1"].id,
        repository=car_person_data_generic["r1"].id,
        file_path="transform01.py",
        class_name="Transform01",
    )
    await t1.save(db=db)

    ad1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
    await ad1.new(
        db=db,
        name="artifactdef01",
        targets=g1,
        transformation=t1,
        content_type="application/json",
        artifact_name="myyartifact",
        parameters={"value": {"name": "name__value"}},
    )
    await ad1.save(db=db)

    art1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
    await art1.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c1"],
        storage_id="8caf6f89-073f-4173-aa4b-f50e1309f03c",
        checksum="60d39063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art1.save(db=db)

    branch3 = await create_branch(branch_name="branch3", db=db)

    art1_branch = await Node.init(db=db, branch=branch3, schema=InfrahubKind.ARTIFACT)
    await art1_branch.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c1"],
        storage_id=str(uuid4()),
        checksum="zxcv9063c26263353de24e1b911z1x2c3v",
        content_type="application/json",
    )
    await art1_branch.save(db=db)
    art1_branch = await NodeManager.get_one(db=db, branch=branch3, id=art1_branch.id)
    art1_branch.storage_id.value = "azertyui-073f-4173-aa4b-f50e1309f03c"
    await art1_branch.save(db=db)
    art1_main = await NodeManager.get_one(db=db, branch=branch3, id=art1.id)
    art1_main.storage_id.value = str(uuid4())
    art1_main.checksum.value = str(uuid4())
    await art1_main.save(db=db)

    art2 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch3)
    await art2.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c2"],
        storage_id="qwertyui-073f-4173-aa4b-f50e1309f03c",
        checksum="zxcv9063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art2.save(db=db)

    art3_main = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=default_branch)
    await art3_main.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c3"],
        storage_id="mnbvcxza-073f-4173-aa4b-f50e1309f03c",
        checksum="poiuytrewq9063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art3_main.save(db=db)

    art3_branch = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch3)
    await art3_branch.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c3"],
        storage_id="lkjhgfds-073f-4173-aa4b-f50e1309f03c",
        checksum="nhytgbvfredc9063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art3_branch.save(db=db)

    art4_main = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=default_branch)
    await art4_main.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c4"],
        storage_id=str(uuid4()),
        checksum=str(uuid4()),
        content_type="application/json",
    )
    await art4_main.save(db=db)

    art4_branch = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch3)
    await art4_branch.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic["c4"],
        storage_id=str(uuid4()),
        checksum=str(uuid4()),
        content_type="application/json",
    )
    await art4_branch.save(db=db)
    await art4_branch.delete(db=db)

    car_person_data_generic["branch3"] = branch3
    car_person_data_generic["art1"] = art1
    car_person_data_generic["art1_branch"] = art1_branch
    car_person_data_generic["art2_branch"] = art2
    car_person_data_generic["art3"] = art3_main
    car_person_data_generic["art3_branch"] = art3_branch

    return car_person_data_generic


async def test_calculate_artifact_diff(
    db: InfrahubDatabase, default_branch: Branch, car_person_data_artifact_diff: dict[str, Node]
):
    source_branch = car_person_data_artifact_diff["branch3"]
    art1_branch = car_person_data_artifact_diff["art1_branch"]
    art2_branch = car_person_data_artifact_diff["art2_branch"]
    art3_branch = car_person_data_artifact_diff["art3_branch"]
    expected_artifact_diff_1 = BranchDiffArtifact(
        branch=source_branch.name,
        id=art1_branch.id,
        display_label="volt #444444 - myyartifact",
        action=DiffAction.UPDATED,
        target=ArtifactTarget(
            id=car_person_data_artifact_diff["c1"].id,
            kind="TestElectricCar",
            display_label="volt #444444",
        ),
        item_new=BranchDiffArtifactStorage(
            storage_id="azertyui-073f-4173-aa4b-f50e1309f03c",
            checksum="zxcv9063c26263353de24e1b911z1x2c3v",
        ),
        item_previous=BranchDiffArtifactStorage(
            storage_id="8caf6f89-073f-4173-aa4b-f50e1309f03c",
            checksum="60d39063c26263353de24e1b913e1e1c",
        ),
    )
    expected_artifact_diff_2 = BranchDiffArtifact(
        branch=source_branch.name,
        id=art2_branch.id,
        display_label="bolt #444444 - myyartifact",
        action=DiffAction.ADDED,
        target=ArtifactTarget(
            id=car_person_data_artifact_diff["c2"].id,
            kind="TestElectricCar",
            display_label="bolt #444444",
        ),
        item_new=BranchDiffArtifactStorage(
            storage_id="qwertyui-073f-4173-aa4b-f50e1309f03c",
            checksum="zxcv9063c26263353de24e1b913e1e1c",
        ),
        item_previous=None,
    )
    expected_artifact_diff_3 = BranchDiffArtifact(
        branch=source_branch.name,
        id=art3_branch.id,
        display_label="nolt #444444 - myyartifact",
        action=DiffAction.UPDATED,
        target=ArtifactTarget(
            id=car_person_data_artifact_diff["c3"].id,
            kind="TestGazCar",
            display_label="nolt #444444",
        ),
        item_new=BranchDiffArtifactStorage(
            storage_id="lkjhgfds-073f-4173-aa4b-f50e1309f03c",
            checksum="nhytgbvfredc9063c26263353de24e1b913e1e1c",
        ),
        item_previous=BranchDiffArtifactStorage(
            storage_id="mnbvcxza-073f-4173-aa4b-f50e1309f03c",
            checksum="poiuytrewq9063c26263353de24e1b913e1e1c",
        ),
    )

    artifact_diff_calculator = ArtifactDiffCalculator(db=db)
    artifact_diffs = await artifact_diff_calculator.calculate(source_branch=source_branch, target_branch=default_branch)

    assert len(artifact_diffs) == 3
    diffs_by_id = {d.id: d for d in artifact_diffs}
    assert set(diffs_by_id.keys()) == {art1_branch.id, art2_branch.id, art3_branch.id}
    assert diffs_by_id[art1_branch.id] == expected_artifact_diff_1
    assert diffs_by_id[art2_branch.id] == expected_artifact_diff_2
    assert diffs_by_id[art3_branch.id] == expected_artifact_diff_3
