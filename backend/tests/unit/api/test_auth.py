import jwt

from infrahub import config

EXPIRED_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YTVjYmNlZS1mN2IwLTRmNzc"
    + "tYjk1Yi1jMjAwODYwOGU5MDAiLCJpYXQiOjE2ODYyMjIzNjUsIm5iZiI6MTY4NjIyMjM2N"
    + "SwiZXhwIjoxNjg2MjIyNDI1LCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MiLCJ1c2V"
    + "yX2NsYWltcyI6eyJyb2xlcyI6WyJyZWFkLXdyaXRlIl19fQ.7d2wSrrTkdAc2ZYjZwOgjR"
    + "jr3c6n9_iN3Miei_zXJ-0"
)


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


async def test_use_expired_token(session, default_branch, client):
    with client:
        response = client.get("/rfile/testing", headers={"Authorization": f"Bearer {EXPIRED_TOKEN}"})

    assert response.status_code == 401
    assert response.json() == {"data": None, "errors": [{"message": "Expired Signature", "extensions": {"code": 401}}]}
