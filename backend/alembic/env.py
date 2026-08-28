from logging.config import fileConfig
from alembic import context
from app.config import settings
from app.database import Base
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.sqlalchemy_database_url.render_as_string(hide_password=False), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    from app.database import engine
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, transactional_ddl=True, transaction_per_migration=False)
        with context.begin_transaction(): context.run_migrations()

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
