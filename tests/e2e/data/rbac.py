"""RBAC slice: accounts, account roles, permissions and account groups.

Faithful transcription of ``models/infrastructure_edge.py``:

* data tables ``GLOBAL_PERMISSIONS`` / ``OBJECT_PERMISSIONS`` /
  ``ACCOUNT_ROLES`` / ``ACCOUNTS`` / ``ACCOUNT_GROUPS`` (lines 728-783),
* ``prepare_permissions`` (line 2211), ``prepare_account_roles`` (line 2231),
  ``prepare_accounts`` (line 2242), ``map_permissions_to_roles`` (line 2256)
  and ``map_user_and_roles_to_groups`` (line 2317),
* with the batch boundaries of ``run()`` (lines 2574-2596): one batch for
  permissions + roles, one for accounts + groups, one for the role->permission
  mapping and one for the group->roles/members mapping.

Like the script, the global permissions are only FETCHED by hfid (they
pre-exist from server initialization) and object permissions are fetched
first, created only when missing (in practice only ``allow_any`` is created).
The script's ``object_permissions == "__all__"`` branch of
``map_permissions_to_roles`` is dead code (no role uses it) and is not
transcribed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import NodeNotFoundError

from data.handles import RbacHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.batch import InfrahubBatchSync
    from infrahub_sdk.node import InfrahubNodeSync

BRANCH = "main"

# action / decision (models/infrastructure_edge.py lines 728-736)
GLOBAL_PERMISSIONS = (
    {"action": "edit_default_branch", "decision": 6},
    {"action": "merge_branch", "decision": 6},
    {"action": "merge_proposed_change", "decision": 6},
    {"action": "manage_schema", "decision": 6},
    {"action": "manage_accounts", "decision": 6},
    {"action": "manage_permissions", "decision": 6},
    {"action": "manage_repositories", "decision": 6},
)

# store key -> namespace / name / action / decision (lines 738-743)
OBJECT_PERMISSIONS = {
    "deny_any": {"namespace": "*", "name": "*", "action": "any", "decision": 1},
    "allow_any": {"namespace": "*", "name": "*", "action": "any", "decision": 6},
    "allow_branches": {"namespace": "*", "name": "*", "action": "any", "decision": 4},
    "view_any": {"namespace": "*", "name": "*", "action": "view", "decision": 6},
}

# name / global_permissions / object_permissions (lines 745-754)
ACCOUNT_ROLES = (
    {"name": "Administrator", "global_permissions": "__all__", "object_permissions": ["allow_any"]},
    {"name": "Global read-only", "global_permissions": None, "object_permissions": ["deny_any", "view_any"]},
    {
        "name": "Global read-write",
        "global_permissions": ["edit_default_branch", "merge_branch", "merge_proposed_change"],
        "object_permissions": ["allow_any"],
    },
    {"name": "Own branches read-write", "global_permissions": None, "object_permissions": ["allow_branches"]},
)

# name / label / password / account_type (lines 756-768)
ACCOUNTS = (
    {"name": "pop-builder", "label": "pop-builder", "password": "Password123", "account_type": "Script"},
    {"name": "crm-sync", "label": "CRM Synchronization", "password": "Password123", "account_type": "Script"},
    {"name": "jbauer", "label": "Jack Bauer", "password": "Password123", "account_type": "User"},
    {"name": "cobrian", "label": "Chloe O'Brian", "password": "Password123", "account_type": "User"},
    {"name": "dpalmer", "label": "David Palmer", "password": "Password123", "account_type": "User"},
    {"name": "sudo", "label": "Sue Dough", "password": "Password123", "account_type": "User"},
    {"name": "elawson", "label": "Emily Lawson", "password": "Password123", "account_type": "User"},
    {"name": "jthompson", "label": "Jacob Thompson", "password": "Password123", "account_type": "User"},
    {"name": "shernandez", "label": "Sofia Hernandez", "password": "Password123", "account_type": "User"},
    {"name": "rpatel", "label": "Ryan Patel", "password": "Password123", "account_type": "User"},
    {"name": "ocarter", "label": "Olivia Carter", "password": "Password123", "account_type": "User"},
)

# store key -> name / roles / members (lines 770-783)
ACCOUNT_GROUPS = {
    "administrators": {
        "name": "Administrators",
        "roles": ["Administrator"],
        "members": ["sudo", "pop-builder", "crm-sync"],
    },
    "ops-team": {
        "name": "Operations Team",
        "roles": ["Global read-only"],
        "members": ["jbauer", "elawson", "jthompson"],
    },
    "eng-team": {
        "name": "Engineering Team",
        "roles": ["Global read-write"],
        "members": ["cobrian", "shernandez", "rpatel"],
    },
    "arch-team": {
        "name": "Architecture Team",
        "roles": ["Own branches read-write"],
        "members": ["dpalmer", "ocarter"],
    },
}


def _prepare_permissions(client: InfrahubClientSync, batch: InfrahubBatchSync) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_permissions`` (lines 2211-2228)."""
    permissions: dict[str, InfrahubNodeSync] = {}
    for perm in GLOBAL_PERMISSIONS:
        obj = client.get(
            branch=BRANCH,
            kind="CoreGlobalPermission",
            hfid=[perm["action"], str(perm["decision"])],
        )
        permissions[perm["action"]] = obj

    for key, perm in OBJECT_PERMISSIONS.items():
        try:
            obj = client.get(
                branch=BRANCH,
                kind="CoreObjectPermission",
                hfid=[perm["namespace"], perm["name"], perm["action"], str(perm["decision"])],
            )
        except NodeNotFoundError:
            obj = client.create(branch=BRANCH, kind="CoreObjectPermission", data=dict(perm))
            batch.add(task=obj.save, node=obj)
        permissions[key] = obj
    return permissions


def _prepare_account_roles(client: InfrahubClientSync, batch: InfrahubBatchSync) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_account_roles`` (lines 2231-2239)."""
    roles: dict[str, InfrahubNodeSync] = {}
    for role in ACCOUNT_ROLES:
        obj = client.create(branch=BRANCH, kind="CoreAccountRole", data={"name": role["name"]})
        batch.add(task=obj.save, node=obj)
        roles[role["name"]] = obj
    return roles


def _prepare_accounts(
    client: InfrahubClientSync, batch: InfrahubBatchSync
) -> tuple[dict[str, InfrahubNodeSync], dict[str, InfrahubNodeSync]]:
    """Transcribes ``prepare_accounts`` (lines 2242-2253): accounts then account groups."""
    accounts: dict[str, InfrahubNodeSync] = {}
    for account in ACCOUNTS:
        obj = client.create(branch=BRANCH, kind="CoreAccount", data=dict(account))
        batch.add(task=obj.save, allow_upsert=True, node=obj)
        accounts[account["name"]] = obj

    groups: dict[str, InfrahubNodeSync] = {}
    for key, group in ACCOUNT_GROUPS.items():
        obj = client.create(branch=BRANCH, kind="CoreAccountGroup", data={"name": group["name"]})
        batch.add(task=obj.save, allow_upsert=True, node=obj)
        groups[key] = obj
    return accounts, groups


def _map_permissions_to_roles(
    roles: dict[str, InfrahubNodeSync],
    permissions: dict[str, InfrahubNodeSync],
    batch: InfrahubBatchSync,
) -> None:
    """Transcribes ``map_permissions_to_roles`` (lines 2256-2314)."""
    for role in ACCOUNT_ROLES:
        if not role["global_permissions"] and not role["object_permissions"]:
            continue

        obj = roles[role["name"]]
        obj.permissions.fetch()

        role_permissions: list[InfrahubNodeSync] = []
        if role["global_permissions"]:
            if role["global_permissions"] == "__all__":
                role_permissions.extend(permissions[perm["action"]] for perm in GLOBAL_PERMISSIONS)
            else:
                role_permissions.extend(permissions[name] for name in role["global_permissions"])
        if role["object_permissions"]:
            role_permissions.extend(permissions[name] for name in role["object_permissions"])

        obj.permissions.extend(role_permissions)
        batch.add(task=obj.save, node=obj)


def _map_user_and_roles_to_groups(
    groups: dict[str, InfrahubNodeSync],
    roles: dict[str, InfrahubNodeSync],
    accounts: dict[str, InfrahubNodeSync],
    batch: InfrahubBatchSync,
) -> None:
    """Transcribes ``map_user_and_roles_to_groups`` (lines 2317-2356)."""
    for group_key, group in ACCOUNT_GROUPS.items():
        updated = False
        obj = groups[group_key]

        if group["roles"]:
            obj.roles.fetch()
            obj.roles.extend(data=[roles[role] for role in group["roles"]])
            updated = True
        if group["members"]:
            obj.members.fetch()
            obj.members.extend(data=[accounts[member] for member in group["members"]])
            updated = True

        if updated:
            batch.add(task=obj.save, node=obj)


@pytest.fixture(scope="session")
def data_rbac(
    data_client: InfrahubClientSync,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> RbacHandle:
    """Accounts, roles, permissions and account groups of the demo dataset."""
    if infrahub_provisioned_externally:
        return RbacHandle.external()

    batch = data_client.create_batch()
    permissions = _prepare_permissions(client=data_client, batch=batch)
    roles = _prepare_account_roles(client=data_client, batch=batch)
    for _ in batch.execute():
        pass

    batch = data_client.create_batch()
    accounts, groups = _prepare_accounts(client=data_client, batch=batch)
    for _ in batch.execute():
        pass

    batch = data_client.create_batch()
    _map_permissions_to_roles(roles=roles, permissions=permissions, batch=batch)
    for _ in batch.execute():
        pass

    batch = data_client.create_batch()
    _map_user_and_roles_to_groups(groups=groups, roles=roles, accounts=accounts, batch=batch)
    for _ in batch.execute():
        pass

    return RbacHandle(
        accounts={key: node.id for key, node in accounts.items()},
        groups={key: node.id for key, node in groups.items()},
        roles={key: node.id for key, node in roles.items()},
        permissions={key: node.id for key, node in permissions.items()},
    )
