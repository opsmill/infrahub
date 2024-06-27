from __future__ import annotations

import asyncio
import importlib
import os
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from git import Repo

from infrahub_sdk import InfrahubClient

from .exceptions import InfrahubTransformNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

    from .schema import InfrahubPythonTransformConfig

INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT = "INFRAHUB_TRANSFORMS"


class InfrahubTransform:
    name: Optional[str] = None
    query: str
    timeout: int = 10

    def __init__(self, branch: str = "", root_directory: str = "", server_url: str = ""):
        self.git: Repo

        self.branch = branch

        self.server_url = server_url or os.environ.get("INFRAHUB_URL", "http://127.0.0.1:8000")
        self.root_directory = root_directory or os.getcwd()

        self.client: InfrahubClient

        if not self.name:
            self.name = self.__class__.__name__

        if not self.query:
            raise ValueError("A query must be provided")

    @classmethod
    async def init(cls, client: Optional[InfrahubClient] = None, *args: Any, **kwargs: Any) -> InfrahubTransform:
        """Async init method, If an existing InfrahubClient client hasn't been provided, one will be created automatically."""

        item = cls(*args, **kwargs)

        if client:
            item.client = client
        else:
            item.client = InfrahubClient(address=item.server_url)

        return item

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
    def transform(self, data: dict) -> Any:
        pass

    async def collect_data(self) -> dict:
        """Query the result of the GraphQL Query defined in self.query and return the result"""

        return await self.client.query_gql_query(name=self.query, branch_name=self.branch_name)

    async def run(self, data: Optional[dict] = None) -> Any:
        """Execute the transformation after collecting the data from the GraphQL query.
        The result of the check is determined based on the presence or not of ERROR log messages."""

        if not data:
            data = await self.collect_data()
        unpacked = data.get("data") or data

        if asyncio.iscoroutinefunction(self.transform):
            return await self.transform(data=unpacked)

        return self.transform(data=unpacked)


def get_transform_class_instance(
    transform_config: InfrahubPythonTransformConfig, search_path: Optional[Path] = None
) -> InfrahubTransform:
    if transform_config.file_path.is_absolute() or search_path is None:
        search_location = transform_config.file_path
    else:
        search_location = search_path / transform_config.file_path

    try:
        spec = importlib.util.spec_from_file_location(transform_config.class_name, search_location)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Get the specified class from the module
        transform_class = getattr(module, transform_config.class_name)

        # Create an instance of the class
        transform_instance = transform_class()
    except (FileNotFoundError, AttributeError) as exc:
        raise InfrahubTransformNotFoundError(name=transform_config.name) from exc

    return transform_instance
