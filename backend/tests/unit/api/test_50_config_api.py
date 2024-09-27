from infrahub.database import InfrahubDatabase


async def test_config_endpoint(db: InfrahubDatabase, client, client_headers, default_branch):
    with client:
        response = client.get(
            "/api/config",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    config = response.json()

    assert sorted(config.keys()) == ["analytics", "experimental_features", "logging", "main", "sso"]
