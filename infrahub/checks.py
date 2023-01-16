import asyncio
import json
import os
from abc import abstractmethod
from typing import Optional

from git import Repo

from infrahub_client import InfrahubClient

VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


class InfrahubCheck:

    name: Optional[str] = None
    query: str = None
    timeout: int = 10
    rebase: bool = True

    def __init__(self, branch=None, root_directory=None, output=None, server_url=None):

        self.data = None
        self.git = None

        self.logs = []
        self.passed = None

        self.output = output

        self.branch = branch

        self.server_url = server_url or os.environ.get("INFRAHUB_URL", "http://127.0.0.1:8000")
        self.root_directory = root_directory or os.getcwd()

        self.client: InfrahubClient = None

        if not self.name:
            self.name = self.__class__.__name__

        if not self.query:
            raise ValueError("A query must be provided")

    @classmethod
    async def init(cls, client=None, test_client=None, *args, **kwargs):

        item = cls(*args, **kwargs)

        if client:
            item.client = client
        else:
            item.client = await InfrahubClient.init(address=item.server_url, test_client=test_client)

        return item

    @property
    def errors(self):
        return [log for log in self.logs if log["level"] == "ERROR"]

    def log_error(self, message, object_id=None, object_type=None):

        log_message = {"level": "ERROR", "message": message, "branch": self.branch_name}
        if object_id:
            log_message["object_id"] = object_id
        if object_type:
            log_message["object_type"] = object_type
        self.logs.append(log_message)

        if self.output == "stdout":
            print(json.dumps(log_message))

    def log_info(self, message, object_id=None, object_type=None):

        log_message = {"level": "INFO", "message": message, "branch": self.branch_name}
        if object_id:
            log_message["object_id"] = object_id
        if object_type:
            log_message["object_type"] = object_type

        self.logs.append(log_message)

        if self.output == "stdout":
            print(json.dumps(log_message))

    @property
    def branch_name(self):
        """Return the name of the current git branch."""

        if self.branch:
            return self.branch

        if not self.git:
            self.git = Repo(self.root_directory)
            self.branch = str(self.git.active_branch)

        return self.branch

    @abstractmethod
    def validate(self):
        pass

    async def collect_data(self):

        data = await self.client.query_gql_query(name=self.query, branch_name=self.branch_name, rebase=self.rebase)
        self.data = data

    async def run(self):
        await self.collect_data()

        if asyncio.iscoroutinefunction(self.validate):
            await self.validate()
        else:
            self.validate()

        nbr_errors = len([log for log in self.logs if log["level"] == "ERROR"])

        self.passed = True if nbr_errors == 0 else False

        if self.passed:
            self.log_info("check succesfully completed")

        return self.passed
