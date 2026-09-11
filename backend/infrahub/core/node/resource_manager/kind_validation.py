from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema import GenericSchema
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def validate_allocated_kind(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    pool_kind: str,
    pool_name: str,
    requested_kind: str | None,
    peer_kind: str | None,
) -> None:
    """Guard an explicitly requested allocation kind against the kind it must satisfy.

    IP pools carry a default target kind (`default_address_type` / `default_prefix_type`), and a
    caller may override it per allocation. The override is only legal when the resulting node can
    actually sit where it is being put: either it is `peer_kind` itself, or `peer_kind` is a
    generic that the requested kind inherits from.

    `peer_kind` is a relationship's declared peer when allocating through a relationship, and the
    builtin IP generic when allocating through the standalone pool mutations — hence the neutral
    name and wording.

    Only the *explicitly requested* kind is validated. The pool's own default is deliberately left
    alone: re-validating it would newly reject pools whose default is not in the peer's `used_by`
    and break working setups.

    A `None` `peer_kind` means the caller has no peer context (`Node.new()`, migrations) and the
    allocation stays unconstrained, as it was before this validation existed.

    Raises:
        ValidationError: when the requested kind cannot satisfy the peer.

    """
    if requested_kind is None or peer_kind is None or requested_kind == peer_kind:
        return

    peer_schema = db.schema.get(name=peer_kind, branch=branch, duplicate=False)

    if isinstance(peer_schema, GenericSchema):
        if requested_kind in peer_schema.used_by:
            return
        allowed_kinds = sorted(peer_schema.used_by)
    else:
        allowed_kinds = [peer_kind]

    raise ValidationError(
        input_value=(
            f"{pool_kind}: {pool_name} | {requested_kind!r} is not a valid kind to allocate for "
            f"{peer_kind!r}, allowed kinds are {allowed_kinds}."
        )
    )
