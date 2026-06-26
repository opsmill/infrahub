"""Replacement for Makefile."""

from invoke import Context, task


def git_info(context: Context) -> tuple[str, str]:
    """Return the name of the current branch and hash of the current commit."""
    branch_name = context.run("git rev-parse --abbrev-ref HEAD", hide=True, pty=False)
    short_hash = context.run("git rev-parse --short HEAD", hide=True, pty=False)
    return branch_name.stdout.strip(), short_hash.stdout.strip()


@task
def build_test_package(context: Context) -> None:
    exec_cmd = "pytest -vv"
    context.run(exec_cmd, pty=True)
