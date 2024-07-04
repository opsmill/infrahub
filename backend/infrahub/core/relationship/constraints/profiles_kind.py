from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub.core import registry
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.relationship.model import Relationship, RelationshipManager
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class RelationshipProfilesKindConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Optional[Branch] = None):
        self.db = db
        self.branch = branch
        self.schema_branch = registry.schema.get_schema_branch(branch.name if branch else registry.default_branch)

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes) -> None:
        if relm.name != "profiles" or not isinstance(node_schema, NodeSchema):
            return

        profile_relationships = await relm.get_relationships(db=self.db)
        if len(profile_relationships) == 0:
            return

        allowed_profile_kinds = {f"Profile{node_schema.kind}"}

        for generic_schema_name in node_schema.inherit_from:
            generic_schema = self.schema_branch.get(name=generic_schema_name, duplicate=False)
            try:
                generic_profiles_schema = generic_schema.get_relationship(name="profiles")
            except ValueError:
                continue
            allowed_profile_kinds.add(generic_profiles_schema.peer)

        illegal_profile_relationships: list[Relationship] = []
        for profile_relationship in profile_relationships:
            if profile_relationship.get_kind() not in allowed_profile_kinds:
                illegal_profile_relationships.append(profile_relationship)
        if not illegal_profile_relationships:
            return

        error_str_parts = [
            f"peer {p_rel.get_peer_id()} is of kind {p_rel.get_kind()}" for p_rel in illegal_profile_relationships
        ]
        error_str = ", ".join(error_str_parts)
        error_str += f". only {allowed_profile_kinds} are allowed"
        raise ValidationError({"profiles": error_str})
