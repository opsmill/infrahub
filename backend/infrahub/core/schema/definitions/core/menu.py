from typing import Any

from infrahub.core.constants import (
    NAMESPACE_REGEX,
)

generic_menu_item: dict[str, Any] = {
    "name": "Menu",
    "namespace": "Core",
    "include_in_menu": False,
    "description": "Element of the Menu",
    "label": "Menu",
    "hierarchical": True,
    "human_friendly_id": ["namespace__value", "name__value"],
    "display_labels": ["label__value"],
    "generate_profile": False,
    "attributes": [
        {"name": "namespace", "kind": "Text", "regex": NAMESPACE_REGEX, "order_weight": 1000},
        {"name": "name", "kind": "Text", "order_weight": 1000},
        {"name": "label", "kind": "Text", "optional": True, "order_weight": 2000},
        {"name": "kind", "kind": "Text", "optional": True, "order_weight": 2500},
        {"name": "path", "kind": "Text", "optional": True, "order_weight": 2500},
        {"name": "description", "kind": "Text", "optional": True, "order_weight": 3000},
        {"name": "icon", "kind": "Text", "optional": True, "order_weight": 4000},
        {"name": "protected", "kind": "Boolean", "default_value": False, "read_only": True, "order_weight": 5000},
        {"name": "order_weight", "kind": "Number", "default_value": 2000, "order_weight": 6000},
        {"name": "required_permissions", "kind": "List", "optional": True, "order_weight": 7000},
        {
            "name": "section",
            "kind": "Text",
            "enum": ["object", "internal"],
            "default_value": "object",
            "order_weight": 8000,
        },
    ],
}

menu_item: dict[str, Any] = {
    "name": "MenuItem",
    "namespace": "Core",
    "include_in_menu": False,
    "description": "Menu Item",
    "label": "Menu Item",
    "inherit_from": ["CoreMenu"],
    "generate_profile": False,
}
