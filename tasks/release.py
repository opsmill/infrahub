"""Release related Invoke Tasks.
"""

from invoke import Context, task


from .utils import ESCAPED_REPO_PATH, check_if_command_available


@task
def markdownlint(context: Context):
    has_markdownlint = check_if_command_available(
        context=context, command_name="markdownlint-cli2"
    )

    if not has_markdownlint:
        print("Warning, markdownlint-cli2 is not installed")
        return
    exec_cmd = "markdownlint-cli2 'changelog/*.md' '!changelog/towncrier_template.md' 'CHANGELOG.md' 'docs/docs/release-notes/infrahub/*.{md,mdx}'"
    print(" - [release] Lint release files with markdownlint-cli2")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def vale(context: Context):
    """Run vale to validate the release notes."""
    has_vale = check_if_command_available(context=context, command_name="vale")

    if not has_vale:
        print("Warning, Vale is not installed")
        return

    exec_cmd = "vale $(find ./changelog ./docs/docs/release-notes/infrahub -type f \\( -name '*.mdx' -o -name '*.md' \\)) CHANGELOG.md"
    print(" - [release] Lint release files with vale")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context):
    """This will run all linter."""
    markdownlint(context)
    vale(context)
