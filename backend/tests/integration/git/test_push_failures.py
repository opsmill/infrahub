"""Push-failure scenarios for InfrahubRepository against a real Gogs server.

These tests exercise paths where the remote rejects a push for a reason other
than authentication: the local branch has diverged from the remote (non-fast-
forward), and the server rejects the push at receive time (mimicking a
protected branch via a server-side pre-receive hook because Gogs 0.13.0 has no
branch-protection API).

`InfrahubRepository.push` calls GitPython's `Remote.push` and returns `True`
without inspecting the result. GitPython does not raise on a rejected push —
it returns a `PushInfoList` whose flags reflect the failure — so today these
rejections are silent at the Python boundary. The rejection is only observable
by re-querying the remote: the upstream tip has not advanced to the local
commit. These tests pin that shape so any change to push's error-handling
path explicitly updates the expected contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git.repository import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import GOGS_ADMIN, create_gogs_repo

if TYPE_CHECKING:
    from git import Repo
    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


def _advance_remote_branch(
    container: DockerContainer, repo_name: str, branch_name: str, file_name: str, message: str
) -> str:
    """Push a new commit to the remote bare repo's branch, bypassing Infrahub.

    Returns the new tip SHA on the remote branch so callers can assert later
    that a subsequent rejected local push did not advance the upstream.
    """
    script = (
        f"set -e && "
        f"rm -rf /tmp/{repo_name}-advance && "
        f"git clone /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git /tmp/{repo_name}-advance && "
        f"cd /tmp/{repo_name}-advance && "
        f"git config user.email 'infrahub@test.local' && "
        f"git config user.name 'Infrahub Test' && "
        f"git checkout {branch_name} && "
        f"printf 'remote-only content\\n' > {file_name} && "
        f"git add {file_name} && "
        f"git commit -m {message!r} && "
        f"git push origin {branch_name} && "
        f"git rev-parse HEAD"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to advance remote branch {branch_name} on {repo_name} "
        f"(exit {result.exit_code}): {result.output.decode()}"
    )
    return result.output.decode().strip().splitlines()[-1].strip()


def _install_protected_branch_hook(container: DockerContainer, repo_name: str, branch_name: str) -> None:
    """Install a server-side pre-receive hook that rejects pushes to `branch_name`.

    Gogs 0.13.0 exposes no branch-protection API, so the closest faithful
    simulation of a protected branch is a pre-receive hook that returns
    non-zero with a "protected" message. Infrahub sees the same surface a real
    protected-branch rejection would produce: the remote refuses to advance
    its branch tip and writes a diagnostic line back to the client.
    """
    hook_path = f"/data/git/repositories/{GOGS_ADMIN}/{repo_name}.git/hooks/pre-receive"
    hook_body = (
        "#!/bin/bash\n"
        "while read oldrev newrev refname; do\n"
        f'  if [ "$refname" = "refs/heads/{branch_name}" ]; then\n'
        f'    echo "branch {branch_name} is protected" >&2\n'
        "    exit 1\n"
        "  fi\n"
        "done\n"
    )
    script = f"set -e\ncat > {hook_path} <<'HOOK'\n{hook_body}HOOK\nchmod +x {hook_path}\n"
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to install protected-branch hook on {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )


def _ls_remote_branch_sha(git_repo: Repo, branch_name: str) -> str:
    """Return the current SHA of `branch_name` on origin, queried over the wire.

    Raises:
        AssertionError: if `git ls-remote` returns no row for the branch.

    """
    output = git_repo.git.ls_remote("origin", f"refs/heads/{branch_name}")
    if not output:
        raise AssertionError(f"`git ls-remote` returned no rows for refs/heads/{branch_name}")
    return output.split()[0]


class TestPushFailures(TestInfrahubApp):
    """Push-failure paths against a real Gogs server."""

    @pytest.fixture(scope="class")
    async def non_fast_forward_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "push-non-fast-forward-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=clone_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "clone_url": clone_url}

    @pytest.fixture(scope="class")
    async def protected_branch_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "push-protected-branch-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=clone_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "clone_url": clone_url}

    async def test_push_silently_swallows_non_fast_forward_rejection(
        self,
        non_fast_forward_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """A diverged push is silently swallowed; the remote tip does not advance.

        `InfrahubRepository.push` returns `True` regardless of whether the
        remote accepted the push. GitPython's `Remote.push` does not raise on
        a non-fast-forward rejection — it returns a result object whose flags
        reflect the failure — and Infrahub does not inspect that result. The
        rejection is observable only by re-querying the remote.

        Callers that need to know whether the push actually applied must
        re-fetch the remote tip themselves. This test pins that contract.
        """
        repo_name = non_fast_forward_dataset["repo_name"]
        clone_url = non_fast_forward_dataset["clone_url"]

        infrahub_repo = await InfrahubRepository.new(
            id=non_fast_forward_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
        )

        remote_tip_after_advance = _advance_remote_branch(
            gogs_server.container,
            repo_name=repo_name,
            branch_name="main",
            file_name="remote_only.txt",
            message="Remote-only commit to force divergence",
        )

        git_repo = infrahub_repo.get_git_repo_main()
        local_file = Path(str(git_repo.working_dir)) / "local_only.txt"
        local_file.write_text("local-only content")
        git_repo.index.add(["local_only.txt"])
        local_commit_sha = git_repo.index.commit("Local-only commit that diverges from remote").hexsha

        push_result = await infrahub_repo.push("main")
        assert push_result is True

        remote_tip_after_push = _ls_remote_branch_sha(git_repo, branch_name="main")
        assert remote_tip_after_push == remote_tip_after_advance, (
            "Remote tip advanced despite non-fast-forward — push contract has changed"
        )
        assert remote_tip_after_push != local_commit_sha, (
            "Remote accepted the diverged local commit — push contract has changed"
        )

    async def test_push_silently_swallows_pre_receive_rejection(
        self,
        protected_branch_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """A server-rejected push is silently swallowed; the remote tip does not advance.

        With a pre-receive hook rejecting writes to `main`, the push attempt
        returns `True` and Infrahub does not surface the remote's
        `pre-receive hook declined` diagnostic. As with non-fast-forward, the
        only observable signal of rejection is that the upstream tip stays
        where it was. This test pins that contract.
        """
        repo_name = protected_branch_dataset["repo_name"]
        clone_url = protected_branch_dataset["clone_url"]

        infrahub_repo = await InfrahubRepository.new(
            id=protected_branch_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
        )

        git_repo = infrahub_repo.get_git_repo_main()
        remote_tip_before = _ls_remote_branch_sha(git_repo, branch_name="main")

        _install_protected_branch_hook(gogs_server.container, repo_name=repo_name, branch_name="main")

        local_file = Path(str(git_repo.working_dir)) / "protected_branch_commit.txt"
        local_file.write_text("local content for protected branch push")
        git_repo.index.add(["protected_branch_commit.txt"])
        local_commit_sha = git_repo.index.commit("Local commit to push at protected branch").hexsha

        push_result = await infrahub_repo.push("main")
        assert push_result is True

        remote_tip_after_push = _ls_remote_branch_sha(git_repo, branch_name="main")
        assert remote_tip_after_push == remote_tip_before, (
            "Remote tip advanced despite pre-receive rejection — push contract has changed"
        )
        assert remote_tip_after_push != local_commit_sha, (
            "Remote accepted the locally-committed change despite pre-receive rejection — push contract has changed"
        )
