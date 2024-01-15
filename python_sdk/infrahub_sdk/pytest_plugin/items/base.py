from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Tuple

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.schema import InfrahubRepositoryConfigElement

    from ..models import InfrahubTest


class InfrahubItem(pytest.Item):
    def __init__(
        self,
        *args: Any,
        resource_name: str,
        resource_config: InfrahubRepositoryConfigElement,
        test: InfrahubTest,
        **kwargs: Dict[str, Any],
    ):
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

        self.resource_name: str = resource_name
        self.resource_config: InfrahubRepositoryConfigElement = resource_config
        test.spec.update_paths(base_dir=self.fspath.dirpath())
        self.test: InfrahubTest = test

    @abstractmethod
    def runtest(self) -> None:
        pass

    def repr_failure(self, excinfo: pytest.ExceptionInfo, style: Optional[str] = None) -> str:
        """Called when self.runtest() raises an exception."""
        return str(excinfo.value)

    def reportinfo(self) -> Tuple[Path, Literal[0], str]:
        return self.path, 0, f"resource: {self.name}"
