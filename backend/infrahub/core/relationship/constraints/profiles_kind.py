from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class RelationshipProfilesKindConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch
        self.schema_branch = registry.schema.get_schema_branch(branch.name if branch else registry.default_branch)

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes) -> None:
        if relm.name != "profiles" or not isinstance(node_schema, NodeSchema):
            return

        profile_relationships = await relm.get_relationships(db=self.db)
        if len(profile_relationships) == 0:
            return

        if not node_schema.generate_profile:
            raise ValidationError({"profiles": f"{node_schema.kind} does not allow profiles"})

        allowed_profile_kinds = {f"Profile{node_schema.kind}"}

        for generic_schema_name in node_schema.inherit_from:
            generic_schema = self.schema_branch.get(name=generic_schema_name, duplicate=False)
            if isinstance(generic_schema, GenericSchema) and generic_schema.generate_profile:
                allowed_profile_kinds.add(f"Profile{generic_schema.kind}")

        illegal_profile_nodes: list[Node] = []
        for profile_relationship in profile_relationships:
            peer_node = await profile_relationship.get_peer(db=self.db)
            if peer_node.get_kind() not in allowed_profile_kinds:
                illegal_profile_nodes.append(peer_node)
        if not illegal_profile_nodes:
            return

        error_str_parts = [f"peer {p_rel.get_id()} is of kind {p_rel.get_kind()}" for p_rel in illegal_profile_nodes]
        error_str = ", ".join(error_str_parts)
        error_str += f". only {sorted(allowed_profile_kinds)} are allowed"
        raise ValidationError({"profiles": error_str})
