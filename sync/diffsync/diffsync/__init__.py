"""DiffSync front-end classes and logic.

Copyright (c) 2020-2021 Network To Code, LLC <info@networktocode.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from inspect import isclass
from typing import Callable, ClassVar, Dict, List, Mapping, Optional, Text, Tuple, Type, Union

import structlog  # type: ignore
from pydantic import BaseModel, PrivateAttr

from diffsync.diff import Diff
from diffsync.enum import DiffSyncFlags, DiffSyncModelFlags, DiffSyncStatus
from diffsync.exceptions import DiffClassMismatch, ObjectAlreadyExists, ObjectNotFound, ObjectStoreWrongType
from diffsync.helpers import DiffSyncDiffer, DiffSyncSyncer
from diffsync.store import BaseStore
from diffsync.store.local import LocalStore
from diffsync.utils import get_path, set_key, tree_string


class DiffSyncModel(BaseModel):
    """Base class for all DiffSync object models.

    Note that read-only APIs of this class are implemented as `get_*()` functions rather than as properties;
    this is intentional as specific model classes may want to use these names (`type`, `keys`, `attrs`, etc.)
    as model attributes and we want to avoid any ambiguity or collisions.

    This class has several underscore-prefixed class variables that subclasses should set as desired; see below.

    NOTE: The groupings _identifiers, _attributes, and _children are mutually exclusive; any given field name can
    be included in **at most** one of these three tuples.
    """

    _modelname: ClassVar[str] = "diffsyncmodel"
    """Name of this model, used by DiffSync to store and look up instances of this model or its equivalents.

    Lowercase by convention; typically corresponds to the class name, but that is not enforced.
    """

    _identifiers: ClassVar[Tuple[str, ...]] = ()
    """List of model fields which together uniquely identify an instance of this model.

    This identifier MUST be globally unique among all instances of this class.
    """

    _shortname: ClassVar[Tuple[str, ...]] = ()
    """Optional: list of model fields that together form a shorter identifier of an instance.

    This MUST be locally unique (e.g., interface shortnames MUST be unique among all interfaces on a given device),
    but does not need to be guaranteed to be globally unique among all instances.
    """

    _attributes: ClassVar[Tuple[str, ...]] = ()
    """Optional: list of additional model fields (beyond those in `_identifiers`) that are relevant to this model.

    Only the fields in `_attributes` (as well as any `_children` fields, see below) will be considered
    for the purposes of Diff calculation.
    A model may define additional fields (not included in `_attributes`) for its internal use;
    a common example would be a locally significant database primary key or id value.

    Note: inclusion in `_attributes` is mutually exclusive from inclusion in `_identifiers`; a field cannot be in both!
    """

    _children: ClassVar[Mapping[str, str]] = {}
    """Optional: dict of `{_modelname: field_name}` entries describing how to store "child" models in this model.

    When calculating a Diff or performing a sync, DiffSync will automatically recurse into these child models.

    Note: inclusion in `_children` is mutually exclusive from inclusion in `_identifiers` or `_attributes`.
    """

    model_flags: DiffSyncModelFlags = DiffSyncModelFlags.NONE
    """Optional: any non-default behavioral flags for this DiffSyncModel.

    Can be set as a class attribute or an instance attribute as needed.
    """

    diffsync: Optional["DiffSync"] = None
    """Optional: the DiffSync instance that owns this model instance."""

    _status: DiffSyncStatus = PrivateAttr(DiffSyncStatus.SUCCESS)
    """Status of the last attempt at creating/updating/deleting this model."""

    _status_message: str = PrivateAttr("")
    """Message, if any, associated with the create/update/delete status value."""

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic class configuration."""

        # Let us have a DiffSync as an instance variable even though DiffSync is not a Pydantic model itself.
        arbitrary_types_allowed = True

    def __init_subclass__(cls):
        """Validate that the various class attribute declarations correspond to actual instance fields.

        Called automatically on subclass declaration.
        """
        variables = cls.__fields__.keys()
        # Make sure that any field referenced by name actually exists on the model
        for attr in cls._identifiers:
            if attr not in variables and not hasattr(cls, attr):
                raise AttributeError(f"_identifiers {cls._identifiers} references missing or un-annotated attr {attr}")
        for attr in cls._shortname:
            if attr not in variables:
                raise AttributeError(f"_shortname {cls._shortname} references missing or un-annotated attr {attr}")
        for attr in cls._attributes:
            if attr not in variables:
                raise AttributeError(f"_attributes {cls._attributes} references missing or un-annotated attr {attr}")
        for attr in cls._children.values():
            if attr not in variables:
                raise AttributeError(f"_children {cls._children} references missing or un-annotated attr {attr}")

        # Any given field can only be in one of (_identifiers, _attributes, _children)
        id_attr_overlap = set(cls._identifiers).intersection(cls._attributes)
        if id_attr_overlap:
            raise AttributeError(f"Fields {id_attr_overlap} are included in both _identifiers and _attributes.")
        id_child_overlap = set(cls._identifiers).intersection(cls._children.values())
        if id_child_overlap:
            raise AttributeError(f"Fields {id_child_overlap} are included in both _identifiers and _children.")
        attr_child_overlap = set(cls._attributes).intersection(cls._children.values())
        if attr_child_overlap:
            raise AttributeError(f"Fields {attr_child_overlap} are included in both _attributes and _children.")

    def __repr__(self):
        return f'{self.get_type()} "{self.get_unique_id()}"'

    def __str__(self):
        return self.get_unique_id()

    def dict(self, **kwargs) -> dict:
        """Convert this DiffSyncModel to a dict, excluding the diffsync field by default as it is not serializable."""
        if "exclude" not in kwargs:
            kwargs["exclude"] = {"diffsync"}
        return super().dict(**kwargs)

    def json(self, **kwargs) -> str:
        """Convert this DiffSyncModel to a JSON string, excluding the diffsync field by default as it is not serializable."""
        if "exclude" not in kwargs:
            kwargs["exclude"] = {"diffsync"}
        if "exclude_defaults" not in kwargs:
            kwargs["exclude_defaults"] = True
        return super().json(**kwargs)

    def str(self, include_children: bool = True, indent: int = 0) -> str:
        """Build a detailed string representation of this DiffSyncModel and optionally its children."""
        margin = " " * indent
        output = f"{margin}{self.get_type()}: {self.get_unique_id()}: {self.get_attrs()}"
        for modelname, fieldname in self._children.items():
            output += f"\n{margin}  {fieldname}"
            child_ids = getattr(self, fieldname)
            if not child_ids:
                output += ": []"
            elif not self.diffsync or not include_children:
                output += f": {child_ids}"
            else:
                for child_id in child_ids:
                    try:
                        child = self.diffsync.get(modelname, child_id)
                        output += "\n" + child.str(include_children=include_children, indent=indent + 4)
                    except ObjectNotFound:
                        output += f"\n{margin}    {child_id} (ERROR: details unavailable)"
        return output

    def set_status(self, status: DiffSyncStatus, message: Text = ""):
        """Update the status (and optionally status message) of this model in response to a create/update/delete call."""
        self._status = status
        self._status_message = message

    @classmethod
    def create_base(cls, diffsync: "DiffSync", ids: Mapping, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Instantiate this class, along with any platform-specific data creation.

        This method is not meant to be subclassed, users should redefine create() instead.

        Args:
            diffsync: The master data store for other DiffSyncModel instances that we might need to reference
            ids: Dictionary of unique-identifiers needed to create the new object
            attrs: Dictionary of additional attributes to set on the new object

        Returns:
            DiffSyncModel: instance of this class.
        """
        model = cls(**ids, diffsync=diffsync, **attrs)
        model.set_status(DiffSyncStatus.SUCCESS, "Created successfully")
        return model

    @classmethod
    async def create(cls, diffsync: "DiffSync", ids: Mapping, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Instantiate this class, along with any platform-specific data creation.

        Subclasses must call `super().create()` or `self.create_base()`; they may wish to then override the default status information
        by calling `set_status()` to provide more context (such as details of any interactions with underlying systems).

        Args:
            diffsync: The master data store for other DiffSyncModel instances that we might need to reference
            ids: Dictionary of unique-identifiers needed to create the new object
            attrs: Dictionary of additional attributes to set on the new object

        Returns:
            DiffSyncModel: instance of this class, if all data was successfully created.
            None: if data creation failed in such a way that child objects of this model should not be created.

        Raises:
            ObjectNotCreated: if an error occurred.
        """
        return cls.create_base(diffsync=diffsync, ids=ids, attrs=attrs)

    def update_base(self, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Base Update method to update the attributes of this instance, along with any platform-specific data updates.

        This method is not meant to be subclassed, users should redefine update() instead.

        Args:
            attrs: Dictionary of attributes to update on the object

        Returns:
            DiffSyncModel: this instance.
        """
        for attr, value in attrs.items():
            # TODO: enforce that only attrs in self._attributes can be updated in this way?
            setattr(self, attr, value)

        self.set_status(DiffSyncStatus.SUCCESS, "Updated successfully")
        return self

    async def update(self, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Update the attributes of this instance, along with any platform-specific data updates.

        Subclasses must call `super().update()` or `self.update_base()`; they may wish to then override the default status information
        by calling `set_status()` to provide more context (such as details of any interactions with underlying systems).

        Args:
            attrs: Dictionary of attributes to update on the object

        Returns:
            DiffSyncModel: this instance, if all data was successfully updated.
            None: if data updates failed in such a way that child objects of this model should not be modified.

        Raises:
            ObjectNotUpdated: if an error occurred.
        """
        return self.update_base(attrs=attrs)

    def delete_base(self) -> Optional["DiffSyncModel"]:
        """Base delete method Delete any platform-specific data corresponding to this instance.

        This method is not meant to be subclassed, users should redefine delete() instead.

        Returns:
            DiffSyncModel: this instance.
        """
        self.set_status(DiffSyncStatus.SUCCESS, "Deleted successfully")
        return self

    async def delete(self) -> Optional["DiffSyncModel"]:
        """Delete any platform-specific data corresponding to this instance.

        Subclasses must call `super().delete()` or `self.delete_base()`; they may wish to then override the default status information
        by calling `set_status()` to provide more context (such as details of any interactions with underlying systems).

        Returns:
            DiffSyncModel: this instance, if all data was successfully deleted.
            None: if data deletion failed in such a way that child objects of this model should not be deleted.

        Raises:
            ObjectNotDeleted: if an error occurred.
        """
        return self.delete_base()

    @classmethod
    def get_type(cls) -> Text:
        """Return the type AKA modelname of the object or the class

        Returns:
            str: modelname of the class, used in to store all objects
        """
        return cls._modelname

    @classmethod
    def create_unique_id(cls, **identifiers) -> Text:
        """Construct a unique identifier for this model class.

        Args:
            **identifiers: Dict of identifiers and their values, as in `get_identifiers()`.
        """
        return "__".join(str(identifiers[key]) for key in cls._identifiers)

    @classmethod
    def get_children_mapping(cls) -> Mapping[Text, Text]:
        """Get the mapping of types to fieldnames for child models of this model."""
        return cls._children

    def get_identifiers(self) -> Mapping:
        """Get a dict of all identifiers (primary keys) and their values for this object.

        Returns:
            dict: dictionary containing all primary keys for this device, as defined in _identifiers
        """
        return self.dict(include=set(self._identifiers))

    def get_attrs(self) -> Mapping:
        """Get all the non-primary-key attributes or parameters for this object.

        Similar to Pydantic's `BaseModel.dict()` method, with the following key differences:
        1. Does not include the fields in `_identifiers`
        2. Only includes fields explicitly listed in `_attributes`
        3. Does not include any additional fields not listed in `_attributes`

        Returns:
            dict: Dictionary of attributes for this object
        """
        return self.dict(include=set(self._attributes))

    def get_unique_id(self) -> Text:
        """Get the unique ID of an object.

        By default the unique ID is built based on all the primary keys defined in `_identifiers`.

        Returns:
            str: Unique ID for this object
        """
        return self.create_unique_id(**self.get_identifiers())

    def get_shortname(self) -> Text:
        """Get the (not guaranteed-unique) shortname of an object, if any.

        By default the shortname is built based on all the keys defined in `_shortname`.
        If `_shortname` is not specified, then this function is equivalent to `get_unique_id()`.

        Returns:
            str: Shortname of this object
        """
        if self._shortname:
            return "__".join([str(getattr(self, key)) for key in self._shortname])
        return self.get_unique_id()

    def get_status(self) -> Tuple[DiffSyncStatus, Text]:
        """Get the status of the last create/update/delete operation on this object, and any associated message."""
        return (self._status, self._status_message)

    def add_child(self, child: "DiffSyncModel"):
        """Add a child reference to an object.

        The child object isn't stored, only its unique id.
        The name of the target attribute is defined in `_children` per object type

        Raises:
            ObjectStoreWrongType: if the type is not part of `_children`
            ObjectAlreadyExists: if the unique id is already stored
        """
        child_type = child.get_type()

        if child_type not in self._children:
            raise ObjectStoreWrongType(
                f"Unable to store {child_type} as a child of {self.get_type()}; "
                f"valid types are {sorted(self._children.keys())}"
            )

        attr_name = self._children[child_type]
        childs = getattr(self, attr_name)
        if child.get_unique_id() in childs:
            raise ObjectAlreadyExists(f"Already storing a {child_type} with unique_id {child.get_unique_id()}", child)
        childs.append(child.get_unique_id())

    def remove_child(self, child: "DiffSyncModel"):
        """Remove a child reference from an object.

        The name of the storage attribute is defined in `_children` per object type.

        Raises:
            ObjectStoreWrongType: if the child model type is not part of `_children`
            ObjectNotFound: if the child wasn't previously present.
        """
        child_type = child.get_type()

        if child_type not in self._children:
            raise ObjectStoreWrongType(
                f"Unable to find and delete {child_type} as a child of {self.get_type()}; "
                f"valid types are {sorted(self._children.keys())}"
            )

        attr_name = self._children[child_type]
        childs = getattr(self, attr_name)
        if child.get_unique_id() not in childs:
            raise ObjectNotFound(f"{child} was not found as a child in {attr_name}")
        childs.remove(child.get_unique_id())


class DiffSync:  # pylint: disable=too-many-public-methods
    """Class for storing a group of DiffSyncModel instances and diffing/synchronizing to another DiffSync instance."""

    # In any subclass, you would add mapping of names to specific model classes here:
    # modelname1 = MyModelClass1
    # modelname2 = MyModelClass2

    type: ClassVar[Optional[str]] = None
    """Type of the object, will default to the name of the class if not provided."""

    top_level: ClassVar[List[str]] = []
    """List of top-level modelnames to begin from when diffing or synchronizing."""

    def __init__(self, name=None, internal_storage_engine=LocalStore):
        """Generic initialization function.

        Subclasses should be careful to call super().__init__() if they override this method.
        """

        if isinstance(internal_storage_engine, BaseStore):
            self.store = internal_storage_engine
            self.store.diffsync = self
        else:
            self.store = internal_storage_engine(diffsync=self)

        # If the type is not defined, use the name of the class as the default value
        if self.type is None:
            self.type = self.__class__.__name__

        # If the name has not been provided, use the type as the name
        self.name = name if name else self.type

    def __init_subclass__(cls):
        """Validate that references to specific DiffSyncModels use the correct modelnames.

        Called automatically on subclass declaration.
        """
        contents = cls.__dict__
        for name, value in contents.items():
            if isclass(value) and issubclass(value, DiffSyncModel) and value.get_type() != name:
                raise AttributeError(
                    f'Incorrect field name - {value.__name__} has type name "{value.get_type()}", not "{name}"'
                )

        for name in cls.top_level:
            if not hasattr(cls, name):
                raise AttributeError(f'top_level references attribute "{name}" but it is not a class attribute!')
            value = getattr(cls, name)
            if not isclass(value) or not issubclass(value, DiffSyncModel):
                raise AttributeError(f'top_level references attribute "{name}" but it is not a DiffSyncModel subclass!')

    def __str__(self):
        """String representation of a DiffSync."""
        if self.type != self.name:
            return f'{self.type} "{self.name}"'
        return self.type

    def __repr__(self):
        return f"<{str(self)}>"

    def __len__(self):
        """Total number of elements stored."""
        return self.store.count()

    @classmethod
    def _get_initial_value_order(cls) -> List[str]:
        """Get the initial value order of diffsync object.

        Returns:
            List of model-referencing attribute names in the order they are initially processed.
        """
        if hasattr(cls, "top_level") and isinstance(getattr(cls, "top_level"), list):
            value_order = cls.top_level.copy()
        else:
            value_order = []

        for item in dir(cls):
            _method = getattr(cls, item)
            if item in value_order:
                continue
            if isclass(_method) and issubclass(_method, DiffSyncModel):
                value_order.append(item)
        return value_order

    async def load(self):
        """Load all desired data from whatever backend data source into this instance."""
        # No-op in this generic class

    def dict(self, exclude_defaults: bool = True, **kwargs) -> Mapping:
        """Represent the DiffSync contents as a dict, as if it were a Pydantic model."""
        data: Dict[str, Dict[str, Dict]] = {}
        for modelname in self.store.get_all_model_names():
            data[modelname] = {}
            for obj in self.store.get_all(model=modelname):
                data[obj.get_type()][obj.get_unique_id()] = obj.dict(exclude_defaults=exclude_defaults, **kwargs)
        return data

    def str(self, indent: int = 0) -> str:
        """Build a detailed string representation of this DiffSync."""
        margin = " " * indent
        output = ""
        for modelname in self.top_level:
            if output:
                output += "\n"
            output += f"{margin}{modelname}"
            models = self.get_all(modelname)
            if not models:
                output += ": []"
            else:
                for model in models:
                    output += "\n" + model.str(indent=indent + 2)
        return output

    def load_from_dict(self, data: Dict):
        """The reverse of `dict` method, taking a dictionary and loading into the inventory.

        Args:
            data: Dictionary in the format that `dict` would export as
        """
        value_order = self._get_initial_value_order()
        for field_name in value_order:
            model_class = getattr(self, field_name)
            for values in data.get(field_name, {}).values():
                self.add(model_class(**values))

    # ------------------------------------------------------------------------------
    # Synchronization between DiffSync instances
    # ------------------------------------------------------------------------------

    async def sync_from(  # pylint: disable=too-many-arguments
        self,
        source: "DiffSync",
        diff_class: Type[Diff] = Diff,
        flags: DiffSyncFlags = DiffSyncFlags.NONE,
        callback: Optional[Callable[[Text, int, int], None]] = None,
        diff: Optional[Diff] = None,
    ) -> Diff:
        """Synchronize data from the given source DiffSync object into the current DiffSync object.

        Args:
            source (DiffSync): object to sync data from into this one
            diff_class (class): Diff or subclass thereof to use to calculate the diffs to use for synchronization
            flags (DiffSyncFlags): Flags influencing the behavior of this sync.
            callback (function): Function with parameters (stage, current, total), to be called at intervals as the
                calculation of the diff and subsequent sync proceed.
            diff (Diff): An existing diff to be used rather than generating a completely new diff.
        Returns:
            Diff: Diff between origin object and source
        Raises:
            DiffClassMismatch: The provided diff's class does not match the diff_class
        """
        if diff_class and diff:
            if not isinstance(diff, diff_class):
                raise DiffClassMismatch(
                    f"The provided diff's class ({diff.__class__.__name__}) does not match the diff_class: {diff_class.__name__}",
                )

        # Generate the diff if an existing diff was not provided
        if not diff:
            diff = self.diff_from(source, diff_class=diff_class, flags=flags, callback=callback)
        syncer = DiffSyncSyncer(diff=diff, src_diffsync=source, dst_diffsync=self, flags=flags, callback=callback)
        result = await syncer.perform_sync()
        if result:
            self.sync_complete(source, diff, flags, syncer.base_logger)

        return diff

    async def sync_to(  # pylint: disable=too-many-arguments
        self,
        target: "DiffSync",
        diff_class: Type[Diff] = Diff,
        flags: DiffSyncFlags = DiffSyncFlags.NONE,
        callback: Optional[Callable[[Text, int, int], None]] = None,
        diff: Optional[Diff] = None,
    ) -> Diff:
        """Synchronize data from the current DiffSync object into the given target DiffSync object.

        Args:
            target (DiffSync): object to sync data into from this one.
            diff_class (class): Diff or subclass thereof to use to calculate the diffs to use for synchronization
            flags (DiffSyncFlags): Flags influencing the behavior of this sync.
            callback (function): Function with parameters (stage, current, total), to be called at intervals as the
                calculation of the diff and subsequent sync proceed.
            diff (Diff): An existing diff that will be used when determining what needs to be synced.
        Returns:
            Diff: Diff between origin object and target
        Raises:
            DiffClassMismatch: The provided diff's class does not match the diff_class
        """
        return await target.sync_from(self, diff_class=diff_class, flags=flags, callback=callback, diff=diff)

    def sync_complete(
        self,
        source: "DiffSync",
        diff: Diff,
        flags: DiffSyncFlags = DiffSyncFlags.NONE,
        logger: structlog.BoundLogger = None,
    ):
        """Callback triggered after a `sync_from` operation has completed and updated the model data of this instance.

        Note that this callback is **only** triggered if the sync actually resulted in data changes. If there are no
        detected changes, this callback will **not** be called.

        The default implementation does nothing, but a subclass could use this, for example, to perform bulk updates
        to a backend (such as a file) that doesn't readily support incremental updates to individual records.

        Args:
          source: The DiffSync whose data was used to update this instance.
          diff: The Diff calculated prior to the sync operation.
          flags: Any flags that influenced the sync.
          logger: Logging context for the sync.
        """

    # ------------------------------------------------------------------------------
    # Diff calculation and construction
    # ------------------------------------------------------------------------------

    def diff_from(
        self,
        source: "DiffSync",
        diff_class: Type[Diff] = Diff,
        flags: DiffSyncFlags = DiffSyncFlags.NONE,
        callback: Optional[Callable[[Text, int, int], None]] = None,
    ) -> Diff:
        """Generate a Diff describing the difference from the other DiffSync to this one.

        Args:
            source (DiffSync): Object to diff against.
            diff_class (class): Diff or subclass thereof to use for diff calculation and storage.
            flags (DiffSyncFlags): Flags influencing the behavior of this diff operation.
            callback (function): Function with parameters (stage, current, total), to be called at intervals as the
                calculation of the diff proceeds.
        """
        differ = DiffSyncDiffer(
            src_diffsync=source, dst_diffsync=self, flags=flags, diff_class=diff_class, callback=callback
        )
        return differ.calculate_diffs()

    def diff_to(
        self,
        target: "DiffSync",
        diff_class: Type[Diff] = Diff,
        flags: DiffSyncFlags = DiffSyncFlags.NONE,
        callback: Optional[Callable[[Text, int, int], None]] = None,
    ) -> Diff:
        """Generate a Diff describing the difference from this DiffSync to another one.

        Args:
            target (DiffSync): Object to diff against.
            diff_class (class): Diff or subclass thereof to use for diff calculation and storage.
            flags (DiffSyncFlags): Flags influencing the behavior of this diff operation.
            callback (function): Function with parameters (stage, current, total), to be called at intervals as the
                calculation of the diff proceeds.
        """
        return target.diff_from(self, diff_class=diff_class, flags=flags, callback=callback)

    # ------------------------------------------------------------------------------
    # Object Storage Management
    # ------------------------------------------------------------------------------

    def get_all_model_names(self):
        """Get all model names.

        Returns:
            List[str]: List of model names
        """
        return self.store.get_all_model_names()

    def get(
        self, obj: Union[Text, DiffSyncModel, Type[DiffSyncModel]], identifier: Union[Text, Mapping]
    ) -> DiffSyncModel:
        """Get one object from the data store based on its unique id.

        Args:
            obj: DiffSyncModel class or instance, or modelname string, that defines the type of the object to retrieve
            identifier: Unique ID of the object to retrieve, or dict of unique identifier keys/values

        Raises:
            ValueError: if obj is a str and identifier is a dict (can't convert dict into a uid str without a model class)
            ObjectNotFound: if the requested object is not present
        """
        return self.store.get(model=obj, identifier=identifier)

    def get_or_none(
        self, obj: Union[Text, DiffSyncModel, Type[DiffSyncModel]], identifier: Union[Text, Mapping]
    ) -> Optional[DiffSyncModel]:
        """Get one object from the data store based on its unique id or get a None

        Args:
            obj: DiffSyncModel class or instance, or modelname string, that defines the type of the object to retrieve
            identifier: Unique ID of the object to retrieve, or dict of unique identifier keys/values

        Raises:
            ValueError: if obj is a str and identifier is a dict (can't convert dict into a uid str without a model class)

        Returns:
            DiffSyncModel matching provided criteria
        """
        try:
            return self.get(obj, identifier)
        except ObjectNotFound:
            return None

    def get_all(self, obj: Union[Text, DiffSyncModel, Type[DiffSyncModel]]) -> List[DiffSyncModel]:
        """Get all objects of a given type.

        Args:
            obj: DiffSyncModel class or instance, or modelname string, that defines the type of the objects to retrieve

        Returns:
            List[DiffSyncModel]: List of Object
        """
        return self.store.get_all(model=obj)

    def get_by_uids(
        self, uids: List[Text], obj: Union[Text, DiffSyncModel, Type[DiffSyncModel]]
    ) -> List[DiffSyncModel]:
        """Get multiple objects from the store by their unique IDs/Keys and type.

        Args:
            uids: List of unique id / key identifying object in the database.
            obj: DiffSyncModel class or instance, or modelname string, that defines the type of the objects to retrieve

        Raises:
            ObjectNotFound: if any of the requested UIDs are not found in the store
        """
        return self.store.get_by_uids(uids=uids, model=obj)

    @classmethod
    def get_tree_traversal(cls, as_dict: bool = False) -> Union[Text, Mapping]:
        """Get a string describing the tree traversal for the diffsync object.

        Args:
            as_dict: Whether or not to return as a dictionary

        Returns:
            A string or dictionary representation of tree
        """
        value_order = cls._get_initial_value_order()
        output_dict: Dict = {}
        for key in value_order:
            model_obj = getattr(cls, key)
            if not get_path(output_dict, key):
                set_key(output_dict, [key])
            if hasattr(model_obj, "_children"):
                children = getattr(model_obj, "_children")
                for child_key in list(children.keys()):
                    path = get_path(output_dict, key) or [key]
                    path.append(child_key)
                    set_key(output_dict, path)
        if as_dict:
            return output_dict
        return tree_string(output_dict, cls.__name__)

    def add(self, obj: DiffSyncModel):
        """Add a DiffSyncModel object to the store.

        Args:
            obj (DiffSyncModel): Object to store

        Raises:
            ObjectAlreadyExists: if a different object with the same uid is already present.
        """
        return self.store.add(obj=obj)

    def update(self, obj: DiffSyncModel):
        """Update a DiffSyncModel object to the store.

        Args:
            obj (DiffSyncModel): Object to store

        Raises:
            ObjectAlreadyExists: if a different object with the same uid is already present.
        """
        return self.store.update(obj=obj)

    def remove(self, obj: DiffSyncModel, remove_children: bool = False):
        """Remove a DiffSyncModel object from the store.

        Args:
            obj (DiffSyncModel): object to remove
            remove_children (bool): If True, also recursively remove any children of this object

        Raises:
            ObjectNotFound: if the object is not present
        """
        return self.store.remove(obj=obj, remove_children=remove_children)

    def get_or_instantiate(
        self, model: Type[DiffSyncModel], ids: Dict, attrs: Dict = None
    ) -> Tuple[DiffSyncModel, bool]:
        """Attempt to get the object with provided identifiers or instantiate it with provided identifiers and attrs.

        Args:
            model (DiffSyncModel): The DiffSyncModel to get or create.
            ids (Mapping): Identifiers for the DiffSyncModel to get or create with.
            attrs (Mapping, optional): Attributes when creating an object if it doesn't exist. Defaults to None.

        Returns:
            Tuple[DiffSyncModel, bool]: Provides the existing or new object and whether it was created or not.
        """
        return self.store.get_or_instantiate(model=model, ids=ids, attrs=attrs)

    def get_or_add_model_instance(self, obj: DiffSyncModel) -> Tuple[DiffSyncModel, bool]:
        """Attempt to get the object with provided obj identifiers or instantiate obj.

        Args:
            obj: An obj of the DiffSyncModel to get or add.

        Returns:
            Provides the existing or new object and whether it was created or not.
        """
        return self.store.get_or_add_model_instance(obj=obj)

    def update_or_instantiate(self, model: Type[DiffSyncModel], ids: Dict, attrs: Dict) -> Tuple[DiffSyncModel, bool]:
        """Attempt to update an existing object with provided ids/attrs or instantiate it with provided identifiers and attrs.

        Args:
            model (DiffSyncModel): The DiffSyncModel to update or create.
            ids (Dict): Identifiers for the DiffSyncModel to update or create with.
            attrs (Dict): Attributes when creating/updating an object if it doesn't exist. Pass in empty dict, if no specific attrs.

        Returns:
            Tuple[DiffSyncModel, bool]: Provides the existing or new object and whether it was created or not.
        """
        return self.store.update_or_instantiate(model=model, ids=ids, attrs=attrs)

    def update_or_add_model_instance(self, obj: DiffSyncModel) -> Tuple[DiffSyncModel, bool]:
        """Attempt to update an existing object with provided obj ids/attrs or instantiate obj.

        Args:
            instance: An instance of the DiffSyncModel to update or create.

        Returns:
            Provides the existing or new object and whether it was created or not.
        """
        return self.store.update_or_add_model_instance(obj=obj)

    def count(self, model: Union[Text, "DiffSyncModel", Type["DiffSyncModel"], None] = None):
        """Count how many objects of one model type exist in the backend store.

        Args:
            model (DiffSyncModel): The DiffSyncModel to check the number of elements. If not provided, default to all.

        Returns:
            Int: Number of elements of the model type
        """
        return self.store.count(model=model)


# DiffSyncModel references DiffSync and DiffSync references DiffSyncModel. Break the typing loop:
DiffSyncModel.update_forward_refs()
