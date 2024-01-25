from __future__ import annotations

import asyncio
import functools
import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from deepdiff import DeepDiff, Delta
from deepdiff.serialization import json_dumps
from httpx import HTTPStatusError

from infrahub_sdk.transforms import get_transform_class_instance

from ..exceptions import OutputMatchException, PythonTransformDefinitionError
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo


class InfrahubPythonTransform(InfrahubItem):
    def run_transform(self, variables: Dict[str, Any]) -> Any:
        transform_instance = get_transform_class_instance(
            transform_config=self.resource_config,  # type: ignore[arg-type]
            search_path=self.session.infrahub_config_path.parent,  # type: ignore[attr-defined]
        )

        # FIXME: ugly as hell, should be normalise
        # https://github.com/opsmill/infrahub/issues/1994
        if "data" in variables:
            variables = variables["data"]

        for attr in ("query", "transform"):
            if not hasattr(transform_instance, attr):
                raise PythonTransformDefinitionError(f"Missing attribute or function {attr}")

        transformer = functools.partial(transform_instance.transform)

        if asyncio.iscoroutinefunction(transformer.func):
            computed = asyncio.run(transformer(variables))
        else:
            computed = transformer(variables)
        return computed

    def get_result_differences(self, computed: Any) -> Any:
        expected = self.test.spec.get_output_data()
        differences = Delta(DeepDiff(expected, computed), serializer=json_dumps)

        return json.dumps(json.loads(differences.dumps()), indent=4, sort_keys=True)

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, HTTPStatusError):
            try:
                response_content = json.dumps(excinfo.value.response.json(), indent=4)
            except json.JSONDecodeError:
                response_content = excinfo.value.response.text
            return "\n".join(
                [
                    f"Failed {excinfo.value.request.method} on {excinfo.value.request.url}",
                    f"Status code: {excinfo.value.response.status_code}",
                    f"Response: {response_content}",
                ]
            )

        if isinstance(excinfo.value, OutputMatchException):
            return "\n".join([excinfo.value.message, excinfo.value.differences])

        return super().repr_failure(excinfo, style=style)


class InfrahubPythonTransformUnitProcessItem(InfrahubPythonTransform):
    def runtest(self) -> None:
        input_data = self.test.spec.get_input_data()
        computed = self.run_transform(input_data)
        expected = self.test.spec.get_output_data()

        if self.test.spec.output and computed != expected and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchException(name=self.name, message=self.get_result_differences(computed))


class InfrahubPythonTransformIntegrationItem(InfrahubPythonTransform):
    def runtest(self) -> None:
        input_data = self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.test.spec.query,  # type: ignore[union-attr]
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
            branch_name=self.test.spec.branch_name,  # type: ignore[union-attr]
            rebase=self.test.spec.rebase,  # type: ignore[union-attr]
        )
        computed = self.run_transform(input_data)
        expected = self.test.spec.get_output_data()

        if self.test.spec.output and computed != expected and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchException(name=self.name, message=self.get_result_differences(computed))
