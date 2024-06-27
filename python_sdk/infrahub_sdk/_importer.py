from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import ModuleImportError

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def import_module(module_path: Path, import_root: str | None = None, relative_path: str | None = None) -> ModuleType:
    import_root = import_root or str(module_path.parent)

    if import_root not in sys.path:
        sys.path.append(import_root)

    module_name = module_path.stem

    if relative_path:
        module_name = relative_path.replace("/", ".") + f".{module_name}"

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleImportError(message=f"Unable to import the specified module in {module_path}") from exc

    return module
