from __future__ import annotations

import io
import platform
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

GITHUB_REPO = "opsmill/infrahub-git-credential-helper"
BINARIES = {"infrahub-git-credential", "infrahub-git-askpass"}


def _get_asset_suffix() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system not in {"darwin", "linux"}:
        raise SystemExit(f"Unsupported OS: {system}")

    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    if not arch:
        raise SystemExit(f"Unsupported architecture: {machine}")

    return f"{system}_{arch}"


def _get_latest_version() -> str:
    resp = httpx.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", headers={"Accept": "application/vnd.github+json"}
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(
            f"Failed to fetch latest release info: {exc.response.status_code} {exc.response.reason_phrase}"
        ) from exc
    return resp.json()["tag_name"].lstrip("v")


@task
def install(context: Context, version: str = "latest", dest: str = "/usr/local/bin") -> None:  # noqa: ARG001
    """Install the Infrahub git credential helper binaries from GitHub releases.

    Args:
        context: Invoke context.
        version: Version to install (e.g. "0.1.2") or "latest" for the most recent release.
        dest: Destination directory for the binaries.
    """
    suffix = _get_asset_suffix()

    if version == "latest":
        version = _get_latest_version()
        print(f"Latest version: {version}")

    url = f"https://github.com/{GITHUB_REPO}/releases/download/v{version}/infrahub-credential-helper_{version}_{suffix}.tar.gz"
    dest_path = Path(dest)

    print(f"Downloading infrahub-git-credential-helper v{version} ({suffix})...")
    resp = httpx.get(url, follow_redirects=True)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(
            f"Failed to download release: {exc.response.status_code} {exc.response.reason_phrase}"
        ) from exc

    try:
        with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
            for binary in BINARIES:
                member = tar.getmember(binary)
                member.name = binary
                tar.extract(member, path=dest_path, filter="data")
                (dest_path / binary).chmod(0o755)
                print(f"Installed {binary} -> {dest_path / binary}")
    except PermissionError as exc:
        raise SystemExit(
            f"Permission denied: cannot write to {dest_path}\n"
            "Try: sudo invoke credential-helper.install\n"
            " or: invoke credential-helper.install --dest ~/.local/bin"
        ) from exc
