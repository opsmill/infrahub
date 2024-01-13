from __future__ import annotations

import asyncio
import functools

from infrahub_sdk.transforms import get_transform_class_instance

from ..exceptions import PythonTransformDefinitionError, PythonTransformException
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem


class InfrahubPythonTransformUnitProcessItem(InfrahubItem):
    def runtest(self) -> None:
        transform_instance = get_transform_class_instance(
            transform_config=self.resource_config,  # type: ignore[arg-type]
            search_path=self.session.infrahub_config_path.parent,  # type: ignore[attr-defined]
        )

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
