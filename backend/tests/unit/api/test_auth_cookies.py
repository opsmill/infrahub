import jwt

from infrahub import config
from infrahub.database import InfrahubDatabase


async def test_password_based_login(db: InfrahubDatabase, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"})

    assert response.status_code == 200

    # Check for cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    access_token = response.cookies["access_token"]
    decoded = jwt.decode(access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])
    assert first_account.id == decoded["sub"]


async def test_refresh_access_token(db: InfrahubDatabase, default_branch, client, first_account):
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


async def test_access_resource_using_refresh_token(db: InfrahubDatabase, default_branch, client, first_account):
    """It should not be possible to access a resource using a refresh token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200

    refresh_token = login_response.cookies["refresh_token"]

    with client:
        response = client.get("/api/transform/jinja2/testing", cookies={"access_token": refresh_token})

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Invalid token", "extensions": {"code": 401}}]}


async def test_generate_api_token(db: InfrahubDatabase, default_branch, client, create_test_admin):
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
    assert jwt_response.json()["data"]["CoreAccountTokenCreate"]["object"]["token"]["value"]
