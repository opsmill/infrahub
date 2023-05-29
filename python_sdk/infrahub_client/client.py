from __future__ import annotations

import asyncio
import copy
import logging
from logging import Logger
from time import sleep
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import httpx

from infrahub_client.batch import InfrahubBatch
from infrahub_client.branch import InfrahubBranchManager, InfrahubBranchManagerSync
from infrahub_client.data import BranchData, RepositoryData
from infrahub_client.exceptions import (
    GraphQLError,
    NodeNotFound,
    ServerNotReacheableError,
    ServerNotResponsiveError,
)
from infrahub_client.graphql import Query
from infrahub_client.node import InfrahubNode, InfrahubNodeSync
from infrahub_client.queries import (
    MUTATION_COMMIT_UPDATE,
    QUERY_ALL_REPOSITORIES,
    QUERY_ALL_REPOSITORIES_NO_PAGINATION,
)
from infrahub_client.schema import InfrahubSchema, InfrahubSchemaSync
from infrahub_client.store import NodeStore, NodeStoreSync
from infrahub_client.timestamp import Timestamp

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# pylint: disable=redefined-builtin


class BaseClient:
    """Base class for InfrahubClient and InfrahubClientSync"""

    def __init__(
        self,
        address: str = "http://localhost:8000",
        default_timeout: int = 10,
        retry_on_failure: bool = False,
        retry_delay: int = 5,
        log: Optional[Logger] = None,
        test_client: Optional[TestClient] = None,
        default_branch: str = "main",
        insert_tracker: bool = False,
        pagination: bool = False,
        max_concurrent_execution: int = 5,
    ):
        self.address = address
        self.client = None
        self.default_timeout = default_timeout
        self.test_client = test_client
        self.retry_on_failure = retry_on_failure
        self.retry_delay = retry_delay
        self.default_branch = default_branch
        self.log = log or logging.getLogger("infrahub_client")
        self.insert_tracker = insert_tracker
        self.pagination = pagination
        self.headers = {"content-type": "application/json"}
        self.max_concurrent_execution = max_concurrent_execution

        if test_client:
            self.address = ""

        self._initialize()

    def _initialize(self) -> None:
        """Sets the properties for each version of the client"""


class InfrahubClient(BaseClient):  # pylint: disable=too-many-public-methods
    """GraphQL Client to interact with Infrahub."""

    def _initialize(self) -> None:
        self.schema = InfrahubSchema(self)
        self.branch = InfrahubBranchManager(self)
        self.store = NodeStore()
        self.concurrent_execution_limit = asyncio.Semaphore(self.max_concurrent_execution)

    @classmethod
    async def init(cls, *args: Any, **kwargs: Any) -> InfrahubClient:
        return cls(*args, **kwargs)

    async def create(
        self, kind: str, data: Optional[dict] = None, branch: Optional[str] = None, **kwargs: Any
    ) -> InfrahubNode:
        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        if not data and not kwargs:
            raise ValueError("Either data or a list of keywords but be provided")

        return InfrahubNode(client=self, schema=schema, branch=branch, data=data or kwargs)

    async def get(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> InfrahubNode:
        if not self.pagination:
            return await self.get_no_pagination(
                kind=kind, at=at, branch=branch, id=id, populate_store=populate_store, **kwargs
            )

        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        at = Timestamp(at)

        node = InfrahubNode(client=self, schema=schema, branch=branch)

        if id:
            filters = {"ids": [id]}
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data(filters=filters)
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-get"
        )

        if len(response[schema.name]["edges"]) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(response[schema.name]["edges"]) > 1:
            raise IndexError("More than 1 node returned")

        obj = InfrahubNode(client=self, schema=schema, branch=branch, data=response[schema.name]["edges"][0])

        if populate_store and obj.id:
            self.store.set(key=obj.id, node=obj)

        return obj

    async def get_no_pagination(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> InfrahubNode:
        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        at = Timestamp(at)

        node = InfrahubNode(client=self, schema=schema, branch=branch)

        if id:
            filters = {"ids": [id]}
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data_no_pagination(
            filters=filters
        )
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-get"
        )

        if len(response[schema.name]) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(response[schema.name]) > 1:
            raise IndexError("More than 1 node returned")

        obj = InfrahubNode(client=self, schema=schema, branch=branch, data=response[schema.name][0])

        if populate_store and obj.id:
            self.store.set(key=obj.id, node=obj)

        return obj

    async def all(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
    ) -> List[InfrahubNode]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.

        Returns:
            List[InfrahubNode]: List of Nodes
        """
        if not self.pagination:
            return await self.all_no_pagination(kind=kind, at=at, branch=branch, populate_store=populate_store)

        schema = await self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data()
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-all"
        )

        nodes = [
            InfrahubNode(client=self, schema=schema, branch=branch, data=item)
            for item in response[schema.name]["edges"]
        ]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    async def all_no_pagination(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
    ) -> List[InfrahubNode]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.

        Returns:
            List[InfrahubNode]: List of Nodes
        """
        schema = await self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data_no_pagination()
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-all"
        )

        nodes = [InfrahubNode(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    async def filters(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNode]:
        if not self.pagination:
            return await self.filters_no_pagination(
                kind=kind, at=at, branch=branch, populate_store=populate_store, **kwargs
            )

        schema = await self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        node = InfrahubNode(client=self, schema=schema, branch=branch)
        filters = kwargs

        if not filters:
            raise ValueError("At least one filter must be provided to filters()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data(filters=filters)
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-filters"
        )

        nodes = [InfrahubNode(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    async def filters_no_pagination(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNode]:
        schema = await self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        node = InfrahubNode(client=self, schema=schema, branch=branch)
        filters = kwargs

        if not filters:
            raise ValueError("At least one filter must be provided to filters()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data_no_pagination(
            filters=filters
        )
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-filters"
        )

        nodes = [InfrahubNode(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    async def execute_graphql(  # pylint: disable=too-many-branches
        self,
        query: str,
        variables: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[Union[str, Timestamp]] = None,
        rebase: bool = False,
        timeout: Optional[int] = None,
        raise_for_error: bool = True,
        tracker: Optional[str] = None,
    ) -> Dict:
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

        payload: Dict[str, Union[str, dict]] = {"query": query}
        if variables:
            payload["variables"] = variables

        url_params = {}
        if at:
            at = Timestamp(at)
            url_params["at"] = at.to_string()

        if rebase:
            url_params["rebase"] = "true"
        if url_params:
            url += "?" + "&".join([f"{key}={value}" for key, value in url_params.items()])

        headers = copy.copy(self.headers or {})
        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        # self.log.error(payload)

        if not self.test_client:
            retry = True
            while retry:
                retry = self.retry_on_failure
                try:
                    resp = await self._post(url=url, payload=payload, headers=headers, timeout=timeout)

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
                resp = client.post(url=url, json=payload, headers=headers)

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    async def _post(
        self, url: str, payload: dict, headers: Optional[dict] = None, timeout: Optional[int] = None
    ) -> httpx.Response:
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        async with httpx.AsyncClient() as client:
            try:
                return await client.post(
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=timeout or self.default_timeout,
                )
            except httpx.ConnectError as exc:
                raise ServerNotReacheableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url) from exc

    async def _get(self, url: str, headers: Optional[dict] = None, timeout: Optional[int] = None) -> httpx.Response:
        """Execute a HTTP GET with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        if not self.test_client:
            async with httpx.AsyncClient() as client:
                try:
                    return await client.get(
                        url=url,
                        headers=headers,
                        timeout=timeout or self.default_timeout,
                    )
                except httpx.ConnectError as exc:
                    raise ServerNotReacheableError(address=self.address) from exc
                except httpx.ReadTimeout as exc:
                    raise ServerNotResponsiveError(url=url) from exc
        else:
            with self.test_client as client:
                return client.get(url=url, headers=headers)

    async def query_gql_query(
        self,
        name: str,
        params: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[str] = None,
        rebase: bool = False,
        timeout: Optional[int] = None,
        raise_for_error: bool = True,
    ) -> Dict:
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

    async def create_batch(self) -> InfrahubBatch:
        return InfrahubBatch(semaphore=self.concurrent_execution_limit)

    async def get_list_repositories(
        self, branches: Optional[Dict[str, BranchData]] = None
    ) -> Dict[str, RepositoryData]:
        if not self.pagination:
            return await self.get_list_repositories_no_pagination(branches=branches)

        if not branches:
            branches = await self.branch.all()  # type: ignore

        branch_names = sorted(branches.keys())  # type: ignore

        tasks = []
        for branch_name in branch_names:
            tasks.append(
                self.execute_graphql(
                    query=QUERY_ALL_REPOSITORIES, branch_name=branch_name, tracker="query-repository-all"
                )
            )
            # TODO need to rate limit how many requests we are sending at once to avoid doing a DOS on the API

        responses = await asyncio.gather(*tasks)

        repositories = {}

        for branch_name, response in zip(branch_names, responses):
            repos = response["repository"]["edges"]
            for repository in repos:
                repo_name = repository["node"]["name"]["value"]
                if repo_name not in repositories:
                    repositories[repo_name] = RepositoryData(
                        id=repository["node"]["id"],
                        name=repo_name,
                        location=repository["node"]["location"]["value"],
                        branches={},
                    )

                repositories[repo_name].branches[branch_name] = repository["node"]["commit"]["value"]

        return repositories

    async def get_list_repositories_no_pagination(
        self, branches: Optional[Dict[str, BranchData]] = None
    ) -> Dict[str, RepositoryData]:
        if not branches:
            branches = await self.branch.all()  # type: ignore

        branch_names = sorted(branches.keys())  # type: ignore

        tasks = []
        for branch_name in branch_names:
            tasks.append(
                self.execute_graphql(
                    query=QUERY_ALL_REPOSITORIES_NO_PAGINATION, branch_name=branch_name, tracker="query-repository-all"
                )
            )
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

    async def repository_update_commit(self, branch_name: str, repository_id: str, commit: str) -> bool:
        variables = {"repository_id": str(repository_id), "commit": str(commit)}
        await self.execute_graphql(
            query=MUTATION_COMMIT_UPDATE,
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-repository-update-commit",
        )

        return True


class InfrahubClientSync(BaseClient):  # pylint: disable=too-many-public-methods
    def _initialize(self) -> None:
        self.schema = InfrahubSchemaSync(self)
        self.branch = InfrahubBranchManagerSync(self)
        self.store = NodeStoreSync()

    @classmethod
    def init(cls, *args: Any, **kwargs: Any) -> InfrahubClientSync:
        return cls(*args, **kwargs)

    def all(
        self, kind: str, at: Optional[Timestamp] = None, branch: Optional[str] = None, populate_store: bool = False
    ) -> List[InfrahubNodeSync]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.

        Returns:
            List[InfrahubNodeSync]: List of Nodes
        """
        if not self.pagination:
            return self.all_no_pagination(kind=kind, at=at, branch=branch, populate_store=populate_store)

        schema = self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data()
        query = Query(query=query_data)
        response = self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-all"
        )

        nodes = [
            InfrahubNodeSync(client=self, schema=schema, branch=branch, data=item)
            for item in response[schema.name]["edges"]
        ]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    def all_no_pagination(
        self, kind: str, at: Optional[Timestamp] = None, branch: Optional[str] = None, populate_store: bool = False
    ) -> List[InfrahubNodeSync]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.

        Returns:
            List[InfrahubNodeSync]: List of Nodes
        """
        schema = self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data_no_pagination()
        query = Query(query=query_data)
        response = self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-all"
        )

        nodes = [
            InfrahubNodeSync(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]
        ]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    def create(
        self, kind: str, data: Optional[dict] = None, branch: Optional[str] = None, **kwargs: Any
    ) -> InfrahubNodeSync:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        if not data and not kwargs:
            raise ValueError("Either data or a list of keywords but be provided")

        return InfrahubNodeSync(client=self, schema=schema, branch=branch, data=data or kwargs)

    def create_batch(self) -> InfrahubBatch:
        raise NotImplementedError("This method hasn't been implemented in the sync client yet.")

    def execute_graphql(  # pylint: disable=too-many-branches
        self,
        query: str,
        variables: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[Union[str, Timestamp]] = None,
        rebase: bool = False,
        timeout: Optional[int] = None,
        raise_for_error: bool = True,
        tracker: Optional[str] = None,
    ) -> Dict:
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

        payload: Dict[str, Union[str, dict]] = {"query": query}
        if variables:
            payload["variables"] = variables

        url_params = {}
        if at:
            at = Timestamp(at)
            url_params["at"] = at.to_string()

        if rebase:
            url_params["rebase"] = "true"
        if url_params:
            url += "?" + "&".join([f"{key}={value}" for key, value in url_params.items()])

        headers = copy.copy(self.headers or {})
        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        if not self.test_client:
            retry = True
            while retry:
                retry = self.retry_on_failure
                try:
                    resp = self._post(url=url, payload=payload, headers=headers, timeout=timeout)

                    if raise_for_error:
                        resp.raise_for_status()

                    retry = False
                except ServerNotReacheableError:
                    if retry:
                        self.log.warning(
                            f"Unable to connect to {self.address}, will retry in {self.retry_delay} seconds .."
                        )
                        sleep(self.retry_delay)
                    else:
                        self.log.error(f"Unable to connect to {self.address} .. ")
                        raise

        else:
            with self.test_client as client:
                resp = client.post(url=url, json=payload, headers=headers)

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    def filters(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNodeSync]:
        if not self.pagination:
            return self.filters_no_pagination(kind=kind, at=at, branch=branch, populate_store=populate_store, **kwargs)

        schema = self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch)
        filters = kwargs

        if not filters:
            raise ValueError("At least one filter must be provided to filters()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data(filters=filters)
        query = Query(query=query_data)
        response = self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-filters"
        )

        nodes = [
            InfrahubNodeSync(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]
        ]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    def filters_no_pagination(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNodeSync]:
        schema = self.schema.get(kind=kind)

        branch = branch or self.default_branch
        at = Timestamp(at)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch)
        filters = kwargs

        if not filters:
            raise ValueError("At least one filter must be provided to filters()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data_no_pagination(
            filters=filters
        )
        query = Query(query=query_data)
        response = self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-filters"
        )

        nodes = [
            InfrahubNodeSync(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]
        ]

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
        return nodes

    def get(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> InfrahubNodeSync:
        if not self.pagination:
            return self.get_no_pagination(
                kind=kind, at=at, branch=branch, id=id, populate_store=populate_store, **kwargs
            )

        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        at = Timestamp(at)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch)

        if id:
            filters = {"ids": [id]}
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data(filters=filters)
        query = Query(query=query_data)
        response = self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-get"
        )

        if len(response[schema.name]["edges"]) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(response[schema.name]["edges"]) > 1:
            raise IndexError("More than 1 node returned")

        obj = InfrahubNodeSync(client=self, schema=schema, branch=branch, data=response[schema.name]["edges"][0])

        if populate_store and obj.id:
            self.store.set(key=obj.id, node=obj)

        return obj

    def get_no_pagination(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        populate_store: bool = False,
        **kwargs: Any,
    ) -> InfrahubNodeSync:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        at = Timestamp(at)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch)

        if id:
            filters = {"ids": [id]}
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        node.validate_filters(filters=filters)
        query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data_no_pagination(
            filters=filters
        )
        query = Query(query=query_data)
        response = self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-get"
        )

        if len(response[schema.name]) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(response[schema.name]) > 1:
            raise IndexError("More than 1 node returned")

        obj = InfrahubNodeSync(client=self, schema=schema, branch=branch, data=response[schema.name][0])

        if populate_store and obj.id:
            self.store.set(key=obj.id, node=obj)

        return obj

    def get_list_repositories(self, branches: Optional[Dict[str, BranchData]] = None) -> Dict[str, RepositoryData]:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    def get_list_repositories_no_pagination(
        self, branches: Optional[Dict[str, BranchData]] = None
    ) -> Dict[str, RepositoryData]:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    def query_gql_query(
        self,
        name: str,
        params: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[str] = None,
        rebase: bool = False,
        timeout: Optional[int] = None,
        raise_for_error: bool = True,
    ) -> Dict:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    def repository_update_commit(self, branch_name: str, repository_id: str, commit: str) -> bool:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    def _get(self, url: str, headers: Optional[dict] = None, timeout: Optional[int] = None) -> httpx.Response:
        """Execute a HTTP GET with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        if not self.test_client:
            with httpx.Client() as client:
                try:
                    return client.get(
                        url=url,
                        headers=headers,
                        timeout=timeout or self.default_timeout,
                    )
                except httpx.ConnectError as exc:
                    raise ServerNotReacheableError(address=self.address) from exc
                except httpx.ReadTimeout as exc:
                    raise ServerNotResponsiveError(url=url) from exc
        else:
            with self.test_client as client:
                return client.get(url=url, headers=headers)

    def _post(
        self, url: str, payload: dict, headers: Optional[dict] = None, timeout: Optional[int] = None
    ) -> httpx.Response:
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        with httpx.Client() as client:
            try:
                return client.post(
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=timeout or self.default_timeout,
                )
            except httpx.ConnectError as exc:
                raise ServerNotReacheableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url) from exc
