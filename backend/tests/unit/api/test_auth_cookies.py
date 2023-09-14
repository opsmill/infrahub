import jwt

from infrahub import config

from .test_auth import EXPIRED_ACCESS_TOKEN, EXPIRED_REFRESH_TOKEN


async def test_password_based_login(session, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"})

    assert response.status_code == 200

    # Check for cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    access_token = response.cookies["access_token"]
    decoded = jwt.decode(access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])
    assert first_account.id == decoded["sub"]


async def test_refresh_with_invalidated_token(session, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"})

    assert response.status_code == 200

    with client:
        logout_response = client.post("/api/auth/logout", cookies=response.cookies)

    assert logout_response.status_code == 200

    with client:
        refresh_response = client.post("/api/auth/refresh", cookies=response.cookies)

    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        "data": None,
        "errors": [
            {"message": "The provided refresh token has been invalidated in the database", "extensions": {"code": 401}}
        ],
    }


async def test_refresh_access_token(session, default_branch, client, first_account):
    """Validate that it's possible to refresh an access token using a refresh token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200
    refresh_token = login_response.cookies["refresh_token"]
    decoded_refresh = jwt.decode(refresh_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])

    with client:
        refresh_response = client.post("/api/auth/refresh")

    assert refresh_response.status_code == 200
    access_token = refresh_response.cookies["access_token"]
    decoded_access = jwt.decode(access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])

    assert first_account.id == decoded_access["sub"]
    assert first_account.id == decoded_refresh["sub"]
    assert decoded_access["session_id"]
    assert decoded_access["session_id"] == decoded_refresh["session_id"]


async def test_fail_to_refresh_access_token_with_access_token(session, default_branch, client, first_account):
    """Validate that it's not possible to refresh an access token using an access token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200

    client.cookies["refresh_token"] = client.cookies["access_token"]

    with client:
        refresh_response = client.post("/api/auth/refresh")

    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        "data": None,
        "errors": [{"message": "Invalid token, current token is not a refresh token", "extensions": {"code": 401}}],
    }


async def test_use_expired_token(session, default_branch, client):
    client.cookies["access_token"] = EXPIRED_ACCESS_TOKEN

    with client:
        response = client.get("/api/rfile/testing")

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Expired Signature", "extensions": {"code": 401}}]}


async def test_refresh_access_token_with_expired_refresh_token(session, default_branch, client):
    """Validate that the correct error is returned for an expired refresh token"""
    with client:
        response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {EXPIRED_REFRESH_TOKEN}"})

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Expired Signature", "extensions": {"code": 401}}]}


async def test_access_resource_using_refresh_token(session, default_branch, client, first_account):
    """It should not be possible to access a resource using a refresh token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200

    refresh_token = login_response.cookies["refresh_token"]

    with client:
        response = client.get("/api/rfile/testing", cookies={"access_token": refresh_token})

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Invalid token", "extensions": {"code": 401}}]}


async def test_generate_api_token(session, default_branch, client, create_test_admin):
    """It should not be possible to generate an API token using a JWT token"""
    with client:
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "test-admin",
                "password": config.SETTINGS.security.initial_admin_password,
            },
        )

    assert login_response.status_code == 200
    access_token = login_response.cookies["access_token"]

    token_mutation = """
    mutation CoreAccountTokenCreate {
        CoreAccountTokenCreate(data: { name: "my-first-token" }) {
            ok
            object {
            token {
                value
            }
            }
        }
    }
    """
    with client:
        jwt_response = client.post(
            "/graphql",
            json={"query": token_mutation},
            cookies={"access_token": access_token},
        )

    assert jwt_response.status_code == 200
    api_token = jwt_response.json()["data"]["CoreAccountTokenCreate"]["object"]["token"]["value"]

    # Validate that the generated API token can't be used to generate another API token
    with client:
        api_response = client.post(
            "/graphql",
            json={"query": token_mutation},
            headers={"X-INFRAHUB-KEY": api_token},
        )

    assert api_response.status_code == 200
    assert not api_response.json()["data"]["CoreAccountTokenCreate"]
    assert api_response.json()["errors"][0]["message"] == api_response.json()["errors"][0]["message"]
