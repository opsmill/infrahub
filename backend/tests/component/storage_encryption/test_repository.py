from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.storage_encryption.repository import StoredObjectRepository
from tests.helpers.artifact import create_stored_artifact
from tests.helpers.schema.file_contract import FILE_CONTRACT

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_each_stored_version_has_only_the_checksum_recorded_with_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
) -> None:
    artifact = await create_stored_artifact(
        db=db,
        car_person_data_generic=car_person_data_generic,
        storage_id="0b9f9a8c-0000-4000-8000-000000000001",
        checksum="11111111111111111111111111111111",
    )
    artifact.storage_id.value = "0b9f9a8c-0000-4000-8000-000000000002"
    artifact.checksum.value = "22222222222222222222222222222222"
    await artifact.save(db=db)
    # Stored again with unchanged content: a new object, the same checksum.
    artifact.storage_id.value = "0b9f9a8c-0000-4000-8000-000000000003"
    await artifact.save(db=db)

    registry.schema.register_schema(schema=SchemaRoot(nodes=[FILE_CONTRACT]), branch=default_branch.name)
    contract = await Node.init(db=db, schema="TestingFileContract")
    await contract.new(
        db=db,
        file_name="contract.pdf",
        checksum="4444444444444444444444444444444444444444",
        file_size=12,
        file_type="application/pdf",
        storage_id="0b9f9a8c-0000-4000-8000-000000000004",
    )
    await contract.save(db=db)
    branch = await create_branch(db=db, branch_name="contract-renewal")
    contract_in_branch = await NodeManager.get_one(db=db, id=contract.id, branch=branch, raise_on_error=True)
    contract_in_branch.storage_id.value = "0b9f9a8c-0000-4000-8000-000000000005"
    contract_in_branch.checksum.value = "5555555555555555555555555555555555555555"
    await contract_in_branch.save(db=db)

    repository = StoredObjectRepository(db=db)
    recorded = {
        index: await repository.get_recorded_checksums(identifier=f"0b9f9a8c-0000-4000-8000-00000000000{index}")
        for index in range(1, 7)
    }

    assert recorded == {
        1: frozenset({"11111111111111111111111111111111"}),
        2: frozenset({"22222222222222222222222222222222"}),
        3: frozenset({"22222222222222222222222222222222"}),
        4: frozenset({"4444444444444444444444444444444444444444"}),
        5: frozenset({"5555555555555555555555555555555555555555"}),
        6: frozenset(),
    }
