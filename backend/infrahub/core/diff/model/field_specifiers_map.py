from __future__ import annotations


class NodeFieldSpecifierMap:
    def __init__(self) -> None:
        # {uuid: {kind: {field_name, ...}}}
        self._map: dict[str, dict[str, set[str]]] = {}

    def __len__(self) -> int:
        return len(self._map)

    def __hash__(self) -> int:
        full_node_hash_sum = 0
        for node_uuid, node_dict in self._map.items():
            node_kinds_hash_sum = 0
            for kind, field_names in node_dict.items():
                fields_hash = hash(frozenset(field_names))
                node_kinds_hash_sum += hash(f"{hash(kind)}:{fields_hash}")
            full_node_hash_sum += hash(f"{node_uuid}:{node_kinds_hash_sum}")
        return hash(full_node_hash_sum)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NodeFieldSpecifierMap):
            return False
        return self._map == other._map

    def __sub__(self, other: NodeFieldSpecifierMap) -> NodeFieldSpecifierMap:
        subtracted = NodeFieldSpecifierMap()
        for node_uuid, node_dict in self._map.items():
            if node_uuid not in other._map:
                subtracted._map[node_uuid] = {**node_dict}
                continue
            subtracted_node_map = {}
            for kind, field_names in node_dict.items():
                subtracted_field_names = field_names - other._map[node_uuid].get(kind, set())
                if not subtracted_field_names:
                    continue
                subtracted_node_map[kind] = subtracted_field_names
            if not subtracted_node_map:
                continue
            subtracted._map[node_uuid] = subtracted_node_map
        return subtracted

    def add_entry(self, node_uuid: str, kind: str, field_name: str) -> None:
        if node_uuid not in self._map:
            self._map[node_uuid] = {}
        if kind not in self._map[node_uuid]:
            self._map[node_uuid][kind] = set()
        self._map[node_uuid][kind].add(field_name)

    def has_entry(self, node_uuid: str, kind: str, field_name: str) -> bool:
        return field_name in self._map.get(node_uuid, {}).get(kind, set())

    def get_uuids_list(self) -> list[str]:
        return list(self._map.keys())

    def get_uuid_field_names_map(self) -> dict[str, list[str]]:
        uuid_field_names_map: dict[str, list[str]] = {}
        for node_uuid, node_dict in self._map.items():
            field_names_set: set[str] = set()
            for field_names in node_dict.values():
                field_names_set |= field_names
            uuid_field_names_map[node_uuid] = list(field_names_set)
        return uuid_field_names_map
