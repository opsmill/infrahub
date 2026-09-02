from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.config import GitSettings

log = get_logger()

# Exit status of ``git config --unset-all`` when the key is not present in the file.
GIT_CONFIG_KEY_NOT_FOUND = 5

GIT_HTTP_SSL_CA_INFO = "http.sslCAInfo"
GIT_HTTP_SSL_VERIFY = "http.sslVerify"


async def _run_git_config_global(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "config",
        "--global",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode or 0, stderr.decode("utf-8", errors="ignore").strip()


async def set_git_global_setting(setting_name: str, *values: str) -> None:
    """Write one key in the global git configuration, logging instead of raising on failure."""
    returncode, stderr = await _run_git_config_global(setting_name, *values)
    if returncode != 0:
        log.error(f"Failed to set git {setting_name}: {stderr or 'unknown error'}")
    else:
        log.info(f"Git {setting_name} set")


async def unset_git_global_setting(setting_name: str) -> None:
    """Remove one key from the global git configuration; a key that is already absent is not an error."""
    returncode, stderr = await _run_git_config_global("--unset-all", setting_name)
    if returncode not in (0, GIT_CONFIG_KEY_NOT_FOUND):
        log.error(f"Failed to unset git {setting_name}: {stderr or 'unknown error'}")


async def apply_git_tls_config(settings: GitSettings) -> None:
    """Point git at the configured CA bundle, or clear the TLS keys when nothing is configured.

    Git reads ``http.sslCAInfo`` and ``http.sslVerify`` from the global configuration on every HTTPS clone,
    fetch and push, so writing them once at startup covers every repository without touching the git
    command paths. Keys that are no longer configured are removed, so a value written by an earlier run
    cannot outlive its setting when the global gitconfig file is persisted between runs.
    """
    if settings.tls_ca_file:
        await set_git_global_setting(GIT_HTTP_SSL_CA_INFO, settings.tls_ca_file)
    else:
        await unset_git_global_setting(GIT_HTTP_SSL_CA_INFO)

    if settings.tls_insecure:
        await set_git_global_setting(GIT_HTTP_SSL_VERIFY, "false")
    else:
        await unset_git_global_setting(GIT_HTTP_SSL_VERIFY)
