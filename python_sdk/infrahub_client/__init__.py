from __future__ import annotations

import asyncio
import copy
import logging
from logging import Logger
from typing import Dict, Optional

import httpx
from pydantic import BaseModel

from infrahub_client.exceptions import (
    GraphQLError,
    ServerNotReacheableError,
    ServerNotResponsiveError,
)
from infrahub_client.queries import (
    MUTATION_BRANCH_CREATE,
    MUTATION_BRANCH_MERGE,
    MUTATION_BRANCH_REBASE,
    MUTATION_BRANCH_VALIDATE,
    MUTATION_CHECK_CREATE,
    MUTATION_CHECK_UPDATE,
    MUTATION_COMMIT_UPDATE,
    MUTATION_GRAPHQL_QUERY_CREATE,
    MUTATION_GRAPHQL_QUERY_UPDATE,
    MUTATION_RFILE_CREATE,
    MUTATION_RFILE_UPDATE,
    MUTATION_TRANSFORM_PYTHON_CREATE,
    MUTATION_TRANSFORM_PYTHON_UPDATE,
    QUERY_ALL_BRANCHES,
    QUERY_ALL_CHECKS,
    QUERY_ALL_GRAPHQL_QUERIES,
    QUERY_ALL_REPOSITORIES,
    QUERY_ALL_RFILES,
    QUERY_ALL_TRANSFORM_PYTHON,
)
from infrahub_client.schema import InfrahubSchema

# pylint: disable=redefined-builtin


class BranchData(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_data_only: bool
    is_default: bool
    origin_branch: Optional[str]
    branched_from: str


class RepositoryData(BaseModel):
    id: str
    name: str
    location: str
    branches: Dict[str, str]


class GraphQLQueryData(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    query: str


class RFileData(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    template_path: str
    template_repository: str
    output_path: Optional[str]
    query: str


class CheckData(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    repository: str
    file_path: str
    class_name: str
    query: str
    timeout: Optional[int]
    rebase: Optional[bool]


class TransformPythonData(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    repository: str
    file_path: str
    class_name: str
    query: str
    url: str
    timeout: Optional[int]
    rebase: Optional[bool]


class InfrahubClient:  # pylint: disable=too-many-public-methods
    """GraphQL Client to interact with Infrahub."""

    def __init__(
        self,
        address: str = "http://localhost:8000",
        default_timeout: int = 10,
        retry_on_failure: bool = False,
        retry_delay: int = 5,
        log: Logger = None,
        test_client=None,
    ):
        self.address = address
        self.client = None
        self.default_timeout = default_timeout
        self.test_client = test_client
        self.retry_on_failure = retry_on_failure
        self.retry_delay = retry_delay
        self.log = log or logging.getLogger("infrahub_client")

        self.schema = InfrahubSchema(self)

        if test_client:
            self.address = ""

    @classmethod
    async def init(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    async def execute_graphql(  # pylint: disable=too-many-branches
        self,
        query: str,
        variables: dict = None,
        branch_name: str = None,
        at: str = None,
        rebase: bool = False,
        timeout: int = None,
        raise_for_error: bool = True,
    ):
        """Execute a GraphQL query (or mutation).
        If retry_on_failure is True, the query will retry until the server becomes reacheable.

        Args:
            query (_type_): GraphQL Query to execute, can be a query or a mutation
            variables (dict, optional): Variables to pass along with the GraphQL query. Defaults to None.
            branch_name (str, optional): Name of the branch on which the query will be executed. Defaults to None.
            at (str, optional): Time when the query should be executed. Defaults to None.
            rebase (bool, optional): Flag to indicate if the branch should be rebased during the query. Defaults to False.
            timeout (int, optional): Timeout in second for the query. Defaults to None.
            raise_for_error (bool, optional): Flag to indicate that we need to raise an exception if the response has some errors. Defaults to True.

        Raises:
            GraphQLError: _description_

        Returns:
            _type_: _description_
        """
        url = f"{self.address}/graphql"
        if branch_name:
            url += f"/{branch_name}"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        url_params = {}
        if at:
            url_params["at"] = at
        if rebase:
            url_params["rebase"] = "true"
        if url_params:
            url += "?" + "&".join([f"{key}={value}" for key, value in url_params.items()])

        if not self.test_client:
            retry = True
            while retry:
                retry = self.retry_on_failure
                try:
                    resp = await self.post(url=url, payload=payload, timeout=timeout)

                    if raise_for_error:
                        resp.raise_for_status()

                    retry = False
                except ServerNotReacheableError:
                    if retry:
                        self.log.warning(
                            f"Unable to connect to {self.address}, will retry in {self.retry_delay} seconds .."
                        )
                        await asyncio.sleep(delay=self.retry_delay)
                    else:
                        self.log.error(f"Unable to connect to {self.address} .. ")
                        raise

        else:
            with self.test_client as client:
                resp = client.post(url=url, json=payload)

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    async def post(self, url: str, payload: dict, timeout: int = None):
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
        """
        async with httpx.AsyncClient() as client:
            try:
                return await client.post(
                    url=url,
                    json=payload,
                    timeout=timeout or self.default_timeout,
                )
            except httpx.ConnectError as exc:
                raise ServerNotReacheableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url) from exc

    async def query_gql_query(
        self,
        name: str,
        params: dict = None,
        branch_name: str = None,
        at: str = None,
        rebase: bool = False,
        timeout: int = None,
        raise_for_error: bool = True,
    ):
        url = f"{self.address}/query/{name}"
        url_params = copy.deepcopy(params or {})

        if branch_name:
            url_params["branch"] = branch_name
        if at:
            url_params["at"] = at
        if rebase:
            url_params["rebase"] = "true"

        if url_params:
            url += "?" + "&".join([f"{key}={value}" for key, value in url_params.items()])

        if not self.test_client:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url=url,
                    timeout=timeout or self.default_timeout,
                )

        else:
            with self.test_client as client:
                resp = client.post(url=url)

        if raise_for_error:
            resp.raise_for_status()

        return resp.json()

    async def create_branch(
        self, branch_name: str, data_only: bool = False, description: str = "", background_execution: bool = False
    ) -> BranchData:
        variables = {
            "branch_name": branch_name,
            "data_only": data_only,
            "description": description,
            "background_execution": background_execution,
        }
        response = await self.execute_graphql(query=MUTATION_BRANCH_CREATE, variables=variables)

        return BranchData(**response["branch_create"]["object"])

    async def branch_rebase(self, branch_name: str) -> BranchData:
        variables = {"branch_name": branch_name}
        response = await self.execute_graphql(query=MUTATION_BRANCH_REBASE, variables=variables)

        return response["branch_rebase"]["ok"]

    async def branch_validate(self, branch_name: str) -> BranchData:
        variables = {"branch_name": branch_name}
        response = await self.execute_graphql(query=MUTATION_BRANCH_VALIDATE, variables=variables)

        return response["branch_validate"]["ok"]

    async def branch_merge(self, branch_name: str) -> BranchData:
        variables = {"branch_name": branch_name}
        response = await self.execute_graphql(query=MUTATION_BRANCH_MERGE, variables=variables)

        return BranchData(**response["branch_merge"]["ok"])

    async def get_list_branches(self) -> Dict[str, BranchData]:
        data = await self.execute_graphql(query=QUERY_ALL_BRANCHES)

        branches = {branch["name"]: BranchData(**branch) for branch in data["branch"]}

        return branches

    async def get_list_repositories(self, branches: Dict[str, RepositoryData] = None) -> Dict[str, RepositoryData]:
        if not branches:
            branches = await self.get_list_branches()

        branch_names = sorted(branches.keys())

        tasks = []
        for branch_name in branch_names:
            tasks.append(self.execute_graphql(query=QUERY_ALL_REPOSITORIES, branch_name=branch_name))
            # TODO need to rate limit how many requests we are sending at once to avoid doing a DOS on the API

        responses = await asyncio.gather(*tasks)

        repositories = {}

        for branch_name, response in zip(branch_names, responses):
            repos = response["repository"]
            for repository in repos:
                repo_name = repository["name"]["value"]
                if repo_name not in repositories:
                    repositories[repo_name] = RepositoryData(
                        id=repository["id"], name=repo_name, location=repository["location"]["value"], branches={}
                    )

                repositories[repo_name].branches[branch_name] = repository["commit"]["value"]

        return repositories

    async def get_list_graphql_queries(self, branch_name: str) -> Dict[str, GraphQLQueryData]:
        data = await self.execute_graphql(query=QUERY_ALL_GRAPHQL_QUERIES, branch_name=branch_name)

        items = {
            item["name"]["value"]: GraphQLQueryData(
                id=item["id"],
                name=item["name"]["value"],
                description=item["description"]["value"],
                query=item["query"]["value"],
            )
            for item in data["graphql_query"]
        }

        return items

    async def get_list_checks(self, branch_name: str) -> Dict[str, CheckData]:
        data = await self.execute_graphql(query=QUERY_ALL_CHECKS, branch_name=branch_name)

        items = {
            item["name"]["value"]: CheckData(
                id=item["id"],
                name=item["name"]["value"],
                description=item["description"]["value"],
                file_path=item["file_path"]["value"],
                class_name=item["class_name"]["value"],
                query=item["query"]["name"]["value"],
                repository=item["repository"]["id"],
                timeout=item["timeout"]["value"],
                rebase=item["rebase"]["value"],
            )
            for item in data["check"]
        }

        return items

    async def get_list_transform_python(self, branch_name: str) -> Dict[str, TransformPythonData]:
        data = await self.execute_graphql(query=QUERY_ALL_TRANSFORM_PYTHON, branch_name=branch_name)

        items = {
            item["name"]["value"]: TransformPythonData(
                id=item["id"],
                name=item["name"]["value"],
                description=item["description"]["value"],
                file_path=item["file_path"]["value"],
                url=item["url"]["value"],
                class_name=item["class_name"]["value"],
                query=item["query"]["name"]["value"],
                repository=item["repository"]["id"],
                timeout=item["timeout"]["value"],
                rebase=item["rebase"]["value"],
            )
            for item in data["transform_python"]
        }

        return items

    async def create_graphql_query(self, branch_name: str, name: str, query: str, description: str = "") -> bool:
        variables = {"name": name, "description": description, "query": query}
        await self.execute_graphql(query=MUTATION_GRAPHQL_QUERY_CREATE, variables=variables, branch_name=branch_name)

        return True

    async def update_graphql_query(
        self, branch_name: str, id: str, name: str, query: str, description: str = ""
    ) -> bool:
        variables = {"id": id, "name": name, "description": description, "query": query}
        await self.execute_graphql(query=MUTATION_GRAPHQL_QUERY_UPDATE, variables=variables, branch_name=branch_name)

        return True

    async def get_list_rfiles(self, branch_name: str) -> Dict[str, RFileData]:
        data = await self.execute_graphql(query=QUERY_ALL_RFILES, branch_name=branch_name)

        items = {
            item["name"]["value"]: RFileData(
                id=item["id"],
                name=item["name"]["value"],
                description=item["description"]["value"],
                template_path=item["template_path"]["value"],
                template_repository=item["template_repository"]["id"],
                query=item["query"]["name"]["value"],
            )
            for item in data["rfile"]
        }

        return items

    async def create_rfile(
        self,
        branch_name: str,
        name: str,
        query: str,
        template_path: str,
        template_repository: str,
        description: str = "",
    ) -> bool:
        variables = {
            "name": name,
            "description": description,
            "template_path": template_path,
            "template_repository": template_repository,
            "query": query,
        }
        await self.execute_graphql(query=MUTATION_RFILE_CREATE, variables=variables, branch_name=branch_name)

        return True

    async def update_rfile(
        self, branch_name: str, id: str, name: str, template_path: str, description: str = ""
    ) -> bool:
        variables = {"id": id, "name": name, "description": description, "template_path": template_path}
        await self.execute_graphql(query=MUTATION_RFILE_UPDATE, variables=variables, branch_name=branch_name)

        return True

    async def create_check(
        self,
        branch_name: str,
        name: str,
        query: str,
        file_path: str,
        class_name: str,
        repository: str,
        description: str = "",
        timeout: int = 10,
        rebase: bool = False,
    ) -> bool:
        variables = {
            "name": name,
            "description": description,
            "file_path": file_path,
            "class_name": class_name,
            "repository": repository,
            "query": query,
            "timeout": timeout,
            "rebase": rebase,
        }
        await self.execute_graphql(query=MUTATION_CHECK_CREATE, variables=variables, branch_name=branch_name)

        return True

    async def update_check(
        self,
        branch_name: str,
        id: str,
        name: str,
        query: str,
        file_path: str,
        class_name: str,
        description: str = "",
        timeout: int = 10,
        rebase: bool = False,
    ):
        variables = {
            "id": id,
            "name": name,
            "description": description,
            "file_path": file_path,
            "class_name": class_name,
            "query": query,
            "timeout": timeout,
            "rebase": rebase,
        }
        await self.execute_graphql(query=MUTATION_CHECK_UPDATE, variables=variables, branch_name=branch_name)

        return True

    async def create_transform_python(
        self,
        branch_name: str,
        name: str,
        query: str,
        file_path: str,
        class_name: str,
        repository: str,
        url: str,
        description: str = "",
        timeout: int = 10,
        rebase: bool = False,
    ) -> bool:
        variables = {
            "name": name,
            "description": description,
            "file_path": file_path,
            "class_name": class_name,
            "repository": repository,
            "url": url,
            "query": query,
            "timeout": timeout,
            "rebase": rebase,
        }
        await self.execute_graphql(query=MUTATION_TRANSFORM_PYTHON_CREATE, variables=variables, branch_name=branch_name)

        return True

    async def update_transform_python(
        self,
        branch_name: str,
        id: str,
        name: str,
        url: str,
        query: str,
        file_path: str,
        class_name: str,
        description: str = "",
        timeout: int = 10,
        rebase: bool = False,
    ):
        variables = {
            "id": id,
            "name": name,
            "description": description,
            "file_path": file_path,
            "class_name": class_name,
            "url": url,
            "query": query,
            "timeout": timeout,
            "rebase": rebase,
        }
        await self.execute_graphql(query=MUTATION_TRANSFORM_PYTHON_UPDATE, variables=variables, branch_name=branch_name)

        return True

    async def repository_update_commit(self, branch_name, repository_id: str, commit: str) -> bool:
        variables = {"repository_id": str(repository_id), "commit": str(commit)}
        await self.execute_graphql(query=MUTATION_COMMIT_UPDATE, variables=variables, branch_name=branch_name)

        return True

    async def get_branch_diff(
        self,
        branch_name: str,
        branch_only: bool = True,
        diff_from: str = None,
        diff_to: str = None,
    ):
        QUERY_BRANCH_DIFF = """
        query($branch_name: String!, $branch_only: Boolean!, $diff_from: String!, $diff_to: String! ) {
            diff(branch: $branch_name, branch_only: $branch_only, time_from: $diff_from, time_to: $diff_to ) {
                nodes {
                    branch
                    kind
                    id
                    changed_at
                    action
                    attributes {
                        name
                        id
                        changed_at
                        action
                        properties {
                            action
                            type
                            changed_at
                            branch
                            value {
                                previous
                                new
                            }
                        }
                    }
                }
                relationships {
                    branch
                    id
                    name
                    properties {
                        branch
                        type
                        changed_at
                        action
                        value {
                            previous
                            new
                        }
                    }
                    nodes {
                        id
                        kind
                    }
                    changed_at
                    action
                }
                files {
                    action
                    repository
                    branch
                    location
                }
            }
        }
        """
        variables = {"branch_name": branch_name, "branch_only": branch_only, "diff_from": diff_from, "diff_to": diff_to}
        response = await self.execute_graphql(query=QUERY_BRANCH_DIFF, variables=variables)

        return response
