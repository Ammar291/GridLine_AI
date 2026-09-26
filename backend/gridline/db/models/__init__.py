"""All SQLAlchemy mapped classes, registered on the single ``gridline.db.base.Base``.

Importing this package registers every table on ``Base.metadata``. Add new model modules here (one import line
each) rather than creating a second declarative base anywhere.
"""

from gridline.db.base import Base
from gridline.db.models.city import Catchment, City, ElevationPoint, GeologicalZone, SoilProfile, Zone
from gridline.db.models.emergency import (
    Ambulance,
    Crew,
    FireStation,
    FireTruck,
    Hospital,
    HospitalBed,
    PoliceStation,
    Shelter,
)
from gridline.db.models.geography import FloodPlain, Hill, River, Slope
from gridline.db.models.history import HistoricalIncident, HistoricalIncidentImpact, InfrastructureChange
from gridline.db.models.infrastructure import Bridge, Dam, DrainageChannel, PumpUnit, Road, Tunnel
from gridline.db.models.knowledge import (
    EMBEDDING_DIMENSION,
    Chunk,
    Document,
    DocumentSection,
    PolicyThreshold,
)
from gridline.db.models.operations import (
    Action,
    Alert,
    BedReservation,
    ConstructionRestriction,
    EvacuationOrder,
    Incident,
    Task,
)
from gridline.db.models.population import ResidentialArea, School, ZoneYearlyStats
from gridline.db.models.utilities import (
    CriticalInfrastructure,
    PowerSubstation,
    Project,
    Sensor,
    WaterFacility,
)

# The 38 static/seeded tables of the city data layer (spec §5-§6). ``chunks`` belongs to the RAG layer.
EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "city",
        "zones",
        "catchments",
        "geological_zones",
        "soil_profiles",
        "elevation_points",
        "rivers",
        "hills",
        "slopes",
        "flood_plains",
        "drainage_channels",
        "pump_units",
        "roads",
        "bridges",
        "tunnels",
        "dams",
        "power_substations",
        "water_facilities",
        "projects",
        "critical_infrastructure",
        "sensors",
        "hospitals",
        "hospital_beds",
        "ambulances",
        "fire_stations",
        "fire_trucks",
        "police_stations",
        "crews",
        "shelters",
        "zone_yearly_stats",
        "residential_areas",
        "schools",
        "infrastructure_changes",
        "historical_incidents",
        "historical_incident_impacts",
        "documents",
        "document_sections",
        "policy_thresholds",
    }
)

# Tables written only by the city operations tools (gridline/tools); empty after seeding.
OPERATIONS_TABLES: frozenset[str] = frozenset(
    {
        "incidents",
        "alerts",
        "evacuation_orders",
        "construction_restrictions",
        "tasks",
        "bed_reservations",
        "actions",
    }
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "EXPECTED_TABLES",
    "OPERATIONS_TABLES",
    "Action",
    "Alert",
    "Ambulance",
    "Base",
    "BedReservation",
    "Bridge",
    "Catchment",
    "Chunk",
    "City",
    "ConstructionRestriction",
    "Crew",
    "CriticalInfrastructure",
    "Dam",
    "Document",
    "DocumentSection",
    "DrainageChannel",
    "ElevationPoint",
    "EvacuationOrder",
    "FireStation",
    "FireTruck",
    "FloodPlain",
    "GeologicalZone",
    "Hill",
    "HistoricalIncident",
    "HistoricalIncidentImpact",
    "Hospital",
    "HospitalBed",
    "Incident",
    "InfrastructureChange",
    "PoliceStation",
    "PolicyThreshold",
    "PowerSubstation",
    "Project",
    "PumpUnit",
    "ResidentialArea",
    "River",
    "Road",
    "School",
    "Sensor",
    "Shelter",
    "SoilProfile",
    "Slope",
    "Task",
    "Tunnel",
    "WaterFacility",
    "Zone",
    "ZoneYearlyStats",
]
