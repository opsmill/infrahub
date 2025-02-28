from infrahub.core.constants import (
    BranchSupportType,
)

builtin_tag = {
    "name": "Tag",
    "namespace": "Builtin",
    "description": "Standard Tag object to attached to other objects to provide some context.",
    "include_in_menu": True,
    "icon": "mdi:tag-multiple",
    "label": "Tag",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "branch": BranchSupportType.AWARE.value,
    "uniqueness_constraints": [["name__value"]],
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "description", "kind": "Text", "optional": True},
    ],
}
