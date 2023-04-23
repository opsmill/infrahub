from collections import defaultdict
from typing import Any, Dict, Optional, Union

from infrahub_client import InfrahubNode, NodeNotFound


class NodeStore:
    """Temporary Store for InfrahubNode objects.

    Often while creating a lot of new objects,
    we need to save them in order to reuse them laterto associate them with another node for example.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, InfrahubNode]] = defaultdict(dict)

    def set(self, key: str, node: InfrahubNode) -> None:
        if not isinstance(node, InfrahubNode):
            raise TypeError(f"'node' must be of type InfrahubNode, not {type(InfrahubNode)!r}")

        node_kind = node._schema.kind
        self._store[node_kind][key] = node

    def get(self, key: str, kind: Optional[str] = None, **kwargs: Any) -> Union[InfrahubNode, Any]:
        if kind and kind not in self._store and key not in self._store[kind]:
            if "default" in kwargs:
                return kwargs.get("default")
            raise NodeNotFound(
                branch_name="n/a",
                node_type=kind,
                identifier={"key": [key]},
                message="Unable to find the node in the Store",
            )

        if kind and kind in self._store and key in self._store[kind]:
            return self._store[kind][key]

        for _, item in self._store.items():
            if key in item:
                return item[key]

        if "default" in kwargs:
            return kwargs.get("default")
        raise NodeNotFound(
            branch_name="n/a",
            node_type="n/a",
            identifier={"key": [key]},
            message=f"Unable to find the node {key!r} in the Store",
        )
