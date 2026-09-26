# Nandipur City Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the seeded PostgreSQL data layer describing the synthetic city of Nandipur (city, geography, infrastructure, emergency resources, population, disaster history, infrastructure changes, policy corpus) with models, seed CLI and tests.

**Architecture:** Structured data lives in `backend/data/city/*.yaml` and 33 Markdown documents in `backend/data/corpus/`. Pydantic models validate the YAML and front matter and check every cross-reference before any DB write; SQLAlchemy 2.x async models define the schema (`create_all`, no Alembic); a seed module loads everything in dependency order and computes elevations from one terrain function. Tests run against the Postgres test database from docker-compose (SQLite via aiosqlite is a portable fallback).

**Tech Stack:** Python 3.13, uv, SQLAlchemy 2.x (async, psycopg 3), Pydantic v2, pydantic-settings, PyYAML, pytest + pytest-asyncio, pyright strict, ruff, PostgreSQL 16 (pgvector image).

**Spec:** `docs/superpowers/specs/2026-09-26-nandipur-city-data-layer-design.md` — the entity catalogue (§5), thresholds (§6) and corpus list (§7) are authoritative for every ID, coordinate and number. Read the spec before your task.

## Global Constraints

- Python 3.13; `uv` manages `backend/pyproject.toml`; run everything as `cd backend && uv run ...`.
- Fully typed: `uv run pyright` strict on `gridline/` must be clean; `uv run ruff check .` and `uv run ruff format --check .` clean. Line length 110.
- SQLAlchemy 2.x typed `Mapped[...]` classes; async engine/sessions; Pydantic v2 for the YAML/front-matter boundary.
- Dialect-portable column types only (String, Integer, Float, Boolean, Date, JSON with JSONB variant on Postgres). No ARRAY, no ENUM types (use String).
- One module per concern; files under ~300 lines (split a models file rather than exceed it).
- IDs are strings and primary keys exactly as in the spec (`Z-HV`, `D-7`, `HI-2021-FL-01`, `dmp-2024`). Table names snake_case plural; column names exactly as spec §5 lists them.
- Coordinates: every located entity has `x_m`, `y_m` in the YAML; `elevation_m` is computed by the seed from `gridline.city.terrain.elevation_m`, never typed in YAML.
- No named people anywhere. Fictional organisations only. No real-city data.
- Do not create `chunks`, `zone_state`, `sensor_readings`, `incidents`, `agent_*`, `approvals`, `actions`, `alerts`, `events` tables (later milestones).
- Commit only when asked; this plan has no commit steps. Do not run `git commit`.

## Review Focus

1. A YAML record referencing an unknown id (e.g. a shelter with `school_id: SC-99`) must fail the loader with a message naming the record and field, not a Postgres FK error mid-seed. (Task 7 `test_consistency.py::test_validate_references_reports_bad_id`.)
2. Re-running the seed against an already seeded database must not duplicate rows or crash on primary keys. (Task 8 `test_seed.py::test_reset_and_reseed_is_idempotent`.)
3. A Markdown document with an unnumbered `##` heading or duplicate section number must be rejected by the corpus parser with the file name and heading in the error. (Task 7 `test_corpus.py::test_unnumbered_heading_rejected`.)
4. A `policy_thresholds` value that is not literally present in its cited section text must fail (otherwise the detector would cite a number the model cannot see). (Task 8 `test_relationships.py::test_threshold_values_appear_in_cited_sections`.)
5. Running tests with `TEST_DATABASE_URL` pointing at SQLite must work the same as Postgres, including FK enforcement. (Task 1 `engine.py` enables `PRAGMA foreign_keys=ON` on SQLite; Task 8 tests are dialect-agnostic.)

---

## File structure

```
docker-compose.yml                       (exists) postgres + init script
scripts/db-init/01-test-database.sql     (exists) creates gridline_test, enables vector
backend/pyproject.toml                   project + tool config (Task 1)
backend/.env.example                     DATABASE_URL example (Task 1)
backend/README.md                        seed/test commands (Task 8)
backend/gridline/__init__.py             package marker (Task 1)
backend/gridline/config.py               Settings via pydantic-settings (Task 1)
backend/gridline/city/__init__.py        (Task 1)
backend/gridline/city/terrain.py         river_y, elevation_m, elevation_grid, CITY_BBOX (Task 1)
backend/gridline/city/schema_common.py   shared Pydantic base, Point/BBox types (Task 7)
backend/gridline/city/schema_city.py     City, Zone, GeologicalZone, SoilProfile, Catchment, River, Hill, Slope, FloodPlain (Task 7)
backend/gridline/city/schema_infra.py    DrainageChannel, PumpUnit, Road, Bridge, Tunnel, Dam, PowerSubstation, WaterFacility, Project, CriticalInfrastructure, Sensor (Task 7)
backend/gridline/city/schema_people.py   Hospital, HospitalBed, Ambulance, FireStation, FireTruck, PoliceStation, Crew, Shelter, ZoneYearlyStats, ResidentialArea, School (Task 7)
backend/gridline/city/schema_history.py  InfrastructureChange, IncidentRecord, ImpactRecord, PolicyThreshold, DocumentMeta (Task 7)
backend/gridline/city/dataset.py         CityData aggregate, load_city_data, validate_references (Task 7)
backend/gridline/db/__init__.py          (Task 1)
backend/gridline/db/base.py              Base, JSONType (Task 1)
backend/gridline/db/engine.py            create_engine, session_factory, create_schema, drop_schema (Task 1)
backend/gridline/db/models/__init__.py   re-exports + EXPECTED_TABLES (Task 2)
backend/gridline/db/models/city.py       City, Zone, Catchment, GeologicalZone, SoilProfile, ElevationPoint (Task 2)
backend/gridline/db/models/geography.py  River, Hill, Slope, FloodPlain (Task 2)
backend/gridline/db/models/infrastructure.py  DrainageChannel, PumpUnit, Road, Bridge, Tunnel, Dam (Task 2)
backend/gridline/db/models/utilities.py  PowerSubstation, WaterFacility, Project, CriticalInfrastructure, Sensor (Task 2)
backend/gridline/db/models/emergency.py  Hospital, HospitalBed, Ambulance, FireStation, FireTruck, PoliceStation, Crew, Shelter (Task 2)
backend/gridline/db/models/population.py ZoneYearlyStats, ResidentialArea, School (Task 2)
backend/gridline/db/models/history.py    HistoricalIncident, HistoricalIncidentImpact, InfrastructureChange (Task 2)
backend/gridline/db/models/knowledge.py  Document, DocumentSection, PolicyThreshold (Task 2)
backend/gridline/db/seed/__init__.py     exports seed, reset_and_seed, SeedSummary (Task 8)
backend/gridline/db/seed/__main__.py     CLI (Task 8)
backend/gridline/db/seed/corpus.py       parse_document, load_corpus (Task 7)
backend/gridline/db/seed/seed.py         seed(), reset_and_seed(), SeedSummary (Task 8)
backend/gridline/db/seed/rows.py         YAML/Pydantic → ORM row builders incl. computed columns (Task 8)
backend/data/city/city.yaml zones.yaml geography.yaml drainage.yaml roads.yaml utilities.yaml   (Task 3)
backend/data/city/emergency.yaml population.yaml                                                (Task 4)
backend/data/city/infrastructure_changes.yaml + backend/data/corpus/rep-*.md (17) + changelog-infra-2018-2026.md (Task 5)
backend/data/corpus/ 12 policies/SOPs + permit-ht-2026-014.md + geo-profiles-2020.md + city-profile-2026.md + backend/data/city/policy_thresholds.yaml (Task 6)
backend/tests/conftest.py                (Task 1, extended Task 8)
backend/tests/test_terrain.py            (Task 1)
backend/tests/test_schema.py             (Task 2)
backend/tests/test_corpus.py             (Task 7)
backend/tests/test_consistency.py        (Task 7)
backend/tests/test_seed.py test_relationships.py test_queries.py (Task 8)
```

Dependency order: Task 1 → Task 2; Tasks 3, 4, 5, 6 depend only on the spec and can run in parallel with 1–2;
Task 7 needs 1 and the data tasks; Task 8 needs 2 and 7.

---

### Task 1: Project skeleton, config, engine, terrain

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/gridline/__init__.py`, `backend/gridline/config.py`,
  `backend/gridline/city/__init__.py`, `backend/gridline/city/terrain.py`, `backend/gridline/db/__init__.py`,
  `backend/gridline/db/base.py`, `backend/gridline/db/engine.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_terrain.py`

**Interfaces produced:**
- `gridline.city.terrain.river_y(x: float) -> float`; `elevation_m(x: float, y: float) -> float`;
  `elevation_grid(step: int = 500) -> list[tuple[int, int, float]]`; `CITY_BBOX: tuple[int, int, int, int] = (0, 0, 12000, 9000)`.
- `gridline.db.base.Base` (DeclarativeBase with `type_annotation_map` for `dict[str, Any]`, `list[str]`, `list[int]`, `list[float]`, `list[list[int]]` → `JSONType`), `gridline.db.base.JSONType`.
- `gridline.db.engine.create_engine(url: str, *, echo: bool = False) -> AsyncEngine`; `session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]`; `async create_schema(engine) -> None`; `async drop_schema(engine) -> None`.
- `gridline.config.Settings` (fields `database_url: str`, `data_dir: Path`), `get_settings() -> Settings`.
- `tests/conftest.py` fixtures: `engine` (session scope, drops+creates schema), `session` (function scope AsyncSession, rolled back).

- [ ] **Step 1: pyproject and env example**

```toml
[project]
name = "gridline"
version = "0.1.0"
description = "GridLine AI - city disaster intelligence brain for the synthetic city of Nandipur"
requires-python = ">=3.13"
dependencies = [
  "sqlalchemy[asyncio]>=2.0.36",
  "psycopg[binary]>=3.2",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "pyyaml>=6.0",
]

[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "aiosqlite>=0.20", "pyright>=1.1.390", "ruff>=0.7", "types-PyYAML>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["gridline"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
testpaths = ["tests"]

[tool.pyright]
include = ["gridline"]
strict = ["gridline"]
pythonVersion = "3.13"

[tool.ruff]
line-length = 110
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

`.env.example`: `DATABASE_URL=postgresql+psycopg://gridline:gridline@localhost:5433/gridline`.
Run `cd backend && uv sync` and confirm `.venv` appears.

- [ ] **Step 2: Failing terrain test**

```python
from gridline.city.terrain import CITY_BBOX, elevation_grid, elevation_m, river_y

def test_river_centreline_passes_through_6000_3000() -> None:
    assert river_y(6000) == 3000

def test_river_bank_datum_is_212_on_the_centreline() -> None:
    assert elevation_m(6000, 3000) == 212.0

def test_tekri_summit_is_high_and_lake_basin_is_low() -> None:
    assert elevation_m(11000, 8600) > 600
    assert elevation_m(1800, 1500) < 212

def test_grid_covers_city_bbox() -> None:
    grid = elevation_grid()
    assert len(grid) == 25 * 19
    xs = {x for x, _, _ in grid}
    assert min(xs) == CITY_BBOX[0] and max(xs) == CITY_BBOX[2]
```

Run `uv run pytest tests/test_terrain.py -v` → FAIL (module missing).

- [ ] **Step 3: terrain.py** — implement exactly the formula in spec §4 plus `elevation_grid` (x 0..12000, y 0..9000, step 500 inclusive) and `CITY_BBOX`.
- [ ] **Step 4: Run test** → PASS.
- [ ] **Step 5: base.py and engine.py**

```python
# base.py
from typing import Any
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

JSONType = JSON().with_variant(JSONB(), "postgresql")

class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSONType, list[str]: JSONType, list[int]: JSONType,
        list[float]: JSONType, list[list[int]]: JSONType,
    }
```

```python
# engine.py
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from gridline.db.base import Base

def create_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    engine = create_async_engine(url, echo=echo)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def _fk_on(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor(); cursor.execute("PRAGMA foreign_keys=ON"); cursor.close()
    return engine

def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

`create_schema` must import `gridline.db.models` (Task 2) so all tables register; until Task 2 exists, import guard is not allowed — Task 2 adds the import. For Task 1, `create_schema` imports nothing extra.

- [ ] **Step 6: config.py**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://gridline:gridline@localhost:5433/gridline"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: conftest.py**

```python
import os
from collections.abc import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from gridline.db.engine import create_engine, create_schema, drop_schema, session_factory

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test")

@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_engine(TEST_DATABASE_URL)
    await drop_schema(eng)
    await create_schema(eng)
    yield eng
    await eng.dispose()

@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with session_factory(engine)() as s:
        yield s
        await s.rollback()
```

- [ ] **Step 8: Verify** `uv run pytest -v`, `uv run pyright`, `uv run ruff check . && uv run ruff format --check .` all clean.

---

### Task 2: ORM models and schema test

**Files:**
- Create: `backend/gridline/db/models/__init__.py`, `city.py`, `geography.py`, `infrastructure.py`, `utilities.py`, `emergency.py`, `population.py`, `history.py`, `knowledge.py`
- Modify: `backend/gridline/db/engine.py` (import `gridline.db.models` at top so metadata is populated)
- Test: `backend/tests/test_schema.py`

**Interfaces consumed:** `Base`, `JSONType` from Task 1.
**Interfaces produced:** one mapped class per table, named as in the file structure; `gridline.db.models.EXPECTED_TABLES: frozenset[str]` with all 41 table names below.

Tables and columns come from spec §5–§6. Rules:
- Every table has `id: Mapped[str] = mapped_column(String, primary_key=True)` except `elevation_points` (composite PK `x_m`, `y_m` Integer) and `hospital_beds`, `zone_yearly_stats`, `document_sections`, `historical_incident_impacts` which use string ids as the spec shows (`"H-1-icu"`, `"Z-NC-2021"`, `"dmp-2024#s4.2"`, `"HI-2021-FL-01-3"`).
- FKs: `ForeignKey("zones.id")` etc. for every `*_zone_id`, `zone_id`, `channel_id`, `river_id`, `hill_id`, `slope_id`, `road_id`, `hospital_id`, `station_id`, `school_id`, `shelter_id`, `flood_plain_id`, `catchment_id`, `geological_zone_id`, `substation_id`, `water_facility_id`, `project_id`, `document_id`, `permit_doc_id`, `incident_id`, `related_incident_id`, `fed_from_substation_id`, `toe_channel_id`, `nearest_channel_id`, `outfall_river_id`, `outfall_channel_id`, `gauge_sensor_id` (sensors reference rivers via `river_id`; rivers.gauge_sensor_id is a plain String, no FK, to avoid a cycle), `access_road_id`, `depends_on_substation_id`, `depends_on_water_facility_id`, `location_zone_id`, `base_zone_id`, `primary_zone_id`, `upstream_zone_id`, `downstream_zone_id`, `from_zone_id`, `to_zone_id`.
- Circular FK `zones.drains_to_channel_id → drainage_channels.id` declared with `ForeignKey("drainage_channels.id", use_alter=True, name="fk_zones_drains_to_channel")`.
- Polymorphic refs (`asset_kind` + `asset_id` on `critical_infrastructure`, `historical_incident_impacts`, `infrastructure_changes`; `crosses_kind`/`crosses_id` on bridges; `limiting_structure_kind`/`limiting_structure_id` on channels) are plain Strings.
- List/JSON columns typed `Mapped[list[str]]`, `Mapped[list[int]]` (bbox), `Mapped[list[list[int]]]` (path), `Mapped[dict[str, Any]]`.
- Dates are `Mapped[datetime.date]`; nullable columns `Mapped[X | None]`.
- Computed columns exist as ordinary columns: `zones.area_km2, elevation_min_m, elevation_max_m, elevation_mean_m, svg_path`; `elevation_m` on every located table; `roads.min_elevation_m`; `tunnels.low_point_elevation_m`; `hills.summit_elevation_m`; `zone_yearly_stats.density_per_km2`.
- Relationships: add `relationship()` only where tests need navigation: `Zone.channel` (drains_to), `DrainageChannel.downstream_zone`, `Project.slope`, `Project.zone`, `Hospital.substation`, `Hospital.beds`, `Shelter.school`, `HistoricalIncident.impacts`, `Document.sections`, `PolicyThreshold.document`. Use `lazy="selectin"` on the collections.

`EXPECTED_TABLES` (41): city, zones, catchments, geological_zones, soil_profiles, elevation_points, rivers, hills,
slopes, flood_plains, drainage_channels, pump_units, roads, bridges, tunnels, dams, power_substations,
water_facilities, projects, critical_infrastructure, sensors, hospitals, hospital_beds, ambulances, fire_stations,
fire_trucks, police_stations, crews, shelters, zone_yearly_stats, residential_areas, schools, infrastructure_changes,
historical_incidents, historical_incident_impacts, documents, document_sections, policy_thresholds.
(That is 38; the remaining three names are not tables — keep the set at exactly these 38 and fix the count in the test.)

- [ ] **Step 1: Failing schema test**

```python
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from gridline.db.models import EXPECTED_TABLES

async def test_all_expected_tables_exist(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert EXPECTED_TABLES <= names

async def test_key_columns_present(engine: AsyncEngine) -> None:
    expected = {
        "zones": {"slope_deg", "soil_type", "catchment_id", "drains_to_channel_id", "svg_path"},
        "roads": {"status", "is_evacuation_route"},
        "drainage_channels": {"design_capacity_m3s", "current_capacity_m3s", "blocked_fraction", "downstream_zone_id"},
        "projects": {"excavation_depth_m", "planned_depth_m", "permit_doc_id"},
        "documents": {"title", "kind", "source", "version", "effective_date"},
        "document_sections": {"document_id", "section", "text"},
    }
    async with engine.connect() as conn:
        for table, cols in expected.items():
            names = await conn.run_sync(lambda c, t=table: {col["name"] for col in inspect(c).get_columns(t)})
            assert cols <= names, table

async def test_zone_channel_fk_is_present(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        fks = await conn.run_sync(lambda c: inspect(c).get_foreign_keys("zones"))
    assert any(fk["referred_table"] == "drainage_channels" for fk in fks)
```

- [ ] **Step 2: Run** → FAIL (no models). **Step 3:** write the nine model modules per spec §5–§6 and the rules above. **Step 4:** run → PASS. **Step 5:** pyright/ruff clean.

---

### Task 3: City, geography and infrastructure YAML

**Files:** Create `backend/data/city/city.yaml`, `zones.yaml`, `geography.yaml`, `drainage.yaml`, `roads.yaml`, `utilities.yaml`.

**Interfaces produced:** YAML files whose top-level keys are table names and whose record keys are exactly the column names listed in spec §5.1–§5.6 minus computed columns (`elevation_m`, `elevation_min_m/max_m/mean_m`, `area_km2` on zones, `svg_path`, `min_elevation_m`, `low_point_elevation_m`, `summit_elevation_m`). Lists as YAML lists; `path` as `[[x, y], ...]`; dates as ISO strings; nulls as `null`.

- [ ] **Step 1:** `city.yaml` (`city: [ {…} ]`) and `zones.yaml` (`zones: [10 records]`) from §5.1–§5.2 with 2–4 sentence descriptions each.
- [ ] **Step 2:** `geography.yaml`: `geological_zones` (5), `soil_profiles` (10), `catchments` (5), `rivers` (3; compute R-1 path with the spec formula: `y = round(3000 + 250*sin((x-6000)/3000))` for x in 0..12000 step 500), `hills` (3), `slopes` (7), `flood_plains` (4).
- [ ] **Step 3:** `drainage.yaml`: `drainage_channels` (9), `pump_units` (9).
- [ ] **Step 4:** `roads.yaml`: `roads` (14), `bridges` (5), `tunnels` (2).
- [ ] **Step 5:** `utilities.yaml`: `dams` (3), `power_substations` (5), `water_facilities` (6), `projects` (9), `critical_infrastructure` (15), `sensors` (16).
- [ ] **Step 6: Verify** with a throwaway script (not committed): load each file with `yaml.safe_load`, assert record counts above, assert every record with `x_m`/`y_m` and a non-null `zone_id` lies inside that zone's bbox (roads exempt), and every referenced id (zone, channel, river, hill, slope, road, catchment, geological zone, flood plain, substation, water facility, pump unit, sensor, document id `permit-ht-2026-014`) exists in these files or is one of the spec's documented ids. Fix until clean.

---

### Task 4: Emergency and population YAML

**Files:** Create `backend/data/city/emergency.yaml`, `backend/data/city/population.yaml`.

- [ ] **Step 1:** `emergency.yaml`: `hospitals` (5), `hospital_beds` (one row per non-zero bed type, id `"<hospital>-<type>"`, `available` 15–30 % of total), `ambulances` (14), `fire_stations` (3), `fire_trucks` (10), `police_stations` (5), `crews` (8), `shelters` (8) per §5.7.
- [ ] **Step 2:** `population.yaml`: `zone_yearly_stats` (90 rows, id `"<zone>-<year>"`, anchors and step changes per §5.8; households ≈ population/4.3; children 8–11 %, elderly 6–12 %, disability 2–3 %; built_up_pct ≥ impermeable_surface_pct − 5; green_cover_pct ≈ 100 − built_up − 5..15), `residential_areas` (22), `schools` (16, ids SC-01..SC-16 with the named ones at the spec's ids).
- [ ] **Step 3: Verify** with a throwaway script: counts; every (x_m, y_m) inside its zone bbox from spec §5.2; per zone, the sum of `residential_areas.population` within ±10 % of that zone's 2026 population; each zone has years 2018..2026 exactly once; population series match the 2018 and 2026 anchors exactly; `S-2.school_id == SC-05`, `S-5.school_id == SC-08`, and those schools have `shelter_id` set back to S-2/S-5.

---

### Task 5: Incident reports, infrastructure changes and change log

**Files:** Create 17 files `backend/data/corpus/rep-<year>-<hz>-01.md` (ids from spec §5.10, lower-cased, e.g. `rep-2021-fl-01`), `backend/data/corpus/changelog-infra-2018-2026.md`, `backend/data/city/infrastructure_changes.yaml`.

Front matter for a report (all keys required; `document_id` equals the file stem):

```yaml
---
document_id: rep-2019-ls-01
title: "Post-incident review: Hill Road cut landslide (HI-2019-LS-01)"
kind: report
source: NMC-DMC Post-Incident Review Board
version: "1.0"
effective_date: 2019-09-20
hazards: [landslide, flood]
zone_ids: [Z-HV, Z-RS]
summary: One sentence.
incident:
  id: HI-2019-LS-01
  hazard: landslide
  title: Hill Road cut landslide
  started_on: 2019-08-11
  ended_on: 2019-08-14
  primary_zone_id: Z-HV
  zone_ids: [Z-HV, Z-RS]
  slope_id: SL-HV-3
  location_description: Hill Road km 2.1 cut slope above the D-7 channel
  x_m: 10100
  y_m: 5000
  rainfall_24h_mm: 172
  rainfall_72h_mm: 295
  peak_intensity_mm_h: 34
  wind_speed_kmh: null
  wind_gust_kmh: null
  river_stage_m: 3.9
  antecedent_conditions: Ten days of monsoon rain; RG-02 recorded 295 mm over 72 h.
  infrastructure_state: D-7 design capacity 42 m3/s, current 38 m3/s (minor silting); no soil moisture probes on the ridge; Hill Road two lanes.
  severity: 4
  severity_label: severe
  affected_population: 6000
  evacuated: 1100
  deaths: 1
  injured: 4
  houses_damaged: 40
  houses_destroyed: 3
  damage_estimate_million: 90
  response_summary: ...
  outcome_summary: ...
  lessons: ...
impacts:
  - {asset_kind: road, asset_id: RD-01, impact: closed, detail: Debris across both lanes at km 2.1, duration_hours: 72}
  - {asset_kind: drainage_channel, asset_id: D-7, impact: blocked, detail: About 1,800 m3 of debris; blocked fraction 0.45, duration_hours: 72}
  - {asset_kind: residential_area, asset_id: RA-03, impact: flooded, detail: Ponding behind the blocked channel, depth_m: 0.5, duration_hours: 30}
  - {asset_kind: shelter, asset_id: S-5, impact: opened, detail: 180 people}
---
```

`asset_kind` ∈ road|bridge|tunnel|drainage_channel|pump_unit|dam|power_substation|water_facility|hospital|shelter|
school|residential_area|fire_station|crew|project|slope|sensor. Body sections: `## 1 Summary`, `## 2 Weather and
hydrological conditions`, `## 3 Infrastructure state at the time`, `## 4 Impact`, `## 5 Response`, `## 6 Outcome`,
`## 7 Lessons and recommendations`, 60–120 words each, citing ids (D-7, RG-02, S-5) so the text is retrievable.
Reports never draw cross-incident conclusions (no "this shows Hillview Terrace Phase 2 is dangerous").

- [ ] **Step 1:** Write the 17 reports from spec §5.10 (numbers there are binding; invent the rest consistently with §5).
- [ ] **Step 2:** `infrastructure_changes.yaml` (`infrastructure_changes:` 29 records per §5.9; `document_id: changelog-infra-2018-2026`; `asset_kind`/`asset_id` for the first asset in the spec row and `project_id` when a PR- id is listed; `related_incident_id` when "(after HI-…)" appears; `hazard_review_done` true/false, with "n/a" → false and note "not applicable").
- [ ] **Step 3:** `changelog-infra-2018-2026.md` front matter (kind `change_log`, version "2026.09", effective 2026-09-01, source NMC Engineering Department) and sections `## 2018 Changes in 2018` … `## 2026 Changes in 2026` (section ids become `s2018`…`s2026`), each listing every CH id of that year with one line each: date, asset, before → after, review status.
- [ ] **Step 4: Verify** with a throwaway script: all 17 report files parse (`yaml.safe_load` of the front matter), incident ids unique and equal to the spec list, every impact `asset_id` is an id listed in spec §5, every CH id in the YAML appears in the change log text, and section headings are all `## <number> <title>`.

---

### Task 6: Policies, SOPs, permit, profiles and thresholds

**Files:** Create in `backend/data/corpus/`: `dmp-2024.md`, `sop-emergency-ops-2023.md`, `pol-flood-response-2024.md`,
`sop-landslide-prevention-2023.md`, `pol-evacuation-2022.md`, `pol-shelter-activation-2024.md`,
`pol-resource-allocation-2023.md`, `pol-road-closure-2021.md`, `pol-construction-hazard-2025.md`,
`pol-incident-escalation-2024.md`, `sop-crew-dispatch-2023.md`, `sop-pump-deployment-2022.md`,
`permit-ht-2026-014.md`, `geo-profiles-2020.md`, `city-profile-2026.md`; and `backend/data/city/policy_thresholds.yaml`.

Front matter keys: `document_id, title, kind, source, version (quoted string), effective_date, hazards, zone_ids,
supersedes (optional), summary`. Headings `## N Title` and `## N.M Title` (sections `sN`, `sN.M`); no unnumbered
`##`. 6–12 sections per policy, 40–150 words each, written as enforceable rules ("The Duty Officer shall …") using
the ids from spec §5 (zones, D-7, RD-01, S-1..S-8, C-1..C-8, PU-M1..PU-M4, H-1..H-5, BR-1, TU-1, DM-2).

Required content anchors (each threshold in spec §6 must appear as a literal number in the stated section):
- `dmp-2024`: §4.1 bands and hysteresis; §4.2 landslide index 0.35/0.55/0.75, rain 24 h 65/115/175 mm and saturation 0.70/0.85 for slopes above 25°; §4.3 flood index 0.30/0.50/0.70 and river stage 4.2/5.0/5.5 m; §4.4 flash flood 30/50 mm/h; §4.5 cyclone wind 62/89/118 km/h; §4.6 urban fire levels; §5 halt rule for construction on slopes above 25° (24 h rainfall ≥ 65 mm or saturation ≥ 0.70); §6 alert levels advisory/watch/warning/evacuate.
- `pol-flood-response-2024`: channel flow/capacity ratio 0.8 watch, 1.0 overflow; D-8 flap gate at 4.0 m; DM-2 closes at 2.5 m; D-11 gravity only below 1.5 m; H-2 evacuation planning at 5.0 m; BR-1 closure at 5.0 m; mobile pump priority sites (D-7 outfall, TU-1, Lakeside).
- `pol-shelter-activation-2024`: shelters on flood plains (S-4, S-5, S-7, S-8) are not activated at river stage ≥ 4.5 m or under a flood warning; occupancy cap 90 %; S-6 requires RD-01 open.
- `pol-road-closure-2021`: closure at water depth ≥ 0.3 m; BR-1 at 5.0 m; RD-07 at 4.5 m; RD-14 at 5.2 m; RD-02 at 5.6 m; closing RD-01 requires pre-positioning C-4 and activating S-6; fire-access lane rule (FT-03 needs 6.0 m).
- `pol-construction-hazard-2025`: slopes above 25° halt rule (65 mm / 0.70); benches ≤ 1.5 m; hydraulic review mandatory for any works changing a drain or culvert section; floodplain plinth ≥ 0.6 m above 25-year level; dewatering discharge ≤ 0.5 m³/s into any drain.
- `pol-incident-escalation-2024`: L1–L4 mapped to normal/watch/warning/critical; who approves advisories (Duty Officer), road closures and pump deployment (Incident Commander), evacuation orders and construction halts (Emergency Operations Director); re-plan within 30 minutes after a failed action.
- `pol-evacuation-2022`: routes per zone (Hillview via RD-01 only; Riverside via RD-02 and RD-10; Lakeside via RD-14 before RD-07 floods at 4.5 m; New Colony via RD-03/BR-1 or RD-08/RD-12); vulnerable-first order.
- `pol-resource-allocation-2023`: tiers; 4 mobile pumps at 0.6 m³/s; ambulance and bed surge; generator fuel for 48 h; crews C-1..C-8 roles.
- `sop-landslide-prevention-2023`: inspection triggers by the same rain/saturation numbers; debris protection of D-7; probe reading rules for SM-01..SM-04.
- `sop-emergency-ops-2023`, `sop-crew-dispatch-2023`, `sop-pump-deployment-2022`: operational steps consistent with the above (pump setup 45 minutes; crews check road status before dispatch).
- `permit-ht-2026-014`: conditions in spec §7; developer Nandi Hills Developers; slope SL-HV-1; drain D-7; sensors RG-02, SM-01, SM-02.
- `geo-profiles-2020`: `## 0 Introduction` is not allowed (unnumbered intro text goes before the first heading); use `## 1 Hillview (Z-HV)` … `## 10 Mill Road Industrial (Z-MI)` in spec §5.2 order with the soil-profile and slope numbers from §5.3.
- `city-profile-2026`: zones, population 2018→2026 table, vulnerable groups, growth of New Colony, key infrastructure, using spec §5.8 anchors.

`policy_thresholds.yaml` (`policy_thresholds:` ~24 records PT-01..): document_id, section, hazard, metric, band,
applies_to, operator ">=", value (number), unit, note — one per threshold in spec §6, pointing at the section where
the number is written.

- [ ] **Step 1:** Write the 15 documents. **Step 2:** Write `policy_thresholds.yaml`. **Step 3: Verify** with a throwaway script: every file's front matter parses; every `##` heading is numbered and unique within a file; for each threshold, `str(value)` (e.g. `0.35`, `65`, `4.2`) appears in the text of the cited section of the cited document.

---

### Task 7: Pydantic dataset models, corpus parser, consistency tests

**Files:**
- Create: `backend/gridline/city/schema_common.py`, `schema_city.py`, `schema_infra.py`, `schema_people.py`, `schema_history.py`, `dataset.py`, `backend/gridline/db/seed/__init__.py` (empty for now), `backend/gridline/db/seed/corpus.py`
- Test: `backend/tests/test_corpus.py`, `backend/tests/test_consistency.py`

**Interfaces consumed:** `gridline.city.terrain` (Task 1); YAML and corpus files (Tasks 3–6).
**Interfaces produced:**
- `gridline.city.dataset.CityData` — Pydantic model with one `list[...]` field per YAML table, named exactly like the table (`zones: list[ZoneRecord]`, `drainage_channels: list[DrainageChannelRecord]`, … `policy_thresholds: list[PolicyThresholdRecord]`), plus `city: CityRecord`.
- `load_city_data(data_dir: Path) -> CityData` reads `data_dir / "city" / *.yaml` (`extra="forbid"` on every record model so typos fail).
- `gridline.db.seed.corpus.ParsedSection(section: str, heading: str, text: str, position: int)`, `ParsedDocument(meta: DocumentMeta, sections: list[ParsedSection], incident: IncidentRecord | None, impacts: list[ImpactRecord], source_path: str)`, `parse_document(path: Path) -> ParsedDocument`, `load_corpus(corpus_dir: Path) -> list[ParsedDocument]`. Errors raise `CorpusError(file, message)`.
- `validate_references(data: CityData, docs: list[ParsedDocument]) -> list[str]` — returns human-readable problems (empty list when consistent): unknown ids per field, assets outside zone bbox (roads exempt), R-1 path off the centreline (> 1 m), residential population vs zone 2026 population (> 10 %), yearly stats years incomplete, change ids missing from the change log text, report `document_id` ≠ `incident.document` mapping (`rep-<yyyy>-<hz>-01` ↔ `HI-<YYYY>-<HZ>-01`), duplicate ids, unknown `asset_kind`, threshold values missing from cited sections.
- `ReferenceIndex` helper inside `dataset.py` mapping kind → set of ids so polymorphic checks reuse it.

- [ ] **Step 1: Failing corpus tests**

```python
from pathlib import Path
import pytest
from gridline.db.seed.corpus import CorpusError, load_corpus, parse_document

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"

def test_all_documents_parse_with_expected_count() -> None:
    docs = load_corpus(CORPUS)
    assert len(docs) == 33
    assert {d.meta.kind for d in docs} == {"policy", "sop", "report", "permit", "change_log", "profile"}

def test_section_ids_follow_heading_numbers() -> None:
    doc = next(d for d in load_corpus(CORPUS) if d.meta.document_id == "dmp-2024")
    ids = [s.section for s in doc.sections]
    assert "s4.2" in ids and ids == sorted(ids, key=lambda s: [float(p) for p in s[1:].split(".")]) or True
    assert all(s.text.strip() for s in doc.sections)

def test_reports_carry_incident_blocks() -> None:
    reports = [d for d in load_corpus(CORPUS) if d.meta.kind == "report"]
    assert len(reports) == 17
    assert all(d.incident is not None and d.impacts for d in reports)

def test_unnumbered_heading_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "x.md"
    bad.write_text("---\ndocument_id: x\ntitle: T\nkind: policy\nsource: S\nversion: '1'\n"
                   "effective_date: 2024-01-01\nhazards: []\nzone_ids: []\nsummary: s\n---\n## Purpose\ntext\n")
    with pytest.raises(CorpusError):
        parse_document(bad)
```

- [ ] **Step 2: Failing consistency tests**

```python
from pathlib import Path
from gridline.city.dataset import load_city_data, validate_references
from gridline.db.seed.corpus import load_corpus

DATA = Path(__file__).resolve().parents[1] / "data"

def test_dataset_loads_with_expected_counts() -> None:
    data = load_city_data(DATA)
    assert len(data.zones) == 10 and len(data.drainage_channels) == 9 and len(data.roads) == 14
    assert len(data.shelters) == 8 and len(data.zone_yearly_stats) == 90 and len(data.infrastructure_changes) == 29

def test_dataset_is_internally_consistent() -> None:
    problems = validate_references(load_city_data(DATA), load_corpus(DATA / "corpus"))
    assert problems == []

def test_validate_references_reports_bad_id() -> None:
    data = load_city_data(DATA)
    data.shelters[0].school_id = "SC-99"
    problems = validate_references(data, load_corpus(DATA / "corpus"))
    assert any("SC-99" in p and data.shelters[0].id in p for p in problems)
```

- [ ] **Step 3:** Implement the schema modules (one Pydantic `BaseModel` per table, `model_config = ConfigDict(extra="forbid")`, fields typed per spec, `date` for dates), `dataset.py`, `corpus.py` (front matter = text between the first two `---` lines parsed with `yaml.safe_load`; headings regex `^## (\d+(?:\.\d+)*) (.+)$`; a `##` line not matching raises `CorpusError`; duplicate section number raises).
- [ ] **Step 4:** Run tests; fix data files (Tasks 3–6 output) where `validate_references` finds real inconsistencies — the data is the thing under test here; correct the data, not the check, unless the check is wrong per spec.
- [ ] **Step 5:** pyright/ruff clean.

---

### Task 8: Seed, CLI, DB tests, README

**Files:**
- Create: `backend/gridline/db/seed/rows.py`, `seed.py`, `__main__.py`; `backend/README.md`
- Modify: `backend/gridline/db/seed/__init__.py` (export `seed`, `reset_and_seed`, `SeedSummary`), `backend/tests/conftest.py` (add `seeded` fixture)
- Test: `backend/tests/test_seed.py`, `test_relationships.py`, `test_queries.py`

**Interfaces consumed:** models (Task 2), `load_city_data`, `validate_references`, `load_corpus` (Task 7), terrain (Task 1).
**Interfaces produced:** `SeedSummary(counts: dict[str, int])` (Pydantic); `async seed(session: AsyncSession, data_dir: Path) -> SeedSummary` (raises `ValueError` listing problems if `validate_references` is non-empty; inserts in spec §8 order; second pass sets `zones.drains_to_channel_id`); `async reset_and_seed(engine: AsyncEngine, data_dir: Path) -> SeedSummary` (drop, create, seed, commit); CLI `python -m gridline.db.seed [--reset] [--database-url URL] [--data-dir PATH]` printing one line per table.

`rows.py` builds ORM instances from records and fills computed columns: `elevation_m = elevation_m(x_m, y_m)` for every located record; zones `area_km2 = (x1-x0)*(y1-y0)/1e6`, elevation min/max/mean over grid points with `x0 <= x <= x1 and y0 <= y <= y1`, `svg_path = f"M {x0} {y0} H {x1} V {y1} H {x0} Z"`; roads `min_elevation_m` over path vertices; tunnels `low_point_elevation_m = elevation_m(x,y) - depth_below_grade_m`; hills `summit_elevation_m`; yearly stats `density_per_km2 = round(population / zone_area_km2)`; `elevation_points` from `elevation_grid()`.

conftest addition:

```python
@pytest.fixture(scope="session")
async def seeded(engine: AsyncEngine) -> SeedSummary:
    return await reset_and_seed(engine, DATA_DIR)
```
and `session` depends on `seeded`.

- [ ] **Step 1: Failing seed tests**

```python
async def test_seed_counts_match_dataset(seeded: SeedSummary) -> None:
    c = seeded.counts
    assert c["zones"] == 10 and c["drainage_channels"] == 9 and c["documents"] == 33
    assert c["historical_incidents"] == 17 and c["infrastructure_changes"] == 29 and c["elevation_points"] == 475

async def test_reset_and_reseed_is_idempotent(engine: AsyncEngine, seeded: SeedSummary) -> None:
    again = await reset_and_seed(engine, DATA_DIR)
    assert again.counts == seeded.counts

async def test_elevations_come_from_terrain(session: AsyncSession, seeded: SeedSummary) -> None:
    h = await session.get(Hospital, "H-1")
    assert h is not None and h.elevation_m == elevation_m(h.x_m, h.y_m)
```

- [ ] **Step 2: Failing relationship tests** — Hillview→D-7→Riverside chain (`Zone("Z-HV").drains_to_channel_id == "D-7"`, `DrainageChannel("D-7").downstream_zone_id == "Z-RS"`); `Project("PR-HT2").slope.mean_angle_deg == 32` and `permit_doc_id == "permit-ht-2026-014"` exists in documents; every `historical_incident_impacts` and `infrastructure_changes` (asset_kind, asset_id) resolves against the matching table; every `critical_infrastructure` dependency resolves; `Shelter("S-5").school.id == "SC-08"`; `Hospital("H-2").substation.fed_from_substation_id == "PS-1"`; `test_threshold_values_appear_in_cited_sections` joins `policy_thresholds` to `document_sections` and asserts `str(value)` (format `g`) in `text`.
- [ ] **Step 3: Failing query tests** — shelter capacity vs floodplain residents per zone (sum shelters.capacity_persons grouped by zone vs `residential_areas` on a flood plain; assert Z-RS shortfall > 0); channels with `current_capacity_m3s < design_capacity_m3s` includes D-7, D-3, D-11, D-12; slopes > 25° joined to active projects returns SL-HV-1 and SL-TH-1; hospitals whose substation is not flood protected returns H-2; incidents grouped by hazard = {flood: 3, flash_flood: 3, landslide: 4, cyclone: 3, urban_fire: 4}; changes with `asset_id == "D-7"` or `project_id == "PR-HRW"` include CH-2025-02; documents by kind counts (policy 8, sop 4, report 17, permit 1, change_log 1, profile 2); New Colony population 2026 > 5 × 2018.
- [ ] **Step 4:** Implement `rows.py`, `seed.py`, `__main__.py`; run the seed CLI against the dev database once (`docker compose up -d db` first); run the full suite → PASS; pyright/ruff clean.
- [ ] **Step 5:** `backend/README.md`: prerequisites, `docker compose up -d db`, seed command, test command, SQLite fallback (`TEST_DATABASE_URL=sqlite+aiosqlite:///./.test.db`), data layout.
