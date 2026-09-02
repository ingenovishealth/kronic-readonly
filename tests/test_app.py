import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config

config.TEST = True

import app as app_module


WRITE_ROUTES = [
    ("POST", "/namespaces/test/cronjobs/some-cron"),
    ("POST", "/api/namespaces/test/cronjobs/some-cron/clone"),
    ("POST", "/api/namespaces/test/cronjobs/create"),
    ("POST", "/api/namespaces/test/cronjobs/some-cron/delete"),
    ("POST", "/api/namespaces/test/cronjobs/some-cron/suspend"),
    ("POST", "/api/namespaces/test/cronjobs/some-cron/trigger"),
    ("POST", "/api/namespaces/test/jobs/some-job/delete"),
]


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.mark.parametrize("method,path", WRITE_ROUTES)
def test_write_routes_return_405(client, method, path):
    resp = client.open(path, method=method)
    assert resp.status_code == 405
    assert resp.headers.get("Allow") == "GET, HEAD, OPTIONS"


def test_api_write_returns_json_405(client):
    resp = client.post("/api/namespaces/test/cronjobs/some-cron/trigger")
    assert resp.status_code == 405
    assert resp.is_json
    assert "error" in resp.get_json()


def test_html_write_returns_plain_405(client):
    resp = client.post("/namespaces/test/cronjobs/some-cron")
    assert resp.status_code == 405
    assert resp.mimetype != "application/json"


def test_healthz_still_works(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_suspend_get_still_allowed(client, monkeypatch):
    called = {}

    def fake_get_cronjob(namespace, name):
        called["ns"] = namespace
        called["name"] = name
        return {"metadata": {"name": name}, "spec": {"suspend": False}}

    monkeypatch.setattr(app_module, "get_cronjob", fake_get_cronjob)
    resp = client.get("/api/namespaces/test/cronjobs/some-cron/suspend")
    assert resp.status_code == 200
    assert called == {"ns": "test", "name": "some-cron"}


def test_index_read_still_works(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_cronjobs", lambda *a, **kw: [])
    resp = client.get("/")
    assert resp.status_code == 200


def test_api_index_read_still_works(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_cronjobs", lambda *a, **kw: [])
    resp = client.get("/api/")
    assert resp.status_code == 200


def test_api_namespace_read_still_works(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_cronjobs", lambda *a, **kw: [])
    resp = client.get("/api/namespaces/test")
    assert resp.status_code == 200
