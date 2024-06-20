from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any, Optional

import jinja2
import ujson
from httpx import HTTPStatusError
from rich.console import Console
from rich.traceback import Traceback

from ...jinja2 import identify_faulty_jinja_code
from ..exceptions import Jinja2TransformError, Jinja2TransformUndefinedError, OutputMatchError
from ..models import InfrahubInputOutputTest, InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import ExceptionInfo


class InfrahubJinja2Item(InfrahubItem):
    def get_jinja2_environment(self) -> jinja2.Environment:
        loader = jinja2.FileSystemLoader(self.session.infrahub_config_path.parent)  # type: ignore[attr-defined]
        return jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)

    def get_jinja2_template(self) -> jinja2.Template:
        return self.get_jinja2_environment().get_template(str(self.resource_config.template_path))  # type: ignore[attr-defined]

    def render_jinja2_template(self, variables: dict[str, Any]) -> Optional[str]:
        try:
            return self.get_jinja2_template().render(**variables)
        except jinja2.UndefinedError as exc:
            traceback = Traceback(show_locals=False)
            errors = identify_faulty_jinja_code(traceback=traceback)
            console = Console()
            with console.capture() as capture:
                console.print(f"An error occurred while rendering Jinja2 transform:{self.name!r}\n", soft_wrap=True)
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

    def get_result_differences(self, computed: Any) -> Optional[str]:
        if not isinstance(self.test.spec, InfrahubInputOutputTest) or not self.test.spec.output or computed is None:
            return None

        differences = difflib.unified_diff(
            self.test.spec.get_output_data().splitlines(),
            computed.splitlines(),
            fromfile="expected",
            tofile="rendered",
            lineterm="",
        )
        return "\n".join(differences)

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, HTTPStatusError):
            try:
                response_content = ujson.dumps(excinfo.value.response.json(), indent=4, sort_keys=True)
            except ujson.JSONDecodeError:
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

        if isinstance(excinfo.value, OutputMatchError):
            return "\n".join([excinfo.value.message, excinfo.value.differences])

        return super().repr_failure(excinfo, style=style)


class InfrahubJinja2TransformSmokeItem(InfrahubJinja2Item):
    def runtest(self) -> None:
        file_path: Path = self.session.infrahub_config_path.parent / self.resource_config.template_path  # type: ignore[attr-defined]
        self.get_jinja2_environment().parse(file_path.read_text(), filename=file_path.name)


class InfrahubJinja2TransformUnitRenderItem(InfrahubJinja2Item):
    def runtest(self) -> None:
        computed = self.render_jinja2_template(self.test.spec.get_input_data())  # type: ignore[union-attr]
        differences = self.get_result_differences(computed)

        if computed is not None and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchError(name=self.name, differences=differences)

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, (Jinja2TransformUndefinedError, Jinja2TransformError)):
            return excinfo.value.message

        return super().repr_failure(excinfo, style=style)


class InfrahubJinja2TransformIntegrationItem(InfrahubJinja2Item):
    def runtest(self) -> None:
        graphql_result = self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.resource_config.query,  # type: ignore[attr-defined]
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
        )
        computed = self.render_jinja2_template(graphql_result)
        differences = self.get_result_differences(computed)

        if computed is not None and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchError(name=self.name, differences=differences)
