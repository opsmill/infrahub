from typing import Any

from infrahub.core.constants import HashableModelState

deprecated_models: dict[str, Any] = {
    "generics": [
        {
            "name": "Source",
            "namespace": "Lineage",
            "display_labels": [],
            "attributes": [
                {"name": "name", "kind": "Text", "state": HashableModelState.ABSENT},
                {"name": "description", "kind": "Text", "state": HashableModelState.ABSENT},
            ],
        },
        {
            "name": "Owner",
            "namespace": "Lineage",
            "display_labels": [],
            "attributes": [
                {"name": "name", "kind": "Text", "state": HashableModelState.ABSENT},
                {"name": "description", "kind": "Text", "state": HashableModelState.ABSENT},
            ],
        },
        {
            "name": "BasePermission",
            "namespace": "Core",
            "attributes": [
                # identifier was moved to CoreGlobalPermission and CoreObjectPermission as a computed attribute
                {"name": "identifier", "kind": "Text", "state": HashableModelState.ABSENT},
            ],
        },
    ]
}
