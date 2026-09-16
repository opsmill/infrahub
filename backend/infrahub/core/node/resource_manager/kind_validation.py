from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from infrahub.core.schema import GenericSchema
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

PoolKind = Literal["IPAddressPool", "IPPrefixPool"]


def validate_allocated_kind(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    pool_kind: PoolKind,
    pool_name: str,
    requested_kind: str | None,
    peer_kind: str | None,
) -> None:
    """Guard an explicitly requested allocation kind against the kind it must satisfy.

    Legal when `peer_kind` is a node and the requested kind is `peer_kind` itself, or when
    `peer_kind` is a generic and the requested kind implements it. A generic is never allocatable,
    including as its own peer. The pool's own default is deliberately not validated: doing so
    would newly reject pools whose default is outside the peer's `used_by`. A `None` `peer_kind`
    leaves the allocation unconstrained.

    Raises:
        ValidationError: when the requested kind cannot satisfy the peer.

    """
    if requested_kind is None or peer_kind is None:
        return

    peer_schema = db.schema.get(name=peer_kind, branch=branch, duplicate=False)

    if isinstance(peer_schema, GenericSchema):
        if requested_kind in peer_schema.used_by:
            return
        allowed_kinds = sorted(peer_schema.used_by)
    else:
        if requested_kind == peer_kind:
            return
        allowed_kinds = [peer_kind]

    raise ValidationError(
        input_value=(
            f"{pool_kind}: {pool_name} | {requested_kind!r} is not a valid kind to allocate for "
            f"{peer_kind!r}, allowed kinds are {allowed_kinds}."
        )
    )
