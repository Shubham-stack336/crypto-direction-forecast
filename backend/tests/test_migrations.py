import psycopg
from alembic import command
from sqlalchemy import create_engine, inspect

from tests.conftest import alembic_config


def test_upgrade_downgrade_upgrade_on_a_fresh_database(pg_server_url):
    admin_url = pg_server_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute("DROP DATABASE IF EXISTS migration_check")
        connection.execute("CREATE DATABASE migration_check")

    url = pg_server_url.rsplit("/", 1)[0] + "/migration_check"
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "head")
        assert {"predictions", "model_versions"} <= set(inspect(engine).get_table_names())

        command.downgrade(cfg, "base")
        assert "predictions" not in inspect(engine).get_table_names()

        command.upgrade(cfg, "head")
        assert "predictions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
