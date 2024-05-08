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
    ]
}
