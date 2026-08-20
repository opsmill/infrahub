"""Find-or-create local account groups for one external login's matched claims.

For each effective name yielded by the configured claim filter, the corresponding
account group is either looked up or created, and the logging-in account is added as a member.
Creation goes through the shared node-creation path, so the name uniqueness constraint is
enforced under the same object lock as every other group mutation; a concurrent creation that
wins the race is reused rather than duplicated. On creation, the configured provider name is
written verbatim to the new group's `origin` attribute; on reuse, `origin` is left untouched.
Names that fail the local-name invariants (empty / whitespace-only) are logged and skipped; the
login completes.

A per-login cap bounds how many new groups one login can spawn. Memberships to already-existing
groups do NOT consume cap budget. Once the cap is reached, every subsequent matching claim that
would have required a fresh creation is dropped and the login still completes.

Auto-group audit events are emitted via an injected emitter; pass the disabled emitter
to suppress emission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import create_node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from infrahub.exceptions import UniquenessViolationError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from .emitter import AutoCreateEventEmitter
    from .filter import ClaimFilter

log = get_logger()


@dataclass(frozen=True, slots=True)
class FindOrCreateResult:
    """Outcome of `AutoCreatedGroupsService._find_or_create`.

    - `group is None`: a non-`CoreAccountGroup` row already holds the name; the claim is skipped.
    - `group is not None, was_created is False`: an existing reusable group was found.
    - `group is not None, was_created is True`: a new group was inserted by this call.
    """

    group: CoreAccountGroup | Node | None
    was_created: bool


class AutoCreatedGroupsService:
    """Find-or-create CoreAccountGroup rows from external claims and assign membership."""

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        account: CoreAccount,
        provider_name: str,
        max_per_login: int,
        emitter: AutoCreateEventEmitter,
        node_manager: type[NodeManager] = NodeManager,
    ) -> None:
        self._db = db
        self._account = account
        self._provider_name = provider_name
        self._max_per_login = max_per_login
        self._emitter = emitter
        self._node_manager = node_manager

    async def assign(
        self,
        claims: Iterable[str],
        claim_filter: ClaimFilter,
    ) -> tuple[str, ...]:
        """Find-or-create groups for `claims` under `claim_filter` and add the account as member.

        New-creation work is bounded by the per-login cap configured at construction. When the
        budget is exhausted, claims that would require a brand-new group are silently dropped.
        Existing-group reuse continues uncapped.

        A claim whose persistence fails is isolated: the error is logged, a rejected event is
        emitted, and the remaining claims are still applied. One failing claim never aborts the
        login or drops the other groups.

        Returns the effective names that resulted in a successful membership, in matching order.
        An empty tuple means auto-creation produced no memberships.
        """
        if not claim_filter.is_active:
            return ()

        granted: list[str] = []
        new_creations = 0
        dropped: list[str] = []
        seen: set[str] = set()

        for claim in claims:
            match = claim_filter.match_for(claim)
            if match is None:
                continue
            name = match.name
            if not name or name.isspace():
                log.info(
                    "auth_groups.skip_invalid_effective_name",
                    provider_name=self._provider_name,
                    effective_name=name,
                )
                await self._emitter.claim_rejected(claim=claim)
                continue
            if name in seen:
                continue
            seen.add(name)

            try:
                if new_creations < self._max_per_login:
                    result = await self._find_or_create(name=name, source_pattern=match.source_pattern)
                    group = result.group
                    if group is None:
                        continue
                    if result.was_created:
                        new_creations += 1
                else:
                    # Cap exhausted: only allow reuse of an existing row. A claim that would
                    # require a fresh creation is dropped.
                    existing = await self._lookup_by_name(name)
                    if existing is None:
                        log.info(
                            "auth_groups.skip_claim_over_per_login_cap",
                            provider_name=self._provider_name,
                            effective_name=name,
                            max_per_login=self._max_per_login,
                        )
                        dropped.append(claim)
                        continue
                    group = self._reuse_or_skip(name, existing)
                    if group is None:
                        continue

                if await self._add_member(group):
                    granted.append(name)
            except Exception:
                # One claim's persistence failing must not abort the login: log it, record a rejected
                # event, and keep applying the remaining claims.
                log.exception(
                    "auth_groups.claim_processing_failed",
                    provider_name=self._provider_name,
                    effective_name=name,
                )
                await self._emitter.claim_rejected(claim=claim)

        if dropped:
            await self._emitter.cap_breached(cap_value=self._max_per_login, dropped_claims=dropped)
        return tuple(granted)

    async def _find_or_create(self, *, name: str, source_pattern: str) -> FindOrCreateResult:
        """Find a `CoreAccountGroup` named `name`, or create one with `origin = provider_name`.

        Creation goes through the shared node-creation path, so the name uniqueness constraint is
        enforced under the same object lock as every other group mutation. A concurrent creation
        that wins the race surfaces here as a uniqueness violation and is resolved by reusing the
        group that won.

        Raises:
            UniquenessViolationError: when the create races and no reusable group can be found afterwards.
            ValidationError: when creation fails for any other reason; such errors are not treated as a race.

        """
        existing = await self._lookup_by_name(name)
        if existing is not None:
            return FindOrCreateResult(group=self._reuse_or_skip(name, existing), was_created=False)

        branch = await registry.get_branch(db=self._db)
        try:
            group = await create_node(
                data={"name": name, "origin": self._provider_name},
                db=self._db,
                branch=branch,
                schema=CoreAccountGroup,
            )
        except UniquenessViolationError:
            existing = await self._lookup_by_name(name)
            if existing is None:
                raise
            return FindOrCreateResult(group=self._reuse_or_skip(name, existing), was_created=False)

        await self._emitter.created(group=group, source_pattern=source_pattern)
        return FindOrCreateResult(group=group, was_created=True)

    async def _lookup_by_name(self, name: str) -> Node | None:
        """Return any `CoreGroup`-derived row named `name`, or None."""
        results = await self._node_manager.query(
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

    async def _add_member(self, group: CoreAccountGroup | Node) -> bool:
        """Add the logging-in account to `group` as a member, idempotently.

        Returns `True` if the account is a member of `group` after this call (whether added
        here or already present), `False` if the group disappeared before membership could
        be established.
        """
        refreshed = await self._node_manager.get_one(db=self._db, id=group.id, prefetch_relationships=True)
        if refreshed is None:
            log.warning("auth_groups.group_disappeared_after_create", group_id=group.id)
            return False
        members_rel = refreshed.get_relationship(name="members")
        members = await members_rel.get_peers(db=self._db, branch_agnostic=True, peer_type=CoreAccount)
        if self._account.id in members:
            return True
        await members_rel.add(db=self._db, data={"id": self._account.id})
        await members_rel.save(db=self._db)
        return True
