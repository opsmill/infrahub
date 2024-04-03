from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional, Type, Union

from infrahub import lock
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.exceptions import (
    BranchNotFoundError,
    DataTypeNotFoundError,
    Error,
    InitializationError,
)

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.definitions import Brancher
    from infrahub.core.manager import NodeManager
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.core.schema_manager import SchemaManager
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.mutations.attribute import BaseAttributeCreate, BaseAttributeUpdate
    from infrahub.graphql.types import InfrahubObject
    from infrahub.storage import InfrahubObjectStorage
    from infrahub.types import InfrahubDataType

# pylint: disable=too-many-public-methods


@dataclass
class Registry:
    id: Optional[str] = None
    attribute: Dict[str, BaseAttribute] = field(default_factory=dict)
    branch: dict = field(default_factory=dict)
    node: dict = field(default_factory=dict)
    _default_branch: Optional[str] = None
    _schema: Optional[SchemaManager] = None
    default_graphql_type: Dict[str, InfrahubObject] = field(default_factory=dict)
    graphql_type: dict = field(default_factory=lambda: defaultdict(dict))
    data_type: Dict[str, InfrahubDataType] = field(default_factory=dict)
    input_type: Dict[str, Union[BaseAttributeCreate, BaseAttributeUpdate]] = field(default_factory=dict)
    account: dict = field(default_factory=dict)
    account_id: dict = field(default_factory=dict)
    node_group: dict = field(default_factory=dict)
    attr_group: dict = field(default_factory=dict)
    branch_object: Optional[Type[Brancher]] = None
    _manager: Optional[Type[NodeManager]] = None
    _storage: Optional[InfrahubObjectStorage] = None

    @property
    def default_branch(self) -> str:
        if not self._default_branch:
            raise InitializationError()

        return self._default_branch

    @default_branch.setter
    def default_branch(self, value: str) -> None:
        self._default_branch = value

    @property
    def schema(self) -> SchemaManager:
        if not self._schema:
            raise InitializationError()

        return self._schema

    @schema.setter
    def schema(self, value: SchemaManager) -> None:
        self._schema = value

    @property
    def manager(self) -> Type[NodeManager]:
        if not self._manager:
            raise InitializationError

        return self._manager

    @manager.setter
    def manager(self, value: Type[NodeManager]) -> None:
        self._manager = value

    @property
    def storage(self) -> InfrahubObjectStorage:
        if not self._storage:
            raise InitializationError

        return self._storage

    @storage.setter
    def storage(self, value: InfrahubObjectStorage) -> None:
        self._storage = value

    def schema_has_been_initialized(self) -> bool:
        if self._schema:
            return True
        return False

    def get_node_schema(self, name: str, branch: Optional[Union[Branch, str]] = None) -> NodeSchema:
        return self.schema.get_node_schema(name=name, branch=branch)

    def get_data_type(
        self,
        name: str,
    ) -> InfrahubDataType:
        if name not in self.data_type:
            raise DataTypeNotFoundError(name=name)
        return self.data_type[name]

    def get_full_schema(
        self, branch: Optional[Union[Branch, str]] = None
    ) -> Dict[str, Union[NodeSchema, GenericSchema]]:
        """Return all the nodes in the schema for a given branch."""
        return self.schema.get_full(branch=branch)

    def delete_all(self) -> None:
        self.branch = {}
        self.node = {}
        self._schema = None
        self.account = {}
        self.account_id = {}
        self.node_group = {}
        self.attr_group = {}
        self.data_type = {}
        self.attribute = {}
        self.input_type = {}

    def get_branch_from_registry(self, branch: Optional[Union[Branch, str]] = None) -> Branch:
        """Return a branch object from the registry based on its name.

        Args:
            branch (Optional[Union[Branch, str]]): Branch object or name of a branch

        Raises:
            BranchNotFoundError:

        Returns:
            Branch: A Branch Object
        """

        if self.branch_object and branch:
            if self.branch_object.isinstance(branch) and not isinstance(branch, str):
                return branch

        # if the name of the branch is not defined or not a string we used the default branch name
        if not branch or not isinstance(branch, str):
            branch = registry.default_branch

        # Try to get it from the registry
        #   if not present in the registry and if a session has been provided get it from the database directly
        #   and update the registry
        if branch in self.branch:
            return self.branch[branch]

        raise BranchNotFoundError(identifier=branch)

    async def get_branch(
        self,
        db: InfrahubDatabase,
        session: Optional[AsyncSession] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> Branch:
        """Return a branch object based on its name.

        First the function will check in the registry
        if the Branch is not present, and if a session object has been provided
            it will attempt to retrieve the branch and its schema from the database.

        Args:
            branch (Optional[Union[Branch, str]]): Branch object or name of a branch
            session (Optional[AsyncSession], optional): AsyncSession to connect to the database. Defaults to None.

        Raises:
            BranchNotFoundError:

        Returns:
            Branch: A Branch Object
        """

        branch_name = ""
        if not isinstance(branch, str) and branch is not None:
            branch_name = branch.name

        if self.branch_object and branch:
            if self.branch_object.isinstance(branch) and not isinstance(branch, str):
                return branch

        if (self.branch_object and self.branch_object.isinstance(branch) and branch_name == GLOBAL_BRANCH_NAME) or (
            isinstance(branch, str) and branch == GLOBAL_BRANCH_NAME
        ):
            raise BranchNotFoundError(identifier=GLOBAL_BRANCH_NAME)

        if not branch or not isinstance(branch, str):
            branch = registry.default_branch

        try:
            return self.get_branch_from_registry(branch=branch)
        except BranchNotFoundError:
            if not session and not db:
                raise

        if not self.branch_object:
            raise Error("Branch object not initialized")

        async with lock.registry.local_schema_lock():
            obj = await self.branch_object.get_by_name(name=branch, db=db)
            registry.branch[branch] = obj

            # Pull the schema for this branch
            await registry.schema.load_schema(db=db, branch=obj)

        return obj

    def get_global_branch(self) -> Branch:
        return self.get_branch_from_registry(branch=GLOBAL_BRANCH_NAME)


registry = Registry()
