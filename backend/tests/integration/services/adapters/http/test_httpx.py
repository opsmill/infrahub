from prefect.client.orchestration import get_client

from infrahub.services.adapters.http.httpx import HttpxAdapter


async def test_httpx_post(prefect_test_fixture: None) -> None:
    async with get_client(sync_client=False) as client:
        # Use the Prefect API for testing as that is up and running
        # and needs to be accessible within the tests
        base_url = str(client.api_url)

    httpx = HttpxAdapter()
    get_response = await httpx.get(f"{base_url}admin/settings")
    post_response = await httpx.post(f"{base_url}events/filter", json={"limit": 1})
    assert get_response.status_code == 200
    assert "api" in get_response.json()
    assert post_response.status_code == 200
    assert "total" in post_response.json()
