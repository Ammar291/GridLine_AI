"""All SQLAlchemy mapped classes, registered on the single ``gridline.db.base.Base``.

Importing this package registers every table on ``Base.metadata``. Add new model modules here (one import line
each) rather than creating a second declarative base anywhere.
"""

from gridline.db.base import Base
from gridline.db.models.knowledge import (
    EMBEDDING_DIMENSION,
    Chunk,
    Document,
    DocumentSection,
    PolicyThreshold,
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "Base",
    "Chunk",
    "Document",
    "DocumentSection",
    "PolicyThreshold",
]
