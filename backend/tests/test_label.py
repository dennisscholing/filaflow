from types import SimpleNamespace

from app.main import render_spool_label


def test_spool_label_contains_qr_and_identification():
    spool = SimpleNamespace(
        code="SPL-0042",
        brand="Prusament",
        material_name="Prusament PETG Orange",
        material_type="PETG",
        color_name="Prusa Orange",
        color_hex="#F15A24",
        serial_number="SN-12345",
    )

    label = render_spool_label(spool, "https://filaflow.example/spools/id").decode()

    assert '<svg xmlns="http://www.w3.org/2000/svg"' in label
    assert "SPL-0042" in label
    assert "Prusament PETG Orange" in label
    assert "Spool S/N:" in label
    assert "SN-12345" in label
    assert "Prusa Orange" in label
    assert "<path" in label


def test_spool_label_escapes_text_and_falls_back_to_internal_code():
    spool = SimpleNamespace(
        code="SPL-0001",
        brand="Brand & Co",
        material_name="PLA <Silk>",
        material_type="PLA",
        color_name="",
        color_hex="invalid",
        serial_number="",
    )

    label = render_spool_label(spool, "https://filaflow.example/spools/id").decode()

    assert "PLA &lt;Silk&gt;" in label
    assert "Brand &amp; Co" in label
    assert "Unnamed color" in label
    assert "#808080" in label
    assert "SPL-0001</tspan>" in label
