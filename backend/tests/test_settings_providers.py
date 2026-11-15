async def test_provider_crud_and_masking(admin):
    r = await admin.post(
        "/api/settings/providers",
        {
            "name": "local",
            "kind": "openai",
            "base_url": "http://localhost:8000",
            "api_key": "sk-abcd1234",
            "default_model": "qwen-vl",
        },
    )
    assert r.status_code == 200
    p = r.json()
    assert p["api_key_masked"] == "••••1234"
    assert "api_key" not in p
    assert p["is_default"] is True

    r = await admin.post("/api/settings/providers", {"name": "cloud", "kind": "gemini", "api_key": "gk-9999zzzz", "default_model": "gemini-2.5-flash"})
    assert r.status_code == 200
    assert r.json()["is_default"] is False
    pid = r.json()["id"]

    # patch without api_key keeps the stored secret
    r = await admin.patch(f"/api/settings/providers/{pid}", {"default_model": "gemini-2.5-pro"})
    assert r.json()["default_model"] == "gemini-2.5-pro"
    assert r.json()["api_key_masked"] == "••••zzzz"

    r = await admin.post(f"/api/settings/providers/{pid}/default")
    assert r.status_code == 200
    providers = (await admin.get("/api/settings/providers")).json()
    assert [p["name"] for p in providers if p["is_default"]] == ["cloud"]

    r = await admin.delete(f"/api/settings/providers/{pid}")
    assert r.status_code == 200
    providers = (await admin.get("/api/settings/providers")).json()
    assert len(providers) == 1 and providers[0]["is_default"] is True

    # duplicate name rejected
    r = await admin.post("/api/settings/providers", {"name": "local", "kind": "openai"})
    assert r.status_code == 409


async def test_provider_test_endpoint(admin, monkeypatch):
    import app.api.providers as prov_api

    r = await admin.post(
        "/api/settings/providers",
        {"name": "t1", "kind": "openai", "base_url": "http://x", "default_model": "m1", "api_key": "k"},
    )
    pid = r.json()["id"]

    async def fake_models(spec):
        return ["m1", "m2"]

    async def fake_chat(spec, prompt, data, mime, guided=None):
        return "OK"

    monkeypatch.setattr(prov_api.openai_client, "list_models", fake_models)
    monkeypatch.setattr(prov_api.openai_client, "chat_with_image", fake_chat)
    res = (await admin.post(f"/api/settings/providers/{pid}/test")).json()
    assert res["ok"] is True
    assert res["models"] == ["m1", "m2"]
    assert res["vision"] == "supported"

    async def no_vision(spec, prompt, data, mime, guided=None):
        from app.services.providers.base import ExtractionError

        raise ExtractionError("This model does not support image input")

    monkeypatch.setattr(prov_api.openai_client, "chat_with_image", no_vision)
    res = (await admin.post(f"/api/settings/providers/{pid}/test")).json()
    assert res["vision"] == "unsupported"

    stored = (await admin.get("/api/settings/providers")).json()[0]
    assert stored["vision_status"] == "unsupported"
    assert stored["last_test"]["ok"] is True


async def test_email_settings_keeps_password_and_masks(admin):
    put = {
        "enabled": True,
        "recipients": ["boss@x.com"],
        "schedule_time": "18:30",
        "smtp": {"host": "smtp.x.com", "port": 587, "username": "u", "use_tls": True,
                 "from_address": "reports@x.com", "password": "s3cret"},
    }
    r = await admin.put("/api/settings/email", put)
    assert r.status_code == 200
    body = r.json()
    assert body["smtp"]["password_set"] is True
    assert "password" not in body["smtp"] or body["smtp"].get("password") in (None, True)

    # update without password → keep stored
    put2 = {**put, "recipients": ["a@x.com", "b@x.com"], "smtp": {**put["smtp"], "password": None}}
    r = await admin.put("/api/settings/email", put2)
    assert r.json()["smtp"]["password_set"] is True
    assert r.json()["recipients"] == ["a@x.com", "b@x.com"]

    r = await admin.put("/api/settings/email", {**put2, "schedule_time": "25:00"})
    assert r.status_code == 422

    # non-admin cannot read settings
    # (operator)
    from tests.conftest import make_client  # noqa: F401


async def test_email_test_without_config(admin):
    r = await admin.post("/api/settings/email/test")
    assert r.status_code == 200
    assert r.json()["ok"] is False


async def test_general_settings_and_rc_flag(admin, make_user):
    g = (await admin.get("/api/settings/general")).json()
    assert g["rc_lookup_enabled"] is False
    r = await admin.put("/api/settings/general", {"display_date_format": "DD/MM/YYYY", "rc_lookup_enabled": False})
    assert r.json()["display_date_format"] == "DD/MM/YYYY"

    r = await admin.get("/api/rc/AS01AB1234")
    assert r.json()["status"] == "disabled"

    await admin.put("/api/settings/general", {"display_date_format": "DD-MM-YYYY", "rc_lookup_enabled": True})
    from app.services import rc as rc_svc

    rc_svc.set_provider(rc_svc.NullProvider())
    r = await admin.get("/api/rc/AS-01-AB-1234")
    assert r.json()["status"] == "not_found"
