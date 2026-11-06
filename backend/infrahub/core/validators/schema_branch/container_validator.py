from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.utils import duplicates

from infrahub.core.constants import ADVANCED_CONTAINER_NAME, BUILT_IN_CONTAINER_NAMES

from .interface import SchemaBranchValidator

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


class ContainerValidator(SchemaBranchValidator):
    """Refuse a schema whose containers collide or whose fields reference a container the kind does not have."""

    def check(self, schema_branch: SchemaBranch) -> None:
        for name in schema_branch.all_names:
            node = schema_branch.get(name=name, duplicate=False)
            self._validate_declarations(node=node)
            self._validate_references(node=node)

    def _validate_declarations(self, node: MainSchemaTypes) -> None:
        # An inherited copy was already checked on the generic that declares it.
        container_names = [container.name for container in node.containers if not container.inherited]
        if duplicated := duplicates(container_names):
            raise ValueError(f"{node.kind}.containers: container names must be unique, duplicate '{duplicated[0]}'")
        for built_in_name in BUILT_IN_CONTAINER_NAMES:
            if built_in_name in container_names:
                raise ValueError(
                    f"{node.kind}.containers: '{built_in_name}' is a built-in container and cannot be declared"
                )

    def _validate_references(self, node: MainSchemaTypes) -> None:
        valid_names = {container.name for container in node.containers} | {ADVANCED_CONTAINER_NAME}
        for field_list, fields in (("attributes", node.attributes), ("relationships", node.relationships)):
            for field in fields:
                if field.inherited:
                    continue
                if field.container is not None and field.container not in valid_names:
                    raise ValueError(
                        f"{node.kind}.{field_list}.{field.name}.container: "
                        f"container '{field.container}' is not declared on {node.kind}"
                    )
