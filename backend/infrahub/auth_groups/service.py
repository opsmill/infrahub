"""`AutoCreatedGroupsService` — find-or-create local `CoreAccountGroup` rows for one external
login's matched claims and add the logging-in account as a member.

For each effective name yielded by the configured `ClaimFilter`, the corresponding
`CoreAccountGroup` is either looked up or created atomically, and the logging-in account is
added as a member. Concurrent first-logins for the same brand-new claim are serialized through
the injected lock registry so exactly one row is produced per name. On creation, the configured
provider name is written verbatim to the new group's `origin` attribute; on reuse, `origin` is
left untouched. Names that fail the local-name invariants (empty / whitespace-only) are logged
and skipped; the login completes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.lock import InfrahubLockRegistry

    from .filter import ClaimFilter

log = get_logger()


class AutoCreatedGroupsService:
    """Find-or-create CoreAccountGroup rows from external claims and assign membership."""

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        account: Node,
        provider_name: str,
        lock_registry: InfrahubLockRegistry,
    ) -> None:
        self._db = db
        self._account = account
        self._provider_name = provider_name
        self._lock_registry = lock_registry

    async def assign(self, claims: Iterable[str], claim_filter: ClaimFilter) -> tuple[str, ...]:
        """Find-or-create groups for `claims` under `claim_filter` and add the account as member.

        Returns the effective names that resulted in a successful membership, in matching order.
        An empty tuple means no claim matched the filter or every matched claim was skipped.
        """
        if not claim_filter.is_active:
            return ()

        granted: list[str] = []
        for name in claim_filter.names_for(claims):
            if not name or name.isspace():
                log.info(
                    "auth_groups.skip_invalid_effective_name",
                    provider_name=self._provider_name,
                    effective_name=name,
                )
                continue

            group = await self._find_or_create(name)
            if group is None:
                continue

            await self._add_member(group)
            granted.append(name)

        return tuple(granted)

    async def _find_or_create(self, name: str) -> CoreAccountGroup | Node | None:
        """Find a `CoreAccountGroup` named `name`, or create one with `origin = provider_name`.

        Serialized through the distributed lock registry under the `auto-create-group` namespace.
        Returns `None` when a non-`CoreAccountGroup` `CoreGroup`-derived row already exists under
        that name.
        """
        existing = await self._lookup_by_name(name)
        if existing is not None:
            return self._reuse_or_skip(name, existing)

        lock_key = f"auto-create-group:{name}"
        async with self._lock_registry.get(name=lock_key, namespace="auto-create-group"):
            existing = await self._lookup_by_name(name)
            if existing is not None:
                return self._reuse_or_skip(name, existing)

            group = await Node.init(db=self._db, schema=InfrahubKind.ACCOUNTGROUP)
            await group.new(db=self._db, name=name, origin=self._provider_name)
            await group.save(db=self._db)
            return group

    async def _lookup_by_name(self, name: str) -> Node | None:
        """Return any `CoreGroup`-derived row named `name`, or None."""
        results = await NodeManager.query(
            db=self._db,
            schema=InfrahubKind.GENERICGROUP,
            filters={"name__value": name},
            limit=1,
        )
        return results[0] if results else None

    def _reuse_or_skip(self, name: str, existing: Node) -> Node | None:
        """Return `existing` if it is a reusable `CoreAccountGroup`; otherwise log and skip."""
        if existing.get_kind() == InfrahubKind.ACCOUNTGROUP:
            return existing
        log.info(
            "auth_groups.skip_name_collision_with_existing_group",
            provider_name=self._provider_name,
            effective_name=name,
            existing_kind=existing.get_kind(),
        )
        return None

    async def _add_member(self, group: CoreAccountGroup | Node) -> None:
        """Add the logging-in account to `group` as a member, idempotently."""
        refreshed = await NodeManager.get_one(db=self._db, id=group.id, prefetch_relationships=True)
        if refreshed is None:
            log.warning("auth_groups.group_disappeared_after_create", group_id=group.id)
            return
        members_rel = refreshed.get_relationship(name="members")
        members = await members_rel.get_peers(db=self._db, branch_agnostic=True, peer_type=CoreAccount)
        if self._account.id in members:
            return
        await members_rel.add(db=self._db, data=self._account)
        await members_rel.save(db=self._db)
