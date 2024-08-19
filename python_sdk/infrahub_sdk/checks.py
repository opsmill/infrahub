from __future__ import annotations

import asyncio
import importlib
import os
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Optional

import ujson
from git.repo import Repo
from pydantic import BaseModel, Field

from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import InfrahubCheckNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.schema import InfrahubCheckDefinitionConfig

INFRAHUB_CHECK_VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


class InfrahubCheckInitializer(BaseModel):
    """Information about the originator of the check."""

    proposed_change_id: str = Field(
        default="", description="If available the ID of the proposed change that requested the check"
    )


class InfrahubCheck:
    name: Optional[str] = None
    query: str = ""
    timeout: int = 10

    def __init__(
        self,
        branch: Optional[str] = None,
        root_directory: str = "",
        output: Optional[str] = None,
        initializer: Optional[InfrahubCheckInitializer] = None,
        params: Optional[dict] = None,
    ):
        self.git: Optional[Repo] = None
        self.initializer = initializer or InfrahubCheckInitializer()

        self.logs: list[dict[str, Any]] = []
        self.passed = False

        self.output = output

        self.branch = branch
        self.params = params or {}

        self.root_directory = root_directory or os.getcwd()

        self.client: InfrahubClient

        if not self.name:
            self.name = self.__class__.__name__

        if not self.query:
            raise ValueError("A query must be provided")

    def __str__(self) -> str:
        return self.__class__.__name__

    @classmethod
    async def init(cls, client: Optional[InfrahubClient] = None, *args: Any, **kwargs: Any) -> InfrahubCheck:
        """Async init method, If an existing InfrahubClient client hasn't been provided, one will be created automatically."""

        instance = cls(*args, **kwargs)
        instance.client = client or InfrahubClient()

        return instance

    @property
    def errors(self) -> list[dict[str, Any]]:
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
            print(ujson.dumps(log_message))

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
    def validate(self, data: dict) -> None:
        """Code to validate the status of this check."""

    async def collect_data(self) -> dict:
        """Query the result of the GraphQL Query defined in self.query and return the result"""

        return await self.client.query_gql_query(name=self.query, branch_name=self.branch_name, variables=self.params)

    async def run(self, data: Optional[dict] = None) -> bool:
        """Execute the check after collecting the data from the GraphQL query.
        The result of the check is determined based on the presence or not of ERROR log messages."""

        if not data:
            data = await self.collect_data()
        unpacked = data.get("data") or data

        if asyncio.iscoroutinefunction(self.validate):
            await self.validate(data=unpacked)
        else:
            self.validate(data=unpacked)

        nbr_errors = len([log for log in self.logs if log["level"] == "ERROR"])

        self.passed = bool(nbr_errors == 0)

        if self.passed:
            self.log_info("Check succesfully completed")

        return self.passed


def get_check_class_instance(
    check_config: InfrahubCheckDefinitionConfig, search_path: Optional[Path] = None
) -> InfrahubCheck:
    if check_config.file_path.is_absolute() or search_path is None:
        search_location = check_config.file_path
    else:
        search_location = search_path / check_config.file_path

    try:
        spec = importlib.util.spec_from_file_location(check_config.class_name, search_location)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Get the specified class from the module
        check_class = getattr(module, check_config.class_name)

        # Create an instance of the class
        check_instance = check_class()
    except (FileNotFoundError, AttributeError) as exc:
        raise InfrahubCheckNotFoundError(name=check_config.name) from exc

    return check_instance
