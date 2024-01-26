from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from httpx import HTTPStatusError

from ..exceptions import OutputMatchException
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo


class InfrahubGraphqlQueryItem(InfrahubItem):
    def execute_query(self) -> Any:
        return self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.test.spec.query,  # type: ignore[union-attr]
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
            branch_name=self.session.config.option.infrahub_branch,  # type: ignore[attr-defined]
            rebase=self.test.spec.rebase,  # type: ignore[union-attr]
        )

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


class InfrahubGraphqlQueryIntegrationItem(InfrahubGraphqlQueryItem):
    def runtest(self) -> None:
        computed = self.execute_query()
        differences = self.get_result_differences(computed)

        if self.test.spec.output and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchException(name=self.name, differences=differences)
