from __future__ import annotations

from typing import TYPE_CHECKING, List

from pydantic import Field

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema.basenode_schema import BaseNodeSchema

if TYPE_CHECKING:
    from infrahub.core.schema.generic_schema import GenericSchema


class ProfileSchema(BaseNodeSchema):
    inherit_from: list[str] = Field(
        default_factory=list,
        description="List of Generic Kind that this profile is inheriting from",
    )

    def get_restricted_attribute_names(self) -> list[str]:
        inherited_attr_names = [attr.name for attr in self.attributes if attr.inherited]
        return ["name", "profile_priority"] + inherited_attr_names

    def inherit_from_interface(self, interface: GenericSchema) -> None:
        existing_inherited_attributes = {item.name: idx for idx, item in enumerate(self.attributes) if item.inherited}

        for attribute in interface.attributes:
            if attribute.name in self.valid_input_names:
                continue

            new_attribute = attribute.duplicate()
            new_attribute.inherited = True

            if attribute.name not in existing_inherited_attributes:
                self.attributes.append(new_attribute)
            else:
                item_idx = existing_inherited_attributes[attribute.name]
                self.attributes[item_idx] = new_attribute

    def get_labels(self) -> List[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""

        labels: List[str] = [self.kind] + self.inherit_from
        if self.namespace not in ["Schema", "Internal"] and InfrahubKind.GENERICGROUP not in self.inherit_from:
            labels.append("CoreProfile")
        return labels
