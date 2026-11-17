from dataclasses import dataclass
from pathlib import Path

import pytest

from infrahub.core.schema.definitions.core import core_models_mixed
from tests.constants import DOCUMENTATION_ROOT


@dataclass
class DocumentationLinkTestCase:
    name: str
    documentation: str


# Links to an external site have no page under the docs folder, so another check has to verify them.
DOCUMENTATION_LINK_TEST_CASES: list[DocumentationLinkTestCase] = [
    DocumentationLinkTestCase(name=schema.kind, documentation=schema.documentation)
    for schema in [*core_models_mixed["generics"], *core_models_mixed["nodes"]]
    if schema.documentation and not schema.documentation.startswith("http")
]


def _candidate_pages(documentation: str) -> list[Path]:
    route = documentation.strip("/")
    return [
        DOCUMENTATION_ROOT / f"{route}.mdx",
        DOCUMENTATION_ROOT / f"{route}.md",
        DOCUMENTATION_ROOT / route / "index.mdx",
        DOCUMENTATION_ROOT / route / "index.md",
    ]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in DOCUMENTATION_LINK_TEST_CASES],
)
def test_documentation_link_matches_docs_page(test_case: DocumentationLinkTestCase) -> None:
    """The web interface opens this link from the object's help menu.

    It must point to a page in the docs folder and end with a slash, because the redirect that adds the slash
    fails when Infrahub runs behind a reverse proxy.
    """
    assert test_case.documentation.endswith("/"), (
        f"{test_case.name} links to {test_case.documentation!r}, which must end with a trailing slash"
    )
    candidates = _candidate_pages(test_case.documentation)
    assert any(candidate.is_file() for candidate in candidates), (
        f"{test_case.name} links to {test_case.documentation!r}, but none of these files exist: "
        f"{[str(candidate.relative_to(DOCUMENTATION_ROOT)) for candidate in candidates]}"
    )


def test_core_models_define_documentation_links() -> None:
    """Without core schemas that define a documentation link, the per-kind test collects no cases and checks nothing."""
    assert len(DOCUMENTATION_LINK_TEST_CASES) > 1
