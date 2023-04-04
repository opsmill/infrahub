from __future__ import annotations

import asyncio
import copy
import logging
from logging import Logger
from typing import Any, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel

from infrahub_client.branch import InfrahubBranchManager
from infrahub_client.exceptions import (
    FilterNotFound,
    GraphQLError,
    NodeNotFound,
    ServerNotReacheableError,
    ServerNotResponsiveError,
)
from infrahub_client.graphql import Mutation, Query
from infrahub_client.queries import (
    MUTATION_CHECK_CREATE,
    MUTATION_CHECK_UPDATE,
    MUTATION_COMMIT_UPDATE,
    MUTATION_GRAPHQL_QUERY_CREATE,
    MUTATION_GRAPHQL_QUERY_UPDATE,
    MUTATION_RFILE_CREATE,
    MUTATION_RFILE_UPDATE,
    MUTATION_TRANSFORM_PYTHON_CREATE,
    MUTATION_TRANSFORM_PYTHON_UPDATE,
    QUERY_ALL_CHECKS,
    QUERY_ALL_GRAPHQL_QUERIES,
    QUERY_ALL_REPOSITORIES,
    QUERY_ALL_RFILES,
    QUERY_ALL_TRANSFORM_PYTHON,
)
from infrahub_client.schema import (
    AttributeSchema,
    InfrahubSchema,
    NodeSchema,
    RelationshipSchema,
)
from infrahub_client.timestamp import Timestamp

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


class Attribute:
    def __init__(self, name: str, schema: AttributeSchema, data: Union[Any, dict]):  # pylint: disable=unused-argument
        self.name = name

        if not isinstance(data, dict):
            data = {"value": data}

        self._properties_flag = ["is_visible", "is_protected"]
        self._properties_object = ["source", "owner"]
        self._properties = self._properties_flag + self._properties_object

        self._read_only = ["updated_at", "is_inherited"]

        self.id: Optional[str] = data.get("id", None)
        self.value: Optional[Any] = data.get("value", None)

        self.is_inherited: Optional[bool] = data.get("is_inherited", None)
        self.updated_at: Optional[str] = data.get("updated_at", None)

        self.is_visible: Optional[bool] = data.get("is_visible", None)
        self.is_protected: Optional[bool] = data.get("is_protected", None)
        self.source: Optional[str] = data.get("source", None)
        self.owner: Optional[str] = data.get("owner", None)

    def _generate_input_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {}

        if self.value is not None:
            data["value"] = self.value

        for prop_name in self._properties:
            if getattr(self, prop_name) is not None:
                data[prop_name] = getattr(self, prop_name)

        return data

    def _generate_query_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {"value": None}

        for prop_name in self._properties_flag:
            data[prop_name] = None
        for prop_name in self._properties_object:
            data[prop_name] = {"id": None, "display_label": None}

        return data


class RelatedNode:
    def __init__(self, schema: RelationshipSchema, data: Union[Any, dict], name: Optional[str] = None):
        self.schema = schema
        self.name = name

        self._properties_flag = ["is_visible", "is_protected"]
        self._properties_object = ["source", "owner"]
        self._properties = self._properties_flag + self._properties_object

        self.peer = None

        if isinstance(data, InfrahubNode):
            self.peer = data
            data = {"id": self.peer.id}
        elif not isinstance(data, dict):
            data = {"id": data}

        self.id: Optional[str] = data.get("id", None)
        self.display_label = data.get("display_label", None)
        self.updated_at: Optional[bool] = data.get("_relation__updated_at", None)

        for prop in self._properties:
            if value := data.get(prop, None):
                setattr(self, prop, value)
                continue

            setattr(self, prop, data.get(f"_relation__{prop}", None))

    def _generate_input_data(self) -> Dict[str, Any]:
        data = {}

        if self.id is not None:
            data["id"] = self.id

        for prop_name in self._properties:
            if getattr(self, prop_name) is not None:
                data[f"_relation__{prop_name}"] = getattr(self, prop_name)

        return data

    def _generate_query_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {"id": None, "display_label": None}

        for prop_name in self._properties_flag:
            data[f"_relation__{prop_name}"] = None
        for prop_name in self._properties_object:
            data[f"_relation__{prop_name}"] = {"id": None, "display_label": None}

        return data


class RelationshipManager:
    def __init__(self, name: str, schema: RelationshipSchema, data: Union[Any, dict]):
        self.name = name
        self.schema = schema
        self.peers: List[RelatedNode] = []

        self._properties_flag = ["is_visible", "is_protected"]
        self._properties_object = ["source", "owner"]
        self._properties = self._properties_flag + self._properties_object

        if data is None:
            return

        if not isinstance(data, list):
            raise ValueError(f"{name} found a {type(data)} instead of a list")

        for item in data:
            self.peers.append(RelatedNode(name=name, schema=schema, data=item))

    def add(self, data: Union[str, RelatedNode, dict]) -> None:
        """Add a new peer to this relationship.
        Need to check if the peer is already present
        """

        # TODO add some check to ensure
        # that we are not adding a node that already exist
        self.peers.append(RelatedNode(schema=self.schema, data=data))

    def remove(self, data: Any) -> None:
        pass

    def _generate_input_data(self) -> List[Dict]:
        return [peer._generate_input_data() for peer in self.peers]

    def _generate_query_data(self) -> Dict:
        data: Dict[str, Any] = {"id": None, "display_label": None}

        for prop_name in self._properties_flag:
            data[f"_relation__{prop_name}"] = None
        for prop_name in self._properties_object:
            data[f"_relation__{prop_name}"] = {"id": None, "display_label": None}

        return data


def generate_relationship_property(name):
    """Return a property that stores values under a private non-public name."""
    internal_name = "_" + name.lower()
    external_name = name

    @property
    def prop(self):
        return getattr(self, internal_name)

    @prop.setter
    def prop(self, value):
        if isinstance(value, RelatedNode) or value is None:
            setattr(self, internal_name, value)
        else:
            schema = [rel for rel in self._schema.relationships if rel.name == external_name][0]
            setattr(self, internal_name, RelatedNode(name=external_name, schema=schema, data=value))

    return prop


class InfrahubNode:
    def __init__(
        self, client: InfrahubClient, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        self._client = client
        self._schema = schema
        self._data = data

        self._branch = branch or self._client.default_branch

        self.id: Optional[str] = data.get("id", None) if isinstance(data, dict) else None
        self.display_label: Optional[str] = data.get("display_label", None) if isinstance(data, dict) else None

        self._attributes = [item.name for item in self._schema.attributes]
        self._relationships = [item.name for item in self._schema.relationships]

        for attr_name in self._attributes:
            attr_schema = [attr for attr in self._schema.attributes if attr.name == attr_name][0]
            attr_data = data.get(attr_name, None) if isinstance(data, dict) else None
            setattr(self, attr_name, Attribute(name=attr_name, schema=attr_schema, data=attr_data))

        for rel_name in self._relationships:
            rel_schema = [rel for rel in self._schema.relationships if rel.name == rel_name][0]
            rel_data = data.get(rel_name, None) if isinstance(data, dict) else None

            if rel_schema.cardinality == "one":
                setattr(self, f"_{rel_name}", None)
                setattr(self.__class__, rel_name, generate_relationship_property(rel_name))
                setattr(self, rel_name, rel_data)
            else:
                setattr(self, rel_name, RelationshipManager(name=rel_name, schema=rel_schema, data=rel_data))

    def __repr__(self) -> str:
        if self.display_label:
            return self.display_label
        if not self.id:
            return f"{self._schema.kind} (no id yet)"

        return f"{self._schema.kind} ({self.id})"

    async def save(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        if not self.id:
            await self._create(at=at)
        else:
            await self._update(at=at)

    async def _create(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        mutation_query = {"ok": None, "object": {"id": None}}
        mutation_name = f"{self._schema.name}_create"
        query = Mutation(mutation=mutation_name, input_data=input_data, query=mutation_query)

        response = await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
        )
        self.id = response[mutation_name]["object"]["id"]

    async def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        input_data["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(mutation=f"{self._schema.name}_update", input_data=input_data, query=mutation_query)
        await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-update",
        )

    def _generate_input_data(self) -> Dict[str, Dict]:
        """Generate a dictionnary that represent the input data required by a mutation.

        Returns:
            Dict[str, Dict]: Representation of an input data in dict format
        """
        data = {}
        for item_name in self._attributes + self._relationships:
            item = getattr(self, item_name)
            if item is None:
                continue

            item_data = item._generate_input_data()
            if item_data:
                data[item_name] = item_data

        return {"data": data}

    def generate_query_data(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Union[Any, Dict]]:
        data: Dict[str, Any] = {"id": None, "display_label": None}

        if filters:
            data["@filters"] = filters

        for attr_name in self._attributes:
            attr: Attribute = getattr(self, attr_name)
            attr_data = attr._generate_query_data()
            if attr_data:
                data[attr_name] = attr_data

        return {self._schema.name: data}

    def validate_filters(self, filters: Optional[Dict[str, Any]] = None) -> bool:
        if not filters:
            return True

        for filter_name in filters.keys():
            found = False
            for filter_schema in self._schema.filters:
                if filter_name == filter_schema.name:
                    found = True
                    break
            if not found:
                raise FilterNotFound(identifier=filter_name, kind=self._schema.kind)

        return True


class InfrahubClient:  # pylint: disable=too-many-public-methods
    """GraphQL Client to interact with Infrahub."""

    def __init__(
        self,
        address: str = "http://localhost:8000",
        default_timeout: int = 10,
        retry_on_failure: bool = False,
        retry_delay: int = 5,
        log: Optional[Logger] = None,
        test_client=None,
        default_branch: str = "main",
        insert_tracker: bool = False,
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

        self.schema = InfrahubSchema(self)
        self.branch = InfrahubBranchManager(self)

        self.headers = {"content-type": "application/json"}

        if test_client:
            self.address = ""

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
        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data(filters=filters)
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-get"
        )

        if len(response[schema.name]) == 0:
            raise NodeNotFound(branch_name=branch, node_type=kind, identifier=filters)
        if len(response[schema.name]) > 1:
            raise IndexError("More than 1 node returned")

        return InfrahubNode(client=self, schema=schema, branch=branch, data=response[schema.name][0])

    async def all(self, kind: str, at: Optional[Timestamp] = None, branch: Optional[str] = None) -> List[InfrahubNode]:
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

        query_data = InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data()
        query = Query(query=query_data)
        response = await self.execute_graphql(
            query=query.render(), branch_name=branch, at=at, tracker=f"query-{str(schema.kind).lower()}-all"
        )
        return [InfrahubNode(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]]

    async def filters(
        self, kind: str, at: Optional[Timestamp] = None, branch: Optional[str] = None, **kwargs: Any
    ) -> List[InfrahubNode]:
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

        return [InfrahubNode(client=self, schema=schema, branch=branch, data=item) for item in response[schema.name]]

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
                    query=QUERY_ALL_REPOSITORIES, branch_name=branch_name, tracker="query-repository-all"
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

    async def get_list_graphql_queries(self, branch_name: str) -> Dict[str, GraphQLQueryData]:
        data = await self.execute_graphql(
            query=QUERY_ALL_GRAPHQL_QUERIES, branch_name=branch_name, tracker="query-graphqlquery-all"
        )

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
        data = await self.execute_graphql(query=QUERY_ALL_CHECKS, branch_name=branch_name, tracker="query-check-all")

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
        data = await self.execute_graphql(
            query=QUERY_ALL_TRANSFORM_PYTHON, branch_name=branch_name, tracker="query-transformpython-all"
        )

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
        await self.execute_graphql(
            query=MUTATION_GRAPHQL_QUERY_CREATE,
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-graphqlquery-create",
        )

        return True

    async def update_graphql_query(
        self, branch_name: str, id: str, name: str, query: str, description: str = ""
    ) -> bool:
        variables = {"id": id, "name": name, "description": description, "query": query}
        await self.execute_graphql(
            query=MUTATION_GRAPHQL_QUERY_UPDATE,
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-graphqlquery-update",
        )

        return True

    async def get_list_rfiles(self, branch_name: str) -> Dict[str, RFileData]:
        data = await self.execute_graphql(query=QUERY_ALL_RFILES, branch_name=branch_name, tracker="query-rfile-all")

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
        await self.execute_graphql(
            query=MUTATION_RFILE_CREATE, variables=variables, branch_name=branch_name, tracker="mutation-rfile-create"
        )

        return True

    async def update_rfile(
        self, branch_name: str, id: str, name: str, template_path: str, description: str = ""
    ) -> bool:
        variables = {"id": id, "name": name, "description": description, "template_path": template_path}
        await self.execute_graphql(
            query=MUTATION_RFILE_UPDATE, variables=variables, branch_name=branch_name, tracker="mutation-rfile-update"
        )

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
        await self.execute_graphql(
            query=MUTATION_CHECK_CREATE, variables=variables, branch_name=branch_name, tracker="mutation-check-create"
        )

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
    ) -> bool:
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
        await self.execute_graphql(
            query=MUTATION_CHECK_UPDATE, variables=variables, branch_name=branch_name, tracker="mutation-check-update"
        )

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
        await self.execute_graphql(
            query=MUTATION_TRANSFORM_PYTHON_CREATE,
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-transformpython-create",
        )

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
    ) -> bool:
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
        await self.execute_graphql(
            query=MUTATION_TRANSFORM_PYTHON_UPDATE,
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-transformpython-update",
        )

        return True

    async def repository_update_commit(self, branch_name: str, repository_id: str, commit: str) -> bool:
        variables = {"repository_id": str(repository_id), "commit": str(commit)}
        await self.execute_graphql(
            query=MUTATION_COMMIT_UPDATE,
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-repository-update-commit",
        )

        return True
