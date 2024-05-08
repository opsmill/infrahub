import jwt

from infrahub import config
from infrahub.database import InfrahubDatabase

EXPIRED_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YTVjYmNlZS1mN2IwLTRmNzc"
    + "tYjk1Yi1jMjAwODYwOGU5MDAiLCJpYXQiOjE2ODYyMjIzNjUsIm5iZiI6MTY4NjIyMjM2N"
    + "SwiZXhwIjoxNjg2MjIyNDI1LCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MiLCJ1c2V"
    + "yX2NsYWltcyI6eyJyb2xlcyI6WyJyZWFkLXdyaXRlIl19fQ.7d2wSrrTkdAc2ZYjZwOgjR"
    + "jr3c6n9_iN3Miei_zXJ-0"
)

EXPIRED_REFRESH_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1N2EzZGNjMi0yYzY0LTQ4MGE"
    + "tOTAyYi1jMzJjZDY0ZDg0NDgiLCJpYXQiOjE2ODY3MjMwMTMsIm5iZiI6MTY4NjcyMzAxM"
    + "ywiZXhwIjoxNjg2NzIzMDczLCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJyZWZyZXNoIiwic2V"
    + "zc2lvbl9pZCI6IjNjY2Q3OTZlLTk0NzUtNGQ2MC05NDQ4LTYyOWVkY2E0NGRiMyJ9.uYjo"
    + "x3qqqr1iPLTkDDCWGUsiuFXFyGjXezt_Vf8Ibf4"
)


async def test_password_based_login(db: InfrahubDatabase, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"})

    assert response.status_code == 200

    # Check for cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    access_token = response.json()["access_token"]
    decoded = jwt.decode(access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])
    assert first_account.id == decoded["sub"]


async def test_refresh_with_invalidated_token(db: InfrahubDatabase, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"})

    assert response.status_code == 200
    access_token = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]
    decoded = jwt.decode(refresh_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])
    assert first_account.id == decoded["sub"]

    with client:
        logout_response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {access_token}"})

    assert logout_response.status_code == 200

    with client:
        refresh_response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})

    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        "data": None,
        "errors": [
            {"message": "The provided refresh token has been invalidated in the database", "extensions": {"code": 401}}
        ],
    }


async def test_refresh_access_token(db: InfrahubDatabase, default_branch, client, first_account):
    """Validate that it's possible to refresh an access token using a refresh token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200
    assert sorted(login_response.json().keys()) == ["access_token", "refresh_token"]
    refresh_token = login_response.json()["refresh_token"]
    decoded_refresh = jwt.decode(refresh_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])
    with client:
        refresh_response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})

    assert refresh_response.status_code == 200
    access_token = refresh_response.json()["access_token"]
    decoded_access = jwt.decode(access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])

    assert first_account.id == decoded_access["sub"]
    assert first_account.id == decoded_refresh["sub"]
    assert decoded_access["session_id"]
    assert decoded_access["session_id"] == decoded_refresh["session_id"]


async def test_refresh_access_token_with_cookies(db: InfrahubDatabase, default_branch, client, first_account):
    """Validate that it's possible to refresh an access token using a refresh token stored in cookies"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200

    # Get tokens from cookies
    refresh_token = login_response.cookies.get("refresh_token")
    assert refresh_token is not None

    decoded_refresh = jwt.decode(refresh_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])

    # Send refresh token as a cookie
    cookies = {"refresh_token": refresh_token}
    with client:
        refresh_response = client.post("/api/auth/refresh", cookies=cookies)

    assert refresh_response.status_code == 200
    new_access_token = refresh_response.json()["access_token"]
    decoded_access = jwt.decode(new_access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])

    assert first_account.id == decoded_access["sub"]
    assert first_account.id == decoded_refresh["sub"]
    assert decoded_access["session_id"]
    assert decoded_access["session_id"] == decoded_refresh["session_id"]


async def test_fail_to_refresh_access_token_with_access_token(
    db: InfrahubDatabase, default_branch, client, first_account
):
    """Validate that it's not possible to refresh an access token using an access token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # Remove cookies
    client.cookies = None

    with client:
        refresh_response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {access_token}"})

    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        "data": None,
        "errors": [{"message": "Invalid token, current token is not a refresh token", "extensions": {"code": 401}}],
    }


async def test_password_based_login_unknown_user(db: InfrahubDatabase, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "i-do-not-exist", "password": "something"})

    assert response.status_code == 404
    assert response.json() == {
        "data": None,
        "errors": [{"extensions": {"code": 404}, "message": "That login user doesn't exist in the system"}],
    }


async def test_password_based_login_invalid_password(db: InfrahubDatabase, default_branch, client, first_account):
    with client:
        response = client.post("/api/auth/login", json={"username": "First Account", "password": "incorrect"})

    assert response.status_code == 401
    assert response.json() == {
        "data": None,
        "errors": [{"extensions": {"code": 401}, "message": "Incorrect password"}],
    }


async def test_use_expired_token(db: InfrahubDatabase, default_branch, client):
    with client:
        response = client.get(
            "/api/transform/jinja2/testing", headers={"Authorization": f"Bearer {EXPIRED_ACCESS_TOKEN}"}
        )

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Expired Signature", "extensions": {"code": 401}}]}


async def test_refresh_access_token_with_expired_refresh_token(db: InfrahubDatabase, default_branch, client):
    """Validate that the correct error is returned for an expired refresh token"""
    with client:
        response = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {EXPIRED_REFRESH_TOKEN}"})

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Expired Signature", "extensions": {"code": 401}}]}


async def test_access_resource_using_refresh_token(db: InfrahubDatabase, default_branch, client, first_account):
    """It should not be possible to access a resource using a refresh token"""
    with client:
        login_response = client.post(
            "/api/auth/login", json={"username": "First Account", "password": "FirstPassword123"}
        )

    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    with client:
        response = client.get("/api/transform/jinja2/testing", headers={"Authorization": f"Bearer {refresh_token}"})

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Invalid token", "extensions": {"code": 401}}]}


async def test_generate_api_token(db: InfrahubDatabase, default_branch, client, create_test_admin):
    """It should not be possible to generate an API token using a JWT token"""
    with client:
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "test-admin",
                "password": config.SETTINGS.initial.admin_password,
            },
        )

    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

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
            headers={"Authorization": f"Bearer {access_token}"},
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
