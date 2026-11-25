"""Keeps the local SQLite file on the latest schema, so development needs no manual migration step."""
from alembic import command
from alembic.config import Config

from app.core.config import BASE_DIR
from app.repositories.database import create_db_engine


def upgrade_local_schema(url: str) -> None:
    """Run the Alembic migrations on a SQLite database. PostgreSQL is migrated at deploy time."""
    if not url.startswith("sqlite"):
        return
    create_db_engine(url).dispose()  # creates the parent folder
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
