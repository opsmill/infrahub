import jwt

from infrahub import config


async def test_password_based_login(session, default_branch, client, first_account):
    with client:
        response = client.post("/auth/login", json={"username": "First Account", "password": "FirstPassword123"})

    assert response.status_code == 200
    access_token = response.json()["access_token"]
    decoded = jwt.decode(access_token, key=config.SETTINGS.security.secret_key, algorithms=["HS256"])
    assert first_account.id == decoded["sub"]


async def test_password_based_login_unknown_user(session, default_branch, client, first_account):
    with client:
        response = client.post("/auth/login", json={"username": "i-do-not-exist", "password": "something"})

    assert response.status_code == 404
    assert response.json() == {
        "data": None,
        "errors": [{"extensions": {"code": 404}, "message": "That login user doesn't exist in the system"}],
    }


async def test_password_based_login_invalid_password(session, default_branch, client, first_account):
    with client:
        response = client.post("/auth/login", json={"username": "First Account", "password": "incorrect"})

    assert response.status_code == 401
    assert response.json() == {
        "data": None,
        "errors": [{"extensions": {"code": 401}, "message": "Incorrect password"}],
    }
