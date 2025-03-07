from typing import Any

core_profile_schema_definition: dict[str, Any] = {
    "name": "Profile",
    "namespace": "Core",
    "include_in_menu": False,
    "icon": "mdi:shape-plus-outline",
    "description": "Base Profile in Infrahub.",
    "label": "Profile",
    "display_labels": ["profile_name__value"],
    "default_filter": "profile_name__value",
    "uniqueness_constraints": [["profile_name__value"]],
    "attributes": [
        {
            "name": "profile_name",
            "kind": "Text",
            "min_length": 3,
            "max_length": 32,
            "optional": False,
            "unique": True,
        },
        {
            "name": "profile_priority",
            "kind": "Number",
            "default_value": 1000,
            "optional": True,
        },
    ],
}
