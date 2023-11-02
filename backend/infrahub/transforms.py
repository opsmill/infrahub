import asyncio
import os
from abc import abstractmethod
from typing import Optional

from git import Repo

from infrahub_sdk import InfrahubClient

INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT = "INFRAHUB_TRANSFORMS"


class InfrahubTransform:
    name: Optional[str] = None
    query: str = None
    url: str = None
    timeout: int = 10
    rebase: bool = True

    def __init__(self, branch=None, root_directory=None, server_url=None):
        self.data = None
        self.git = None

        self.logs = []

        self.branch = branch

        self.server_url = server_url or os.environ.get("INFRAHUB_URL", "http://127.0.0.1:8000")
        self.root_directory = root_directory or os.getcwd()

        self.client: InfrahubClient = None

        if not self.name:
            self.name = self.__class__.__name__

        if not self.query:
            raise ValueError("A query must be provided")
        if not self.url:
            raise ValueError("A url must be provided")

    @classmethod
    async def init(cls, client=None, *args, **kwargs):
        """Async init method, If an existing InfrahubClient client hasn't been provided, one will be created automatically."""

        item = cls(*args, **kwargs)

        if client:
            item.client = client
        else:
            item.client = await InfrahubClient.init(address=item.server_url)

        return item

    # def log_error(self, message, object_id=None, object_type=None):

    #     log_message = {"level": "ERROR", "message": message, "branch": self.branch_name}
    #     if object_id:
    #         log_message["object_id"] = object_id
    #     if object_type:
    #         log_message["object_type"] = object_type
    #     self.logs.append(log_message)

    #     if self.output == "stdout":
    #         print(json.dumps(log_message))

    # def log_info(self, message, object_id=None, object_type=None):

    #     log_message = {"level": "INFO", "message": message, "branch": self.branch_name}
    #     if object_id:
    #         log_message["object_id"] = object_id
    #     if object_type:
    #         log_message["object_type"] = object_type

    #     self.logs.append(log_message)

    #     if self.output == "stdout":
    #         print(json.dumps(log_message))

    @property
    def branch_name(self) -> str:
        """Return the name of the current git branch."""

        if self.branch:
            return self.branch

        if not self.git:
            self.git = Repo(self.root_directory)
            self.branch = str(self.git.active_branch)

        return self.branch

    @abstractmethod
    def transform(self, data: dict):
        pass

    async def collect_data(self):
        """Query the result of the GraphQL Query defined in sef.query and return the result"""

        return await self.client.query_gql_query(name=self.query, branch_name=self.branch_name, rebase=self.rebase)

    async def run(self, data: dict = None) -> bool:
        """Execute the transformation after collecting the data from the GraphQL query.
        The result of the check is determined based on the presence or not of ERROR log messages."""

        if not data:
            data = await self.collect_data()

        if asyncio.iscoroutinefunction(self.transform):
            return await self.transform(data=data)

        return self.transform(data=data)
