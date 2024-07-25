from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import BaseModel

from infrahub_sdk.exceptions import BranchNotFoundError
from infrahub_sdk.graphql import Mutation, Query
from infrahub_sdk.utils import decode_json

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync


class BranchData(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    sync_with_git: bool
    is_default: bool
    has_schema_changes: bool
    origin_branch: Optional[str] = None
    branched_from: str


BRANCH_DATA = {
    "id": None,
    "name": None,
    "description": None,
    "origin_branch": None,
    "branched_from": None,
    "is_default": None,
    "sync_with_git": None,
    "has_schema_changes": None,
}

BRANCH_DATA_FILTER = {"@filters": {"name": "$branch_name"}}


MUTATION_QUERY_DATA = {"ok": None, "object": BRANCH_DATA}

QUERY_ALL_BRANCHES_DATA = {"Branch": BRANCH_DATA}

QUERY_ONE_BRANCH_DATA = {"Branch": {**BRANCH_DATA, **BRANCH_DATA_FILTER}}


class InfraHubBranchManagerBase:
    @classmethod
    def generate_diff_data_url(
        cls,
        client: Union[InfrahubClient, InfrahubClientSync],
        branch_name: str,
        branch_only: bool = True,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> str:
        """Generate the URL for the diff_data function."""
        url = f"{client.address}/api/diff/data?branch={branch_name}"
        url += f"&branch_only={str(branch_only).lower()}"
        if time_from:
            url += f"&time_from={time_from}"
        if time_to:
            url += f"&time_to={time_to}"

        return url


class InfrahubBranchManager(InfraHubBranchManagerBase):
    def __init__(self, client: InfrahubClient):
        self.client = client

    async def create(
        self,
        branch_name: str,
        sync_with_git: bool = True,
        description: str = "",
        background_execution: bool = False,
    ) -> BranchData:
        input_data = {
            "background_execution": background_execution,
            "data": {
                "name": branch_name,
                "description": description,
                "sync_with_git": sync_with_git,
            },
        }

        query = Mutation(mutation="BranchCreate", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-create")

        return BranchData(**response["BranchCreate"]["object"])

    async def delete(self, branch_name: str) -> bool:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchDelete", input_data=input_data, query={"ok": None})
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-delete")
        return response["BranchDelete"]["ok"]

    async def rebase(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchRebase", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-rebase")
        return response["BranchRebase"]["ok"]

    async def validate(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }

        query_data = {
            "ok": None,
            "messages": None,
            "object": {
                "id": None,
                "name": None,
            },
        }

        query = Mutation(mutation="BranchValidate", input_data=input_data, query=query_data)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-validate")

        return response["BranchValidate"]["ok"]

    async def merge(self, branch_name: str) -> bool:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchMerge", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(
            query=query.render(), tracker="mutation-branch-merge", timeout=max(120, self.client.default_timeout)
        )

        return response["BranchMerge"]["ok"]

    async def all(self) -> dict[str, BranchData]:
        query = Query(name="GetAllBranch", query=QUERY_ALL_BRANCHES_DATA)
        data = await self.client.execute_graphql(query=query.render(), tracker="query-branch-all")

        branches = {branch["name"]: BranchData(**branch) for branch in data["Branch"]}

        return branches

    async def get(self, branch_name: str) -> BranchData:
        query = Query(name="GetBranch", query=QUERY_ONE_BRANCH_DATA, variables={"branch_name": str})
        data = await self.client.execute_graphql(
            query=query.render(),
            variables={"branch_name": branch_name},
            tracker="query-branch",
        )

        if not data["Branch"]:
            raise BranchNotFoundError(identifier=branch_name)
        return BranchData(**data["Branch"][0])

    async def diff_data(
        self,
        branch_name: str,
        branch_only: bool = True,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> dict[Any, Any]:
        url = self.generate_diff_data_url(
            client=self.client,
            branch_name=branch_name,
            branch_only=branch_only,
            time_from=time_from,
            time_to=time_to,
        )
        response = await self.client._get(url=url, headers=self.client.headers)
        return decode_json(response=response)


class InfrahubBranchManagerSync(InfraHubBranchManagerBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client

    def all(self) -> dict[str, BranchData]:
        query = Query(name="GetAllBranch", query=QUERY_ALL_BRANCHES_DATA)
        data = self.client.execute_graphql(query=query.render(), tracker="query-branch-all")

        branches = {branch["name"]: BranchData(**branch) for branch in data["Branch"]}

        return branches

    def get(self, branch_name: str) -> BranchData:
        query = Query(name="GetBranch", query=QUERY_ONE_BRANCH_DATA, variables={"branch_name": str})
        data = self.client.execute_graphql(
            query=query.render(),
            variables={"branch_name": branch_name},
            tracker="query-branch",
        )

        if not data["Branch"]:
            raise BranchNotFoundError(identifier=branch_name)
        return BranchData(**data["Branch"][0])

    def create(
        self,
        branch_name: str,
        sync_with_git: bool = True,
        description: str = "",
        background_execution: bool = False,
    ) -> BranchData:
        input_data = {
            "background_execution": background_execution,
            "data": {
                "name": branch_name,
                "description": description,
                "sync_with_git": sync_with_git,
            },
        }

        query = Mutation(mutation="BranchCreate", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-create")

        return BranchData(**response["BranchCreate"]["object"])

    def delete(self, branch_name: str) -> bool:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchDelete", input_data=input_data, query={"ok": None})
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-delete")
        return response["BranchDelete"]["ok"]

    def diff_data(
        self,
        branch_name: str,
        branch_only: bool = True,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> dict[Any, Any]:
        url = self.generate_diff_data_url(
            client=self.client,
            branch_name=branch_name,
            branch_only=branch_only,
            time_from=time_from,
            time_to=time_to,
        )
        response = self.client._get(url=url, headers=self.client.headers)
        return decode_json(response=response)

    def merge(self, branch_name: str) -> bool:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchMerge", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-merge")

        return response["BranchMerge"]["ok"]

    def rebase(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchRebase", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-rebase")
        return response["BranchRebase"]["ok"]

    def validate(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }

        query_data = {
            "ok": None,
            "messages": None,
            "object": {
                "id": None,
                "name": None,
            },
        }

        query = Mutation(mutation="BranchValidate", input_data=input_data, query=query_data)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-validate")

        return response["BranchValidate"]["ok"]
