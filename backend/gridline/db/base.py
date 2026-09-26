"""Single SQLAlchemy declarative base shared by every mapped table in GridLine.

All model modules (city data layer, RAG corpus, operations, ...) must import ``Base`` from here so that one
``Base.metadata`` holds every table and ``create_all`` builds the whole schema in one call.
"""

import datetime as dt
from typing import Any

from sqlalchemy import JSON, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

# JSON on any dialect, JSONB on PostgreSQL (the production target).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base with JSON mappings for list/dict annotations and timezone-aware datetimes.

    ``AsyncAttrs`` adds ``obj.awaitable_attrs.<relationship>`` for lazy navigation on async sessions.
    """

    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy reads this class attribute once at mapping time
        dict[str, Any]: JSONType,
        list[str]: JSONType,
        list[int]: JSONType,
        list[float]: JSONType,
        list[list[int]]: JSONType,
        dt.datetime: DateTime(timezone=True),
    }
