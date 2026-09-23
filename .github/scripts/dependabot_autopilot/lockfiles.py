"""Package names a lockfile change introduces, read from the lockfile text without resolving anything."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

_PEP503_SEPARATORS = re.compile(r"[-_.]+")
_NODE_MODULES = "node_modules/"


class LockfileError(Exception):
    """A lockfile could not be parsed into a package set."""


def added_packages(*, path: str, base_text: str | None, head_text: str | None) -> tuple[str, ...]:
    """Return, sorted, the package names present at head and absent at base.

    `None` text means the lockfile does not exist at that ref. Paths that are not a `uv.lock`,
    `pnpm-lock.yaml` or `package-lock.json` return nothing.

    Raises:
        LockfileError: When either side of a recognised lockfile cannot be parsed.

    """
    parser = _PARSERS.get(PurePosixPath(path).name)
    if parser is None or head_text is None:
        return ()
    base = frozenset() if base_text is None else _package_names(parser=parser, path=path, text=base_text)
    head = _package_names(parser=parser, path=path, text=head_text)
    return tuple(sorted(head - base))


def _package_names(*, parser: Callable[[str], frozenset[str]], path: str, text: str) -> frozenset[str]:
    try:
        return parser(text)
    except (tomllib.TOMLDecodeError, yaml.YAMLError, json.JSONDecodeError, LockfileError) as exc:
        raise LockfileError(f"{path} cannot be parsed: {exc}") from exc


def _uv_names(text: str) -> frozenset[str]:
    packages = tomllib.loads(text).get("package", [])
    if not isinstance(packages, list):
        raise LockfileError("`package` is not an array of tables")
    names = [package.get("name") if isinstance(package, dict) else None for package in packages]
    if not all(isinstance(name, str) for name in names):
        raise LockfileError("a `[[package]]` entry has no string `name`")
    return frozenset(_PEP503_SEPARATORS.sub("-", str(name)).lower() for name in names)


def _pnpm_names(text: str) -> frozenset[str]:
    document = yaml.safe_load(text)
    packages = document.get("packages") if isinstance(document, dict) else None
    if packages is None:
        return frozenset()
    if not isinstance(packages, dict):
        raise LockfileError("`packages` is not a mapping")
    return frozenset(_pnpm_key_name(key=str(key)) for key in packages)


def _pnpm_key_name(*, key: str) -> str:
    specifier = key.partition("(")[0]
    version_at = specifier.rfind("@")
    return specifier[:version_at] if version_at > 0 else specifier


def _npm_names(text: str) -> frozenset[str]:
    document = json.loads(text)
    packages = document.get("packages", {}) if isinstance(document, dict) else None
    if not isinstance(packages, dict):
        raise LockfileError("`packages` is not an object")
    return frozenset(key.rpartition(_NODE_MODULES)[2] for key in packages if _NODE_MODULES in key)


_PARSERS: dict[str, Callable[[str], frozenset[str]]] = {
    "uv.lock": _uv_names,
    "pnpm-lock.yaml": _pnpm_names,
    "package-lock.json": _npm_names,
}
