from deepdiff import DeepDiff


async def test_check_data_attribute(session, client, client_headers, data_conflict_attribute):
    p1 = data_conflict_attribute["p1"]
    r1 = data_conflict_attribute["r1"]

    with client:
        response = client.get(
            "/api/check/data?branch=branch2",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()

    expected_response = [
        {
            "check_type": "data-integrity",
            "message": None,
            "paths": [f"data/{p1}/height/value"],
            "status": "error",
        },
        {
            "check_type": "data-integrity",
            "message": None,
            "paths": [f"data/{r1}/commit/value"],
            "status": "error",
        },
    ]

    assert DeepDiff(expected_response, data, ignore_order=True).to_dict() == {}
