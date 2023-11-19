from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from infrahub_sdk.exceptions import BranchNotFound
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.queries import QUERY_ALL_BRANCHES, QUERY_BRANCH

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync


class BranchData(pydantic.BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_data_only: bool
    is_default: bool
    origin_branch: Optional[str] = None
    branched_from: str


MUTATION_QUERY_DATA = {
    "ok": None,
    "object": {
        "id": None,
        "name": None,
        "description": None,
        "origin_branch": None,
        "branched_from": None,
        "is_default": None,
        "is_data_only": None,
    },
}


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
        url = f"{client.address}/diff/data?branch={branch_name}"
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
        data_only: bool = False,
        description: str = "",
        background_execution: bool = False,
    ) -> BranchData:
        input_data = {
            "background_execution": background_execution,
            "data": {
                "name": branch_name,
                "description": description,
                "is_data_only": data_only,
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

    async def merge(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="BranchMerge", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-merge", timeout=120)

        return response["BranchMerge"]["ok"]

    async def all(self) -> Dict[str, BranchData]:
        data = await self.client.execute_graphql(query=QUERY_ALL_BRANCHES, tracker="query-branch-all")

        branches = {branch["name"]: BranchData(**branch) for branch in data["Branch"]}

        return branches

    async def get(self, branch_name: str) -> BranchData:
        data = await self.client.execute_graphql(
            query=QUERY_BRANCH,
            variables={"branch_name": branch_name},
            tracker="query-branch",
        )

        if not data["Branch"]:
            raise BranchNotFound(identifier=branch_name)
        return BranchData(**data["Branch"][0])

    async def diff_data(
        self,
        branch_name: str,
        branch_only: bool = True,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> Dict[Any, Any]:
        url = self.generate_diff_data_url(
            client=self.client,
            branch_name=branch_name,
            branch_only=branch_only,
            time_from=time_from,
            time_to=time_to,
        )
        response = await self.client._get(url=url, headers=self.client.headers)
        return response.json()


class InfrahubBranchManagerSync(InfraHubBranchManagerBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client

    def all(self) -> Dict[str, BranchData]:
        data = self.client.execute_graphql(query=QUERY_ALL_BRANCHES, tracker="query-branch-all")

        branches = {branch["name"]: BranchData(**branch) for branch in data["Branch"]}

        return branches

    def get(self, branch_name: str) -> BranchData:
        data = self.client.execute_graphql(
            query=QUERY_BRANCH,
            variables={"branch_name": branch_name},
            tracker="query-branch",
        )

        if not data["Branch"]:
            raise BranchNotFound(identifier=branch_name)
        return BranchData(**data["Branch"][0])

    def create(
        self,
        branch_name: str,
        data_only: bool = False,
        description: str = "",
        background_execution: bool = False,
    ) -> BranchData:
        input_data = {
            "background_execution": background_execution,
            "data": {
                "name": branch_name,
                "description": description,
                "is_data_only": data_only,
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
    ) -> Dict[Any, Any]:
        url = self.generate_diff_data_url(
            client=self.client,
            branch_name=branch_name,
            branch_only=branch_only,
            time_from=time_from,
            time_to=time_to,
        )
        response = self.client._get(url=url, headers=self.client.headers)
        return response.json()

    def merge(self, branch_name: str) -> BranchData:
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
