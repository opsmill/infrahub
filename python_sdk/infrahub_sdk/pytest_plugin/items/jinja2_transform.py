from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Optional

import jinja2
from rich.console import Console
from rich.traceback import Traceback

from ..exceptions import Jinja2TransformException, Jinja2TransformUndefinedError
from ..models import InfrahubTestExpectedResult
from ..utils import identify_faulty_jinja_code
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo


class InfrahubJinja2TransformUnitRenderItem(InfrahubItem):
    def runtest(self) -> None:
        # Search for template based on jinja2 transform config, then repo directory
        template_loader = jinja2.FileSystemLoader(self.session.infrahub_config_path.parent)  # type: ignore[attr-defined]
        template_env = jinja2.Environment(loader=template_loader, trim_blocks=True, lstrip_blocks=True)
        template = template_env.get_template(str(self.resource_config.template_path))  # type: ignore[attr-defined]

        input_data = self.test.spec.get_input_data()
        expected_output = self.test.spec.get_output_data()

        try:
            rendered_output = template.render(data=input_data["data"])
        except jinja2.UndefinedError as exc:
            traceback = Traceback(show_locals=False)
            errors = identify_faulty_jinja_code(traceback=traceback)
            console = Console()
            with console.capture() as capture:
                console.print(
                    f"An error occured while rendering the jinja template, Jinja2Transform:{self.name!r}\n",
                    soft_wrap=True,
                )
                console.print(f"{exc.message}\n", soft_wrap=True)
                for frame, syntax in errors:
                    console.print(f"{frame.filename} on line {frame.lineno}\n", soft_wrap=True)
                    console.print(syntax, soft_wrap=True)
            str_output = capture.get()
            if self.test.expect == InfrahubTestExpectedResult.PASS:
                raise Jinja2TransformUndefinedError(
                    name=self.name, message=str_output, rtb=traceback, errors=errors
                ) from exc
            return

        if self.test.spec.output and expected_output != rendered_output:
            if self.test.expect == InfrahubTestExpectedResult.PASS:
                # Provide a line by line sequence for unified diff to run
                differences = difflib.unified_diff(expected_output.split("\n"), rendered_output.split("\n"))
                # Join the diff back into one string
                diff_string = "\n".join(differences)
                raise Jinja2TransformException(name=self.name, message=f"Outputs don't match.\n{diff_string}")

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        """Called when self.runtest() raises an exception."""

        if isinstance(excinfo.value, jinja2.TemplateSyntaxError):
            return "\n".join(["[red]Syntax Error detected on the template", f"  [yellow]  {excinfo}"])

        if isinstance(excinfo.value, (Jinja2TransformUndefinedError, Jinja2TransformException)):
            return excinfo.value.message

        return super().repr_failure(excinfo, style=style)
