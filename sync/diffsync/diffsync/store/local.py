"""LocalStore module."""

from collections import defaultdict
from typing import List, Mapping, Text, Type, Union, TYPE_CHECKING, Dict, Set

from diffsync.exceptions import ObjectNotFound, ObjectAlreadyExists
from diffsync.store import BaseStore


if TYPE_CHECKING:
    from diffsync import DiffSyncModel


class LocalStore(BaseStore):
    """LocalStore class."""

    def __init__(self, *args, **kwargs) -> None:
        """Init method for LocalStore."""
        super().__init__(*args, **kwargs)

        self._data: Dict = defaultdict(dict)

    def get_all_model_names(self) -> Set[str]:
        """Get all the model names stored.

        Return:
            Set[str]: Set of all the model names.
        """
        return set(self._data.keys())

    def get(
        self, *, model: Union[Text, "DiffSyncModel", Type["DiffSyncModel"]], identifier: Union[Text, Mapping]
    ) -> "DiffSyncModel":
        """Get one object from the data store based on its unique id.

        Args:
            model: DiffSyncModel class or instance, or modelname string, that defines the type of the object to retrieve
            identifier: Unique ID of the object to retrieve, or dict of unique identifier keys/values

        Raises:
            ValueError: if obj is a str and identifier is a dict (can't convert dict into a uid str without a model class)
            ObjectNotFound: if the requested object is not present
        """
        object_class, modelname = self._get_object_class_and_model(model)

        uid = self._get_uid(model, object_class, identifier)

        if uid not in self._data[modelname]:
            raise ObjectNotFound(f"{modelname} {uid} not present in {str(self)}")
        return self._data[modelname][uid]

    def get_all(self, *, model: Union[Text, "DiffSyncModel", Type["DiffSyncModel"]]) -> List["DiffSyncModel"]:
        """Get all objects of a given type.

        Args:
            model: DiffSyncModel class or instance, or modelname string, that defines the type of the objects to retrieve

        Returns:
            List[DiffSyncModel]: List of Object
        """
        if isinstance(model, str):
            modelname = model
        else:
            modelname = model.get_type()

        return list(self._data[modelname].values())

    def get_by_uids(
        self, *, uids: List[Text], model: Union[Text, "DiffSyncModel", Type["DiffSyncModel"]]
    ) -> List["DiffSyncModel"]:
        """Get multiple objects from the store by their unique IDs/Keys and type.

        Args:
            uids: List of unique id / key identifying object in the database.
            model: DiffSyncModel class or instance, or modelname string, that defines the type of the objects to retrieve

        Raises:
            ObjectNotFound: if any of the requested UIDs are not found in the store
        """
        if isinstance(model, str):
            modelname = model
        else:
            modelname = model.get_type()

        results = []
        for uid in uids:
            if uid not in self._data[modelname]:
                raise ObjectNotFound(f"{modelname} {uid} not present in {str(self)}")
            results.append(self._data[modelname][uid])
        return results

    def add(self, *, obj: "DiffSyncModel"):
        """Add a DiffSyncModel object to the store.

        Args:
            obj (DiffSyncModel): Object to store

        Raises:
            ObjectAlreadyExists: if a different object with the same uid is already present.
        """
        modelname = obj.get_type()
        uid = obj.get_unique_id()

        existing_obj = self._data[modelname].get(uid)
        if existing_obj:
            if existing_obj is not obj:
                raise ObjectAlreadyExists(f"Object {uid} already present", obj)
            # Return so we don't have to change anything on the existing object and underlying data
            return

        if not obj.diffsync:
            obj.diffsync = self.diffsync

        self._data[modelname][uid] = obj

    def update(self, *, obj: "DiffSyncModel"):
        """Update a DiffSyncModel object to the store.

        Args:
            obj (DiffSyncModel): Object to update
        """
        modelname = obj.get_type()
        uid = obj.get_unique_id()

        existing_obj = self._data[modelname].get(uid)
        if existing_obj is obj:
            return

        self._data[modelname][uid] = obj

    def remove_item(self, modelname: str, uid: str):
        """Remove one item from store."""
        if uid not in self._data[modelname]:
            raise ObjectNotFound(f"{modelname} {uid} not present in {str(self)}")
        del self._data[modelname][uid]

    def count(self, *, model: Union[Text, "DiffSyncModel", Type["DiffSyncModel"], None] = None) -> int:
        """Returns the number of elements of a specific model, or all elements in the store if unspecified."""
        if not model:
            return sum(len(entries) for entries in self._data.values())

        if isinstance(model, str):
            modelname = model
        else:
            modelname = model.get_type()
        return len(self._data[modelname])
