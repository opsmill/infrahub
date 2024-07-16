import linecache

from rich.syntax import Syntax
from rich.traceback import Frame, Traceback


def identify_faulty_jinja_code(traceback: Traceback, nbr_context_lines: int = 3) -> list[tuple[Frame, Syntax]]:
    """This function identifies the faulty Jinja2 code and beautify it to provide meaningful information to the user.

    We use the rich's Traceback to parse the complete stack trace and extract Frames for each expection found in the trace.
    """
    response = []

    # Extract only the Jinja related exception
    for frame in [frame for frame in traceback.trace.stacks[0].frames if frame.filename.endswith(".j2")]:
        code = "".join(linecache.getlines(frame.filename))
        lexer_name = Traceback._guess_lexer(frame.filename, code)
        syntax = Syntax(
            code,
            lexer_name,
            line_numbers=True,
            line_range=(frame.lineno - nbr_context_lines, frame.lineno + nbr_context_lines),
            highlight_lines={frame.lineno},
            code_width=88,
            theme=traceback.theme,
            dedent=False,
        )
        response.append((frame, syntax))

    return response
