import os
import tempfile

import pytest_asyncio

_TMP = tempfile.mkdtemp(prefix="vehrep-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/test.db")
os.environ.setdefault("DATA_DIR", os.path.join(_TMP, "data"))
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "test-password-1")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("STATIC_DIR", "")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import httpx  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app, bootstrap_admin  # noqa: E402

ADMIN_PASSWORD = "test-password-1"
USER_PASSWORD = "user-password-1"


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


class Api:
    def __init__(self, ac: httpx.AsyncClient):
        self.ac = ac
        self.csrf: str | None = None

    async def login(self, username: str, password: str) -> httpx.Response:
        r = await self.ac.get("/api/auth/csrf")
        assert r.status_code == 200
        self.csrf = r.json()["csrf_token"]
        r = await self.ac.post(
            "/api/auth/login",
            json={"username": username, "password": password},
            headers={"X-CSRF-Token": self.csrf},
        )
        return r

    def _headers(self, extra=None):
        h = {"X-CSRF-Token": self.csrf or ""}
        if extra:
            h.update(extra)
        return h

    async def get(self, url, **kw):
        return await self.ac.get(url, **kw)

    async def post(self, url, json=None, headers=None, **kw):
        return await self.ac.post(url, json=json, headers=self._headers(headers), **kw)

    async def put(self, url, json=None):
        return await self.ac.put(url, json=json, headers=self._headers())

    async def patch(self, url, json=None):
        return await self.ac.patch(url, json=json, headers=self._headers())

    async def delete(self, url):
        return await self.ac.delete(url, headers=self._headers())


async def make_client(username: str, password: str) -> Api:
    transport = httpx.ASGITransport(app=app)
    ac = httpx.AsyncClient(transport=transport, base_url="http://test")
    api = Api(ac)
    r = await api.login(username, password)
    assert r.status_code == 200, r.text
    return api


@pytest_asyncio.fixture()
async def admin() -> Api:
    await bootstrap_admin()
    return await make_client("admin", ADMIN_PASSWORD)


_counter = {"n": 0}


@pytest_asyncio.fixture()
async def make_user(admin: Api):
    async def _make(role: str) -> Api:
        _counter["n"] += 1
        username = f"{role}-{_counter['n']}"
        r = await admin.post(
            "/api/users",
            {
                "username": username,
                "display_name": username.title(),
                "password": USER_PASSWORD,
                "role": role,
            },
        )
        assert r.status_code == 200, r.text
        return await make_client(username, USER_PASSWORD)

    return _make


@pytest_asyncio.fixture()
async def location(admin: Api) -> dict:
    r = await admin.post("/api/locations", {"name": "Hailakandi"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest_asyncio.fixture()
async def location2(admin: Api) -> dict:
    r = await admin.post("/api/locations", {"name": "Karimganj"})
    assert r.status_code == 200, r.text
    return r.json()


VALID_ENTRY = {
    "sr_no": 1,
    "vrn": "AS-01-AB-1234",
    "model": "Maruti Swift",
    "entry_date": "2026-02-07",
    "in_time": "10:30",
    "out_date": "2026-02-07",
    "out_time": "16:00",
    "status": "work_done",
    "remarks": None,
}


@pytest_asyncio.fixture()
async def make_entry(admin: Api, location: dict):
    async def _make(**overrides) -> dict:
        payload = {**VALID_ENTRY, **overrides, "location_id": overrides.get("location_id", location["id"])}
        r = await admin.post("/api/entries", payload)
        assert r.status_code == 200, r.text
        return r.json()

    return _make
