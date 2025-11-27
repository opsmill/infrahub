"""Infrahub load test: bulk creation and deletion of users & branches, proposed changes."""

from __future__ import annotations

import asyncio
import random
import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import logging
    from collections.abc import Iterable

    from infrahub_sdk import InfrahubClient

DEFAULT_N_USERS: int = 60
DEFAULT_PREFIX: str = "loadtest"
DEFAULT_PASSWORD: int = 16


def _rand_pwd(length: int = DEFAULT_PASSWORD) -> str:
    """Return a random alphanumeric password of *length* characters."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


async def _create_one(idx: int, client: InfrahubClient, prefix: str, log: logging.Logger) -> tuple[str, str]:
    """Create one account, branch and diff; return `(username, branch)."""
    uname = f"{prefix}_user_{idx:02d}"
    pwd = _rand_pwd()

    acc = await client.create("CoreAccount", name=uname, password=pwd, branch="main")
    await acc.save()

    branch_name = f"{prefix}/{uname}"
    await client.branch.create(branch_name=branch_name)

    tag = await client.create("BuiltinTag", name=f"{uname}-tag", branch=branch_name)
    await tag.save()

    try:
        proposed_change = await client.create(
            "CoreProposedChange",
            data={"name": f"Proposed change for {uname}", "source_branch": branch_name, "destination_branch": "main"},
        )
        await proposed_change.save()
        log.info(f"✅ Created proposed change for branch {branch_name}")
    except Exception as e:
        log.error(f"❌ Error creating proposed change for branch {branch_name}: {e}")

    log.info(f"✅ User {uname} created with branch {branch_name}")
    return uname, branch_name


async def setup(client: InfrahubClient, log: logging.Logger, *, n_users: int, prefix: str) -> None:
    """Create *n_users* users + branches in parallel."""
    tasks = [_create_one(i, client, prefix, log) for i in range(1, n_users + 1)]
    await asyncio.gather(*tasks, return_exceptions=False)


def _generate_usernames(n_users: int, prefix: str) -> list[str]:
    """Return the expected usernames produced during setup."""
    return [f"{prefix}_user_{i:02d}" for i in range(1, n_users + 1)]


async def _delete_branches(client: InfrahubClient, prefix: str, usernames: Iterable[str], log: logging.Logger) -> None:
    """Delete branches `<prefix>/<username> one by one."""
    try:
        all_branches = await client.branch.all()
    except Exception as e:
        log.error(f"Error retrieving branches: {e}")

    for uname in usernames:
        br = f"{prefix}/{uname}"
        log.info(f"Attempting to delete branch {br}")
        try:
            branch_exists = br in all_branches
            log.info(f"Branch {br} exists: {branch_exists}")

            if branch_exists:
                await client.branch.delete(br)
                log.info(f"🗑️ Branch {br} deleted")
            else:
                log.warning(f"Branch {br} not found")
        except Exception as exc:
            log.error(f"Error deleting branch {br}: {exc}")


async def _delete_users(client: InfrahubClient, usernames: Iterable[str], log: logging.Logger) -> None:
    """Delete CoreAccounts listed in *usernames*."""
    for uname in usernames:
        log.info(f"Trying to remove user {uname}")
        try:
            all_users = await client.all("CoreAccount", branch="main")
            for user in all_users:
                user_name = None
                if hasattr(user, "name"):
                    if hasattr(user.name, "value"):
                        user_name = user.name.value
                    else:
                        user_name = str(user.name)

                if user_name == uname:
                    log.info(f"Found! Removing {uname}")
                    try:
                        await user.delete()
                        log.info(f"🗑️ User {uname} Deleted")
                        break
                    except Exception as e:
                        log.error(f"Error while deleting: {str(e)}")
            else:
                log.warning(f"User {uname} not found in the list")

        except Exception as exc:
            log.error(f"❌ General: {exc}")


async def cleanup(client: InfrahubClient, log: logging.Logger, *, prefix: str, n_users: int) -> None:
    """Remove test branches **and** test accounts."""
    usernames = _generate_usernames(n_users, prefix)
    await _delete_branches(client, prefix, usernames, log)
    await _delete_users(client, usernames, log)


async def create_admin_branches(client: InfrahubClient, log: logging.Logger, *, n_branches: int, prefix: str) -> None:
    """Create multiple branches for the admin user without creating new users."""
    log.info(f"Creating {n_branches} branches for admin user with prefix {prefix}")

    for i in range(1, n_branches + 1):
        branch_name = f"{prefix}/admin_branch_{i:02d}"
        try:
            log.info(f"Creating branch {branch_name}")
            await client.branch.create(branch_name=branch_name)

            tag = await client.create("BuiltinTag", name=f"admin-tag-{i:02d}", branch=branch_name)
            await tag.save()

            log.info(f"✅ Branch created: {branch_name} with test tag")
        except Exception as exc:
            log.error(f"❌ Error creating branch {branch_name}: {exc}")


async def delete_admin_branches(client: InfrahubClient, log: logging.Logger, *, n_branches: int, prefix: str) -> None:
    """Delete branches created for the admin user."""
    log.info(f"Deleting {n_branches} admin branches with prefix {prefix}")

    try:
        all_branches = await client.branch.all()
    except Exception as e:
        log.error(f"Error retrieving branches: {e}")
        return

    for i in range(1, n_branches + 1):
        branch_name = f"{prefix}/admin_branch_{i:02d}"
        log.info(f"Attempting to delete branch {branch_name}")

        try:
            branch_exists = branch_name in all_branches
            log.info(f"Branch {branch_name} exists: {branch_exists}")

            if branch_exists:
                await client.branch.delete(branch_name)
                log.info(f"🗑️ Branch {branch_name} deleted")
            else:
                log.warning(f"Branch {branch_name} not found")
        except Exception as exc:
            log.error(f"Error deleting branch {branch_name}: {exc}")


async def run(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str = "main",  # noqa: ARG001
    mode: str = "setup",
    n_users: int | str = DEFAULT_N_USERS,
    prefix: str = DEFAULT_PREFIX,
) -> None:
    """Main entrypoint executed by **infrahubctl run**."""

    mode = str(mode).lower()
    prefix = str(prefix)
    n_users = int(n_users)

    log.info("Mode: %s | Users/Branches: %s | Prefix: %s", mode, n_users, prefix)

    if mode in {"setup", "create"}:
        await setup(client, log, n_users=n_users, prefix=prefix)
    elif mode in {"cleanup", "delete", "purge"}:
        await cleanup(client, log, prefix=prefix, n_users=n_users)
    elif mode == "admin_branches":
        await create_admin_branches(client, log, n_branches=n_users, prefix=prefix)
    elif mode == "delete_admin_branches":
        await delete_admin_branches(client, log, n_branches=n_users, prefix=prefix)
    else:
        log.error("Unknown mode: %s (expected: setup / cleanup / admin_branches / delete_admin_branches)", mode)
