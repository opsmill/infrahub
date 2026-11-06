from __future__ import annotations

from dataclasses import dataclass

import pytest
from opentelemetry.util.http import parse_excluded_urls

from infrahub.server import TRACING_EXCLUDED_URLS


@dataclass
class TracedUrlTestCase:
    name: str
    url: str
    excluded: bool


TRACED_URL_TEST_CASES: list[TracedUrlTestCase] = [
    TracedUrlTestCase(name="health_endpoint", url="http://infrahub-server:8000/api/health", excluded=True),
    TracedUrlTestCase(name="metrics_endpoint", url="http://infrahub-server:8000/metrics", excluded=True),
    TracedUrlTestCase(
        name="graphql_on_a_branch_named_api_health",
        url="http://infrahub-server:8000/graphql/api/health",
        excluded=False,
    ),
    TracedUrlTestCase(name="path_below_health", url="http://infrahub-server:8000/api/health/x", excluded=False),
    TracedUrlTestCase(name="path_sharing_the_prefix", url="http://infrahub-server:8000/api/healthz", excluded=False),
    TracedUrlTestCase(name="other_rest_endpoint", url="http://infrahub-server:8000/api/config", excluded=False),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TRACED_URL_TEST_CASES])
def test_tracing_excludes_only_the_health_and_metrics_endpoints(test_case: TracedUrlTestCase) -> None:
    assert parse_excluded_urls(TRACING_EXCLUDED_URLS).url_disabled(test_case.url) is test_case.excluded
