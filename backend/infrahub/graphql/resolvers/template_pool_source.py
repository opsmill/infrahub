from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import BranchSupportType
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.core.schema.node_schema import NodeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class TemplatePoolSourceResolver:
    """Resolves pool source information for template relationship properties.

    When a template has a _from_resource_pool relationship set for a given relationship
    (e.g. primary_ip_from_resource_pool) but no direct peer on the main relationship,
    this resolver returns the pool node as the "source" property of that relationship.
    """

    async def get_pool_source(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        parent_id: str,
        source_kind: str,
        node_schema: NodeSchema,
        rel_name: str,
        property_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not node_schema.is_template_schema or not property_fields:
            return None

        pool_rel_name = f"{rel_name}{RESOURCE_POOL_REL_SUFFIX}"
        try:
            pool_rel_schema = node_schema.get_relationship(pool_rel_name)
        except ValueError:
            return None

        async with db.start_session(read_only=True) as dbs:
            pool_rels = await NodeManager.query_peers(
                db=dbs,
                ids=[parent_id],
                source_kind=source_kind,
                schema=pool_rel_schema,
                filters={},
                at=at,
                branch=branch,
                branch_agnostic=pool_rel_schema.branch is BranchSupportType.AGNOSTIC,
                fetch_peers=True,
            )
        if not pool_rels:
            return None

        pool_rel = pool_rels[0]
        response: dict[str, Any] = {"node": None, "properties": {}}

        if "source" in property_fields:
            source_fields = property_fields.get("source", {})
            async with db.start_session(read_only=True) as dbs:
                pool_peer = await pool_rel.get_peer(db=dbs)
                response["properties"]["source"] = await pool_peer.to_graphql(db=dbs, fields=source_fields or None)

        return response
