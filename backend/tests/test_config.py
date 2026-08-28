from app.config import Settings


def test_database_password_with_special_characters_is_encoded():
    password = "percent% bang! hash# at@ dollar$"
    settings = Settings(
        _env_file=None,
        database_url=None,
        database_host="db",
        database_port=5432,
        database_name="filaflow",
        database_user="filaflow",
        database_password=password,
    )

    url = settings.sqlalchemy_database_url
    rendered = url.render_as_string(hide_password=False)

    assert url.password == password
    assert rendered.endswith("@db:5432/filaflow")
    assert "%25" in rendered
    assert "%23" in rendered
    assert "%40" in rendered


def test_explicit_database_url_override_is_preserved():
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///./test.db",
    )

    assert settings.sqlalchemy_database_url.drivername == "sqlite+pysqlite"

