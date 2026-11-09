"""The Prefect test server report, against the real ephemeral server."""

import io

from prefect.client.orchestration import PrefectClient

from tests.helpers.prefect_diagnostics import dump_prefect_test_server_diagnostics


async def test_the_server_answers_a_stack_dump_request_and_survives_it(prefect_client: PrefectClient) -> None:
    out = io.StringIO()

    dump_prefect_test_server_diagnostics("probing the server", stream=out)

    reported = out.getvalue()
    assert "probing the server" in reported
    assert "Current thread" in reported
    assert "uvicorn" in reported

    # A server killed by the signal that asked it what it was doing would take every later test
    # with it.
    assert (await prefect_client.api_healthcheck()) is None
