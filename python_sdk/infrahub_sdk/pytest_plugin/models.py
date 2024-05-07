from __future__ import annotations

import glob
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import ujson
import yaml

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from .exceptions import DirectoryNotFoundError


class InfrahubTestExpectedResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class InfrahubTestResource(str, Enum):
    CHECK = "Check"
    JINJA2_TRANSFORM = "Jinja2Transform"
    PYTHON_TRANSFORM = "PythonTransform"
    GRAPHQL_QUERY = "GraphQLQuery"


class InfrahubBaseTest(pydantic.BaseModel):
    """Basic Infrahub test model used as a common ground for all tests."""


class InfrahubInputOutputTest(InfrahubBaseTest):
    directory: Optional[Path] = pydantic.Field(
        None, description="Path to the directory where the input and output files are located"
    )
    input: Path = pydantic.Field(
        Path("input.json"),
        description="Path to the file with the input data for the test, can be a relative path from the config file or from the directory.",
    )
    output: Optional[Path] = pydantic.Field(
        None,
        description="Path to the file with the expected output for the test, can be a relative path from the config file or from the directory.",
    )

    @staticmethod
    def parse_user_provided_data(path: Union[Path, None]) -> Any:
        """Read and parse user provided data depending on a file extension.

        This function handles JSON and YAML as they can be used to achieve the same goal. However some users may be more used to one format or
        another. If the file extension isn't known, assume the content is plain text.
        """
        if path is None:
            return None

        suffix = path.suffix.lower()[1:] if path.suffix else ""
        text = path.read_text()

        if suffix and suffix == "json":
            return ujson.loads(text)
        if suffix in ("yml", "yaml"):
            return yaml.safe_load(text)

        return text

    def update_paths(self, base_dir: Path) -> None:
        if self.directory and not self.directory.is_absolute() and not self.directory.is_dir():
            self.directory = Path(base_dir / self.directory)
            if not self.directory.is_dir():
                raise DirectoryNotFoundError(name=str(self.directory))
        else:
            self.directory = base_dir

        if (self.input and not self.input.is_file()) or not self.input:
            search_input = self.input or "input.*"
            results = glob.glob(str(self.directory / search_input))
            if not results:
                raise FileNotFoundError(self.input)
            if len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are matching: {self.input}, please set the 'input' test key to the file to use."
                )
            self.input = Path(results[0])

        if (self.output and not self.output.is_file()) or not self.output:
            search_input = self.output or "output.*"

            results = glob.glob(str(self.directory / search_input))
            if results and len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are matching: {self.output}, please set the 'output' test key to the file to use."
                )
            if results:
                self.output = Path(results[0])

    def get_input_data(self) -> Any:
        return self.parse_user_provided_data(self.input)

    def get_output_data(self) -> Any:
        return self.parse_user_provided_data(self.output)


class InfrahubIntegrationTest(InfrahubInputOutputTest):
    variables: Union[Path, Dict[str, Any]] = pydantic.Field(
        Path("variables.json"), description="Variables and corresponding values to pass to the GraphQL query"
    )

    def update_paths(self, base_dir: Path) -> None:
        super().update_paths(base_dir)

        if self.variables and not isinstance(self.variables, dict) and not self.variables.is_file():
            search_variables = self.variables or "variables.*"
            results = glob.glob(str(self.directory / search_variables))  # type: ignore[operator]
            if not results:
                raise FileNotFoundError(self.variables)
            if len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are matching: {self.variables}, please set the 'variables' test key to the file to use."
                )
            self.variables = Path(results[0])

    def get_variables_data(self) -> Dict[str, Any]:
        if isinstance(self.variables, dict):
            return self.variables
        return self.parse_user_provided_data(self.variables)


class InfrahubCheckSmokeTest(InfrahubBaseTest):
    kind: Literal["check-smoke"]


class InfrahubCheckUnitProcessTest(InfrahubInputOutputTest):
    kind: Literal["check-unit-process"]


class InfrahubCheckIntegrationTest(InfrahubIntegrationTest):
    kind: Literal["check-integration"]


class InfrahubGraphQLQuerySmokeTest(InfrahubBaseTest):
    kind: Literal["graphql-query-smoke"]
    path: Path = pydantic.Field(description="Path to the file in which the GraphQL query is defined")


class InfrahubGraphQLQueryIntegrationTest(InfrahubIntegrationTest):
    kind: Literal["graphql-query-integration"]
    query: str = pydantic.Field(description="Name of a pre-defined GraphQL query to execute")


class InfrahubJinja2TransformSmokeTest(InfrahubBaseTest):
    kind: Literal["jinja2-transform-smoke"]


class InfrahubJinja2TransformUnitRenderTest(InfrahubInputOutputTest):
    kind: Literal["jinja2-transform-unit-render"]


class InfrahubJinja2TransformIntegrationTest(InfrahubIntegrationTest):
    kind: Literal["jinja2-transform-integration"]


class InfrahubPythonTransformSmokeTest(InfrahubBaseTest):
    kind: Literal["python-transform-smoke"]


class InfrahubPythonTransformUnitProcessTest(InfrahubInputOutputTest):
    kind: Literal["python-transform-unit-process"]


class InfrahubPythonTransformIntegrationTest(InfrahubIntegrationTest):
    kind: Literal["python-transform-integration"]


class InfrahubTest(pydantic.BaseModel):
    name: str = pydantic.Field(..., description="Name of the test, must be unique")
    expect: InfrahubTestExpectedResult = pydantic.Field(
        InfrahubTestExpectedResult.PASS,
        description="Expected outcome of the test, can be either PASS (default) or FAIL",
    )
    spec: Union[
        InfrahubCheckSmokeTest,
        InfrahubCheckUnitProcessTest,
        InfrahubCheckIntegrationTest,
        InfrahubGraphQLQuerySmokeTest,
        InfrahubGraphQLQueryIntegrationTest,
        InfrahubJinja2TransformSmokeTest,
        InfrahubJinja2TransformUnitRenderTest,
        InfrahubJinja2TransformIntegrationTest,
        InfrahubPythonTransformSmokeTest,
        InfrahubPythonTransformUnitProcessTest,
        InfrahubPythonTransformIntegrationTest,
    ] = pydantic.Field(..., discriminator="kind")


class InfrahubTestGroup(pydantic.BaseModel):
    resource: InfrahubTestResource
    resource_name: str
    tests: List[InfrahubTest]


class InfrahubTestFileV1(pydantic.BaseModel):
    version: Optional[str] = "1.0"
    infrahub_tests: List[InfrahubTestGroup]

    class Config:
        extra = pydantic.Extra.forbid
