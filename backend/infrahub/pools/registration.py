from infrahub.core.registry import registry
from infrahub.exceptions import SchemaNotFoundError


def get_branches_with_schema_number_pool(kind: str, attribute_name: str) -> list[str]:
    """Return branches where schema defined NumberPool exists"""

    registered_branches = []
    active_branches = registry.schema.get_branches()

    for active_branch in active_branches:
        try:
            schema = registry.schema.get(name=kind, branch=active_branch)
        except SchemaNotFoundError:
            continue

        if attribute_name in schema.attribute_names:
            attribute = schema.get_attribute(name=attribute_name)
            if attribute.kind == "NumberPool":
                registered_branches.append(active_branch)

    return registered_branches
