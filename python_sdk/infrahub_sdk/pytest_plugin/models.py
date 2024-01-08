from __future__ import annotations

import glob
from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional, Union

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from .exceptions import DirectoryNotFoundError


class InfrahubTestExpectedResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class InfrahubTestResource(str, Enum):
    RFILE = "RFile"
    TRANSFORMPYTHON = "TransformPython"
    GRAPHQL = "GraphQLQuery"


class InfrahubInputOutputTest(pydantic.BaseModel):
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
                    f"Too many files are mathing: {self.input}, please adjust the value to match only one file."
                )
            self.input = Path(results[0])

        if (self.output and not self.output.is_file()) or not self.output:
            search_input = self.output or "output.*"

            results = glob.glob(str(self.directory / search_input))
            if results and len(results) != 1:
                raise FileNotFoundError(
                    f"Too many files are mathing: {self.output}, please adjust the value to match only one file."
                )
            if results:
                self.output = Path(results[0])


class InfrahubRFileUnitRenderTest(InfrahubInputOutputTest):
    kind: Literal["rfile-unit-render"]


class InfrahubTransformPythonUnitProcessTest(InfrahubInputOutputTest):
    kind: Literal["transform-python-unit-process"]


class InfrahubTest(pydantic.BaseModel):
    name: str = pydantic.Field(..., description="Name of the test, must be unique")
    expect: InfrahubTestExpectedResult
    spec: Union[InfrahubRFileUnitRenderTest, InfrahubTransformPythonUnitProcessTest] = pydantic.Field(
        ..., discriminator="kind"
    )


class InfrahubTestGroup(pydantic.BaseModel):
    resource: InfrahubTestResource
    resource_name: str
    tests: List[InfrahubTest]


class InfrahubTestFileV1(pydantic.BaseModel):
    version: Optional[str] = "1.0"
    infrahub_tests: List[InfrahubTestGroup]

    class Config:
        extra = pydantic.Extra.forbid
