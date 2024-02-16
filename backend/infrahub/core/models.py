from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from infrahub_sdk.utils import compare_lists, deep_merge_dict, duplicates, intersection
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from infrahub.core.constants import (
    SchemaPathType,
    UpdateSupport,
    UpdateValidationErrorType,
)
from infrahub.core.path import SchemaPath

if TYPE_CHECKING:
    from infrahub.core.schema_manager import SchemaBranch


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

    @property
    def has_diff(self) -> bool:
        if self.nodes or self.generics:
            return True
        return False


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


class SchemaDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    added: Dict[str, HashableModelDiff] = Field(default_factory=dict)
    changed: Dict[str, HashableModelDiff] = Field(default_factory=dict)
    removed: Dict[str, HashableModelDiff] = Field(default_factory=dict)

    @property
    def all(self) -> List[str]:
        return list(self.changed.keys()) + list(self.added.keys()) + list(self.removed.keys())

    def __add__(self, other: SchemaDiff) -> SchemaDiff:
        merged_dict = deep_merge_dict(self.model_dump(), other.model_dump())
        return self.__class__(**merged_dict)


class SchemaUpdateValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    error: UpdateValidationErrorType
    message: Optional[str] = None

    def to_string(self) -> str:
        return f"{self.error.value!r}: {self.path.schema_kind} {self.path.field_name} {self.message}"


class SchemaUpdateMigrationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    migration_name: str

    @property
    def routing_key(self) -> str:
        return "schema.migration.path"


class SchemaUpdateConstraintInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    constraint_name: str

    @property
    def routing_key(self) -> str:
        return "schema.validator.path"

    def __hash__(self) -> int:
        return hash((type(self),) + tuple([self.constraint_name + self.path.get_path()]))


class SchemaUpdateValidationResult(BaseModel):
    errors: List[SchemaUpdateValidationError] = Field(default_factory=list)
    constraints: List[SchemaUpdateConstraintInfo] = Field(default_factory=list)
    migrations: List[SchemaUpdateMigrationInfo] = Field(default_factory=list)
    diff: SchemaDiff

    @classmethod
    def init(cls, diff: SchemaDiff, schema: SchemaBranch) -> Self:
        obj = cls(diff=diff)
        obj.process_diff(schema=schema)

        return obj

    def process_diff(self, schema: SchemaBranch) -> None:
        for schema_name, schema_diff in self.diff.changed.items():
            schema_node = schema.get(name=schema_name, duplicate=False)

            # Nothing to do today if we add a new model in the schema
            # for node_field_name, _ in schema_diff.added.items():
            #     pass

            # Not possible today, we need to add some specific mutations to support that
            # for node_field_name, _ in schema_diff.removed.items():
            #     pass

            for node_field_name, node_field_diff in schema_diff.changed.items():
                if node_field_diff and node_field_name in ["attributes", "relationships"]:
                    field_type = node_field_name[:-1]  # Remove the trailing 's's
                    path_type = SchemaPathType.ATTRIBUTE if field_type == "attribute" else SchemaPathType.RELATIONSHIP
                    for field_name, _ in node_field_diff.added.items():
                        if field_type == "attribute":
                            self.migrations.append(
                                SchemaUpdateMigrationInfo(
                                    path=SchemaPath(  # type: ignore[call-arg]
                                        schema_kind=schema_name, path_type=path_type, field_name=field_name
                                    ),
                                    migration_name="node.attribute.add",
                                )
                            )

                    for field_name, _ in node_field_diff.removed.items():
                        self.migrations.append(
                            SchemaUpdateMigrationInfo(  # type: ignore[call-arg]
                                path=SchemaPath(  # type: ignore[call-arg]
                                    schema_kind=schema_name, path_type=path_type, field_name=field_name
                                ),
                                migration_name=f"node.{field_type}.remove",
                            )
                        )

                    for field_name, sub_field_diff in node_field_diff.changed.items():
                        field = schema_node.get_field(name=field_name)

                        if not sub_field_diff or not field:
                            raise ValueError("sub_field_diff and field must be defined, unexpected situation")

                        for prop_name, _ in sub_field_diff.changed.items():
                            field_info = field.model_fields[prop_name]
                            field_update = str(field_info.json_schema_extra.get("update"))  # type: ignore[union-attr]

                            schema_path = SchemaPath(  # type: ignore[call-arg]
                                schema_kind=schema_name,
                                path_type=path_type,
                                field_name=field_name,
                                property_name=prop_name,
                            )

                            self._process_field(
                                schema_path=schema_path,
                                field_update=field_update,
                            )

                else:
                    field_info = schema_node.model_fields[node_field_name]
                    field_update = str(field_info.json_schema_extra.get("update"))  # type: ignore[union-attr]

                    schema_path = SchemaPath(  # type: ignore[call-arg]
                        schema_kind=schema_name,
                        path_type=SchemaPathType.NODE,
                        field_name=node_field_name,
                        property_name=node_field_name,
                    )
                    self._process_field(
                        schema_path=schema_path,
                        field_update=field_update,
                    )

    def _process_field(
        self,
        schema_path: SchemaPath,
        field_update: str,
    ) -> None:
        if field_update == UpdateSupport.NOT_SUPPORTED.value:
            self.errors.append(
                SchemaUpdateValidationError(
                    path=schema_path,
                    error=UpdateValidationErrorType.NOT_SUPPORTED,
                )
            )
        elif field_update == UpdateSupport.MIGRATION_REQUIRED.value:
            migration_name = f"{schema_path.path_type.value}.{schema_path.field_name}.update"
            self.migrations.append(
                SchemaUpdateMigrationInfo(
                    path=schema_path,
                    migration_name=migration_name,
                )
            )
        elif field_update == UpdateSupport.VALIDATE_CONSTRAINT.value:
            constraint_name = f"{schema_path.path_type.value}.{schema_path.property_name}.update"
            self.constraints.append(
                SchemaUpdateConstraintInfo(
                    path=schema_path,
                    constraint_name=constraint_name,
                )
            )

    def validate_all(self, migration_map: Dict[str, Any], validator_map: Dict[str, Any]) -> None:
        self.validate_migrations(migration_map=migration_map)
        self.validate_constraints(validator_map=validator_map)

    def validate_migrations(self, migration_map: Dict[str, Any]) -> None:
        for migration in self.migrations:
            if migration_map.get(migration.migration_name, None) is None:
                self.errors.append(
                    SchemaUpdateValidationError(
                        path=migration.path,
                        error=UpdateValidationErrorType.MIGRATION_NOT_AVAILABLE,
                        message=f"Migration {migration.migration_name!r} is not available yet",
                    )
                )

    def validate_constraints(self, validator_map: Dict[str, Any]) -> None:
        for constraint in self.constraints:
            if validator_map.get(constraint.constraint_name, None) is None:
                self.errors.append(
                    SchemaUpdateValidationError(
                        path=constraint.path,
                        error=UpdateValidationErrorType.VALIDATOR_NOT_AVAILABLE,
                        message=f"Validator {constraint.constraint_name!r} is not available yet",
                    )
                )


class HashableModelDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    added: Dict[str, Optional[HashableModelDiff]] = Field(default_factory=dict)
    changed: Dict[str, Optional[HashableModelDiff]] = Field(default_factory=dict)
    removed: Dict[str, Optional[HashableModelDiff]] = Field(default_factory=dict)

    @property
    def has_diff(self) -> bool:
        return bool(len(self.added) + len(self.changed) + len(self.removed))


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

        values = []
        md5hash = hashlib.md5()
        for field_name in sorted(self.model_fields.keys()):
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            value = getattr(self, field_name)
            signatures = self._get_signature_field(value)
            for item in signatures:
                values.append(item)
                md5hash.update(item)

        if display_values:
            from rich import print as rprint  # pylint: disable=import-outside-toplevel

            rprint(tuple(values))

        return md5hash.hexdigest()

    @classmethod
    def _get_hash_value(cls, value: Any) -> bytes:
        if hasattr(value, "get_hash"):
            return value.get_hash().encode()

        return str(value).encode()

    @classmethod
    def _get_signature_field(cls, value: Any) -> List[bytes]:
        hashes: List[bytes] = []
        if isinstance(value, list):
            for item in sorted(value):
                hashes.append(cls._get_hash_value(item))
        elif isinstance(value, dict):
            for key, content in frozenset(sorted(value.items())):
                hashes.append(cls._get_hash_value(key))
                hashes.append(cls._get_hash_value(content))
        else:
            hashes.append(cls._get_hash_value(value))

        return hashes

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

    def diff(self, other: Self) -> HashableModelDiff:
        in_both, local_only, other_only = compare_lists(
            list1=list(self.model_fields.keys()), list2=list(other.model_fields.keys())
        )
        diff_result = HashableModelDiff(
            added={item: None for item in local_only}, removed={item: None for item in other_only}
        )

        for field_name in in_both:
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            local_value = getattr(self, field_name)
            other_value = getattr(other, field_name)
            local_signatures = self._get_signature_field(local_value)
            other_signatures = other._get_signature_field(other_value)

            if local_signatures != other_signatures:
                if isinstance(local_value, HashableModel) and isinstance(other_value, HashableModel):
                    diff_result.changed[field_name] = local_value.diff(other=other_value)
                else:
                    diff_result.changed[field_name] = None

        return diff_result
