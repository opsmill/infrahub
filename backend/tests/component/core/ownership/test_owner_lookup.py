import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.ownership.input import OwnerInputParser
from infrahub.core.ownership.models import NODE_HOLDER, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.ownership import add_node


def _parser(db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch) -> OwnerInputParser:
    return OwnerInputParser(schema_branch=schema_branch, lookup=OwnershipRepository(db=db, branch=branch, at=None))


async def test_parse_finds_accounts_and_account_groups_in_the_database(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-emea")
    other_group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-emea")
    account = await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="jane", password="a-password")
    parser = _parser(db=db, branch=default_branch, schema_branch=register_core_models_schema)

    states = await parser.parse(
        node_metadata={
            "owners": [
                {"id": group.id},
                {"kind": InfrahubKind.ACCOUNTGROUP, "hfid": ["network-emea"]},
                {"id": account.id},
                {"kind": InfrahubKind.ACCOUNT, "hfid": ["jane"]},
            ]
        },
        schema=register_core_models_schema.get(name=InfrahubKind.TAG, duplicate=False),
    )

    assert states == {NODE_HOLDER: StoredOwnerState(owner_ids=(group.id, other_group.id, account.id))}


async def test_parse_refuses_owners_that_the_database_does_not_hold_as_accounts_or_account_groups(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    tag = await add_node(db=db, kind=InfrahubKind.TAG, name="blue")
    deleted_group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-emea")
    await deleted_group.delete(db=db)
    parser = _parser(db=db, branch=default_branch, schema_branch=register_core_models_schema)
    schema = register_core_models_schema.get(name=InfrahubKind.TAG, duplicate=False)

    with pytest.raises(ValidationError) as tag_exc:
        await parser.parse(node_metadata={"owners": [{"id": tag.id}]}, schema=schema)
    with pytest.raises(ValidationError) as deleted_id_exc:
        await parser.parse(node_metadata={"owners": [{"id": deleted_group.id}]}, schema=schema)
    with pytest.raises(ValidationError) as deleted_hfid_exc:
        await parser.parse(
            node_metadata={"owners": [{"kind": InfrahubKind.ACCOUNTGROUP, "hfid": ["dc-emea"]}]}, schema=schema
        )

    assert tag_exc.value.message == (
        f"Only an account or an account group can be an owner, not: {tag.id} at node_metadata.owners"
    )
    assert deleted_id_exc.value.message == f"Owner not found: {deleted_group.id} at node_metadata.owners"
    assert deleted_hfid_exc.value.message == "Owner not found: CoreAccountGroup ['dc-emea'] at node_metadata.owners"
