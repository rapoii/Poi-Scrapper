"""Alembic env.py — pakai sync DSN (DATABASE_URL_SYNC) supaya migrasi simple."""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings

# Import semua models supaya metadata ke-populate sebelum autogen.
from app.db import models  # noqa: F401
from app.db.base import Base

# ---- Alembic config + settings ---------------------------------------------
config = context.config
settings = get_settings()

# Inject DSN sync dari env.
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


# ---- Offline / online runners ----------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations tanpa koneksi DB (generate SQL)."""
    context.configure(
        url=settings.database_url_sync,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations dengan koneksi sync ke DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
