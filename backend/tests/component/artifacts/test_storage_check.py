from __future__ import annotations

import io
from typing import TYPE_CHECKING

from infrahub.artifacts.storage_check import ArtifactStorageChecker
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE
from tests.adapters.storage import DummyObjectStorage
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

CONTENT = b"hostname leaf01\n"
CONTENT_CHECKSUM = "46d5b267ca287bb93ae4e9654c7fa964"


async def create_definition(db: InfrahubDatabase, data: dict[str, Node]) -> Node:
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="cars", members=[data["c1"], data["c2"], data["c3"], data["c4"]])
    await group.save(db=db)

    transform = await Node.init(db=db, schema="CoreTransformPython")
    await transform.new(
        db=db,
        name="car_config",
        query=str(data["q1"].id),
        repository=str(data["r1"].id),
        file_path="transform01.py",
        class_name="Transform01",
    )
    await transform.save(db=db)

    definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
    await definition.new(
        db=db,
        name="car_config",
        targets=group,
        transformation=transform,
        content_type="text/plain",
        artifact_name="car-config",
        parameters={"value": {"name": "name__value"}},
    )
    await definition.save(db=db)
    return definition


async def create_artifact(
    db: InfrahubDatabase,
    storage: DummyObjectStorage,
    definition: Node,
    target: Node,
    storage_id: str,
    status: str = "Ready",
) -> Node:
    artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
    await artifact.new(
        db=db,
        name="car-config",
        definition=definition,
        status=status,
        object=target,
        storage_id=storage_id,
        checksum=CONTENT_CHECKSUM,
        content_type="text/plain",
    )
    await artifact.save(db=db)
    storage.store(identifier=storage_id, content=io.BytesIO(CONTENT))
    return artifact


async def test_regenerates_ready_artifacts_whose_stored_file_is_missing_or_modified(
    db: InfrahubDatabase, default_branch: Branch, car_person_data_generic: dict[str, Node]
) -> None:
    storage = DummyObjectStorage()
    workflow = WorkflowRecorder()
    definition = await create_definition(db=db, data=car_person_data_generic)
    await create_artifact(
        db=db, storage=storage, definition=definition, target=car_person_data_generic["c1"], storage_id="intact"
    )
    modified = await create_artifact(
        db=db, storage=storage, definition=definition, target=car_person_data_generic["c2"], storage_id="modified"
    )
    missing = await create_artifact(
        db=db, storage=storage, definition=definition, target=car_person_data_generic["c3"], storage_id="missing"
    )
    await create_artifact(
        db=db,
        storage=storage,
        definition=definition,
        target=car_person_data_generic["c4"],
        storage_id="failed",
        status="Error",
    )
    storage.store(identifier="modified", content=io.BytesIO(b"hostname modified-in-storage\n"))
    storage.delete(identifier="missing")
    storage.delete(identifier="failed")

    await ArtifactStorageChecker(db=db, storage=storage, workflow=workflow).check(branch=default_branch)

    assert [
        call["parameters"]["model"]
        for call in workflow.get_submit_calls_for(workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE)
    ] == [
        RequestArtifactDefinitionGenerate(
            artifact_definition_id=definition.id,
            artifact_definition_name="car_config",
            branch=default_branch.name,
            limit=sorted([modified.id, missing.id]),
        )
    ]


async def test_regenerates_nothing_when_every_stored_file_matches(
    db: InfrahubDatabase, default_branch: Branch, car_person_data_generic: dict[str, Node]
) -> None:
    storage = DummyObjectStorage()
    workflow = WorkflowRecorder()
    definition = await create_definition(db=db, data=car_person_data_generic)
    await create_artifact(
        db=db, storage=storage, definition=definition, target=car_person_data_generic["c1"], storage_id="intact-1"
    )
    await create_artifact(
        db=db, storage=storage, definition=definition, target=car_person_data_generic["c2"], storage_id="intact-2"
    )

    await ArtifactStorageChecker(db=db, storage=storage, workflow=workflow).check(branch=default_branch)

    assert workflow.submit_calls == []
