from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Tuple

import jinja2
import pytest
import yaml
from rich.console import Console
from rich.traceback import Traceback

from ..exceptions import RFileException, RFileUndefinedError
from ..models import InfrahubTest, InfrahubTestExpectedResult
from ..utils import identify_faulty_jinja_code

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.schema import InfrahubRepositoryRFileConfig


class InfrahubRFileUnitRenderItem(pytest.Item):
    def __init__(
        self,
        *args: Any,
        resource_name: str,
        resource_config: InfrahubRepositoryRFileConfig,
        test: InfrahubTest,
        **kwargs: Dict[str, Any],
    ):
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

        self.resource_name: str = resource_name
        self.resource_config: InfrahubRepositoryRFileConfig = resource_config
        test.spec.update_paths(base_dir=self.fspath.dirpath())
        self.test: InfrahubTest = test

    def runtest(self) -> None:
        templateLoader = jinja2.FileSystemLoader(searchpath=".")
        templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
        template = templateEnv.get_template(str(self.resource_config.template_path))

        input_data = yaml.safe_load(self.test.spec.input.read_text())

        try:
            rendered_tpl = template.render(data=input_data["data"])
        except jinja2.UndefinedError as exc:
            traceback = Traceback(show_locals=False)
            errors = identify_faulty_jinja_code(traceback=traceback)
            console = Console()
            with console.capture() as capture:
                console.print(
                    f"An error occured while rendering the jinja template, RFile:{self.name!r}\n", soft_wrap=True
                )
                console.print(f"{exc.message}\n", soft_wrap=True)
                for frame, syntax in errors:
                    console.print(f"{frame.filename} on line {frame.lineno}\n", soft_wrap=True)
                    console.print(syntax, soft_wrap=True)
            str_output = capture.get()
            if self.test.spec.expect == InfrahubTestExpectedResult.PASS:
                raise RFileUndefinedError(name=self.name, message=str_output, rtb=traceback, errors=errors) from exc
            return

        if self.test.spec.output and rendered_tpl != self.test.spec.output.read_text():
            if self.test.expect == InfrahubTestExpectedResult.PASS:
                raise RFileException(name=self.name, message="Output don't match")

    def repr_failure(self, excinfo: pytest.ExceptionInfo, style: Optional[str] = None) -> str:
        """Called when self.runtest() raises an exception."""

        if isinstance(excinfo.value, jinja2.TemplateSyntaxError):
            return "\n".join(["[red]Syntax Error detected on the template", f"  [yellow]  {excinfo}"])

        if isinstance(excinfo.value, (RFileUndefinedError, RFileException)):
            return excinfo.value.message

        return str(excinfo.value)

    def reportinfo(self) -> Tuple[Path, Literal[0], str]:
        return self.path, 0, f"resource: {self.name}"
