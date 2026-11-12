from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.utils import duplicates

from infrahub.core.constants import (
    BUILTIN_CONTAINER_PREFIX,
    DETAILS_CONTAINER_NAME,
    PROFILE_CONTAINER_NAME,
    TEMPLATE_CONTAINER_NAME,
    TEMPLATE_NAMESPACE,
)
from infrahub.core.schema import ProfileSchema

from .interface import SchemaBranchValidator

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


class ContainerValidator(SchemaBranchValidator):
    """Refuse containers that collide or set conflicting flags, and fields that reference an unknown container."""

    def check(self, schema_branch: SchemaBranch) -> None:
        for name in schema_branch.all_names:
            node = schema_branch.get(name=name, duplicate=False)
            self._validate_declarations(node=node)
            self._validate_references(node=node)

    def _validate_declarations(self, node: MainSchemaTypes) -> None:
        # An inherited copy was already checked on the generic that declares it.
        declared_containers = [container for container in node.containers if not container.inherited]
        container_names = [container.name for container in declared_containers]
        if duplicated := duplicates(container_names):
            raise ValueError(f"{node.kind}.containers: container names must be unique, duplicate '{duplicated[0]}'")
        if DETAILS_CONTAINER_NAME in container_names:
            raise ValueError(
                f"{node.kind}.containers: '{DETAILS_CONTAINER_NAME}' is a built-in container and cannot be declared"
            )
        generated_names = self._generated_container_names(node=node)
        for container_name in container_names:
            if container_name.startswith(BUILTIN_CONTAINER_PREFIX) and container_name not in generated_names:
                raise ValueError(
                    f"{node.kind}.containers: '{container_name}' starts with the reserved prefix "
                    f"'{BUILTIN_CONTAINER_PREFIX}' and cannot be declared"
                )
        for container in declared_containers:
            if container.collapsed and not container.collapsible:
                raise ValueError(f"{node.kind}.containers.{container.name}: collapsed requires collapsible")

    @staticmethod
    def _generated_container_names(node: MainSchemaTypes) -> set[str]:
        if isinstance(node, ProfileSchema):
            return {PROFILE_CONTAINER_NAME}
        # The object template generated for a generic is a generic, so only its namespace marks it as a template.
        if node.namespace == TEMPLATE_NAMESPACE:
            return {TEMPLATE_CONTAINER_NAME}
        return set()

    def _validate_references(self, node: MainSchemaTypes) -> None:
        valid_names = {container.name for container in node.containers}
        for field_list, fields in (("attributes", node.attributes), ("relationships", node.relationships)):
            for field in fields:
                if field.inherited:
                    continue
                if field.container is not None and field.container not in valid_names:
                    raise ValueError(
                        f"{node.kind}.{field_list}.{field.name}.container: "
                        f"container '{field.container}' is not declared on {node.kind}"
                    )
