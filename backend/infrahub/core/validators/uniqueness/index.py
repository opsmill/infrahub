from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from infrahub.core.query import QueryResult
    from infrahub.core.schema import SchemaAttributePath, SchemaAttributePathValue


class GroupedIndexKey:
    def __init__(self) -> None:
        self._keys: list[tuple[str, str]] = []

    def add_key(self, key: tuple[str, Any]) -> None:
        self._keys.append(key)

    def get_key(self) -> list[tuple[str, Any]]:
        return self._keys

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.get_key() == other.get_key()

    def __hash__(self) -> int:
        to_hash = ".".join([f"{k[0]}-{k[1]}" for k in self._keys])
        return hash(to_hash)


class UniquenessQueryResultsIndex:
    def __init__(self, query_results: Iterable[QueryResult], exclude_node_ids: set[str] | None = None) -> None:
        self._relationship_index: dict[str, dict[str, set[str]]] = {}
        self._attribute_index: dict[str, dict[Any, set[str]]] = {}
        self._node_index: dict[str, dict[str, Any]] = {}
        self._all_node_ids: set[str] = set()
        for query_result in query_results:
            node_id = query_result.get_as_str("node_id")
            if not node_id or (exclude_node_ids and node_id in exclude_node_ids):
                continue
            if node_id not in self._node_index:
                self._node_index[node_id] = {}
            self._all_node_ids.add(node_id)
            relationship_identifier = query_result.get_as_str("relationship_identifier")
            attr_name = query_result.get_as_str("attr_name")
            attr_value = query_result.get_as_str("attr_value")
            if relationship_identifier:
                if relationship_identifier not in self._relationship_index:
                    self._relationship_index[relationship_identifier] = defaultdict(set)
                if attr_value and node_id:
                    self._relationship_index[relationship_identifier][attr_value].add(node_id)
                    self._node_index[node_id][relationship_identifier] = attr_value
            elif attr_name:
                if attr_name not in self._attribute_index:
                    self._attribute_index[attr_name] = defaultdict(set)
                if attr_value and node_id:
                    self._attribute_index[attr_name][attr_value].add(node_id)
                    self._node_index[node_id][attr_name] = attr_value

    def get_node_ids_for_value_group(self, path_value_group: list[SchemaAttributePathValue]) -> set[str]:
        matching_node_ids = self._all_node_ids.copy()
        for schema_attribute_path_value in path_value_group:
            if schema_attribute_path_value.value is None:
                return set()
            value = str(schema_attribute_path_value.value)
            if schema_attribute_path_value.relationship_schema:
                relationship_identifier = schema_attribute_path_value.relationship_schema.get_identifier()
                matching_node_ids &= self._relationship_index.get(relationship_identifier, {}).get(value, set())
            elif schema_attribute_path_value.attribute_schema:
                attribute_name = schema_attribute_path_value.attribute_schema.name
                matching_node_ids &= self._attribute_index.get(attribute_name, {}).get(value, set())
            if not matching_node_ids:
                return matching_node_ids
        return matching_node_ids

    def get_node_ids_for_path_group(self, path_group: list[SchemaAttributePath]) -> set[str]:
        node_ids_by_attr_name_and_value: dict[GroupedIndexKey, set[str]] = {}
        key_group = []
        for schema_attribute_path in path_group:
            if schema_attribute_path.relationship_schema:
                key_group.append(schema_attribute_path.relationship_schema.get_identifier())
            elif schema_attribute_path.attribute_schema:
                key_group.append(schema_attribute_path.attribute_schema.name)
            else:
                continue
        for node_id, attribute_details in self._node_index.items():
            node_includes_none = False
            grouped_key = GroupedIndexKey()
            for element_key in key_group:
                element_value = attribute_details.get(element_key)
                if element_value is None:
                    node_includes_none = True
                    break
                grouped_key.add_key((element_key, element_value))
            if node_includes_none:
                continue
            if grouped_key not in node_ids_by_attr_name_and_value:
                node_ids_by_attr_name_and_value[grouped_key] = set()
            node_ids_by_attr_name_and_value[grouped_key].add(node_id)
        node_ids_in_violation = set()
        for node_ids in node_ids_by_attr_name_and_value.values():
            if len(node_ids) > 1:
                node_ids_in_violation |= node_ids
        return node_ids_in_violation
