from __future__ import annotations

from typing import TYPE_CHECKING

from .generated.genericnode_schema import GeneratedGenericSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class GenericSchema(GeneratedGenericSchema):
    """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

    @property
    def is_node_schema(self) -> bool:
        return False

    @property
    def is_generic_schema(self) -> bool:
        return True

    @property
    def is_profile_schema(self) -> bool:
        return False

    @property
    def is_template_schema(self) -> bool:
        return False

    def get_hierarchy_schema(self, db: InfrahubDatabase, branch: Branch | str | None = None) -> GenericSchema:  # noqa: ARG002
        if self.hierarchical:
            return self

        raise ValueError(f"hierarchical mode is not enabled on {self.kind}")

    def get_labels(self) -> list[str]:
        """Return the labels for this object"""
        return [self.kind]

    def _get_field_names_for_diff(self) -> list[str]:
        """Exclude used_by from the diff for generic nodes"""
        fields = super()._get_field_names_for_diff()
        return [field for field in fields if field not in ["used_by"]]
