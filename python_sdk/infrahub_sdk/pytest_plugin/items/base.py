from __future__ import annotations

import difflib
import json
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

import pytest
from git.exc import InvalidGitRepositoryError

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

    def get_result_differences(self, computed: Any) -> Optional[str]:
        """Compute the differences between the computed result and the expected one.

        If the results are not JSON parsable, this method must be redefined to handle them.
        """
        if not self.test.spec.output or computed is None:
            return None

        expected = self.test.spec.get_output_data()
        differences = difflib.unified_diff(
            json.dumps(expected, indent=4, sort_keys=True).splitlines(),
            json.dumps(computed, indent=4, sort_keys=True).splitlines(),
            fromfile="expected",
            tofile="rendered",
            lineterm="",
        )
        return "\n".join(differences)

    def runtest(self) -> None:
        """Run the test logic."""

    def repr_failure(self, excinfo: pytest.ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, InvalidGitRepositoryError):
            return f"Invalid Git repository at {excinfo.value}"

        return str(excinfo.value)

    def reportinfo(self) -> Tuple[Union[Path, str], Optional[int], str]:
        return self.path, 0, f"resource: {self.name}"
