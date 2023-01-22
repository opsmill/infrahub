from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional, Union

import infrahub.config as config
from infrahub.exceptions import BranchNotFound

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch
    from infrahub.core.schema import GenericSchema, GroupSchema, NodeSchema
    from infrahub.graphql.query import InfrahubObject


def get_branch_from_registry(branch: Optional[Union[Branch, str]] = None) -> Branch:
    """Return a branch object from the registry based on its name.

    Args:
        branch (Optional[Union[Branch, str]]): Branch object or name of a branch

    Raises:
        BranchNotFound:

    Returns:
        Branch: A Branch Object
    """

    from .branch import Branch

    if isinstance(branch, Branch):
        return branch

    # if the name of the branch is not defined or not a string we used the default branch name
    if not branch or not isinstance(branch, str):
        branch = config.SETTINGS.main.default_branch

    # Try to get it from the registry
    #   if not present in the registry and if a session has been provided get it from the database directly
    #   and update the registry
    if branch in registry.branch:
        return registry.branch[branch]

    raise BranchNotFound(identifier=branch)


async def get_branch(branch: Optional[Union[Branch, str]], session: Optional[AsyncSession] = None) -> Branch:
    """Return a branch object based on its name.

    First the function will chec in the registry and if the Branch is not present,
     and if a session object has been provided it will attempt to retrieve the branch from the database.

    Args:
        branch (Optional[Union[Branch, str]]): Branch object or name of a branch
        session (Optional[AsyncSession], optional): AsyncSession to connect to the database. Defaults to None.

    Raises:
        BranchNotFound:

    Returns:
        Branch: A Branch Object
    """

    from .branch import Branch

    if not branch or not isinstance(branch, str):
        branch = config.SETTINGS.main.default_branch

    try:
        return get_branch_from_registry(branch=branch)
    except BranchNotFound:
        if not session:
            raise

    obj = await Branch.get_by_name(branch, session=session)
    registry.branch[branch] = obj

    return obj


async def get_account(
    account,
    session: AsyncSession,
    branch=None,
    at=None,
):

    # No default value supported for now
    if not account:
        return None

    if hasattr(account, "schema") and account.schema.kind == "Account":
        return account

    # Try to get it from the registry
    #   if not present in the registry, get it from the database directly
    #   and update the registry
    if account in registry.account:
        return registry.account[account]

    from infrahub.core.manager import NodeManager

    account_schema = registry.get_schema(name="Account")

    obj = await NodeManager.query(
        account_schema, filters={account_schema.default_filter: account}, branch=branch, at=at, session=session
    )
    registry.account[account] = obj

    return obj


def get_account_by_id(id):

    # No default value supported for now
    if not id:
        return None

    # from .account import Account

    # if id in registry.account_id:
    #     return registry.account_id[id]

    # obj = Account.get(id=id)
    # if not obj:
    #     return None

    # registry.account[obj.name.value] = obj
    # registry.account_id[id] = obj
    # return obj


@dataclass
class Registry:
    branch: dict = field(default_factory=dict)
    node: dict = field(default_factory=dict)
    schema: dict = field(default_factory=lambda: defaultdict(dict))
    graphql_type: dict = field(default_factory=lambda: defaultdict(dict))
    account: dict = field(default_factory=dict)
    account_id: dict = field(default_factory=dict)
    node_group: dict = field(default_factory=dict)
    attr_group: dict = field(default_factory=dict)

    def set_item(self, kind: str, name: str, item, branch: str = None) -> bool:
        branch = branch or config.SETTINGS.main.default_branch
        getattr(self, kind)[branch][name] = item
        return True

    def has_item(self, kind: str, name: str, branch=None) -> bool:
        try:
            self.get_item(kind=kind, name=name, branch=branch)
            return True
        except ValueError:
            return False

    def get_item(self, kind: str, name: str, branch: Optional[Union[Branch, str]] = None):

        branch = get_branch_from_registry(branch=branch)

        attr = getattr(self, kind)

        if branch.name in attr and name in attr[branch.name]:
            return attr[branch.name][name]

        default_branch = config.SETTINGS.main.default_branch
        if name in attr[default_branch]:
            return attr[default_branch][name]

        raise ValueError(f"Unable to find the {kind} {name} for the branch {branch.name} in the registry")

    def get_all_item(self, kind: str, branch: Optional[Union[Branch, str]] = None) -> dict:
        """Return all the nodes in the schema for a given branch.
        The current implementation is a bit simplistic, will need to re-evaluate."""
        branch = get_branch_from_registry(branch=branch)

        attr = getattr(self, kind)

        if branch.name in attr:
            return attr[branch.name]

        default_branch = config.SETTINGS.main.default_branch
        return attr[default_branch]

    def set_schema(
        self, name: str, schema: Union[NodeSchema, GenericSchema, GroupSchema], branch: Optional[str] = None
    ) -> bool:
        return self.set_item(kind="schema", name=name, item=schema, branch=branch)

    def has_schema(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        return self.has_item(kind="schema", name=name, branch=branch)

    def get_schema(
        self, name: str, branch: Optional[Union[Branch, str]] = None
    ) -> Union[NodeSchema, GenericSchema, GroupSchema]:
        return self.get_item(kind="schema", name=name, branch=branch)

    def get_full_schema(
        self, branch: Optional[Union[Branch, str]] = None
    ) -> Dict[str, Union[NodeSchema, GenericSchema, GroupSchema]]:
        """Return all the nodes in the schema for a given branch.

        The current implementation is a bit simplistic, will need to re-evaluate."""
        return self.get_all_item(kind="schema", branch=branch)

    def set_graphql_type(self, name: str, graphql_type: InfrahubObject, branch: Optional[str] = None) -> bool:
        return self.set_item(kind="graphql_type", name=name, item=graphql_type, branch=branch)

    def has_graphql_type(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        return self.has_item(kind="graphql_type", name=name, branch=branch)

    def get_graphql_type(self, name: str, branch: Optional[Union[Branch, str]] = None) -> InfrahubObject:
        return self.get_item(kind="graphql_type", name=name, branch=branch)

    def get_all_graphql_type(self, branch: Optional[Union[Branch, str]] = None) -> Dict[str, InfrahubObject]:
        """Return all the graphql_type for a given branch."""
        return self.get_all_item(kind="graphql_type", branch=branch)


registry = Registry()
