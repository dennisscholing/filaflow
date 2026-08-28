from fastapi.testclient import TestClient

from app.main import app


def test_edit_route_book_and_analyse_workflow():
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "admin@test.local", "password": "test-password-123"},
        )
        assert login.status_code == 200, login.text
        csrf = {"X-CSRF-Token": login.json()["csrf"]}

        first = client.post(
            "/api/printers",
            headers=csrf,
            json={
                "name": "Workshop printer",
                "manufacturer": "Prusa",
                "model": "MK4S",
                "location": "Workshop",
                "slicer_profile": "Original Prusa MK4S 0.4 nozzle",
                "preset": "single",
            },
        )
        second = client.post(
            "/api/printers",
            headers=csrf,
            json={"name": "Office printer", "location": "Office", "preset": "dual"},
        )
        indx = client.post(
            "/api/printers",
            headers=csrf,
            json={"name": "INDX printer", "location": "Workshop", "preset": "indx8"},
        )
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert indx.status_code == 201, indx.text

        edited_printer = client.put(
            f"/api/printers/{second.json()['id']}",
            headers=csrf,
            json={
                "name": "Office printer A",
                "manufacturer": "Prusa",
                "model": "XL",
                "location": "Print room",
                "slicer_profile": "Office XL",
                "notes": "Primary office printer",
            },
        )
        assert edited_printer.status_code == 200, edited_printer.text
        assert edited_printer.json()["location"] == "Print room"

        spool = client.post(
            "/api/spools",
            headers=csrf,
            json={
                "brand": "Example",
                "material_name": "Signal red PLA",
                "material_type": "PLA",
                "color_name": "",
                "color_hex": "#FF0505",
                "location": "Workshop",
                "initial_weight_g": 1000,
            },
        )
        assert spool.status_code == 201, spool.text
        original = spool.json()
        assert original["colorName"] == "Red"

        edited_spool = client.put(
            f"/api/spools/{original['id']}",
            headers=csrf,
            json={
                "brand": "Example Filament",
                "material_name": "Signal red PLA",
                "material_type": "PLA",
                "color_name": "Signal Red",
                "color_hex": "#FF0505",
                "location": "Print room",
                "lot_number": "LOT-1",
                "serial_number": "SER-1",
                "diameter_mm": 1.75,
                "density_g_cm3": 1.25,
                "tare_weight_g": 210,
                "low_stock_weight_g": 75,
                "purchase_price": 29.95,
                "currency": "eur",
            },
        )
        assert edited_spool.status_code == 200, edited_spool.text
        updated = edited_spool.json()
        assert updated["code"] == original["code"]
        assert updated["remainingWeightG"] == original["remainingWeightG"]
        assert updated["remainingLengthM"] != original["remainingLengthM"]
        assert updated["currency"] == "EUR"
        assert set(updated["openPrintTag"]) == {
            "brandUuid", "materialUuid", "packageUuid", "containerUuid"
        }
        detail = client.get(f"/api/spools/{original['id']}")
        assert any(entry["kind"] == "METADATA_CORRECTION" for entry in detail.json()["ledger"])

        colors = client.get("/api/colors/nearest", params={"hex": "#FF0505"})
        locations = client.get("/api/locations")
        assert colors.json()["name"] == "Red"
        assert "Print room" in locations.json()

        token = client.post(
            "/api/tokens",
            headers=csrf,
            json={"name": "Workshop hook", "printer_id": first.json()["id"]},
        )
        assert token.status_code == 200, token.text
        gcode = b"""M83\nT0\nG1 X1 E100\n; filament used [mm] = 100.00\n; filament used [g] = 0.30\n; filament_type = PLA\n; filament_colour = #FF0505\n"""
        ingested = client.post(
            "/api/slicer/jobs",
            headers={
                "Authorization": f"Bearer {token.json()['token']}",
                "Idempotency-Key": "integration-route-1",
            },
            data={
                "printer_id": first.json()["id"],
                "source_profile": "Unknown local profile",
                "routing_mode": "default",
            },
            files={"file": ("route-test.gcode", gcode, "application/octet-stream")},
        )
        assert ingested.status_code == 201, ingested.text
        job = ingested.json()
        assert job["status"] == "NEEDS_REVIEW"
        assert job["slicerProfile"] == "Unknown local profile"
        assert job["routingMode"] == "default"

        first_mapping = client.put(
            f"/api/jobs/{job['id']}/mapping",
            headers=csrf,
            json={
                "mappings": [
                    {"usage_id": job["usages"][0]["id"], "spool_id": original["id"]}
                ]
            },
        )
        assert first_mapping.status_code == 200, first_mapping.text
        assert client.get(f"/api/spools/{original['id']}").json()["reservedWeightG"] == 0.3

        changed = client.put(
            f"/api/jobs/{job['id']}/printer",
            headers=csrf,
            json={"printer_id": second.json()["id"]},
        )
        assert changed.status_code == 200, changed.text
        corrected = changed.json()
        assert corrected["printer"]["id"] == second.json()["id"]
        assert corrected["routingMode"] == "corrected"
        assert corrected["usages"][0]["mappedSpoolId"] is None
        assert client.get(f"/api/spools/{original['id']}").json()["reservedWeightG"] == 0

        mapped = client.put(
            f"/api/jobs/{job['id']}/mapping",
            headers=csrf,
            json={
                "mappings": [
                    {"usage_id": corrected["usages"][0]["id"], "spool_id": original["id"]}
                ]
            },
        )
        assert mapped.status_code == 200, mapped.text
        booked = client.post(
            f"/api/jobs/{job['id']}/book",
            headers=csrf,
            json={"usages": [], "allow_negative": False},
        )
        assert booked.status_code == 200, booked.text
        assert booked.json()["status"] == "BOOKED"

        analytics = client.get(
            "/api/analytics/usage", params={"days": 30, "timezone": "Europe/Amsterdam"}
        )
        assert analytics.status_code == 200, analytics.text
        assert len(analytics.json()["points"]) == 30
        assert analytics.json()["totals"]["weightG"] == 0.3
        assert analytics.json()["totals"]["lengthM"] == 0.1

        blocked = client.put(
            f"/api/jobs/{job['id']}/printer",
            headers=csrf,
            json={"printer_id": first.json()["id"]},
        )
        assert blocked.status_code == 409

        mismatch_job = client.post(
            "/api/slicer/jobs",
            headers={
                "Authorization": f"Bearer {token.json()['token']}",
                "Idempotency-Key": "integration-route-2",
            },
            data={"printer_id": first.json()["id"], "source_profile": "MK4 profile"},
            files={"file": ("tool-zero.gcode", gcode, "application/octet-stream")},
        ).json()
        mismatch = client.put(
            f"/api/jobs/{mismatch_job['id']}/printer",
            headers=csrf,
            json={"printer_id": indx.json()["id"]},
        )
        assert mismatch.status_code == 200, mismatch.text
        assert mismatch.json()["status"] == "NEEDS_REVIEW"
        assert any("No matching tool T0" in warning for warning in mismatch.json()["warnings"])
