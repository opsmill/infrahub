async def test_get_invalid(
    client,
):
    with client:
        response = client.get(
            "/api/so-such-route",
        )

    assert response.status_code == 404
    assert response.json()
    assert response.json()["errors"]
    assert response.json()["errors"] == [
        {"message": "The requested endpoint /api/so-such-route does not exist", "extensions": {"code": 404}}
    ]
