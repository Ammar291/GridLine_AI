"""Shared Pydantic bases for the YAML / front-matter boundary of the city data layer.

Every record forbids unknown keys, so a typo in a YAML file fails validation instead of being dropped.
"""

from pydantic import BaseModel, ConfigDict


class Record(BaseModel):
    """A row of a YAML table; ``id`` is the primary key exactly as in the spec."""

    model_config = ConfigDict(extra="forbid")

    id: str


class Located(Record):
    """A record with a schematic position; its ``elevation_m`` is computed by the seed, never typed."""

    x_m: int
    y_m: int
