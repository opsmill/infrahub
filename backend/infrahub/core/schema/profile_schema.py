from __future__ import annotations

from typing import List

from pydantic import Field

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema.basenode_schema import BaseNodeSchema


class ProfileSchema(BaseNodeSchema):
    inherit_from: list[str] = Field(
        default_factory=list,
        description="List of Generic Kind that this profile is inheriting from",
    )

    def get_labels(self) -> List[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""

        labels: List[str] = [self.kind] + self.inherit_from
        if self.namespace not in ["Schema", "Internal"] and InfrahubKind.GENERICGROUP not in self.inherit_from:
            labels.append("CoreNode")
        return labels
