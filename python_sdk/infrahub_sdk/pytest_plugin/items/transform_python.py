from __future__ import annotations

import asyncio
import functools
import importlib
from typing import TYPE_CHECKING, Any, Dict, Literal, Tuple

import pytest

from infrahub_sdk.ctl.exceptions import InfrahubTransformNotFoundError

from ..exceptions import PythonTransformDefinitionError, PythonTransformException
from ..models import InfrahubTest, InfrahubTestExpectedResult

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.schema import InfrahubPythonTransformConfig
    from infrahub_sdk.transforms import InfrahubTransform


def get_transform_class_instance(transform_config: InfrahubPythonTransformConfig) -> InfrahubTransform:
    """FIXME: Move it somewhere else to avoid having the exact same function as in sdk/ctl/cli"""
    try:
        spec = importlib.util.spec_from_file_location(transform_config.class_name, transform_config.file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        transform_class = getattr(module, transform_config.class_name)

        transform_instance = transform_class()
    except (FileNotFoundError, AttributeError) as e:
        raise InfrahubTransformNotFoundError(name=transform_config.name) from e

    return transform_instance


class InfrahubPythonTransformUnitProcessItem(pytest.Item):
    def __init__(
        self,
        *args: Any,
        resource_name: str,
        resource_config: InfrahubPythonTransformConfig,
        test: InfrahubTest,
        **kwargs: Dict[str, Any],
    ):
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

        self.resource_name: str = resource_name
        self.resource_config: InfrahubPythonTransformConfig = resource_config
        test.spec.update_paths(base_dir=self.fspath.dirpath())
        self.test: InfrahubTest = test

    def runtest(self) -> None:
        transform_instance = get_transform_class_instance(self.resource_config)

        for attr in ("query", "url", "transform"):
            if not hasattr(transform_instance, attr):
                raise PythonTransformDefinitionError(f"Missing attribute or function {attr}")

        input_data = self.test.spec.get_input_data()
        transformer = functools.partial(transform_instance.transform)

        if asyncio.iscoroutinefunction(transformer.func):
            computed_output = asyncio.run(transformer(input_data))
        else:
            computed_output = transformer(input_data)

        expected_output = self.test.spec.get_output_data()

        if self.test.spec.output and computed_output != expected_output:
            if self.test.expect == InfrahubTestExpectedResult.PASS:
                # TODO: Make this more readable for end user
                raise PythonTransformException(
                    name=self.name, message=f"Expected:\n{expected_output}\nGot:\n{computed_output}"
                )

    def reportinfo(self) -> Tuple[Path, Literal[0], str]:
        return self.path, 0, f"resource: {self.name}"
