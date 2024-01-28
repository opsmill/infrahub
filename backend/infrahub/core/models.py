from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from infrahub_sdk.utils import duplicates, intersection
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self


class NodeKind(BaseModel):
    namespace: str
    name: str

    def __str__(self) -> str:
        return f"{self.namespace}{self.name}"


class SchemaBranchDiff(BaseModel):
    nodes: List[str] = Field(default_factory=list)
    generics: List[str] = Field(default_factory=list)

    def to_string(self) -> str:
        return ", ".join(self.nodes + self.generics)

    def to_list(self) -> List[str]:
        return self.nodes + self.generics


class SchemaBranchHash(BaseModel):
    main: str
    nodes: Dict[str, str] = Field(default_factory=dict)
    generics: Dict[str, str] = Field(default_factory=dict)

    def compare(self, other: SchemaBranchHash) -> Optional[SchemaBranchDiff]:
        if other.main == self.main:
            return None

        return SchemaBranchDiff(
            nodes=[key for key, value in other.nodes.items() if key not in self.nodes or self.nodes[key] != value],
            generics=[
                key for key, value in other.generics.items() if key not in self.generics or self.generics[key] != value
            ],
        )


class HashableModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    _exclude_from_hash: List[str] = []
    _sort_by: List[str] = []

    def __hash__(self) -> int:
        return hash(self.get_hash())

    def get_hash(self, display_values: bool = False) -> str:
        """Generate a hash for the object.

        Calculating a hash can be very complicated if the data that we are storing is dynamic
        In order for this function to work, it's recommended to exclude all objects or list of objects with _exclude_from_hash
        List of hashable elements are fine and they will be converted automatically to Tuple.
        """

        def prep_for_hash(v: Any) -> bytes:
            if hasattr(v, "get_hash"):
                return v.get_hash().encode()

            return str(v).encode()

        values = []
        md5hash = hashlib.md5()
        for field_name in sorted(self.model_fields.keys()):
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            value = getattr(self, field_name)
            if isinstance(value, list):
                for item in sorted(value):
                    values.append(prep_for_hash(item))
                    md5hash.update(prep_for_hash(item))
            elif hasattr(value, "get_hash"):
                values.append(value.get_hash().encode())
                md5hash.update(value.get_hash().encode())
            elif isinstance(value, dict):
                for key, value in frozenset(sorted(value.items())):
                    values.append(prep_for_hash(key))
                    values.append(prep_for_hash(value))
                    md5hash.update(prep_for_hash(key))
                    md5hash.update(prep_for_hash(value))
            else:
                md5hash.update(prep_for_hash(value))
                values.append(prep_for_hash(value))

        if display_values:
            from rich import print as rprint  # pylint: disable=import-outside-toplevel

            rprint(tuple(values))

        return md5hash.hexdigest()

    @property
    def _sorting_id(self) -> Tuple[Any]:
        return tuple(getattr(self, key) for key in self._sort_by if hasattr(self, key))

    def _sorting_keys(self, other: HashableModel) -> Tuple[List[Any], List[Any]]:
        """Retrieve the values of the attributes listed in the _sort_key list, for both objects."""
        if not self._sort_by:
            raise TypeError(f"Sorting not supported for instance of {self.__class__.__name__}")

        if not hasattr(other, "_sort_by") and not other._sort_by:
            raise TypeError(
                f"Sorting not supported between instance of {other.__class__.__name__} and {self.__class__.__name__}"
            )

        self_sort_keys: List[Any] = [getattr(self, key) for key in self._sort_by if hasattr(self, key)]
        other_sort_keys: List[Any] = [getattr(other, key) for key in other._sort_by if hasattr(other, key)]

        return self_sort_keys, other_sort_keys

    def __lt__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) < tuple(other_sort_keys)

    def __le__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) <= tuple(other_sort_keys)

    def __gt__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) > tuple(other_sort_keys)

    def __ge__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) >= tuple(other_sort_keys)

    def duplicate(self) -> Self:
        """Duplicate the current object by doing a deep copy of everything and recreating a new object."""
        return self.model_copy(deep=True)

    @staticmethod
    def is_list_composed_of_schema_model(items: List[Any]) -> bool:
        for item in items:
            if not isinstance(item, HashableModel):
                return False
        return True

    @staticmethod
    def is_list_composed_of_standard_type(items: List[Any]) -> bool:
        for item in items:
            if not isinstance(item, (int, str, bool, float)):
                return False
        return True

    @staticmethod
    def update_list_schema_model(field_name: str, attr_local: List[Any], attr_other: List[Any]) -> List[Any]:
        # merging the list is not easy, we need to create a unique id based on the
        # sorting keys and if we have 2 sub items with the same key we can merge them recursively with update()
        local_sub_items = {item._sorting_id: item for item in attr_local if hasattr(item, "_sorting_id")}
        other_sub_items = {item._sorting_id: item for item in attr_other if hasattr(item, "_sorting_id")}

        new_list = []

        if len(local_sub_items) != len(attr_local) or len(other_sub_items) != len(attr_other):
            raise ValueError(f"Unable to merge the list for {field_name}, not all items are supporting _sorting_id")

        if duplicates(list(local_sub_items.keys())) or duplicates(list(other_sub_items.keys())):
            raise ValueError(f"Unable to merge the list for {field_name}, some items have the same _sorting_id")

        shared_ids = intersection(list(local_sub_items.keys()), list(other_sub_items.keys()))
        local_only_ids = set(list(local_sub_items.keys())) - set(shared_ids)
        other_only_ids = set(list(other_sub_items.keys())) - set(shared_ids)

        new_list = [value for key, value in local_sub_items.items() if key in local_only_ids]
        new_list.extend([value for key, value in other_sub_items.items() if key in other_only_ids])

        for item_id in shared_ids:
            other_item = other_sub_items[item_id]
            local_item = local_sub_items[item_id]
            new_list.append(local_item.update(other_item))

        return new_list

    def update(self, other: Self) -> Self:
        """Update the current object with the new value from the new one if they are defined.

        Currently this method works for the following type of fields
            int, str, bool, float: If present the value from Other is overwriting the local value
            list[BaseSchemaModel]: The list will be merge if all elements in the list have a _sorting_id and if it's unique.

        TODO Implement other fields type like dict
        """

        for field_name, _ in other.model_fields.items():
            if not hasattr(self, field_name):
                setattr(self, field_name, getattr(other, field_name))
                continue

            attr_other = getattr(other, field_name)
            attr_local = getattr(self, field_name)
            if attr_other is None or attr_local == attr_other:
                continue

            if attr_local is None or isinstance(attr_other, (int, str, bool, float)):
                setattr(self, field_name, getattr(other, field_name))
                continue

            if isinstance(attr_local, list) and isinstance(attr_other, list):
                if self.is_list_composed_of_schema_model(attr_local) and self.is_list_composed_of_schema_model(
                    attr_other
                ):
                    new_attr = self.update_list_schema_model(
                        field_name=field_name, attr_local=attr_local, attr_other=attr_other
                    )
                    setattr(self, field_name, new_attr)

                elif self.is_list_composed_of_standard_type(attr_local) and self.is_list_composed_of_standard_type(
                    attr_other
                ):
                    new_attr = list(dict.fromkeys(attr_local + attr_other))
                    setattr(self, field_name, new_attr)

        return self
