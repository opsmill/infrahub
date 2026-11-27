from typing import Any
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def target_group(db: InfrahubDatabase, car_person_data_generic: dict[str, Node]) -> Node:
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="targets", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
    await group.save(db=db)
    return group


@pytest.fixture
async def artifact_definition(
    db: InfrahubDatabase, car_person_data_generic: dict[str, Node], target_group: Node
) -> Node:
    transform = await Node.init(db=db, schema="CoreTransformPython")
    await transform.new(
        db=db,
        name="transform01",
        query=car_person_data_generic["q1"].id,
        repository=car_person_data_generic["r1"].id,
        file_path="transform01.py",
        class_name="Transform01",
    )
    await transform.save(db=db)

    definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
    await definition.new(
        db=db,
        name="artifactdef01",
        targets=target_group,
        transformation=transform,
        content_type="application/json",
        artifact_name="myartifact",
        parameters={"value": {"name": "name__value"}},
    )
    await definition.save(db=db)
    return definition


@pytest.fixture
async def generator_definitions(
    db: InfrahubDatabase, car_person_data_generic: dict[str, Node], target_group: Node
) -> list[Node]:
    definitions: list[Node] = []
    for index in (1, 2):
        definition = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await definition.new(
            db=db,
            name=f"generatordef0{index}",
            query=str(car_person_data_generic["q1"].id),
            repository=str(car_person_data_generic["r1"].id),
            file_path=f"generator0{index}.py",
            class_name=f"Generator0{index}",
            targets=str(target_group.id),
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)
        definitions.append(definition)
    return definitions


async def create_artifact(
    db: InfrahubDatabase, definition: Node, target: Node, name: str, branch: Branch | None = None, **attributes: Any
) -> Node:
    artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch)
    await artifact.new(
        db=db, name=name, definition=definition, object=target, content_type="application/json", **attributes
    )
    await artifact.save(db=db)
    return artifact


async def create_generated_artifact(
    db: InfrahubDatabase, definition: Node, target: Node, name: str, branch: Branch | None = None
) -> Node:
    return await create_artifact(
        db=db,
        definition=definition,
        target=target,
        name=name,
        branch=branch,
        status="Ready",
        storage_id=str(uuid4()),
        checksum=str(uuid4()),
    )


async def create_generator_instance(
    db: InfrahubDatabase,
    definition: Node,
    target: Node,
    status: GeneratorInstanceStatus = GeneratorInstanceStatus.READY,
    branch: Branch | None = None,
) -> Node:
    instance = await Node.init(db=db, schema=InfrahubKind.GENERATORINSTANCE, branch=branch)
    await instance.new(
        db=db, name=f"instance-{uuid4().hex[:8]}", status=status.value, object=target, definition=definition
    )
    await instance.save(db=db)
    return instance
