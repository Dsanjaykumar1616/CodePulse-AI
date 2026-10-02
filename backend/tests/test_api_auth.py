from conftest import signup


def test_signup_returns_token_and_user(client):
    body = signup(client)
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "ada@example.com"
    assert "password" not in str(body["user"]).lower()


def test_signup_rejects_duplicate_email_case_insensitively(client):
    signup(client)
    response = client.post(
        "/api/auth/signup", json={"name": "Ada", "email": "ADA@example.com", "password": "analytical1"}
    )
    assert response.status_code == 409


def test_signup_validates_password_and_email(client):
    weak = client.post("/api/auth/signup", json={"name": "A", "email": "a@example.com", "password": "short"})
    assert weak.status_code == 422
    letters_only = client.post(
        "/api/auth/signup", json={"name": "A", "email": "a@example.com", "password": "onlyletters"}
    )
    assert letters_only.status_code == 422
    bad_email = client.post("/api/auth/signup", json={"name": "A", "email": "nope", "password": "analytical1"})
    assert bad_email.status_code == 422


def test_password_is_hashed(client):
    from app.db.session import SessionLocal
    from app.models import User

    signup(client)
    with SessionLocal() as db:
        user = db.query(User).one()
        assert user.password_hash != "analytical1"
        assert user.password_hash.startswith("$2")


def test_login_success_and_failure(client):
    signup(client)
    ok = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "analytical1"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    wrong = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong-pass1"})
    assert wrong.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "analytical1"})
    assert unknown.status_code == 401


def test_me_requires_valid_token(client, auth_headers):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    me = client.get("/api/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["name"] == "Ada"


def test_logout(client, auth_headers):
    assert client.post("/api/auth/logout", headers=auth_headers).status_code == 204


def test_protected_routes_reject_unauthenticated(client):
    for method, path in [
        ("get", "/api/repositories"),
        ("post", "/api/repositories"),
        ("get", "/api/repositories/x/overview"),
        ("get", "/api/analysis/x"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path
