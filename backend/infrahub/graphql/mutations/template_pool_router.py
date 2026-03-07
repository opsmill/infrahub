from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.schema.template_schema import TemplateSchema

POOL_PEER_KINDS = {InfrahubKind.IPADDRESSPOOL, InfrahubKind.IPPREFIXPOOL}


class TemplatePoolHandler:
    """Routes pool-eligible relationship data to the correct internal relationship.

    For template mutations, a user can provide a pool reference via ``from_pool``
    on a regular relationship field (e.g., ``primary_ip: { from_pool: { id: "..." } }``).
    This handler detects the ``from_pool`` key and moves the data to the internal
    ``_from_resource_pool`` relationship, using the pool's ``id`` as the relationship peer.
    """

    @staticmethod
    def get_pool_eligible_relationships(schema: TemplateSchema) -> dict[str, str]:
        """Return a mapping of relationship name -> pool relationship name for pool-eligible relationships.

        A relationship pair is only eligible if:
        - A non-suffixed relationship exists (e.g., "prefix")
        - A corresponding "_from_resource_pool" relationship exists (e.g., "prefix_from_resource_pool")
        - The pool relationship's peer is one of the known pool kinds
        """
        eligible = {}
        pool_rel_names = {rel.name for rel in schema.relationships if rel.name.endswith(RESOURCE_POOL_REL_SUFFIX)}

        for rel in schema.relationships:
            if rel.name.endswith(RESOURCE_POOL_REL_SUFFIX):
                continue
            pool_rel_name = f"{rel.name}{RESOURCE_POOL_REL_SUFFIX}"
            if pool_rel_name not in pool_rel_names:
                continue
            pool_rel = schema.get_relationship(pool_rel_name)
            if pool_rel.peer in POOL_PEER_KINDS:
                eligible[rel.name] = pool_rel_name
        return eligible

    @staticmethod
    def route_relationships(
        data: dict[str, Any],
        schema: TemplateSchema,
    ) -> dict[str, Any]:
        """Route relationship data to the correct internal relationship based on from_pool presence.

        For pool-eligible relationships on templates, if the user provides ``from_pool``
        in the relationship data, the pool reference is extracted and moved to the
        ``_from_resource_pool`` relationship key. The direct relationship is cleared.

        If ``from_pool`` is not present (just ``id`` or ``hfid``), the data stays on the
        direct relationship and the pool relationship is cleared.
        """
        eligible = TemplatePoolHandler.get_pool_eligible_relationships(schema)

        for rel_name, pool_rel_name in eligible.items():
            if rel_name not in data:
                continue

            rel_data = data[rel_name]

            # When the user sends null, clear both the direct and pool relationships
            if rel_data is None:
                data[pool_rel_name] = None
                continue

            if not isinstance(rel_data, dict):
                continue

            from_pool = rel_data.get("from_pool")
            has_direct = rel_data.get("id") is not None or rel_data.get("hfid") is not None
            if from_pool is not None and has_direct:
                raise ValidationError(
                    input_value=f"Cannot specify both a direct reference and from_pool on '{rel_name}'"
                )
            if from_pool is not None:
                # Route to the pool relationship using the pool's id from from_pool
                data[pool_rel_name] = {"id": from_pool["id"]}
                data[rel_name] = None
            # Direct relationship — clear the pool counterpart to allow swapping
            elif pool_rel_name not in data:
                data[pool_rel_name] = None

        return data
