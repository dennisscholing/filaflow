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
        assert [(tool["index"], tool["label"]) for tool in indx.json()["tools"]] == [
            (index, f"T{index + 1}") for index in range(8)
        ]

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

        consumed = client.post(
            f"/api/spools/{original['id']}/weigh",
            headers=csrf,
            json={"consumed_weight_g": 10, "note": "Missing slicer job"},
        )
        assert consumed.status_code == 200, consumed.text
        assert consumed.json()["remainingWeightG"] == 990
        detail = client.get(f"/api/spools/{original['id']}")
        assert detail.json()["ledger"][0]["kind"] == "MANUAL_CONSUMPTION"

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
        assert mismatch.json()["status"] == "NEW"
        assert mismatch.json()["usages"][0]["toolIndex"] == 0
        assert mismatch.json()["usages"][0]["toolLabel"] == "T1"
        assert not any("No matching tool" in warning for warning in mismatch.json()["warnings"])


def test_v030_preferences_revision_labels_reorder_and_quick_booking():
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "admin@test.local", "password": "test-password-123"},
        )
        assert login.status_code == 200, login.text
        csrf = {"X-CSRF-Token": login.json()["csrf"]}

        before = client.get("/api/state/revision")
        assert before.status_code == 200
        preferred = client.put(
            "/api/account/preferences",
            headers=csrf,
            json={"preferred_unit": "meters"},
        )
        assert preferred.status_code == 200
        assert preferred.json()["preferredUnit"] == "meters"
        changed = client.get(
            "/api/state/revision", headers={"If-None-Match": before.headers["etag"]}
        )
        assert changed.status_code == 200
        unchanged = client.get(
            "/api/state/revision", headers={"If-None-Match": changed.headers["etag"]}
        )
        assert unchanged.status_code == 304

        templates = client.get("/api/label-templates")
        assert templates.status_code == 200
        assert len([row for row in templates.json() if row["builtin"]]) == 3
        source = templates.json()[0]
        duplicate = client.post(
            f"/api/label-templates/{source['id']}/duplicate", headers=csrf
        )
        assert duplicate.status_code == 201, duplicate.text
        custom = duplicate.json()
        edited = client.put(
            f"/api/label-templates/{custom['id']}",
            headers=csrf,
            json={
                "name": "Integration label",
                "width_mm": custom["widthMm"],
                "height_mm": custom["heightMm"],
                "layout": custom["layout"],
            },
        )
        assert edited.status_code == 200, edited.text

        printer = client.post(
            "/api/printers",
            headers=csrf,
            json={"name": "Quick-book printer", "slicer_profile": "Quick profile", "preset": "single"},
        )
        spool = client.post(
            "/api/spools",
            headers=csrf,
            json={
                "brand": "Quick brand", "material_name": "Quick PLA", "material_type": "PLA",
                "color_hex": "#112233", "initial_weight_g": 1000,
            },
        )
        assert printer.status_code == 201 and spool.status_code == 201
        assert client.get("/api/dashboard").status_code == 200
        for built_in in templates.json():
            preview = client.get(
                f"/api/spools/{spool.json()['id']}/label.svg",
                params={"templateId": built_in["id"]},
            )
            assert preview.status_code == 200, f"{built_in['name']}: {preview.text}"
        loaded = client.put(
            f"/api/printers/{printer.json()['id']}/tools/{printer.json()['tools'][0]['id']}/loadout",
            headers=csrf,
            json={"spool_id": spool.json()["id"]},
        )
        assert loaded.status_code == 200

        ranked = client.get(
            "/api/spools/ranked", params={"materialType": "PLA", "colorHex": "#112233"}
        )
        assert ranked.status_code == 200
        assert ranked.json()[0]["id"] == spool.json()["id"]

        reorder = client.put(
            "/api/inventory/settings", headers=csrf, json={"reorder_threshold_g": 1200}
        )
        assert reorder.status_code == 200
        suggestions = client.get("/api/inventory/reorder-suggestions?all=true")
        group = next(row for row in suggestions.json()["groups"] if row["productKey"] == spool.json()["productKey"])
        assert group["needsOrdering"] is True
        assert group["shortageG"] == 200

        token = client.post(
            "/api/tokens", headers=csrf,
            json={"name": "Quick hook", "printer_id": printer.json()["id"]},
        )
        gcode = b"""M83\nT0\nG1 X1 E100\n; filament used [mm] = 100.00\n; filament used [g] = 0.30\n; filament_type = PLA\n; filament_colour = #112233\n"""
        ingested = client.post(
            "/api/slicer/jobs",
            headers={"Authorization": f"Bearer {token.json()['token']}", "Idempotency-Key": "quick-book-v030"},
            data={"printer_id": printer.json()["id"], "source_profile": "Quick profile", "routing_mode": "profile"},
            files={"file": ("quick.gcode", gcode, "application/octet-stream")},
        )
        assert ingested.status_code == 201, ingested.text
        assert ingested.json()["status"] == "NEW"
        booked = client.post(
            f"/api/jobs/{ingested.json()['id']}/confirm-and-book", headers=csrf
        )
        assert booked.status_code == 200, booked.text
        assert booked.json()["status"] == "BOOKED"
        assert client.get(f"/api/spools/{spool.json()['id']}").json()["remainingWeightG"] == 999.7

        label = client.get(
            f"/api/spools/{spool.json()['id']}/label.svg",
            params={"templateId": custom["id"], "monochrome": True},
        )
        assert label.status_code == 200
        assert "SPL-" in label.text and "Quick PLA" in label.text
        activity = client.get(
            "/api/activity", params={"entity_type": "spool", "entity_id": spool.json()["id"]}
        )
        assert activity.status_code == 200
        assert any(row["action"] == "spool.created" for row in activity.json())

        rollback_printer = client.post(
            "/api/printers", headers=csrf,
            json={"name": "Rollback printer", "preset": "dual"},
        ).json()
        rollback_spools = [
            client.post(
                "/api/spools", headers=csrf,
                json={"brand": "Rollback", "material_name": f"Rollback {index}", "material_type": "PLA", "color_hex": color, "initial_weight_g": 100},
            ).json()
            for index, color in enumerate(("#AA0000", "#0000AA"), start=1)
        ]
        for tool, rollback_spool in zip(rollback_printer["tools"], rollback_spools, strict=True):
            response = client.put(
                f"/api/printers/{rollback_printer['id']}/tools/{tool['id']}/loadout",
                headers=csrf, json={"spool_id": rollback_spool["id"]},
            )
            assert response.status_code == 200
        rollback_token = client.post(
            "/api/tokens", headers=csrf,
            json={"name": "Rollback hook", "printer_id": rollback_printer["id"]},
        ).json()["token"]
        dual_gcode = b"""M83\nT0\nG1 E10\nT1\nG1 E20\n; filament used [mm] = 10.00, 20.00\n; filament used [g] = 0.03, 0.06\n; filament_type = PLA;PLA\n; filament_colour = #AA0000;#0000AA\n"""
        rollback_job = client.post(
            "/api/slicer/jobs",
            headers={"Authorization": f"Bearer {rollback_token}", "Idempotency-Key": "rollback-quick-v030"},
            data={"printer_id": rollback_printer["id"], "routing_mode": "profile"},
            files={"file": ("rollback.gcode", dual_gcode, "application/octet-stream")},
        ).json()
        assert rollback_job["status"] == "NEW"
        assert client.post(f"/api/spools/{rollback_spools[1]['id']}/archive", headers=csrf).status_code == 200
        rejected = client.post(
            f"/api/jobs/{rollback_job['id']}/confirm-and-book", headers=csrf
        )
        assert rejected.status_code == 422
        after_rejection = next(row for row in client.get("/api/jobs").json() if row["id"] == rollback_job["id"])
        assert after_rejection["status"] == "NEW"
        assert all(usage["mappedSpoolId"] is None for usage in after_rejection["usages"])
