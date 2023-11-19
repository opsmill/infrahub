from __future__ import annotations

import asyncio
import json
import os
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from git.repo import Repo

from infrahub_sdk import InfrahubClient

INFRAHUB_CHECK_VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


class InfrahubCheck:
    name: Optional[str] = None
    query: str = ""
    timeout: int = 10
    rebase: bool = True

    def __init__(self, branch: str = "", root_directory: str = "", output: Optional[str] = None):
        self.data: Dict = {}
        self.git: Optional[Repo] = None

        self.logs: List[Dict[str, Any]] = []
        self.passed = False

        self.output = output

        self.branch = branch

        self.root_directory = root_directory or os.getcwd()

        self.client: InfrahubClient

        if not self.name:
            self.name = self.__class__.__name__

        if not self.query:
            raise ValueError("A query must be provided")

    @classmethod
    async def init(cls, client: Optional[InfrahubClient] = None, *args: Any, **kwargs: Any) -> InfrahubCheck:
        """Async init method, If an existing InfrahubClient client hasn't been provided, one will be created automatically."""

        instance = cls(*args, **kwargs)
        instance.client = client or InfrahubClient()

        return instance

    @property
    def errors(self) -> List[Dict[str, Any]]:
        return [log for log in self.logs if log["level"] == "ERROR"]

    def _write_log_entry(
        self, message: str, level: str, object_id: Optional[str] = None, object_type: Optional[str] = None
    ) -> None:
        log_message = {"level": level, "message": message, "branch": self.branch_name}
        if object_id:
            log_message["object_id"] = object_id
        if object_type:
            log_message["object_type"] = object_type
        self.logs.append(log_message)

        if self.output == "stdout":
            print(json.dumps(log_message))

    def log_error(self, message: str, object_id: Optional[str] = None, object_type: Optional[str] = None) -> None:
        self._write_log_entry(message=message, level="ERROR", object_id=object_id, object_type=object_type)

    def log_info(self, message: str, object_id: Optional[str] = None, object_type: Optional[str] = None) -> None:
        self._write_log_entry(message=message, level="INFO", object_id=object_id, object_type=object_type)

    @property
    def log_entries(self) -> str:
        output = ""
        for log in self.logs:
            output += "-----------------------\n"
            output += f"Message: {log['message']}\n"
            output += f"Level: {log['level']}\n"
            if "object_id" in log:
                output += f"Object ID: {log['object_id']}\n"
            if "object_type" in log:
                output += f"Object ID: {log['object_type']}\n"
        return output

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
    def validate(self) -> None:
        """Code to validate the status of this check."""

    async def collect_data(self) -> None:
        """Query the result of the GraphQL Query defined in sef.query and store the result in self.data"""

        data = await self.client.query_gql_query(name=self.query, branch_name=self.branch_name, rebase=self.rebase)
        self.data = data

    async def run(self) -> bool:
        """Execute the check after collecting the data from the GraphQL query.
        The result of the check is determined based on the presence or not of ERROR log messages."""

        await self.collect_data()

        validate_method = getattr(self, "validate")
        if asyncio.iscoroutinefunction(validate_method):
            await validate_method()
        else:
            validate_method()

        nbr_errors = len([log for log in self.logs if log["level"] == "ERROR"])

        self.passed = bool(nbr_errors == 0)

        if self.passed:
            self.log_info("Check succesfully completed")

        return self.passed
