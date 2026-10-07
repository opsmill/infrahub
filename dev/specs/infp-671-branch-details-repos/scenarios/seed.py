# noqa: INP001
"""Seed a local Infrahub with branches, Git repositories and tasks for the branch details page.

Usage:
    uv run --no-project seed.py up [--with-unreachable] [--many-branches [N]]
    uv run --no-project seed.py status
    uv run --no-project seed.py down

Everything this script creates is named `scn-*`. Standard library only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess  # noqa: S404
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
ADDRESS = os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000").rstrip("/")
USERNAME = os.environ.get("INFRAHUB_USERNAME", "admin")
PASSWORD = os.environ.get("INFRAHUB_PASSWORD", "infrahub")
STATE = Path(os.environ.get("SCN_STATE_DIR", Path.home() / ".cache" / "scn-infp-671"))
BARE = STATE / "git"
WORK = STATE / "work"
DAEMON_PID = STATE / "git-daemon.pid"
HTTP_PID = {"serve": STATE / "githttp-serve.pid", "deny": STATE / "githttp-deny.pid"}
# How the task workers reach this machine.
GIT_HOST = os.environ.get("SCN_GIT_HOST", "host.docker.internal")
# The fixture servers have no auth and accept pushes, so every one of them binds to loopback.
GIT_BIND = os.environ.setdefault("SCN_GIT_BIND", "127.0.0.1")
CRED_PORT = int(os.environ.get("SCN_CRED_PORT", "9419"))  # answers 401 once seeded
CONN_PORT = int(os.environ.get("SCN_CONN_PORT", "9420"))  # nothing listens once seeded
TIMEOUT = int(os.environ.get("SCN_TIMEOUT", "420"))
HTTP_UNAUTHORIZED = 401

SMALL_REPOS = [f"scn-repo-{i:02d}" for i in range(1, 12)]
RW_REPOS = ["scn-fixtures", *SMALL_REPOS]
RO_REPO = "scn-readonly"
HIDDEN_REPO = "scn-repo-04"  # --with-unreachable: import error on scn-many-errors AND unreachable
# Read-write, because the periodic sync (which records operational_status) skips read-only repositories.
UNREACHABLE = {
    # name: (port, expected operational_status)
    "scn-unreachable": (CONN_PORT, "error-connection"),
    "scn-badcreds": (CRED_PORT, "error-cred"),
}

# Infrahub branch -> (sync_with_git, description, {repo: overlay dir under fixtures/})
BRANCHES: dict[str, tuple[bool, str, dict[str, str]]] = {
    "scn-all-clear": (True, "Every repository in sync", {}),
    "scn-import-error": (True, "One repository fails to import", {"scn-fixtures": "broken"}),
    "scn-many-errors": (
        True,
        "Five repositories fail to import (3 bands + Show all)",
        dict.fromkeys(["scn-fixtures", "scn-repo-01", "scn-repo-02", "scn-repo-03", "scn-repo-04"], "broken"),
    ),
    "scn-generator-failed": (True, "Generator runs, one definition fails", {"scn-fixtures": "generators"}),
    "scn-many-tasks": (True, "More than 10 tasks on the branch", {}),
    "scn-no-git": (False, "Sync with Git off", {}),
}
# --many-branches: small branches that page the repository page's branch list for scn-fixtures.
EXTRA_PREFIX = "scn-b-"
EXTRA_DEFAULT = 11
# By index % 4: 1 and 3 stay on main's commit, 2 gets its own commit, 0 fails to import.
EXTRA_OVERLAYS = {2: "change", 0: "broken"}
EXTRA_DESCRIPTIONS = {None: "in sync, main's commit", "change": "in sync, own commit", "broken": "import error"}


def extra_branches(count: int) -> dict[str, tuple[bool, str, dict[str, str]]]:
    extras: dict[str, tuple[bool, str, dict[str, str]]] = {}
    for i in range(1, count + 1):
        overlay = EXTRA_OVERLAYS.get(i % 4)
        description = f"Branch list filler, scn-fixtures {EXTRA_DESCRIPTIONS[overlay]}"
        extras[f"{EXTRA_PREFIX}{i:02d}"] = (True, description, {"scn-fixtures": overlay} if overlay else {})
    return extras


def expected_sync(branches: dict[str, tuple[bool, str, dict[str, str]]]) -> dict[str, dict[str, str]]:
    return {
        branch: {repo: ("error-import" if overlays.get(repo) == "broken" else "in-sync") for repo in RW_REPOS}
        for branch, (sync, _, overlays) in branches.items()
        if sync
    }


NO_REIMPORT = {("scn-many-errors", "scn-repo-02")}  # its band says the error details couldn't be found
VALIDATE_RUNS = 12  # scn-many-tasks: enough tasks for a second page
SETTLED_STATES = {"COMPLETED", "FAILED", "CANCELLED", "CRASHED"}


def log(msg: str) -> None:
    print(f"[scn] {msg}", flush=True)


# --------------------------------------------------------------------------- API


class Api:
    def __init__(self) -> None:
        self.token = self._login()

    @staticmethod
    def _request(path: str, payload: dict, token: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(ADDRESS + path, data=json.dumps(payload).encode(), headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            return json.load(resp)

    def _login(self) -> str:
        return self._request("/api/auth/login", {"username": USERNAME, "password": PASSWORD})["access_token"]

    def gql(self, query: str, variables: dict | None = None, branch: str | None = None, check: bool = True) -> dict:
        path = "/graphql" + (f"/{branch}" if branch else "")
        payload = {"query": query, "variables": variables or {}}
        try:
            result = self._request(path, payload, self.token)
        except urllib.error.HTTPError as exc:
            if exc.code != HTTP_UNAUTHORIZED:
                raise
            self.token = self._login()
            result = self._request(path, payload, self.token)
        if check and result.get("errors"):
            raise RuntimeError(json.dumps(result["errors"], indent=2))
        return result

    # ---- reads

    def branches(self) -> dict[str, dict]:
        data = self.gql("{ Branch { id name sync_with_git is_default } }")["data"]["Branch"]
        return {b["name"]: b for b in data}

    def repos(self, branch: str | None = None) -> dict[str, dict]:
        query = """
        { CoreGenericRepository(limit: 500) { edges { node {
            id __typename name { value } location { value } commit { value }
            sync_status { value } operational_status { value } } } } }
        """
        edges = self.gql(query, branch=branch)["data"]["CoreGenericRepository"]["edges"]
        return {e["node"]["name"]["value"]: e["node"] for e in edges if e["node"]["name"]["value"].startswith("scn-")}

    def tasks(self, branch: str, limit: int = 200) -> list[dict]:
        query = """
        query($branch: String!, $limit: Int!) {
          InfrahubTask(branch: $branch, limit: $limit) {
            count edges { node { id title state workflow updated_at } } } }
        """
        return [e["node"] for e in self.gql(query, {"branch": branch, "limit": limit})["data"]["InfrahubTask"]["edges"]]


# --------------------------------------------------------------------------- git fixtures


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "scn", "GIT_AUTHOR_EMAIL": "scn@example.invalid"}
    env |= {"GIT_COMMITTER_NAME": "scn", "GIT_COMMITTER_EMAIL": "scn@example.invalid"}
    proc = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False)  # noqa: S603, S607
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def render_tree(src: Path, dest: Path, repo: str) -> None:
    """Copy a fixture directory into a work tree, substituting {{repo}} in every file."""
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        target = dest / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(path.read_text().replace("{{repo}}", repo))


def commit_all(work: Path, message: str) -> bool:
    git("add", "-A", cwd=work)
    if not git("status", "--porcelain", cwd=work):
        return False
    git("commit", "-q", "-m", message, cwd=work)
    return True


def bare_path(repo: str) -> Path:
    return BARE / f"{repo}.git"


def ensure_bare_repo(repo: str) -> None:
    bare = bare_path(repo)
    if bare.exists():
        return
    hidden = bare.with_suffix(".git.hidden")
    if hidden.exists():
        hidden.rename(bare)
        return
    git("init", "-q", "--bare", "-b", "main", str(bare))
    git("config", "http.receivepack", "true", cwd=bare)
    work = WORK / repo
    shutil.rmtree(work, ignore_errors=True)
    git("clone", "-q", str(bare), str(work))
    git("checkout", "-q", "-b", "main", cwd=work)
    render_tree(FIXTURES / "base", work, repo)
    commit_all(work, f"{repo}: initial commit")
    git("push", "-q", "origin", "main", cwd=work)
    log(f"created fixture repository {bare}")


def remote_has_branch(repo: str, branch: str) -> bool:
    return bool(git("ls-remote", str(bare_path(repo)), f"refs/heads/{branch}"))


def push_overlay(repo: str, branch: str, overlay: str) -> None:
    work = WORK / repo
    if not work.exists():
        git("clone", "-q", str(bare_path(repo)), str(work))
    git("fetch", "-q", "origin", cwd=work)
    git("checkout", "-q", "-B", branch, f"origin/{branch}", cwd=work)
    render_tree(FIXTURES / overlay, work, repo)
    if commit_all(work, f"{repo}: {overlay} on {branch}"):
        git("push", "-q", "origin", f"{branch}:{branch}", cwd=work)
        log(f"pushed '{overlay}' to {repo}@{branch}")


# --------------------------------------------------------------------------- local servers


def read_pids(pid_file: Path) -> list[int]:
    """Pids in the file, which holds one per server, space-separated."""
    if not pid_file.exists():
        return []
    try:
        return [int(pid) for pid in pid_file.read_text(encoding="utf-8").split()]
    except ValueError:
        return []


def pid_alive(pid_file: Path) -> bool:
    pids = read_pids(pid_file)
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
    return True


def stop_pid(pid_file: Path, name: str) -> None:
    stopped = False
    for pid in read_pids(pid_file):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)
            stopped = True
    if stopped:
        log(f"stopped {name}")
    pid_file.unlink(missing_ok=True)


def start_git_daemon() -> None:
    if pid_alive(DAEMON_PID):
        return
    git(
        "daemon", "--export-all", "--enable=receive-pack", "--reuseaddr", "--detach", f"--listen={GIT_BIND}",
        f"--pid-file={DAEMON_PID}", f"--base-path={BARE}", str(BARE),
    )  # fmt: skip
    time.sleep(1)
    log(f"git daemon serving {BARE} on git://{GIT_HOST}:9418/")


def start_http(mode: Literal["serve", "deny"], ports: list[int]) -> None:
    """Start an HTTP git server on each port; `serve` serves BARE over smart HTTP, `deny` answers 401."""
    if pid_alive(HTTP_PID[mode]):
        return
    stop_http(mode)  # a partly dead set still holds some of the ports
    pids = []
    for port in ports:
        proc = subprocess.Popen(  # noqa: S603
            [sys.executable, str(HERE / "githttp.py"), str(port), str(BARE), mode],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )  # fmt: skip
        pids.append(str(proc.pid))
    HTTP_PID[mode].write_text(" ".join(pids))
    time.sleep(1)
    log(f"HTTP git server ({mode}) on port(s) {ports}")


def stop_http(mode: Literal["serve", "deny"]) -> None:
    stop_pid(HTTP_PID[mode], f"HTTP git server ({mode})")


# --------------------------------------------------------------------------- waits


def wait_for(
    what: str, predicate: Callable[[], tuple[bool, object]], timeout: int = TIMEOUT, interval: float = 5
) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        done, detail = predicate()
        if done:
            log(f"ok: {what}")
            return True
        if time.monotonic() > deadline:
            log(f"TIMEOUT waiting for {what}: {detail}")
            return False
        time.sleep(interval)


def wait_tasks_settled(api: Api, branch: str, timeout: int = TIMEOUT) -> bool:
    def check() -> tuple[bool, object]:
        pending = [t["title"] for t in api.tasks(branch) if t["state"] not in SETTLED_STATES]
        return not pending, pending

    return wait_for(f"tasks settled on {branch}", check, timeout)


# --------------------------------------------------------------------------- up


def create_rw_repo(api: Api, repo: str, location: str) -> None:
    api.gql(
        "mutation($name: String!, $loc: String!) { CoreRepositoryCreate(data: {"
        ' name: {value: $name}, location: {value: $loc}, default_branch: {value: "main"},'
        ' description: {value: "infp-671 scenario fixture"} }) { ok } }',
        {"name": repo, "loc": location},
    )
    log(f"created CoreRepository {repo} -> {location}")


def create_repos(api: Api) -> None:
    existing = api.repos()
    for repo in RW_REPOS:
        if repo not in existing:
            create_rw_repo(api, repo, f"git://{GIT_HOST}/{repo}.git")
    if RO_REPO not in existing:
        api.gql(
            "mutation($name: String!, $loc: String!) { CoreReadOnlyRepositoryCreate(data: {"
            ' name: {value: $name}, location: {value: $loc}, ref: {value: "main"},'
            ' description: {value: "infp-671 scenario fixture"} }) { ok } }',
            {"name": RO_REPO, "loc": f"git://{GIT_HOST}/{RO_REPO}.git"},
        )
        log(f"created CoreReadOnlyRepository {RO_REPO}")


def add_unreachable(api: Api) -> bool:
    """Create the unreachable repositories, then take their remotes away.

    Infrahub refuses a remote it can't clone, so they are created while reachable. Then one port
    stops serving and the other answers 401.
    """
    missing = [name for name in UNREACHABLE if name not in api.repos()]
    if missing:
        stop_http("deny")
        start_http("serve", [CONN_PORT, CRED_PORT])
        for name in missing:
            ensure_bare_repo(name)
            create_rw_repo(api, name, f"http://{GIT_HOST}:{UNREACHABLE[name][0]}/{name}.git")
        imported = wait_for(
            "unreachable fixtures imported while reachable",
            lambda: (
                all(api.repos().get(n, {}).get("sync_status", {}).get("value") == "in-sync" for n in missing),
                missing,
            ),
        )
        stop_http("serve")
        if not imported:
            log(f"FAILED: {missing} never imported while reachable, so they can't be made unreachable")
            return False
    else:
        # A run that crashed while serving leaves the remotes reachable.
        stop_http("serve")
    start_http("deny", [CRED_PORT])

    hidden = bare_path(HIDDEN_REPO)
    if hidden.exists():
        hidden.rename(hidden.with_suffix(".git.hidden"))
        log(f"stopped serving {HIDDEN_REPO}: it becomes unreachable")

    want = {name: status for name, (_, status) in UNREACHABLE.items()} | {HIDDEN_REPO: "error"}

    def check() -> tuple[bool, object]:
        repos = api.repos()
        bad = {n: repos.get(n, {}).get("operational_status", {}).get("value") for n in want}
        bad = {n: v for n, v in bad.items() if v != want[n]}
        return not bad, bad

    return wait_for("unreachable repositories report their operational_status", check)


def create_branches(api: Api, branches: dict[str, tuple[bool, str, dict[str, str]]]) -> None:
    existing = api.branches()
    for name, (sync, description, _) in branches.items():
        if name in existing:
            continue
        api.gql(
            "mutation($name: String!, $desc: String!, $sync: Boolean!) {"
            " BranchCreate(data: {name: $name, description: $desc, sync_with_git: $sync},"
            " wait_until_completion: true) { ok } }",
            {"name": name, "desc": f"infp-671 scenario: {description}", "sync": sync},
        )
        log(f"created branch {name} (sync_with_git={sync})")


def sync_mismatches(api: Api, branch: str, expected: dict[str, str]) -> dict[str, str]:
    repos = api.repos(branch)
    return {
        repo: f"{repos.get(repo, {}).get('sync_status', {}).get('value')} != {want}"
        for repo, want in expected.items()
        if repos.get(repo, {}).get("sync_status", {}).get("value") != want
        and not (repo == HIDDEN_REPO and not bare_path(repo).exists())
    }


def reimport_failed(api: Api, branch: str, overlays: dict[str, str]) -> None:
    """Run "Import current commit" for each broken repository of the branch.

    A failing periodic sync is tagged with the default branch only, so the branch page can't find
    its log. A manual import is tagged with the branch and the repository, which is what the band
    looks up. NO_REIMPORT repositories are left alone so the "details not found" band shows too.
    """
    repos = api.repos(branch)
    for repo, overlay in overlays.items():
        if overlay != "broken" or (branch, repo) in NO_REIMPORT or repo not in repos:
            continue
        repo_id = repos[repo]["id"]
        query = """
        query($branch: String!, $id: String!) { InfrahubTask(branch: $branch, related_node__ids: [$id],
          workflow: ["git-repository-import-object"], state: [FAILED], limit: 1) { count } }
        """
        if api.gql(query, {"branch": branch, "id": repo_id})["data"]["InfrahubTask"]["count"]:
            continue
        api.gql(
            "mutation($id: String!) { InfrahubRepositoryProcess(data: {id: $id}) { ok } }",
            {"id": repo_id},
            branch=branch,
        )
        log(f"ran Import current commit for {repo} on {branch}")


def run_generators(api: Api) -> None:
    branch = "scn-generator-failed"
    query = "{ CoreGeneratorDefinition { edges { node { id name { value } } } } }"
    defs = {
        e["node"]["name"]["value"]: e["node"]["id"]
        for e in api.gql(query, branch=branch)["data"]["CoreGeneratorDefinition"]["edges"]
        if e["node"]["name"]["value"].startswith("scn-")
    }
    runs = [t for t in api.tasks(branch) if t["workflow"] == "request-generator-definition-run"]
    if defs and len(runs) >= len(defs):
        log(f"generators already ran on {branch} ({len(runs)} definition runs)")
        return
    for name, def_id in sorted(defs.items()):
        api.gql(
            "mutation($id: String!) { CoreGeneratorDefinitionRun(data: {id: $id}, wait_until_completion: false) { ok } }",
            {"id": def_id},
            branch=branch,
        )
        log(f"ran generator definition {name} on {branch}")


def pad_tasks(api: Api) -> None:
    branch = "scn-many-tasks"
    validates = [t for t in api.tasks(branch) if t["workflow"] == "branch-validate"]
    for _ in range(max(0, VALIDATE_RUNS - len(validates))):
        api.gql(
            "mutation($name: String!) { BranchValidate(data: {name: $name}, wait_until_completion: false) { ok } }",
            {"name": branch},
        )
    if len(validates) < VALIDATE_RUNS:
        log(f"ran BranchValidate on {branch} x{VALIDATE_RUNS - len(validates)}")


def remove_unreachable(api: Api) -> None:
    """Converge back to a seed where every remote is reachable."""
    for name, repo in api.repos().items():
        if name in UNREACHABLE:
            api.gql("mutation($id: String!) { CoreRepositoryDelete(data: {id: $id}) { ok } }", {"id": repo["id"]})
            log(f"deleted {name}")
    stop_http("serve")
    stop_http("deny")


def remove_extra_branches(api: Api, keep: set[str]) -> None:
    """Delete the extra branches past the requested count, so the seed converges."""
    for name in sorted(api.branches()):
        if name.startswith(EXTRA_PREFIX) and name not in keep:
            api.gql(
                "mutation($name: String!) { BranchDelete(data: {name: $name}, wait_until_completion: true) { ok } }",
                {"name": name},
            )
            log(f"deleted branch {name}")


def up(with_unreachable: bool, many_branches: int) -> int:
    branches = BRANCHES | extra_branches(many_branches)
    expected = expected_sync(branches)
    api = Api()
    STATE.mkdir(parents=True, exist_ok=True)
    BARE.mkdir(parents=True, exist_ok=True)
    for repo in [*RW_REPOS, RO_REPO]:
        ensure_bare_repo(repo)  # also serves HIDDEN_REPO again
    start_git_daemon()

    create_repos(api)
    ok = wait_for(
        "scn repositories in sync on main",
        lambda: (
            not (bad := {n: r["sync_status"]["value"] for n, r in api.repos().items()
                         if n in {*RW_REPOS, RO_REPO} and r["sync_status"]["value"] != "in-sync"}),
            bad,
        ),
    )  # fmt: skip

    remove_extra_branches(api, set(branches))
    if set(branches) - set(api.branches()) and set(UNREACHABLE) & set(api.repos()):
        # Infrahub can't push a new branch to an unreachable remote, so they are re-added after the branches exist.
        log("new branches to create: removing the unreachable repositories first")
        remove_unreachable(api)
    create_branches(api, branches)

    def unpushed() -> list[tuple[str, str]]:
        return [
            (repo, b) for b, (sync, _, _) in branches.items() if sync for repo in RW_REPOS
            if bare_path(repo).exists() and not remote_has_branch(repo, b)
        ]  # fmt: skip

    # Infrahub pushes each new branch to every read-write remote in turn.
    push_timeout = TIMEOUT + 30 * max(0, len(branches) - len(BRANCHES))
    if not wait_for(
        "Infrahub pushed every scn branch to the fixture remotes",
        lambda: (not (m := unpushed()), [f"{r}@{b}" for r, b in m]),
        push_timeout,
    ):
        # A branch whose Git push task failed is never pushed again; create it from main like Infrahub would.
        for repo, b in unpushed():
            git("branch", b, "main", cwd=bare_path(repo))
            log(f"created {repo}@{b} from main (Infrahub never pushed it)")

    # One branch at a time: a single sync of a repository that picks up several updated Git branches
    # runs as one task tagged with only one of them, and the other branches lose their import task.
    for branch, want in expected.items():
        overlays = branches[branch][2]
        for repo, overlay in overlays.items():
            if bare_path(repo).exists():
                push_overlay(repo, branch, overlay)
        ok &= wait_for(f"sync_status on {branch}", lambda b=branch, w=want: (not (m := sync_mismatches(api, b, w)), m))
        reimport_failed(api, branch, overlays)

    if wait_tasks_settled(api, "scn-generator-failed"):
        run_generators(api)
    pad_tasks(api)

    if with_unreachable:
        ok &= add_unreachable(api)
    else:
        remove_unreachable(api)

    for branch in branches:
        ok &= wait_tasks_settled(api, branch)
    status(api)
    return 0 if ok else 1


# --------------------------------------------------------------------------- status / down


def status(api: Api | None = None) -> int:
    api = api or Api()
    branches = api.branches()
    print("\nRepositories (operational_status is global):")
    for name, repo in sorted(api.repos().items()):
        print(
            f"  {name:18} {repo['__typename']:24} {repo['operational_status']['value']:17} {repo['location']['value']}"
        )
    print("\nBranches:")
    for name in [*BRANCHES, *sorted(n for n in branches if n.startswith(EXTRA_PREFIX))]:
        if name not in branches:
            print(f"  {name:22} MISSING")
            continue
        repos = api.repos(name)
        states = {}
        for repo in repos.values():
            states.setdefault(repo["sync_status"]["value"], []).append(repo["name"]["value"])
        tasks = api.tasks(name)
        by_state: dict[str, int] = {}
        for task in tasks:
            by_state[task["state"]] = by_state.get(task["state"], 0) + 1
        sync = "sync" if branches[name]["sync_with_git"] else "no-sync"
        print(f"  {name:22} {sync:8} tasks={len(tasks)} {by_state}")
        for state, names in sorted(states.items()):
            shown = sorted(names) if state != "in-sync" else f"{len(names)} repos"
            print(f"      {state:13} {shown}")
    print(f"\nState dir: {STATE}  git daemon: {'up' if pid_alive(DAEMON_PID) else 'down'}")
    return 0


def down() -> int:
    api = Api()
    for name in [n for n in api.branches() if n.startswith("scn-")]:
        api.gql(
            "mutation($name: String!) { BranchDelete(data: {name: $name}, wait_until_completion: true) { ok } }",
            {"name": name},
        )
        log(f"deleted branch {name}")
    for name, repo in api.repos().items():
        mutation = (
            "CoreReadOnlyRepositoryDelete" if repo["__typename"] == "CoreReadOnlyRepository" else "CoreRepositoryDelete"
        )
        api.gql(f"mutation($id: String!) {{ {mutation}(data: {{id: $id}}) {{ ok }} }}", {"id": repo["id"]})
        log(f"deleted {repo['__typename']} {name}")
    stop_pid(DAEMON_PID, "git daemon")
    stop_http("serve")
    stop_http("deny")
    shutil.rmtree(STATE, ignore_errors=True)
    log(f"removed {STATE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    up_parser = sub.add_parser("up", help="create or complete the seed (idempotent)")
    up_parser.add_argument(
        "--with-unreachable", action="store_true",
        help="also add unreachable repositories; they are global and show on every branch",
    )  # fmt: skip
    up_parser.add_argument(
        "--many-branches", type=int, nargs="?", const=EXTRA_DEFAULT, default=0, metavar="N",
        help=f"also add N small Sync-with-Git branches {EXTRA_PREFIX}NN (default {EXTRA_DEFAULT}) so branch lists page",
    )  # fmt: skip
    sub.add_parser("status", help="print repositories, per-branch sync_status and task states")
    sub.add_parser("down", help="delete every scn- branch and repository, stop local servers")
    args = parser.parse_args()
    if args.command == "up":
        return up(args.with_unreachable, args.many_branches)
    if args.command == "status":
        return status()
    return down()


if __name__ == "__main__":
    sys.exit(main())
