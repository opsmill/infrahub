import builtins

from rich import inspect as rinspect
from rich import print as rprint

builtins.rinspect = rinspect  # type: ignore
builtins.rprint = rprint  # type: ignore
