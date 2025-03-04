from __future__ import annotations

from pydantic import Field

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema.basenode_schema import BaseNodeSchema


class ProfileSchema(BaseNodeSchema):
    inherit_from: list[str] = Field(
        default_factory=list,
        description="List of Generic Kind that this profile is inheriting from",
    )

    @property
    def is_node_schema(self) -> bool:
        return False

    @property
    def is_generic_schema(self) -> bool:
        return False

    @property
    def is_profile_schema(self) -> bool:
        return True

    @property
    def is_template_schema(self) -> bool:
        return False

    def get_labels(self) -> list[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""

        labels: list[str] = [self.kind] + self.inherit_from
        if self.namespace not in ["Schema", "Internal"] and InfrahubKind.GENERICGROUP not in self.inherit_from:
            labels.append(InfrahubKind.PROFILE)
        return labels
