from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import SPAStaticFiles


def test_spa_deep_links_fall_back_to_index(tmp_path):
    (tmp_path / "index.html").write_text("<title>FilaFlow test</title>", encoding="utf-8")
    static_app = FastAPI()
    static_app.mount("/", SPAStaticFiles(directory=tmp_path, html=True, fallback_file=tmp_path / "index.html"))

    with TestClient(static_app) as client:
        response = client.get("/labels/print?spools=test")

    assert response.status_code == 200
    assert "FilaFlow test" in response.text


def test_spa_missing_asset_remains_not_found(tmp_path):
    (tmp_path / "index.html").write_text("<title>FilaFlow test</title>", encoding="utf-8")
    static_app = FastAPI()
    static_app.mount("/", SPAStaticFiles(directory=tmp_path, html=True, fallback_file=tmp_path / "index.html"))

    with TestClient(static_app) as client:
        response = client.get("/missing.js")

    assert response.status_code == 404
