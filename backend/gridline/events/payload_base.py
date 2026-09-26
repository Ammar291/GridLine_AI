"""The base of every event payload model; a leaf module, so models outside ``events`` can extend it."""

from pydantic import BaseModel, ConfigDict


class Payload(BaseModel):
    # A serialized payload carries every field, so the published (serialization) schema marks all required.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)
