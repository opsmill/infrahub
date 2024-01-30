from infrahub.core.branch.branch import Branch


async def test_openapi(
    client,
    default_branch: Branch,
):
    """Validate that the OpenAPI specs can be generated."""
    with client:
        response = client.get(
            "/api/openapi.json",
        )

    assert response.status_code == 200
    assert response.json() is not None
