"""The knowledge graph's edge schema, taken from the city database's own references (no second graph store).

Every foreign key the dataset declares in ``gridline.city.references.REFERENCES`` is an edge type, plus the
historical-incident keys (seeded from the corpus, so not in that list) and the polymorphic ``asset_kind`` +
``asset_id`` links of incident impacts and infrastructure changes.
"""

from pydantic import BaseModel, ConfigDict

from gridline.city.references import ASSET_KINDS, REFERENCES

HISTORY_REFERENCES: tuple[tuple[str, str, str], ...] = (
    ("historical_incidents", "primary_zone_id", "zones"),
    ("historical_incidents", "zone_ids", "zones"),
    ("historical_incidents", "slope_id", "slopes"),
)

# Readable relation names for the edges reasoning leans on; any other edge is named after its column.
LABELS: dict[tuple[str, str], str] = {
    ("projects", "slope_id"): "located on",
    ("projects", "zone_id"): "in zone",
    ("projects", "nearest_channel_id"): "beside drain",
    ("projects", "flood_plain_id"): "on flood plain",
    ("slopes", "zone_id"): "in zone",
    ("slopes", "hill_id"): "on hill",
    ("slopes", "toe_channel_id"): "toe drains into",
    ("drainage_channels", "upstream_zone_id"): "drains",
    ("drainage_channels", "downstream_zone_id"): "flows to",
    ("drainage_channels", "outfall_river_id"): "outfalls to",
    ("drainage_channels", "outfall_channel_id"): "outfalls to",
    ("zones", "drains_to_channel_id"): "drains into",
    ("residential_areas", "zone_id"): "population in",
    ("residential_areas", "slope_id"): "population on",
    ("residential_areas", "flood_plain_id"): "population on flood plain",
    ("residential_areas", "nearest_channel_id"): "population beside",
    ("roads", "zone_id"): "road in",
    ("roads", "from_zone_id"): "road from",
    ("roads", "to_zone_id"): "road to",
    ("hospitals", "zone_id"): "hospital in",
    ("shelters", "zone_id"): "shelter in",
    ("crews", "location_zone_id"): "crew located in",
    ("crews", "base_zone_id"): "crew based in",
    ("historical_incidents", "primary_zone_id"): "occurred in",
    ("historical_incidents", "zone_ids"): "affected zone",
    ("historical_incidents", "slope_id"): "occurred on",
}


class EdgeType(BaseModel):
    model_config = ConfigDict(frozen=True)

    table: str
    field: str
    target: str
    label: str

    @property
    def many(self) -> bool:
        """``*_ids`` columns hold a JSON list of targets."""
        return self.field.endswith("_ids")


class AssetLink(BaseModel):
    """Rows of ``table`` link their owner (``owner_field`` -> ``owner_table``) to any asset by kind and id."""

    model_config = ConfigDict(frozen=True)

    table: str
    owner_field: str
    owner_table: str
    label: str


def _label(table: str, field: str) -> str:
    return LABELS.get((table, field), field.removesuffix("_ids").removesuffix("_id").replace("_", " "))


EDGE_TYPES: tuple[EdgeType, ...] = tuple(
    EdgeType(table=t, field=f, target=dst, label=_label(t, f))
    for t, f, dst in (*REFERENCES, *HISTORY_REFERENCES)
)

ASSET_LINKS: tuple[AssetLink, ...] = (
    AssetLink(
        table="historical_incident_impacts",
        owner_field="incident_id",
        owner_table="historical_incidents",
        label="impacted",
    ),
    AssetLink(
        table="infrastructure_changes",
        owner_field="id",
        owner_table="infrastructure_changes",
        label="changed",
    ),
)

ASSET_TABLES = dict(ASSET_KINDS)  # asset_kind -> table
KIND_OF_TABLE = {table: kind for kind, table in ASSET_KINDS.items()}

# Hub or reference tables that would connect everything to everything; traversal does not enter them.
SKIPPED_TABLES: frozenset[str] = frozenset(
    {
        "documents",
        "policy_thresholds",
        "catchments",
        "geological_zones",
        "soil_profiles",
        "zone_yearly_stats",
        "hospital_beds",
        "sensors",
    }
)
