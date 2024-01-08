from __future__ import annotations

import asyncio
import copy
import logging
from logging import Logger
from time import sleep
from typing import Any, Dict, List, MutableMapping, Optional, TypedDict, Union

import httpx

from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.branch import (
    BranchData,
    InfrahubBranchManager,
    InfrahubBranchManagerSync,
)
from infrahub_sdk.config import Config
from infrahub_sdk.data import RepositoryData
from infrahub_sdk.exceptions import (
    AuthenticationError,
    Error,
    GraphQLError,
    NodeNotFound,
    ServerNotReacheableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.graphql import Query
from infrahub_sdk.node import (
    InfrahubNode,
    InfrahubNodeSync,
)
from infrahub_sdk.object_store import ObjectStore, ObjectStoreSync
from infrahub_sdk.queries import MUTATION_COMMIT_UPDATE, QUERY_ALL_REPOSITORIES
from infrahub_sdk.schema import InfrahubSchema, InfrahubSchemaSync, NodeSchema
from infrahub_sdk.store import NodeStore, NodeStoreSync
from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.types import AsyncRequester, HTTPMethod, SyncRequester
from infrahub_sdk.utils import is_valid_uuid

# pylint: disable=redefined-builtin  disable=too-many-lines


class ProcessRelationsNode(TypedDict):
    nodes: List[InfrahubNode]
    related_nodes: List[InfrahubNode]


class ProcessRelationsNodeSync(TypedDict):
    nodes: List[InfrahubNodeSync]
    related_nodes: List[InfrahubNodeSync]


class BaseClient:
    """Base class for InfrahubClient and InfrahubClientSync"""

    def __init__(
        self,
        address: str = "",
        retry_on_failure: bool = False,
        retry_delay: int = 5,
        log: Optional[Logger] = None,
        insert_tracker: bool = False,
        pagination_size: int = 50,
        max_concurrent_execution: int = 5,
        config: Optional[Config] = None,
    ):
        self.client = None
        self.retry_on_failure = retry_on_failure
        self.retry_delay = retry_delay
        self.log = log or logging.getLogger("infrahub_sdk")
        self.insert_tracker = insert_tracker
        self.pagination_size = pagination_size
        self.headers = {"content-type": "application/json"}
        self.access_token: str = ""
        self.refresh_token: str = ""
        if isinstance(config, Config):
            self.config = config
        elif isinstance(config, dict):
            self.config = Config(**config)
        else:
            self.config = Config()

        self.default_branch = self.config.default_infrahub_branch
        self.default_timeout = self.config.timeout
        self.config.address = address or self.config.address
        self.address = self.config.address

        if self.config.api_token:
            self.headers["X-INFRAHUB-KEY"] = self.config.api_token

        self.max_concurrent_execution = max_concurrent_execution

        self._initialize()

    def _initialize(self) -> None:
        """Sets the properties for each version of the client"""

    def _record(self, response: httpx.Response) -> None:
        self.config.custom_recorder.record(response)


class InfrahubClient(BaseClient):  # pylint: disable=too-many-public-methods
    """GraphQL Client to interact with Infrahub."""

    def _initialize(self) -> None:
        self.schema = InfrahubSchema(self)
        self.branch = InfrahubBranchManager(self)
        self.object_store = ObjectStore(self)
        self.store = NodeStore()
        self.concurrent_execution_limit = asyncio.Semaphore(self.max_concurrent_execution)
        self._request_method: AsyncRequester = self.config.requester or self._default_request_method

    @classmethod
    async def init(cls, *args: Any, **kwargs: Any) -> InfrahubClient:
        return cls(*args, **kwargs)

    async def create(
        self,
        kind: str,
        data: Optional[dict] = None,
        branch: Optional[str] = None,
        **kwargs: Any,
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
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        populate_store: bool = False,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        **kwargs: Any,
    ) -> InfrahubNode:
        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        filters: MutableMapping[str, Any] = {}

        if id:
            if not is_valid_uuid(id) and isinstance(schema, NodeSchema) and schema.default_filter:
                filters[schema.default_filter] = id
            else:
                filters["ids"] = [id]
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        results = await self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
            **filters,
        )  # type: ignore[arg-type]

        if len(results) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(results) > 1:
            raise IndexError("More than 1 node returned")

        return results[0]

    async def _process_nodes_and_relationships(
        self, response: Dict[str, Any], schema_kind: str, branch: str, prefetch_relationships: bool
    ) -> ProcessRelationsNode:
        """Processes InfrahubNode and their Relationships from the GraphQL query response.

        Args:
            response (Dict[str, Any]): The response from the GraphQL query.
            schema_kind (str): The kind of schema being queried.
            branch (str): The branch name.
            prefetch_relationships (bool): Flag to indicate whether to prefetch relationship data.

        Returns:
            ProcessRelationsNodeSync: A TypedDict containing two lists:
                - 'nodes': A list of InfrahubNode objects representing the nodes processed.
                - 'related_nodes': A list of InfrahubNode objects representing the related nodes
        """

        nodes: List[InfrahubNode] = []
        related_nodes: List[InfrahubNode] = []

        for item in response.get(schema_kind, {}).get("edges", []):
            node = await InfrahubNode.from_graphql(client=self, branch=branch, data=item)
            nodes.append(node)

            if prefetch_relationships:
                await node._process_relationships(node_data=item, branch=branch, related_nodes=related_nodes)

        return ProcessRelationsNode(nodes=nodes, related_nodes=related_nodes)

    async def all(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
    ) -> List[InfrahubNode]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.

        Returns:
            List[InfrahubNode]: List of Nodes
        """
        return await self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            offset=offset,
            limit=limit,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
        )

    async def filters(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNode]:
        """Retrieve nodes of a given kind based on provided filters.

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.
            **kwargs (Any): Additional filter criteria for the query.

        Returns:
            List[InfrahubNodeSync]: List of Nodes that match the given filters.
        """
        schema = await self.schema.get(kind=kind)

        branch = branch or self.default_branch
        if at:
            at = Timestamp(at)

        node = InfrahubNode(client=self, schema=schema, branch=branch)
        filters = kwargs

        if filters:
            node.validate_filters(filters=filters)

        nodes: List[InfrahubNode] = []
        related_nodes: List[InfrahubNode] = []
        # If Offset or Limit was provided we just query as it
        # If not, we'll query all nodes based on the size of the batch
        if offset or limit:
            query_data = await InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data(
                offset=offset,
                limit=limit,
                filters=filters,
                include=include,
                exclude=exclude,
                fragment=fragment,
                prefetch_relationships=prefetch_relationships,
            )
            query = Query(query=query_data)
            response = await self.execute_graphql(
                query=query.render(),
                branch_name=branch,
                at=at,
                tracker=f"query-{str(schema.kind).lower()}-page1",
            )

            process_result: ProcessRelationsNode = await self._process_nodes_and_relationships(
                response=response, schema_kind=schema.kind, branch=branch, prefetch_relationships=prefetch_relationships
            )
            nodes = process_result["nodes"]
            related_nodes = process_result["related_nodes"]

        else:
            has_remaining_items = True
            page_number = 1
            while has_remaining_items:
                page_offset = (page_number - 1) * self.pagination_size

                query_data = await InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data(
                    offset=page_offset,
                    limit=self.pagination_size,
                    filters=filters,
                    include=include,
                    exclude=exclude,
                    fragment=fragment,
                    prefetch_relationships=prefetch_relationships,
                )
                query = Query(query=query_data)
                response = await self.execute_graphql(
                    query=query.render(),
                    branch_name=branch,
                    at=at,
                    tracker=f"query-{str(schema.kind).lower()}-page{page_number}",
                )
                _process_result: ProcessRelationsNode = await self._process_nodes_and_relationships(
                    response=response,
                    schema_kind=schema.kind,
                    branch=branch,
                    prefetch_relationships=prefetch_relationships,
                )
                nodes.extend(_process_result["nodes"])
                related_nodes.extend(_process_result["related_nodes"])

                remaining_items = response[schema.kind].get("count", 0) - (page_offset + self.pagination_size)
                if remaining_items < 0:
                    has_remaining_items = False

                page_number += 1

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
            related_nodes = list(set(related_nodes))
            for node in related_nodes:
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

        retry = True
        resp = None
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
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in [401, 403]:
                    response = exc.response.json()
                    errors = response.get("errors")
                    messages = [error.get("message") for error in errors]
                    raise AuthenticationError(" | ".join(messages)) from exc

        if not resp:
            raise Error("Unexpected situation, resp hasn't been initialized.")

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    async def _post(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> httpx.Response:
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didn't respond before the timeout expired
        """
        await self.login()
        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)
        return await self._request(
            url=url,
            method=HTTPMethod.POST,
            headers=headers,
            timeout=timeout or self.default_timeout,
            payload=payload,
        )

    async def _get(self, url: str, headers: Optional[dict] = None, timeout: Optional[int] = None) -> httpx.Response:
        """Execute a HTTP GET with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        await self.login()
        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)
        return await self._request(
            url=url,
            method=HTTPMethod.GET,
            headers=headers,
            timeout=timeout or self.default_timeout,
        )

    async def _request(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        response = await self._request_method(url=url, method=method, headers=headers, timeout=timeout, payload=payload)
        self._record(response)
        return response

    async def _default_request_method(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        params: Dict[str, Any] = {}
        if payload:
            params["json"] = payload
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method.value,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    **params,
                )
            except httpx.NetworkError as exc:
                raise ServerNotReacheableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url, timeout=timeout) from exc

        return response

    async def login(self, refresh: bool = False) -> None:
        if not self.config.password_authentication:
            return

        if self.access_token and not refresh:
            return

        url = f"{self.address}/api/auth/login"
        response = await self._request(
            url=url,
            method=HTTPMethod.POST,
            payload={
                "username": self.config.username,
                "password": self.config.password,
            },
            headers={"content-type": "application/json"},
            timeout=self.default_timeout,
        )

        response.raise_for_status()
        self.access_token = response.json()["access_token"]
        self.refresh_token = response.json()["refresh_token"]
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    async def query_gql_query(  # pylint: disable=too-many-branches
        self,
        name: str,
        variables: Optional[dict] = None,
        update_group: bool = False,
        subscribers: Optional[List[str]] = None,
        params: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[str] = None,
        rebase: bool = False,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Dict:
        url = f"{self.address}/api/query/{name}"
        url_params = copy.deepcopy(params or {})
        headers = copy.copy(self.headers or {})

        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        if branch_name:
            url_params["branch"] = branch_name
        if at:
            url_params["at"] = at
        if rebase:
            url_params["rebase"] = "true"
        if update_group:
            url_params["update_group"] = "true"
        if subscribers:
            url_params["subscribers"] = subscribers

        if url_params:
            url_params_str = []
            for key, value in url_params.items():
                if isinstance(value, (list)):
                    for item in value:
                        url_params_str.append(f"{key}={item}")
                else:
                    url_params_str.append(f"{key}={value}")

            url += "?" + "&".join(url_params_str)

        payload = None
        if variables:
            payload = {"variables": variables}

        resp = await self._request(
            url=url,
            method=HTTPMethod.POST,
            headers=headers,
            payload=payload,
            timeout=timeout or self.default_timeout,
        )

        if raise_for_error:
            resp.raise_for_status()

        return resp.json().get("data")

    async def create_batch(self, return_exceptions: bool = False) -> InfrahubBatch:
        return InfrahubBatch(semaphore=self.concurrent_execution_limit, return_exceptions=return_exceptions)

    async def get_list_repositories(
        self, branches: Optional[Dict[str, BranchData]] = None
    ) -> Dict[str, RepositoryData]:
        if not branches:
            branches = await self.branch.all()  # type: ignore

        branch_names = sorted(branches.keys())  # type: ignore

        tasks = []
        for branch_name in branch_names:
            tasks.append(
                self.execute_graphql(
                    query=QUERY_ALL_REPOSITORIES,
                    branch_name=branch_name,
                    tracker="query-repository-all",
                )
            )
            # TODO need to rate limit how many requests we are sending at once to avoid doing a DOS on the API

        responses = await asyncio.gather(*tasks)

        repositories = {}

        for branch_name, response in zip(branch_names, responses):
            repos = response["CoreRepository"]["edges"]
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
        self.object_store = ObjectStoreSync(self)
        self.store = NodeStoreSync()
        self._request_method: SyncRequester = self.config.sync_requester or self._default_request_method

    @classmethod
    def init(cls, *args: Any, **kwargs: Any) -> InfrahubClientSync:
        return cls(*args, **kwargs)

    def create(
        self,
        kind: str,
        data: Optional[dict] = None,
        branch: Optional[str] = None,
        **kwargs: Any,
    ) -> InfrahubNodeSync:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        if not data and not kwargs:
            raise ValueError("Either data or a list of keywords but be provided")

        return InfrahubNodeSync(client=self, schema=schema, branch=branch, data=data or kwargs)

    def create_batch(self, return_exceptions: bool = False) -> InfrahubBatch:
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

        retry = True
        resp = None
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
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in [401, 403]:
                    response = exc.response.json()
                    errors = response.get("errors")
                    messages = [error.get("message") for error in errors]
                    raise AuthenticationError(" | ".join(messages)) from exc

        if not resp:
            raise Error("Unexpected situation, resp hasn't been initialized.")

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    def all(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
    ) -> List[InfrahubNodeSync]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.

        Returns:
            List[InfrahubNodeSync]: List of Nodes
        """
        return self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            offset=offset,
            limit=limit,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
        )

    def _process_nodes_and_relationships(
        self, response: Dict[str, Any], schema_kind: str, branch: str, prefetch_relationships: bool
    ) -> ProcessRelationsNodeSync:
        """Processes InfrahubNodeSync and their Relationships from the GraphQL query response.

        Args:
            response (Dict[str, Any]): The response from the GraphQL query.
            schema_kind (str): The kind of schema being queried.
            branch (str): The branch name.
            prefetch_relationships (bool): Flag to indicate whether to prefetch relationship data.

        Returns:
            ProcessRelationsNodeSync: A TypedDict containing two lists:
                - 'nodes': A list of InfrahubNodeSync objects representing the nodes processed.
                - 'related_nodes': A list of InfrahubNodeSync objects representing the related nodes
        """

        nodes: List[InfrahubNodeSync] = []
        related_nodes: List[InfrahubNodeSync] = []

        for item in response.get(schema_kind, {}).get("edges", []):
            node = InfrahubNodeSync.from_graphql(client=self, branch=branch, data=item)
            nodes.append(node)

            if prefetch_relationships:
                node._process_relationships(node_data=item, branch=branch, related_nodes=related_nodes)

        return ProcessRelationsNodeSync(nodes=nodes, related_nodes=related_nodes)

    def filters(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNodeSync]:
        """Retrieve nodes of a given kind based on provided filters.

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.
            **kwargs (Any): Additional filter criteria for the query.

        Returns:
            List[InfrahubNodeSync]: List of Nodes that match the given filters.
        """
        schema = self.schema.get(kind=kind)

        branch = branch or self.default_branch
        if at:
            at = Timestamp(at)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch)
        filters = kwargs

        if filters:
            node.validate_filters(filters=filters)

        nodes: List[InfrahubNodeSync] = []
        related_nodes: List[InfrahubNodeSync] = []
        # If Offset or Limit was provided we just query as it
        # If not, we'll query all nodes based on the size of the batch
        if offset or limit:
            query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data(
                offset=offset,
                limit=limit,
                filters=filters,
                include=include,
                exclude=exclude,
                fragment=fragment,
                prefetch_relationships=prefetch_relationships,
            )
            query = Query(query=query_data)
            response = self.execute_graphql(
                query=query.render(),
                branch_name=branch,
                at=at,
                tracker=f"query-{str(schema.kind).lower()}-page1",
            )
            process_result: ProcessRelationsNodeSync = self._process_nodes_and_relationships(
                response=response, schema_kind=schema.kind, branch=branch, prefetch_relationships=prefetch_relationships
            )
            nodes = process_result["nodes"]
            related_nodes = process_result["related_nodes"]

        else:
            has_remaining_items = True
            page_number = 1
            while has_remaining_items:
                page_offset = (page_number - 1) * self.pagination_size

                query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data(
                    offset=page_offset,
                    limit=self.pagination_size,
                    filters=filters,
                    include=include,
                    exclude=exclude,
                    fragment=fragment,
                    prefetch_relationships=prefetch_relationships,
                )
                query = Query(query=query_data)
                response = self.execute_graphql(
                    query=query.render(),
                    branch_name=branch,
                    at=at,
                    tracker=f"query-{str(schema.kind).lower()}-page{page_number}",
                )

                _process_result: ProcessRelationsNodeSync = self._process_nodes_and_relationships(
                    response=response,
                    schema_kind=schema.kind,
                    branch=branch,
                    prefetch_relationships=prefetch_relationships,
                )
                nodes.extend(_process_result["nodes"])
                related_nodes.extend(_process_result["related_nodes"])

                remaining_items = response[schema.kind].get("count", 0) - (page_offset + self.pagination_size)
                if remaining_items < 0:
                    has_remaining_items = False

                page_number += 1

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
            related_nodes = list(set(related_nodes))
            for node in related_nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)

        return nodes

    def get(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        populate_store: bool = False,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        **kwargs: Any,
    ) -> InfrahubNodeSync:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        filters: MutableMapping[str, Any] = {}

        if id:
            if not is_valid_uuid(id) and isinstance(schema, NodeSchema) and schema.default_filter:
                filters[schema.default_filter] = id
            else:
                filters["ids"] = [id]
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        results = self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
            **filters,
        )  # type: ignore[arg-type]

        if len(results) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(results) > 1:
            raise IndexError("More than 1 node returned")

        return results[0]

    def get_list_repositories(self, branches: Optional[Dict[str, BranchData]] = None) -> Dict[str, RepositoryData]:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    def query_gql_query(  # pylint: disable=too-many-branches
        self,
        name: str,
        variables: Optional[dict] = None,
        update_group: bool = False,
        subscribers: Optional[List[str]] = None,
        params: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[str] = None,
        rebase: bool = False,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Dict:
        url = f"{self.address}/api/query/{name}"
        url_params = copy.deepcopy(params or {})
        headers = copy.copy(self.headers or {})

        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        if branch_name:
            url_params["branch"] = branch_name
        if at:
            url_params["at"] = at
        if rebase:
            url_params["rebase"] = "true"
        if update_group:
            url_params["update_group"] = "true"
        if subscribers:
            url_params["subscribers"] = subscribers

        if url_params:
            url_params_str = []
            for key, value in url_params.items():
                if isinstance(value, (list)):
                    for item in value:
                        url_params_str.append(f"{key}={item}")
                else:
                    url_params_str.append(f"{key}={value}")

            url += "?" + "&".join(url_params_str)

        payload = None
        if variables:
            payload = {"variables": variables}

        resp = self._request(
            url=url,
            method=HTTPMethod.POST,
            headers=headers,
            payload=payload,
            timeout=timeout or self.default_timeout,
        )

        if raise_for_error:
            resp.raise_for_status()

        return resp.json().get("data")

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
        self.login()
        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)
        return self._request(
            url=url,
            method=HTTPMethod.GET,
            headers=headers,
            timeout=timeout or self.default_timeout,
        )

    def _post(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> httpx.Response:
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        self.login()
        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)

        return self._request(
            url=url,
            method=HTTPMethod.POST,
            payload=payload,
            headers=headers,
            timeout=timeout or self.default_timeout,
        )

    def _request(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        response = self._request_method(url=url, method=method, headers=headers, timeout=timeout, payload=payload)
        self._record(response)
        return response

    def _default_request_method(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        params: Dict[str, Any] = {}
        if payload:
            params["json"] = payload
        with httpx.Client() as client:
            try:
                response = client.request(
                    method=method.value,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    **params,
                )
            except httpx.NetworkError as exc:
                raise ServerNotReacheableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url, timeout=timeout) from exc

        return response

    def login(self, refresh: bool = False) -> None:
        if not self.config.password_authentication:
            return

        if self.access_token and not refresh:
            return

        url = f"{self.address}/api/auth/login"
        response = self._request(
            url=url,
            method=HTTPMethod.POST,
            payload={
                "username": self.config.username,
                "password": self.config.password,
            },
            headers={"content-type": "application/json"},
            timeout=self.default_timeout,
        )

        response.raise_for_status()
        self.access_token = response.json()["access_token"]
        self.refresh_token = response.json()["refresh_token"]
        self.headers["Authorization"] = f"Bearer {self.access_token}"
