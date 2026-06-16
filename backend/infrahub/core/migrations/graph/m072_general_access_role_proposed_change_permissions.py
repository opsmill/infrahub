from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationInput, MigrationResult, get_migration_console
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccountRole, CoreObjectPermission
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()
console = get_migration_console()


GENERAL_ACCESS_ROLE_NAME = "General Access"

PROPOSED_CHANGE_PERMISSIONS = [
    ("Core", "ProposedChange", "proposed changes"),
    ("Core", "ChangeComment", "proposed change comments"),
    ("Core", "ChangeThread", "proposed change threads"),
    ("Core", "ThreadComment", "proposed change thread comments"),
]


async def _existing_pc_permissions(db: InfrahubDatabase, role: CoreAccountRole) -> set[tuple[str, str]]:
    peers = await role.permissions.get_peers(db=db, peer_type=CoreObjectPermission)
    existing: set[tuple[str, str]] = set()
    for peer in peers.values():
        if peer.get_kind() != InfrahubKind.OBJECTPERMISSION:
            continue
        action_value = peer.action.value
        decision_value = peer.decision.value
        action_str = action_value.value if hasattr(action_value, "value") else action_value
        decision_int = decision_value.value if hasattr(decision_value, "value") else decision_value
        if action_str != PermissionAction.ANY.value or decision_int != PermissionDecision.ALLOW_ALL.value:
            continue
        existing.add((peer.namespace.value, peer.name.value))
    return existing


class Migration072(ArbitraryMigration):
    name: str = "072_general_access_role_proposed_change_permissions"
    minimum_version: int = 71

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        roles = await NodeManager.query(
            db=db, schema=CoreAccountRole, filters={"name__value": GENERAL_ACCESS_ROLE_NAME}
        )
        if not roles:
            console.log(
                f"[yellow]No '{GENERAL_ACCESS_ROLE_NAME}' role found, skipping proposed change permission backfill[/yellow]"
            )
            return result
        role = roles[0]

        existing = await _existing_pc_permissions(db=db, role=role)
        new_permissions: list[Node] = []
        for namespace, name, label in PROPOSED_CHANGE_PERMISSIONS:
            if (namespace, name) in existing:
                continue
            permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
            await permission.new(
                db=db,
                name=name,
                namespace=namespace,
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOW_ALL.value,
                description=f"Allow a user to manage {label}",
            )
            await permission.save(db=db)
            new_permissions.append(permission)

        if not new_permissions:
            console.log(
                f"[green]'{GENERAL_ACCESS_ROLE_NAME}' role already has the expected proposed change permissions, nothing to do[/green]"
            )
            return result

        for permission in new_permissions:
            await role.permissions.add(db=db, data=permission)
        await role.permissions.save(db=db)
        console.log(
            f"[green]Added {len(new_permissions)} proposed change permission(s) to '{GENERAL_ACCESS_ROLE_NAME}' role[/green]"
        )

        return result
