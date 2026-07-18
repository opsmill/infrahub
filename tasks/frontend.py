import sys

from invoke import Context, task

from . import backend, docs
from .utils import ESCAPED_REPO_PATH

NAMESPACE = "FRONTEND"

# Canonical committed artefacts derived from the backend error catalogue. Their freshness is
# enforced in CI; regenerate all three together with `regenerate-error-bindings`.
GENERATED_ERROR_FILES = [
    "schema/error-catalogue.json",
    "frontend/app/src/shared/api/errors/catalogue.generated.ts",
    "docs/docs/reference/error-catalogue.mdx",
]


@task(name="regenerate-error-bindings")
def regenerate_error_bindings(context: Context) -> None:
    """Regenerate the error catalogue JSON, the frontend TypeScript bindings, and the docs page."""
    backend.export_error_catalogue(context)
    with context.cd(f"{ESCAPED_REPO_PATH}/frontend/app"):
        context.run("pnpm generate:error-bindings")
    docs.generate_error_catalogue(context)


@task(name="check-error-bindings")
def check_error_bindings(context: Context) -> None:
    """Fail if the committed error catalogue artefacts are out of sync with the backend catalogue."""
    regenerate_error_bindings(context)

    files = " ".join(GENERATED_ERROR_FILES)
    with context.cd(ESCAPED_REPO_PATH):
        result = context.run(f"git diff --exit-code {files}", warn=True)

    if result.exited != 0:
        print()
        print("ERROR: error catalogue bindings are out of date.")
        print()
        print("Fix:")
        print("  uv run invoke frontend.regenerate-error-bindings")
        print()
        print("Then commit the regenerated files and push again.")
        sys.exit(1)
