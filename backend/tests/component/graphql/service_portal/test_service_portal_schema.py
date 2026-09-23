from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.services import InfrahubServices
from tests.helpers.graphql import graphql_mutation, graphql_query

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

CREATE_ENTRY = """
mutation {
    CoreServiceCatalogEntryCreate(data: {
        name: {value: "Dedicated Internet"}
        target_kind: {value: "ServiceDedicatedInternet"}
        generators: {value: ["zeta", "alpha", "mid"]}
        fields: {value: ["name", "location", "bandwidth"]}
    }) {
        ok
        object { id mode { value } generators { value } fields { value } }
    }
}
"""

UPDATE_ENTRY = """
mutation($id: String!) {
    CoreServiceCatalogEntryUpdate(data: {id: $id, fields: {value: ["bandwidth", "name"]}, mode: {value: "direct"}}) {
        ok
        object { mode { value } fields { value } }
    }
}
"""

INPUT_FIELDS = """
query($name: String!) {
    __type(name: $name) { inputFields { name } }
}
"""


async def test_catalog_entry_create_and_update(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch, create_test_admin: Node
) -> None:
    service = await InfrahubServices.new(database=db)
    session = AccountSession(authenticated=True, account_id=create_test_admin.id, auth_type=AuthType.API)

    created = await graphql_mutation(query=CREATE_ENTRY, db=db, service=service, account_session=session)
    assert not created.errors
    assert created.data
    entry = created.data["CoreServiceCatalogEntryCreate"]["object"]
    assert entry["mode"]["value"] == "review"
    assert entry["generators"]["value"] == ["zeta", "alpha", "mid"]
    assert entry["fields"]["value"] == ["name", "location", "bandwidth"]

    updated = await graphql_mutation(
        query=UPDATE_ENTRY, db=db, service=service, account_session=session, variables={"id": entry["id"]}
    )
    assert not updated.errors
    assert updated.data
    assert updated.data["CoreServiceCatalogEntryUpdate"]["object"] == {
        "mode": {"value": "direct"},
        "fields": {"value": ["bandwidth", "name"]},
    }


async def test_service_request_inputs_exclude_backend_owned_fields(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    backend_owned = {"status", "message", "branch", "task_id", "service", "proposed_change"}
    for input_type in ("CoreServiceRequestCreateInput", "CoreServiceRequestUpdateInput"):
        result = await graphql_query(query=INPUT_FIELDS, db=db, variables={"name": input_type})
        assert not result.errors
        assert result.data
        names = {field["name"] for field in result.data["__type"]["inputFields"]}
        assert "inputs" in names
        assert not backend_owned & names, input_type


async def test_service_portal_nodes_registered(register_core_models_schema: None, default_branch: Branch) -> None:
    entry = registry.schema.get_node_schema(name=InfrahubKind.SERVICECATALOGENTRY, branch=default_branch)
    request = registry.schema.get_node_schema(name=InfrahubKind.SERVICEREQUEST, branch=default_branch)
    assert entry.branch.value == "aware"
    assert request.branch.value == "agnostic"
    assert not entry.include_in_menu
