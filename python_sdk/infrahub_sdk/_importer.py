from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING, Optional

from infrahub_sdk.exceptions import ModuleImportError

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def import_module(
    module_path: Path, import_root: Optional[str] = None, relative_path: Optional[str] = None
) -> ModuleType:
    import_root = import_root or str(module_path.parent)

    if import_root not in sys.path:
        sys.path.append(import_root)

    module_name = module_path.stem

    if relative_path:
        module_name = relative_path.replace("/", ".") + f".{module_name}"

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleImportError(message=f"{str(exc)} ({module_path})") from exc
    except SyntaxError as exc:
        raise ModuleImportError(message=str(exc)) from exc

    return module
