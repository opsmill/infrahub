from __future__ import annotations

import difflib
import json
from typing import TYPE_CHECKING, Any, Dict, Optional

import jinja2
from httpx import HTTPStatusError
from rich.console import Console
from rich.traceback import Traceback

from ...utils import identify_faulty_jinja_code
from ..exceptions import Jinja2TransformException, Jinja2TransformUndefinedError, OutputMatchException
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo


class InfrahubJinja2Item(InfrahubItem):
    def render_jinja2_template(self, variables: Dict[str, Any]) -> Optional[str]:
        loader = jinja2.FileSystemLoader(self.session.infrahub_config_path.parent)  # type: ignore[attr-defined]
        env = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        template = env.get_template(str(self.resource_config.template_path))  # type: ignore[attr-defined]

        try:
            # FIXME: https://github.com/opsmill/infrahub/issues/1994
            return template.render(data=variables["data"])
        except jinja2.UndefinedError as exc:
            traceback = Traceback(show_locals=False)
            errors = identify_faulty_jinja_code(traceback=traceback)
            console = Console()
            with console.capture() as capture:
                console.print(f"An error occured while rendering Jinja2 transform:{self.name!r}\n", soft_wrap=True)
                console.print(f"{exc.message}\n", soft_wrap=True)
                for frame, syntax in errors:
                    console.print(f"{frame.filename} on line {frame.lineno}\n", soft_wrap=True)
                    console.print(syntax, soft_wrap=True)
            str_output = capture.get()
            if self.test.expect == InfrahubTestExpectedResult.PASS:
                raise Jinja2TransformUndefinedError(
                    name=self.name, message=str_output, rtb=traceback, errors=errors
                ) from exc
            return None

    def get_result_differences(self, computed: Any) -> Any:
        if not self.test.spec.output or computed is None:
            return None

        differences = difflib.unified_diff(
            self.test.spec.get_output_data().split("\n"),
            computed.split("\n"),
            fromfile="expected",
            tofile="rendered",
            lineterm="",
        )
        return "\n".join(differences)

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, HTTPStatusError):
            try:
                response_content = json.dumps(excinfo.value.response.json(), indent=4, sort_keys=True)
            except json.JSONDecodeError:
                response_content = excinfo.value.response.text
            return "\n".join(
                [
                    f"Failed {excinfo.value.request.method} on {excinfo.value.request.url}",
                    f"Status code: {excinfo.value.response.status_code}",
                    f"Response: {response_content}",
                ]
            )

        if isinstance(excinfo.value, jinja2.TemplateSyntaxError):
            return "\n".join(["Syntax error detected in the template", excinfo.value.message or ""])

        if isinstance(excinfo.value, OutputMatchException):
            return "\n".join([excinfo.value.message, excinfo.value.differences])

        return super().repr_failure(excinfo, style=style)


class InfrahubJinja2TransformUnitRenderItem(InfrahubJinja2Item):
    def runtest(self) -> None:
        expected_output = self.render_jinja2_template(self.test.spec.get_input_data())
        differences = self.get_result_differences(expected_output)

        if expected_output is not None and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchException(name=self.name, differences=differences)

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, (Jinja2TransformUndefinedError, Jinja2TransformException)):
            return excinfo.value.message

        return super().repr_failure(excinfo, style=style)


class InfrahubJinja2TransformIntegrationItem(InfrahubJinja2Item):
    def runtest(self) -> None:
        graphql_result = self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.test.spec.query,  # type: ignore[union-attr]
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
            branch_name=self.session.config.option.infrahub_branch,  # type: ignore[attr-defined]
            rebase=self.test.spec.rebase,  # type: ignore[union-attr]
        )
        expected_output = self.render_jinja2_template(graphql_result)
        differences = self.get_result_differences(expected_output)

        if expected_output is not None and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchException(name=self.name, differences=differences)
