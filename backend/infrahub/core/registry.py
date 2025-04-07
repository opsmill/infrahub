from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.exceptions import BranchNotFoundError, DataTypeNotFoundError, InitializationError

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.manager import NodeManager
    from infrahub.core.schema import MainSchemaTypes, NodeSchema
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.mutations.attribute import BaseAttributeCreate, BaseAttributeUpdate
    from infrahub.graphql.types import InfrahubObject
    from infrahub.permissions import PermissionBackend
    from infrahub.storage import InfrahubObjectStorage
    from infrahub.types import InfrahubDataType


@dataclass
class Registry:
    id: str | None = None
    attribute: dict[str, type[BaseAttribute]] = field(default_factory=dict)
    branch: dict[str, Branch] = field(default_factory=dict)
    node: dict = field(default_factory=dict)
    _default_branch: str | None = None
    _default_ipnamespace: str | None = None
    _schema: SchemaManager | None = None
    default_graphql_type: dict[str, InfrahubObject | type[BaseAttribute]] = field(default_factory=dict)
    graphql_type: dict = field(default_factory=lambda: defaultdict(dict))
    data_type: dict[str, type[InfrahubDataType]] = field(default_factory=dict)
    input_type: dict[str, type[BaseAttributeCreate | BaseAttributeUpdate]] = field(default_factory=dict)
    attr_group: dict = field(default_factory=dict)
    _branch_object: type[Branch] | None = None
    _manager: type[NodeManager] | None = None
    _storage: InfrahubObjectStorage | None = None
    permission_backends: list[PermissionBackend] = field(default_factory=list)

    @property
    def branch_object(self) -> type[Branch]:
        if not self._branch_object:
            raise InitializationError
        return self._branch_object

    @branch_object.setter
    def branch_object(self, value: type[Branch]) -> None:
        self._branch_object = value

    @property
    def default_branch(self) -> str:
        if not self._default_branch:
            raise InitializationError()

        return self._default_branch

    @default_branch.setter
    def default_branch(self, value: str) -> None:
        self._default_branch = value

    @property
    def default_ipnamespace(self) -> str:
        if not self._default_ipnamespace:
            raise InitializationError()

        return self._default_ipnamespace

    @default_ipnamespace.setter
    def default_ipnamespace(self, value: str) -> None:
        self._default_ipnamespace = value

    @property
    def schema(self) -> SchemaManager:
        if not self._schema:
            raise InitializationError()

        return self._schema

    @schema.setter
    def schema(self, value: SchemaManager) -> None:
        self._schema = value

    @property
    def manager(self) -> type[NodeManager]:
        if not self._manager:
            raise InitializationError

        return self._manager

    @manager.setter
    def manager(self, value: type[NodeManager]) -> None:
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

    def get_node_schema(self, name: str, branch: Branch | str | None = None) -> NodeSchema:
        return self.schema.get_node_schema(name=name, branch=branch)

    def get_data_type(self, name: str) -> type[InfrahubDataType]:
        if name not in self.data_type:
            raise DataTypeNotFoundError(name=name)
        return self.data_type[name]

    def get_full_schema(self, branch: Branch | str | None = None, duplicate: bool = True) -> dict[str, MainSchemaTypes]:
        """Return all the nodes in the schema for a given branch."""
        return self.schema.get_full(branch=branch, duplicate=duplicate)

    def delete_all(self) -> None:
        self.branch = {}
        self.node = {}
        self._schema = None
        self._default_ipnamespace = None
        self.attr_group = {}
        self.data_type = {}
        self.attribute = {}
        self.input_type = {}

    def get_branch_from_registry(self, branch: Branch | str | None = None) -> Branch:
        """Return a branch object from the registry based on its name.

        Args:
            branch (Optional[Union[Branch, str]]): Branch object or name of a branch

        Raises:
            BranchNotFoundError:

        Returns:
            Branch: A Branch Object
        """

        if branch and not isinstance(branch, str):
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
        session: AsyncSession | None = None,
        branch: Branch | str | None = None,
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

        if branch and not isinstance(branch, str):
            return branch

        if not branch or not isinstance(branch, str):
            branch = registry.default_branch

        try:
            return self.get_branch_from_registry(branch=branch)
        except BranchNotFoundError:
            if not session and not db:
                raise

        async with lock.registry.local_schema_lock():
            obj = await self.branch_object.get_by_name(name=branch, db=db)
            registry.branch[branch] = obj

            # Pull the schema for this branch
            await registry.schema.load_schema(db=db, branch=obj)

        return obj

    def get_global_branch(self) -> Branch:
        return self.get_branch_from_registry(branch=GLOBAL_BRANCH_NAME)

    def get_altered_schema_branches(self) -> list[str]:
        """Return a list of branch names that has a different hash than the default branch"""
        default_branch = self.branch[registry.default_branch]
        return [
            name
            for name, branch in self.branch.items()
            if name not in [registry.default_branch, GLOBAL_BRANCH_NAME]
            and branch.active_schema_hash.main != default_branch.active_schema_hash.main
        ]

    async def purge_inactive_branches(
        self, db: InfrahubDatabase, active_branches: list[Branch] | None = None
    ) -> list[str]:
        """Return a list of branches that were purged from the registry."""
        active_branches = active_branches or await self.branch_object.get_list(db=db)
        active_branch_names = [branch.name for branch in active_branches]
        purged_branches: set[str] = set()

        for branch_name in list(registry.branch.keys()):
            if branch_name not in active_branch_names:
                del registry.branch[branch_name]
                purged_branches.add(branch_name)

        purged_branches.update(self.schema.purge_inactive_branches(active_branches=active_branch_names))
        purged_branches.update(db.purge_inactive_schemas(active_branches=active_branch_names))

        return sorted(purged_branches)


registry = Registry()
