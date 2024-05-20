from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from infrahub_sdk.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync


class NodeStoreBase:
    """Internal Store for InfrahubNode objects.

    Often while creating a lot of new objects,
    we need to save them in order to reuse them laterto associate them with another node for example.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict] = defaultdict(dict)
        self._store_by_hfid: Dict[str, Any] = defaultdict(dict)

    def _set(self, key: str, node: Union[InfrahubNode, InfrahubNodeSync]) -> None:
        node_kind = node._schema.kind
        self._store[node_kind][key] = node  # type: ignore[attr-defined]

        if hfid := node.get_human_friendly_id_as_string(include_kind=True):
            self._store_by_hfid[hfid] = node

    def _get(self, key: str, kind: Optional[str] = None, raise_when_missing: bool = True):  # type: ignore[no-untyped-def]
        if kind and kind not in self._store and key not in self._store[kind]:  # type: ignore[attr-defined]
            if not raise_when_missing:
                return None
            raise NodeNotFoundError(
                node_type=kind,
                identifier={"key": [key]},
                message="Unable to find the node in the Store",
            )

        if kind and kind in self._store and key in self._store[kind]:  # type: ignore[attr-defined]
            return self._store[kind][key]  # type: ignore[attr-defined]

        for _, item in self._store.items():  # type: ignore[attr-defined]
            if key in item:
                return item[key]

        if not raise_when_missing:
            return None
        raise NodeNotFoundError(
            node_type="n/a",
            identifier={"key": [key]},
            message=f"Unable to find the node {key!r} in the store",
        )

    def _get_by_hfid(self, key: str, raise_when_missing: bool = True):  # type: ignore[no-untyped-def]
        try:
            return self._store_by_hfid[key]
        except KeyError as exc:
            if raise_when_missing:
                raise NodeNotFoundError(
                    node_type="n/a",
                    identifier={"key": [key]},
                    message="Unable to find the node {key!r} in the store",
                ) from exc
        return None


class NodeStore(NodeStoreBase):
    def get(self, key: str, kind: Optional[str] = None, raise_when_missing: bool = True) -> Optional[InfrahubNode]:
        return self._get(key=key, kind=kind, raise_when_missing=raise_when_missing)

    def get_by_hfid(self, key: str, raise_when_missing: bool = True) -> Optional[InfrahubNode]:
        return self._get_by_hfid(key=key, raise_when_missing=raise_when_missing)

    def set(self, key: str, node: InfrahubNode) -> None:
        return self._set(key=key, node=node)


class NodeStoreSync(NodeStoreBase):
    def get(self, key: str, kind: Optional[str] = None, raise_when_missing: bool = True) -> Optional[InfrahubNodeSync]:
        return self._get(key=key, kind=kind, raise_when_missing=raise_when_missing)

    def get_by_hfid(self, key: str, raise_when_missing: bool = True) -> Optional[InfrahubNodeSync]:
        return self._get_by_hfid(key=key, raise_when_missing=raise_when_missing)

    def set(self, key: str, node: InfrahubNodeSync) -> None:
        return self._set(key=key, node=node)
