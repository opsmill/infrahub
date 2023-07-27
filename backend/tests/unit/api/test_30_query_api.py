from infrahub.core.initialization import create_branch


async def test_query_endpoint_default_branch(session, client, client_headers, default_branch, car_person_data):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query01",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_query_endpoint_branch1(session, client, client_headers, default_branch, car_person_data):
    await create_branch(branch_name="branch1", session=session)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query01?branch=branch1",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_query_endpoint_wrong_query(
    session, client, client_headers, default_branch, car_person_schema, register_core_models_schema
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query99",
            headers=client_headers,
        )

    assert response.status_code == 404


async def test_query_endpoint_wrong_branch(
    session, client, client_headers, default_branch, car_person_schema, register_core_models_schema
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query01?branch=notvalid",
            headers=client_headers,
        )

    assert response.status_code == 400
