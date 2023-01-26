import asyncio
import copy
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel

# pylint: disable=redefined-builtin


QUERY_ALL_REPOSITORIES = """
query {
    repository {
        id
        name {
            value
        }
        location {
            value
        }
        commit {
            value
        }
    }
}
"""

QUERY_ALL_GRAPHQL_QUERIES = """
query {
    graphql_query {
        id
        name {
            value
        }
        description {
            value
        }
        query {
            value
        }
    }
}
"""

QUERY_ALL_RFILES = """
query {
    rfile {
        id
        name {
            value
        }
        description {
            value
        }
        template_path {
            value
        }
        template_repository {
            id
            name {
                value
            }
        }
        query {
            id
            name {
                value
            }
        }
    }
}
"""

QUERY_ALL_CHECKS = """
query {
    check {
        id
        name {
            value
        }
        description {
            value
        }
        file_path {
            value
        }
        class_name {
            value
        }
        rebase {
            value
        }
        timeout {
            value
        }
        query {
            id
            name {
                value
            }
        }
        repository {
            id
            name {
                value
            }
        }
    }
}
"""

QUERY_ALL_TRANSFORM_PYTHON = """
query {
    transform_python {
        id
        name {
            value
        }
        description {
            value
        }
        file_path {
            value
        }
        class_name {
            value
        }
        rebase {
            value
        }
        timeout {
            value
        }
        url {
            value
        }
        query {
            id
            name {
                value
            }
        }
        repository {
            id
            name {
                value
            }
        }
    }
}
"""

QUERY_ALL_BRANCHES = """
query {
    branch {
        id
        name
        is_data_only
    }
}
"""

MUTATION_COMMIT_UPDATE = """
mutation ($repository_id: String!, $commit: String!) {
    repository_update(data: { id: $repository_id, commit: { value: $commit } }) {
        ok
        object {
            commit {
                value
            }
        }
    }
}
"""

MUTATION_BRANCH_CREATE = """
mutation ($branch_name: String!, $background_execution: Boolean!) {
    branch_create(background_execution: $background_execution, data: { name: $branch_name, is_data_only: false }) {
        ok
        object {
            id
            name
        }
    }
}
"""

MUTATION_GRAPHQL_QUERY_CREATE = """
mutation($name: String!, $description: String!, $query: String!) {
  graphql_query_create(data: {
    name: { value: $name },
    description: { value: $description },
    query: { value: $query }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_GRAPHQL_QUERY_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $query: String!) {
  graphql_query_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    query: { value: $query }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_RFILE_CREATE = """
mutation($name: String!, $description: String!, $template_path: String!, $template_repository: String!, $query: String!) {
  rfile_create(data: {
    name: { value: $name },
    description: { value: $description },
    query: { id: $query }
    template_path: { value: $template_path }
    template_repository: { id: $template_repository }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_RFILE_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $template_path: String!) {
  rfile_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    template_path: { value: $template_path }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_CHECK_CREATE = """
mutation($name: String!, $description: String!, $file_path: String!, $class_name: String!, $repository: String!, $query: String!, $timeout: Int!, $rebase: Boolean!) {
  check_create(data: {
    name: { value: $name }
    description: { value: $description }
    query: { id: $query }
    file_path: { value: $file_path }
    class_name: { value: $class_name }
    repository: { id: $repository }
    timeout: { value: $timeout }
    rebase: { value: $rebase }
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_CHECK_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $file_path: String!, $class_name: String!, $query: String!, $timeout: Int!, $rebase: Boolean!) {
  check_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    file_path: { value: $file_path },
    class_name: { value: $class_name },
    query: { id: $query },
    timeout: { value: $timeout },
    rebase: { value: $rebase },
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""


MUTATION_TRANSFORM_PYTHON_CREATE = """
mutation($name: String!, $description: String!, $file_path: String!, $class_name: String!, $repository: String!, $query: String!, $url: String!, $timeout: Int!, $rebase: Boolean!) {
  transform_python_create(data: {
    name: { value: $name }
    description: { value: $description }
    query: { id: $query }
    file_path: { value: $file_path }
    url: { value: $url }
    class_name: { value: $class_name }
    repository: { id: $repository }
    timeout: { value: $timeout }
    rebase: { value: $rebase }
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_TRANSFORM_PYTHON_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $file_path: String!, $class_name: String!, $query: String!, $url: String!, $timeout: Int!, $rebase: Boolean!) {
  transform_python_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    file_path: { value: $file_path },
    class_name: { value: $class_name },
    url: { value: $url },
    query: { id: $query },
    timeout: { value: $timeout },
    rebase: { value: $rebase },
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""


class GraphQLError(Exception):
    def __init__(self, errors: List[str], query: str = None, variables: dict = None):
        self.query = query
        self.variables = variables
        self.errors = errors
        self.message = f"An error occured while executing the GraphQL Query {self.query}, {self.errors}"
        super().__init__(self.message)


class BranchData(BaseModel):
    id: str
    name: str
    is_data_only: bool


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


class InfrahubClient:
    """GraphQL Client to interact with Infrahub."""

    def __init__(self, address="http://localhost:8000", default_timeout=5, test_client=None):

        self.address = address
        self.client = None
        self.default_timeout = default_timeout
        self.test_client = test_client

        if test_client:
            self.address = ""

    @classmethod
    async def init(cls, *args, **kwargs):

        return cls(*args, **kwargs)

    async def execute_graphql(
        self,
        query,
        variables: dict = None,
        branch_name: str = None,
        at: str = None,
        rebase: bool = False,
        timeout: int = None,
        raise_for_error: bool = True,
    ):

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
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url=url,
                    json=payload,
                    timeout=timeout or self.default_timeout,
                )

        else:
            with self.test_client as client:
                resp = client.post(url=url, json=payload)

        if raise_for_error:
            resp.raise_for_status()

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

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

    async def create_branch(self, branch_name: str, background_execution: bool = False) -> bool:

        variables = {"branch_name": branch_name, "background_execution": background_execution}

        await self.execute_graphql(query=MUTATION_BRANCH_CREATE, variables=variables)

        return True

    async def get_list_branches(self) -> Dict[str, BranchData]:

        data = await self.execute_graphql(query=QUERY_ALL_BRANCHES)

        branches = {
            branch["name"]: BranchData(id=branch["id"], name=branch["name"], is_data_only=branch["is_data_only"])
            for branch in data["branch"]
        }

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
