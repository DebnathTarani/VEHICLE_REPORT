import httpx

from app.main import app, bootstrap_admin
from tests.conftest import Api, make_client


async def test_csrf_and_login_flow(clean_db):
    await bootstrap_admin()
    api = await make_client("admin", "test-password-1")
    r = await api.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    r = await api.post("/api/auth/change-password", {"current_password": "nope", "new_password": "abcdefghij"})
    assert r.status_code == 400
    r = await api.post("/api/auth/change-password", {"current_password": "test-password-1", "new_password": "new-password-9"})
    assert r.status_code == 200


async def test_login_wrong_password(clean_db):
    await bootstrap_admin()
    api = Api(httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test"))
    r = await api.login("admin", "wrong-password")
    assert r.status_code == 401
    r = await api.login("ghost", "whatever-123")
    assert r.status_code == 401


async def test_post_without_csrf_rejected(clean_db):
    await bootstrap_admin()
    api = await make_client("admin", "test-password-1")
    r = await api.ac.post("/api/locations", json={"name": "X"})  # no csrf header
    assert r.status_code == 403
    assert r.json()["detail"] == "csrf_failed"


async def test_unauthenticated_blocked(clean_db):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        r = await ac.get("/api/entries")
        assert r.status_code == 401
        r = await ac.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


async def test_rbac_viewer_and_operator(admin, make_user):
    viewer = await make_user("viewer")
    operator = await make_user("operator")

    assert (await operator.get("/api/users")).status_code == 403
    assert (await viewer.get("/api/users")).status_code == 403
    assert (await viewer.get("/api/locations")).status_code == 200
    assert (await viewer.post("/api/locations", {"name": "Nope"})).status_code == 403

    loc = await (await make_user("operator")).get("/api/locations")
    assert loc.status_code == 200


async def test_last_admin_protection(admin, make_user):
    await make_user("operator")  # second user exists but is not admin
    users = (await admin.get("/api/users")).json()
    admin_id = [u["id"] for u in users if u["username"] == "admin"][0]
    r = await admin.patch(f"/api/users/{admin_id}", {"role": "operator"})
    assert r.status_code == 400
    r = await admin.patch(f"/api/users/{admin_id}", {"is_active": False})
    assert r.status_code == 400
