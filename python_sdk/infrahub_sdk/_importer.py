from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING, Optional

from infrahub_sdk.exceptions import ModuleImportError

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def import_module(
    module_path: Path, import_root: Optional[str] = None, relative_path: Optional[str] = None
) -> ModuleType:
    import_root = import_root or os.path.dirname(module_path)

    if import_root not in sys.path:
        sys.path.append(import_root)

    filename = os.path.basename(module_path)
    module_name = os.path.splitext(filename)[0]

    if relative_path:
        module_name = relative_path.replace("/", ".") + f".{module_name}"

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleImportError(message=f"Unable to import the specified module in {module_path}") from exc

    return module
