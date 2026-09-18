from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Registers every table with Base.metadata; Alembic autogenerate reads it.
import app.models  # noqa: F401
