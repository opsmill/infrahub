from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any, Optional, Union

import pytest
import ujson
from git.exc import InvalidGitRepositoryError

from ..exceptions import InvalidResourceConfigError
from ..models import InfrahubInputOutputTest

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
        **kwargs: dict[str, Any],
    ):
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

        self.resource_name: str = resource_name
        self.resource_config: InfrahubRepositoryConfigElement = resource_config
        self.test: InfrahubTest = test

        # Smoke tests do not need this, hence this clause
        if isinstance(self.test.spec, InfrahubInputOutputTest):
            self.test.spec.update_paths(base_dir=self.path.parent)

    def validate_resource_config(self) -> None:
        """Make sure that a test resource config is properly defined."""
        if self.resource_config is None:
            raise InvalidResourceConfigError(self.resource_name)

    def get_result_differences(self, computed: Any) -> Optional[str]:
        """Compute the differences between the computed result and the expected one.

        If the results are not JSON parsable, this method must be redefined to handle them.
        """
        # We cannot compute a diff if:
        # 1. Test is not an input/output one
        # 2. Expected output is not provided
        # 3. Output can't be computed
        if not isinstance(self.test.spec, InfrahubInputOutputTest) or not self.test.spec.output or computed is None:
            return None

        expected = self.test.spec.get_output_data()
        differences = difflib.unified_diff(
            ujson.dumps(expected, indent=4, sort_keys=True).splitlines(),
            ujson.dumps(computed, indent=4, sort_keys=True).splitlines(),
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

    def reportinfo(self) -> tuple[Union[Path, str], Optional[int], str]:
        return self.path, 0, f"resource: {self.name}"
