import io
import uuid
import zipfile

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import catalog
from app.database import Base
from app.models import CatalogMaterial


def _catalog_zip() -> bytes:
    files = {
        "repo/data/brands/example.yaml": """
uuid: 11111111-1111-5111-8111-111111111111
slug: example
name: Example Filament
""",
        "repo/data/materials/example/example-pla-blue.yaml": """
uuid: 22222222-2222-5222-8222-222222222222
slug: example-pla-blue
brand:
  slug: example
name: PLA Galaxy Blue
class: FFF
type: PLA
primary_color:
  color_rgba: '#0095ffff'
tags: [glitter, silk]
properties:
  density: 1.21
""",
        "repo/data/material-packages/example/example-pla-blue-1000.yaml": """
uuid: 33333333-3333-5333-8333-333333333333
slug: example-pla-blue-1000
url: https://example.test/blue
material:
  slug: example-pla-blue
container:
  slug: example-spool
nominal_netto_full_weight: 1000
filament_diameter: 1750
nominal_full_length: 338638
gtin: 1234567890123
""",
        "repo/data/material-containers/example-spool.yaml": """
uuid: 44444444-4444-5444-8444-444444444444
slug: example-spool
name: Example 1 kg spool
empty_weight: 277
""",
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return output.getvalue()


def test_sync_catalog_links_nested_references_and_units(monkeypatch):
    class Response:
        content = _catalog_zip()
        headers = {"etag": 'W/"test-revision"'}

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(catalog.httpx, "get", lambda *args, **kwargs: Response())
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as database:
        snapshot = catalog.sync_catalog(database)
        row = database.scalar(select(CatalogMaterial))

        assert snapshot.material_count == 1
        assert row is not None
        assert row.brand == "Example Filament"
        assert row.brand_uuid == uuid.UUID("11111111-1111-5111-8111-111111111111")
        assert row.package_uuid == uuid.UUID("33333333-3333-5333-8333-333333333333")
        assert row.container_uuid == uuid.UUID("44444444-4444-5444-8444-444444444444")
        assert str(row.diameter_mm) == "1.750"
        assert str(row.density_g_cm3) == "1.2100"
        assert row.color_hex == "#0095ff"
        assert row.nominal_weight_mg == 1_000_000
        assert int(row.nominal_length_mm) == 338_638
        assert row.tare_weight_mg == 277_000
        assert row.raw_data["package"]["gtin"] == 1_234_567_890_123


def test_catalog_metadata_exposes_complete_selection_details():
    metadata = catalog.catalog_metadata({
        "material": {
            "primary_color": {"color_rgba": "#abcdefff"},
            "tags": ["matte"],
            "properties": {"min_print_temperature": 205},
            "photos": [{"url": "https://example.test/photo.png"}],
        },
        "package": {"slug": "blue-1000", "gtin": 123, "url": "https://example.test/product"},
        "container": {"name": "Reusable spool"},
    })

    assert metadata["colorHex"] == "#abcdef"
    assert metadata["gtin"] == "123"
    assert metadata["tags"] == ["matte"]
    assert metadata["properties"]["min_print_temperature"] == 205
    assert metadata["photoUrl"] == "https://example.test/photo.png"


def test_sync_catalog_reports_download_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(catalog.httpx, "get", fail)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as database, pytest.raises(catalog.CatalogSyncError, match="internet connection"):
        catalog.sync_catalog(database)
