from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Union

from .generated.genericnode_schema import GeneratedGenericSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


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

    def get_hierarchy_schema(self, branch: Optional[Union[Branch, str]] = None) -> GenericSchema:  # pylint: disable=unused-argument
        if self.hierarchical:
            return self

        raise ValueError(f"hierarchical mode is not enabled on {self.kind}")

    def get_labels(self) -> List[str]:
        """Return the labels for this object"""
        return [self.kind]
