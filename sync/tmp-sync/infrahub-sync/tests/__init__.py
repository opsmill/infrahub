import builtins

from rich import print as rprint

builtins.rprint = rprint  # type: ignore
