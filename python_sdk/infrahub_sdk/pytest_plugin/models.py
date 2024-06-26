from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional, Union

import ujson
import yaml
from pydantic import BaseModel, ConfigDict, Field

from .exceptions import DirectoryNotFoundError


class InfrahubTestExpectedResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class InfrahubTestResource(str, Enum):
    CHECK = "Check"
    JINJA2_TRANSFORM = "Jinja2Transform"
    PYTHON_TRANSFORM = "PythonTransform"
    GRAPHQL_QUERY = "GraphQLQuery"


class InfrahubBaseTest(BaseModel):
    """Basic Infrahub test model used as a common ground for all tests."""


class InfrahubInputOutputTest(InfrahubBaseTest):
    directory: Optional[Path] = Field(
        None, description="Path to the directory where the input and output files are located"
    )
    input: Path = Field(
        Path("input.json"),
        description="Path to the file with the input data for the test, can be a relative path from the config file or from the directory.",
    )
    output: Optional[Path] = Field(
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

        if not self.input or not self.input.is_file():
            search_input: Union[Path, str] = self.input or "input.*"
            results = list(self.directory.rglob(str(search_input)))

            if not results:
                raise FileNotFoundError(self.input)
            if len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are matching: {self.input}, please set the 'input' test key to the file to use."
                )
            self.input = results[0]

        if not self.output or not self.output.is_file():
            search_output: Union[Path, str] = self.output or "output.*"
            results = list(self.directory.rglob(str(search_output)))

            if results and len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are matching: {self.output}, please set the 'output' test key to the file to use."
                )
            if results:
                self.output = results[0]

    def get_input_data(self) -> Any:
        return self.parse_user_provided_data(self.input)

    def get_output_data(self) -> Any:
        return self.parse_user_provided_data(self.output)


class InfrahubIntegrationTest(InfrahubInputOutputTest):
    variables: Union[Path, dict[str, Any]] = Field(
        Path("variables.json"), description="Variables and corresponding values to pass to the GraphQL query"
    )

    def update_paths(self, base_dir: Path) -> None:
        super().update_paths(base_dir)

        if self.variables and not isinstance(self.variables, dict) and not self.variables.is_file():
            search_variables: Union[Path, str] = self.variables or "variables.*"
            results = list(self.directory.rglob(str(search_variables)))  # type: ignore[union-attr]

            if not results:
                raise FileNotFoundError(self.variables)
            if len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are matching: {self.variables}, please set the 'variables' test key to the file to use."
                )
            self.variables = results[0]

    def get_variables_data(self) -> dict[str, Any]:
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
    path: Path = Field(..., description="Path to the file in which the GraphQL query is defined")


class InfrahubGraphQLQueryIntegrationTest(InfrahubIntegrationTest):
    kind: Literal["graphql-query-integration"]
    query: str = Field(..., description="Name of a pre-defined GraphQL query to execute")


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


class InfrahubTest(BaseModel):
    name: str = Field(..., description="Name of the test, must be unique")
    expect: InfrahubTestExpectedResult = Field(
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
    ] = Field(..., discriminator="kind")


class InfrahubTestGroup(BaseModel):
    resource: InfrahubTestResource
    resource_name: str
    tests: list[InfrahubTest]


class InfrahubTestFileV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Optional[str] = "1.0"
    infrahub_tests: list[InfrahubTestGroup]
