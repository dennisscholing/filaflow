from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def test_initial_migration_is_frozen_and_explicit():
    source = (BACKEND / "alembic" / "versions" / "0001_initial.py").read_text(encoding="utf-8")
    assert "Base.metadata" not in source
    assert "from app" not in source
    assert 'op.create_table("users"' in source


def test_runtime_never_creates_schema_from_current_models():
    source = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    assert "metadata.create_all" not in source


def test_v020_schema_change_is_additive():
    source = (BACKEND / "alembic" / "versions" / "0003_printer_location.py").read_text(encoding="utf-8")
    upgrade = source.split("def downgrade", 1)[0]
    assert 'op.add_column("printers"' in upgrade
    assert "drop_" not in upgrade
    assert "alter_column" not in upgrade


def test_v030_schema_changes_are_additive():
    source = (BACKEND / "alembic" / "versions" / "0004_v030_ui_labels.py").read_text(encoding="utf-8")
    upgrade = source.split("def downgrade", 1)[0]
    assert upgrade.count("op.create_table(") == 3
    assert '"label_templates"' in upgrade
    assert '"inventory_settings"' in upgrade
    assert '"reorder_rules"' in upgrade
    assert "drop_" not in upgrade
    assert "alter_column" not in upgrade


def test_v050_password_schema_change_is_additive():
    source = (BACKEND / "alembic" / "versions" / "0006_user_password_security.py").read_text(encoding="utf-8")
    upgrade = source.split("def downgrade", 1)[0]
    assert upgrade.count('op.add_column("users"') == 2
    assert "drop_" not in upgrade
    assert "alter_column" not in upgrade
