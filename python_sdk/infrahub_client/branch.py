from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from pydantic import BaseModel

from infrahub_client.graphql import Mutation
from infrahub_client.queries import QUERY_ALL_BRANCHES, QUERY_BRANCH_DIFF

if TYPE_CHECKING:
    from infrahub_client.client import InfrahubClient, InfrahubClientSync


class BranchData(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_data_only: bool
    is_default: bool
    origin_branch: Optional[str]
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
    pass


class InfrahubBranchManager(InfraHubBranchManagerBase):
    def __init__(self, client: InfrahubClient):
        self.client = client

    async def create(
        self, branch_name: str, data_only: bool = False, description: str = "", background_execution: bool = False
    ) -> BranchData:
        input_data = {
            "background_execution": background_execution,
            "data": {"name": branch_name, "description": description, "is_data_only": data_only},
        }

        query = Mutation(mutation="branch_create", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-create")

        return BranchData(**response["branch_create"]["object"])

    async def rebase(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="branch_rebase", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-rebase")
        return response["branch_rebase"]["ok"]

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

        query = Mutation(mutation="branch_validate", input_data=input_data, query=query_data)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-validate")

        return response["branch_validate"]["ok"]

    async def merge(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="branch_merge", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = await self.client.execute_graphql(query=query.render(), tracker="mutation-branch-merge")

        return response["branch_merge"]["ok"]

    async def all(self) -> Dict[str, BranchData]:
        data = await self.client.execute_graphql(query=QUERY_ALL_BRANCHES, tracker="query-branch-all")

        branches = {branch["name"]: BranchData(**branch) for branch in data["branch"]}

        return branches

    async def diff(
        self,
        branch_name: str,
        branch_only: bool = True,
        diff_from: Optional[str] = None,
        diff_to: Optional[str] = None,
    ) -> Dict[Any, Any]:
        variables = {"branch_name": branch_name, "branch_only": branch_only, "diff_from": diff_from, "diff_to": diff_to}
        response = await self.client.execute_graphql(
            query=QUERY_BRANCH_DIFF, variables=variables, tracker="query-branch-diff"
        )

        return response

    async def diff_data(
        self,
        branch_name: str,
        branch_only: bool = True,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> Dict[Any, Any]:
        url = f"{self.client.address}/diff/data?branch={branch_name}"
        url += f"&branch_only={str(branch_only).lower()}"
        if time_from:
            url += f"&time_from={time_from}"
        if time_to:
            url += f"&time_to={time_to}"

        response = await self.client._get(url=url, headers=self.client.headers)
        return response


class InfrahubBranchManagerSync(InfraHubBranchManagerBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client

    def all(self) -> Dict[str, BranchData]:
        data = self.client.execute_graphql(query=QUERY_ALL_BRANCHES, tracker="query-branch-all")

        branches = {branch["name"]: BranchData(**branch) for branch in data["branch"]}

        return branches

    def create(
        self, branch_name: str, data_only: bool = False, description: str = "", background_execution: bool = False
    ) -> BranchData:
        input_data = {
            "background_execution": background_execution,
            "data": {"name": branch_name, "description": description, "is_data_only": data_only},
        }

        query = Mutation(mutation="branch_create", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-create")

        return BranchData(**response["branch_create"]["object"])

    def diff(
        self,
        branch_name: str,
        branch_only: bool = True,
        diff_from: Optional[str] = None,
        diff_to: Optional[str] = None,
    ) -> Dict[Any, Any]:
        variables = {"branch_name": branch_name, "branch_only": branch_only, "diff_from": diff_from, "diff_to": diff_to}
        response = self.client.execute_graphql(
            query=QUERY_BRANCH_DIFF, variables=variables, tracker="query-branch-diff"
        )

        return response

    def merge(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="branch_merge", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-merge")

        return response["branch_merge"]["ok"]

    def rebase(self, branch_name: str) -> BranchData:
        input_data = {
            "data": {
                "name": branch_name,
            }
        }
        query = Mutation(mutation="branch_rebase", input_data=input_data, query=MUTATION_QUERY_DATA)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-rebase")
        return response["branch_rebase"]["ok"]

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

        query = Mutation(mutation="branch_validate", input_data=input_data, query=query_data)
        response = self.client.execute_graphql(query=query.render(), tracker="mutation-branch-validate")

        return response["branch_validate"]["ok"]
