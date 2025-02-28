from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)

core_webhook = {
    "name": "Webhook",
    "namespace": "Core",
    "description": "A webhook that connects to an external integration",
    "label": "Webhook",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "include_in_menu": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "uniqueness_constraints": [["name__value"]],
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True, "order_weight": 1000},
        {"name": "description", "kind": "Text", "optional": True, "order_weight": 2000},
        {"name": "url", "kind": "URL", "order_weight": 3000},
        {
            "name": "validate_certificates",
            "kind": "Boolean",
            "default_value": True,
            "optional": True,
            "order_weight": 5000,
        },
    ],
}

core_standard_webhook = {
    "name": "StandardWebhook",
    "namespace": "Core",
    "description": "A webhook that connects to an external integration",
    "label": "Standard Webhook",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "include_in_menu": False,
    "icon": "mdi:webhook",
    "branch": BranchSupportType.AGNOSTIC.value,
    "generate_profile": False,
    "inherit_from": [InfrahubKind.WEBHOOK, InfrahubKind.TASKTARGET],
    "attributes": [
        {"name": "shared_key", "kind": "Password", "unique": False, "order_weight": 4000},
    ],
}

core_custom_webhook = {
    "name": "CustomWebhook",
    "namespace": "Core",
    "description": "A webhook that connects to an external integration",
    "label": "Custom Webhook",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "include_in_menu": False,
    "icon": "mdi:cog-outline",
    "branch": BranchSupportType.AGNOSTIC.value,
    "generate_profile": False,
    "inherit_from": [InfrahubKind.WEBHOOK, InfrahubKind.TASKTARGET],
    "attributes": [],
    "relationships": [
        {
            "name": "transformation",
            "peer": InfrahubKind.TRANSFORMPYTHON,
            "kind": "Attribute",
            "identifier": "webhook___transformation",
            "cardinality": "one",
            "optional": True,
            "order_weight": 7000,
        },
    ],
}
