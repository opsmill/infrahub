from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.permissions.constants import PermissionDecisionFlag
from tests.helpers.graphql import graphql_query

from .conftest import CIRCUIT_KIND, ServicePortalData, TemplateEntry, create_account, create_node, session_for

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

QUERY = """
query {
    ServiceCatalog {
        count
        entries { id name description icon tags target_kind mode fields generators template_id }
    }
}
"""


@dataclass
class CatalogVisibilityCase:
    name: str
    create_decision: PermissionDecisionFlag | None
    expected_names: list[str]


@pytest.mark.parametrize(
    "case",
    [
        CatalogVisibilityCase(
            name="allow_other",
            create_decision=PermissionDecisionFlag.ALLOW_OTHER,
            expected_names=["Circuit"],
        ),
        CatalogVisibilityCase(
            name="allow_all",
            create_decision=PermissionDecisionFlag.ALLOW_ALL,
            expected_names=["Circuit"],
        ),
        CatalogVisibilityCase(
            name="allow_default", create_decision=PermissionDecisionFlag.ALLOW_DEFAULT, expected_names=[]
        ),
        CatalogVisibilityCase(name="no_create_permission", create_decision=None, expected_names=[]),
    ],
    ids=lambda case: case.name,
)
async def test_catalog_lists_review_entries_the_caller_may_request(
    db: InfrahubDatabase, service_portal_data: ServicePortalData, case: CatalogVisibilityCase
) -> None:
    account = await create_account(db=db, name=f"account-{case.name}", create_decision=case.create_decision)

    result = await graphql_query(query=QUERY, db=db, account_session=session_for(account))

    assert not result.errors
    assert result.data
    catalog = result.data["ServiceCatalog"]
    assert sorted(entry["name"] for entry in catalog["entries"]) == case.expected_names
    assert catalog["count"] == len(case.expected_names)


async def test_catalog_entry_fields(db: InfrahubDatabase, service_portal_data: ServicePortalData) -> None:
    data = service_portal_data

    result = await graphql_query(query=QUERY, db=db, account_session=session_for(data.requester))

    assert not result.errors
    assert result.data
    assert result.data["ServiceCatalog"] == {
        "count": 1,
        "entries": [
            {
                "id": data.entry.id,
                "name": "Circuit",
                "description": "A circuit",
                "icon": "mdi:cable-data",
                "tags": ["network"],
                "target_kind": CIRCUIT_KIND,
                "mode": "review",
                "fields": ["name", "speed", "vlan", "provider", "description"],
                "generators": ["zeta", "alpha"],
                "template_id": None,
            }
        ],
    }


async def test_catalog_entry_template(
    db: InfrahubDatabase, service_portal_data: ServicePortalData, template_entry: TemplateEntry
) -> None:
    result = await graphql_query(query=QUERY, db=db, account_session=session_for(service_portal_data.requester))

    assert not result.errors
    assert result.data
    templates = {entry["name"]: entry["template_id"] for entry in result.data["ServiceCatalog"]["entries"]}
    assert templates == {"Circuit": None, "Gold Circuit": template_entry.template.id}


async def test_catalog_ignores_entries_staged_on_a_branch(
    db: InfrahubDatabase, service_portal_data: ServicePortalData
) -> None:
    staging = await create_branch(branch_name="staging", db=db)
    await create_node(
        db=db,
        kind=InfrahubKind.SERVICECATALOGENTRY,
        branch=staging,
        name="Staged Circuit",
        target_kind=CIRCUIT_KIND,
        fields=["name"],
    )

    result = await graphql_query(
        query=QUERY, db=db, branch=staging, account_session=session_for(service_portal_data.requester)
    )

    assert not result.errors
    assert result.data
    assert sorted(entry["name"] for entry in result.data["ServiceCatalog"]["entries"]) == ["Circuit"]


async def test_catalog_skips_entries_whose_target_kind_is_not_a_node(
    db: InfrahubDatabase, service_portal_data: ServicePortalData
) -> None:
    await create_node(
        db=db, kind=InfrahubKind.SERVICECATALOGENTRY, name="Ghost", target_kind="TestingGhost", fields=["name"]
    )

    result = await graphql_query(query=QUERY, db=db, account_session=session_for(service_portal_data.requester))

    assert not result.errors
    assert result.data
    assert sorted(entry["name"] for entry in result.data["ServiceCatalog"]["entries"]) == ["Circuit"]
