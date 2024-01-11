import linecache
from pathlib import Path
from typing import List, Tuple

import yaml
from rich.syntax import Syntax
from rich.traceback import Frame, Traceback

from infrahub_sdk.schema import InfrahubPythonTransformConfig, InfrahubRepositoryConfig, InfrahubRepositoryRFileConfig

from .exceptions import FileNotValidError


def load_repository_config(repo_config_file: Path) -> InfrahubRepositoryConfig:
    if not repo_config_file.is_file():
        raise FileNotFoundError(repo_config_file)

    try:
        yaml_data = repo_config_file.read_text()
        data = yaml.safe_load(yaml_data)
    except yaml.YAMLError as exc:
        raise FileNotValidError(name=str(repo_config_file)) from exc

    return InfrahubRepositoryConfig(**data)


def find_rfile_in_repository_config(
    rfile: str, repository_config: InfrahubRepositoryConfig
) -> InfrahubRepositoryRFileConfig:
    filtered = [entry for entry in repository_config.rfiles if entry.name == rfile]
    if len(filtered) == 0 or len(filtered) > 1:
        raise ValueError
    return filtered[0]


def find_python_transform_in_repository_config(
    transform: str, repository_config: InfrahubRepositoryConfig
) -> InfrahubPythonTransformConfig:
    filtered = [entry for entry in repository_config.python_transforms if entry.name == transform]
    if len(filtered) == 0 or len(filtered) > 1:
        raise ValueError
    return filtered[0]


def identify_faulty_jinja_code(traceback: Traceback, nbr_context_lines: int = 3) -> List[Tuple[Frame, Syntax]]:
    response = []

    # The Traceback from rich is very helpful to parse the entire stack trace
    # to will generate a Frame object for each exception in the trace

    # Extract only the Jinja related exceptioin from the stack
    frames = [frame for frame in traceback.trace.stacks[0].frames if frame.filename.endswith(".j2")]

    for frame in frames:
        code = "".join(linecache.getlines(frame.filename))
        lexer_name = Traceback._guess_lexer(frame.filename, code)
        syntax = Syntax(
            code,
            lexer_name,
            line_numbers=True,
            line_range=(
                frame.lineno - nbr_context_lines,
                frame.lineno + nbr_context_lines,
            ),
            highlight_lines={frame.lineno},
            code_width=88,
            theme=traceback.theme,
            dedent=False,
        )
        response.append((frame, syntax))

    return response
