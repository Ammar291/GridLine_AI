# Nandipur synthetic city data layer — design

Date: 2026-09-26. Status: written under autonomous execution; the request in the brief was treated as the approved
design intent. Assumptions are marked **A#** and can be overridden after the fact.

## 1. Intent

Build the data layer for the GridLine AI brain described in [ARCHITECTURE.md](../../../ARCHITECTURE.md): a rich,
internally consistent synthetic description of the fictional city of Nandipur, covering city metadata, geography,
infrastructure, emergency resources, population, disaster history 2012–2026, infrastructure changes 2018–2026,
and the disaster-management knowledge corpus, plus the SQLAlchemy models, schema creation, seed scripts and tests.

The brief is broader than ARCHITECTURE.md §6 ("kept small enough to hold in one head"). The resolution is: keep every
entity, ID and number named in §4 and §6 exactly (zones, D-7, Hill Road, Riverside Bypass, HT-2026-014, RG-01..04,
SM-01..03, CL-D7, CL-D3, C-1..C-3, S-1..S-2, four pump units, the 2014/2019/2022 landslide reports and the 2021
flood report, halt rule for slopes above 25°) and extend around them. Nothing in §4's column lists is renamed.

Success criteria: (1) `uv run python -m gridline.db.seed --reset` builds the schema and loads every row from
`backend/data/`; (2) all tests pass against Postgres; (3) every cross-reference in the data resolves; (4) the data
contains relationships the agent can discover (examples in §9) that are never stated as conclusions anywhere.

Out of scope (later milestones): LangGraph, FastAPI app, WebSockets, frontend, simulation, RAG chunking/embeddings
(`chunks` table with `vector(384)`), and the dynamic tables `zone_state`, `sensor_readings`, `incidents`, `agent_runs`,
`agent_steps`, `approvals`, `actions`, `alerts`, `events`. This layer creates the static/seeded tables only; the
mutable "live" columns on them (`status`, `current_capacity_m3s`, `blocked_fraction`, `available` beds, occupancy)
are seeded to their initial values.

## 2. Technology and conventions

- Python 3.13, uv, `backend/pyproject.toml`. Dependencies now: `sqlalchemy[asyncio]`, `psycopg[binary]`, `pydantic`,
  `pydantic-settings`, `pyyaml`. Dev: `pytest`, `pytest-asyncio`, `aiosqlite`, `pyright`, `ruff`. **A1:** `fastapi`,
  `pgvector`, `langgraph`, `fastembed`, `anthropic` are added by the milestones that need them.
- PostgreSQL 16 + pgvector via `docker-compose.yml` (`pgvector/pgvector:pg16`), database `gridline`, plus an init
  script creating `gridline_test`. No Alembic: `create_schema()` runs `metadata.create_all`; `--reset` drops and
  recreates. **A2:** models use only dialect-portable types (String, Integer, Float, Boolean, Date, JSON with a JSONB
  variant on Postgres) so the same schema also works on SQLite for offline unit tests; Postgres remains the target
  and the default for tests (`TEST_DATABASE_URL`, default `postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test`).
- SQLAlchemy 2.x typed `Mapped[...]` classes, async engine and sessions (`gridline/db/engine.py`), pyright strict,
  ruff, files under ~300 lines, one module per concern.
- IDs are human-readable strings and primary keys (`Z-HV`, `D-7`, `RD-01`, `HI-2021-FL-01`, `CH-2025-02`,
  `dmp-2024`). Tables are snake_case plural. Domain words: zone, channel, project, crew, incident, shelter,
  document, section. "Rescue teams" in the brief are `crews` with `kind = rescue|hill_rescue|...`.
- Coordinates are schematic metres (ARCHITECTURE A2): x 0..12000 east, y 0..9000 north. Every located entity
  carries `x_m`, `y_m`; `elevation_m` is **computed at seed time** from `gridline/city/terrain.py`, never typed by hand.
- No personal data: no named people anywhere, including reports (use roles: "the Duty Officer"). Organisations,
  developers, storm names are fictional.
- Money: `damage_estimate_million` in fictional local currency units ("million"); no currency code.
- Dates: ISO `YYYY-MM-DD`. The seed's "as of" date is 2026-09-26.

## 3. Repository layout produced by this work

```
docker-compose.yml
backend/
  pyproject.toml  .env.example  README.md
  data/city/*.yaml            structured seed (one file per domain, listed in §5)
  data/corpus/*.md            33 documents, YAML front matter + numbered `##` sections (§7)
  gridline/__init__.py  config.py
  gridline/city/__init__.py  terrain.py  schema_*.py   (Pydantic models of the YAML, validation)
  gridline/db/__init__.py  base.py  engine.py
  gridline/db/models/{__init__,city,geography,infrastructure,utilities,emergency,population,history,knowledge}.py
  gridline/db/seed/{__init__,__main__,loader,corpus,seed}.py
  tests/conftest.py  test_schema.py  test_seed.py  test_relationships.py  test_queries.py  test_corpus.py  test_consistency.py
```

Seed command: `cd backend && uv run python -m gridline.db.seed --reset`. Test command: `cd backend && uv run pytest`.

## 4. Terrain (single source of truth for elevation)

`gridline/city/terrain.py`:

```python
import math
def river_y(x: float) -> float:            # centreline of the Kalinadi (R-1)
    return 3000 + 250 * math.sin((x - 6000) / 3000)
def elevation_m(x: float, y: float) -> float:
    d = y - river_y(x)
    base = 212 + (0.003 * d if d >= 0 else 0.0015 * -d)     # north bank rises 3 m/km, south bank 1.5 m/km
    hill = 400 * math.exp(-(((x - 11000) / 2400) ** 2 + ((y - 8600) / 2000) ** 2))   # Tekri Hill
    plateau = 30 * math.exp(-(((x - 5500) / 1500) ** 2 + ((y - 6500) / 900) ** 2))   # Civil Lines rise
    lake = -4 * math.exp(-(((x - 1800) / 1100) ** 2 + ((y - 1500) / 800) ** 2))      # Nandi Lake basin
    return round(base + hill + plateau + lake, 1)
```

Derived: river bank datum 212 m; gauge RV-01 zero = 207.0 m (ordinary stage 1.6 m, flood stage 4.2 m, danger
5.5 m, record 5.8 m on 2021-09-14). `elevation_points` grid: x = 0,500,…,12000 × y = 0,500,…,9000 (475 rows).
Zone `elevation_min_m/max_m/mean_m` = over grid points inside the zone bbox. Road `min_elevation_m` = min over
path vertices. Tunnel `low_point_elevation_m` = terrain − `depth_below_grade_m`. R-1 `path` vertices are
(x, round(river_y(x))) for x = 0,500,…,12000.

## 5. Entity catalogue (authoritative IDs, coordinates, relationships)

YAML files live in `backend/data/city/`. Each file is a mapping of table name → list of records; keys equal ORM
column names except the computed ones (`elevation_m`, `*_elevation_m`, `density_per_km2`, `area_km2` for zones,
`svg_path`). Lists (zone_ids, path, capabilities, serves_zone_ids) are JSON columns.

### 5.1 `city.yaml` — table `city` (one row)
`id: nandipur`, `name: Nandipur`, `region: Kalinadi Valley`, `country: Vandara (fictional)`, `founded_year: 1740`,
`area_km2: 73.3`, `population_2026: 344700`, `bbox: [0,0,12000,9000]`, `crs: schematic_metres`,
`river_datum_m: 212`, `gauge_zero_m: 207.0`, `as_of_date: 2026-09-26`, `administration: Nandipur Municipal Corporation (NMC)`,
`disaster_authority: NMC Disaster Management Cell (NMC-DMC)`, `emergency_number: "112"`, `description`.

### 5.2 `zones.yaml` — table `zones` (10 rows)
Columns: id, name, kind, bbox [x0,y0,x1,y1], slope_deg, soil_type, geological_zone_id, catchment_id,
drains_to_channel_id, description. Computed: area_km2 (from bbox), elevation_min/max/mean_m, svg_path.

| id | name | kind | bbox | slope_deg | soil_type | geo | catchment | drains_to |
|---|---|---|---|---|---|---|---|---|
| Z-HV | Hillview | hillside | 8200,4400,11400,6400 | 32 | colluvial silty clay over weathered phyllite | GZ-2 | CT-2 | D-7 |
| Z-TH | Tekri Heights | hillside_upper | 8200,6400,12000,9000 | 24 | thin residual soil over quartzite | GZ-1 | CT-1 | D-7 |
| Z-RS | Riverside | floodplain | 7600,3300,11400,4400 | 3 | alluvial silt and sand | GZ-3 | CT-2 | D-8 |
| Z-OT | Old Town | urban_core | 4800,3300,7600,4600 | 4 | alluvial clay loam | GZ-3 | CT-3 | D-3 |
| Z-MW | Market Ward | commercial | 4800,4600,7600,5800 | 3 | clay loam | GZ-4 | CT-3 | D-4 |
| Z-SR | Station Road | transport | 1800,3800,4800,6000 | 2 | silty loam over railway fill | GZ-4 | CT-3 | D-5 |
| Z-CL | Civil Lines | administrative | 4800,5800,8200,7800 | 6 | lateritic gravel over shale | GZ-4 | CT-3 | D-2 |
| Z-LK | Lakeside | lakeside | 0,0,3600,2700 | 1 | lacustrine clay and peat | GZ-5 | CT-4 | D-11 |
| Z-NC | New Colony | suburban | 3600,0,8400,2700 | 2 | alluvial silt (former paddy) | GZ-3 | CT-5 | D-9 |
| Z-MI | Mill Road Industrial | industrial | 8400,0,12000,2700 | 2 | alluvial sand and gravel | GZ-3 | CT-5 | D-12 |

Every located asset's (x_m, y_m) must fall inside its zone's bbox (tested). `zones.drains_to_channel_id` is a
circular FK with `drainage_channels` → declare `use_alter=True`; the seed inserts zones with it null and sets it
in a second pass.

### 5.3 `geography.yaml`
**`geological_zones`** (id, name, lithology, description, permeability_class, bearing_capacity_class, hazard_notes):
GZ-1 Tekri Quartzite Ridge (hard quartzite, thin soils, rockfall on cuts, very high runoff); GZ-2 Hillview Phyllite
Slopes (weathered phyllite, 2–6 m colluvium, dip slope to SW, slide-prone when saturated); GZ-3 Kalinadi Recent
Alluvium (high water table, moderate liquefaction, flood plain); GZ-4 Older Alluvial Terrace (compact, good bearing,
moderate permeability); GZ-5 Nandi Lacustrine Basin (soft clay, peat, poor bearing, subsidence, waterlogging).

**`soil_profiles`** (id SP-<zone suffix>, zone_id, soil_type, depth_to_bedrock_m, permeability_class,
infiltration_rate_mm_h, field_capacity, plasticity_index, shrink_swell, liquefaction_susceptibility,
bearing_capacity_kpa, water_table_depth_m, notes) — one per zone. Hillview: depth 4.5 m, infiltration 8 mm/h,
plasticity 22, bearing 120 kPa, water table 3 m (perched after rain). Lakeside: depth 30 m, infiltration 2, bearing 45,
water table 0.8. New Colony: infiltration 10, water table 1.5. Others plausible.

**`catchments`** (id, name, zone_ids, area_km2, outlet_river_id, outlet_description, impervious_pct_2018,
impervious_pct_2026): CT-1 Tekri Upper [Z-TH] 9.9 → D-7 head and R-2 (8→14); CT-2 Hillview–Riverside [Z-HV, Z-RS]
10.6 → D-7 → R-1 (31→44); CT-3 North Bank Urban [Z-OT, Z-MW, Z-SR, Z-CL] 20.4 → D-2→D-4→D-3→R-1 and D-5→R-1 (58→66);
CT-4 Nandi Lake Basin [Z-LK] 9.7 → D-11 pumped → R-1 (42→49); CT-5 South Bank [Z-NC, Z-MI] 22.7 → D-9, D-12 → R-1 (24→52).

**`rivers`** (id, name, kind river|stream|lake, description, length_km, ordinary_flow_m3s, bankfull_flow_m3s,
gauge_sensor_id, gauge_zero_m, flood_stage_m, danger_stage_m, record_stage_m, record_date, surface_level_m, path):
R-1 Kalinadi (river, 12.4 km, 85 / 1100 m³/s, RV-01, 207.0, 4.2, 5.5, 5.8, 2021-09-14, path per §4);
R-2 Tekri Nala (stream, 4.1 km, seasonal, from (11500,8400) via (11500,7600) (11600,6400) (11600,5000) to
(11400,3250); check dams DM-3); R-3 Nandi Lake (lake, 1.6 km², surface_level_m 208.5, regulated by DM-2,
centre (1800,1500), path = rough outline).

**`hills`** (id, name, summit_x_m, summit_y_m, summit_elevation computed, zone_ids, geological_zone_id, description):
HL-1 Tekri Hill (11000,8600) [Z-TH]; HL-2 Hillview Ridge (10400,6400) [Z-HV] spur of Tekri; HL-3 Civil Lines Rise
(5500,6500) [Z-CL].

**`slopes`** (id, name, zone_id, hill_id, x_m, y_m, mean_angle_deg, max_angle_deg, aspect, length_m, height_m,
soil_depth_m, vegetation_cover_pct, stability_class stable|marginal|unstable|stabilised, retaining_structures,
toe_channel_id, toe_distance_to_channel_m, has_active_construction, description):

| id | name | zone | hill | x,y | mean/max ° | veg % | stability | toe channel / m | notes |
|---|---|---|---|---|---|---|---|---|---|
| SL-HV-1 | Hillview Terrace slope | Z-HV | HL-2 | 9700,5500 | 32/38 | 20 | marginal | D-7 / 60 | colluvium 4.5 m; PR-HT2 active; no retaining wall yet; 400 m below WF-3 |
| SL-HV-2 | Hillview Terrace Phase 1 cut | Z-HV | HL-2 | 9350,5200 | 28/34 | 35 | stabilised | D-7 / 140 | failed 2022 (HI-2022-LS-01); 6 m retaining wall 2022 |
| SL-HV-3 | Hill Road cut km 2.1 | Z-HV | HL-2 | 10100,5000 | 41/55 | 15 | marginal | D-7 / 20 | slide 2019 blocked D-7 (HI-2019-LS-01); mesh 2020 |
| SL-TH-1 | Tekri Quarry face | Z-TH | HL-1 | 10600,7200 | 55/70 | 30 | unstable | D-7 / 350 | PR-TQ; bench slide 2024 |
| SL-TH-2 | Tekri Nala gully slopes | Z-TH | HL-1 | 11500,7600 | 30/40 | 70 | stable | none | check dams DM-3 |
| SL-TH-3 | Quarry Road hairpins | Z-TH | HL-1 | 10200,6900 | 36/48 | 40 | marginal | none | 2014 landslide (HI-2014-LS-01) |
| SL-CL-1 | Civil Lines scarp | Z-CL | HL-3 | 7900,6600 | 15/20 | 60 | stable | D-2 / 300 | shale |

**`flood_plains`** (id, name, river_id, zone_ids, area_km2, return_period_years, typical_depth_m, protection_type,
protection_crest_m, protection_year_built, protection_year_raised, residents_2018, residents_2026, description):
FP-1 Riverside plain (R-1, [Z-RS], 3.1, 10, 0.8, "Bypass embankment (partial)", 214.5, 2016, null, 11000, 14000);
FP-2 South Bank plain (R-1, [Z-NC, Z-MI], 15.0, 25, 0.6, none, null, null, null, 6000, 41000);
FP-3 Old Town riverfront (R-1, [Z-OT], 1.4, 50, 0.4, "earth embankment", 214.6, 1978, 2022, 9000, 8500);
FP-4 Nandi Lake basin (R-3, [Z-LK], 5.2, 10, 1.2, "regulator DM-2 + pumped drain D-11", 209.5, 1996, null, 17000, 21000).

### 5.4 `drainage.yaml`
**`drainage_channels`** (id, name, kind, catchment_id, upstream_zone_id, downstream_zone_id, x_m, y_m, length_m,
year_built, year_relined, design_capacity_m3s, current_capacity_m3s, blocked_fraction, condition, last_desilted,
outfall_river_id, outfall_channel_id, limiting_structure_id, limiting_structure_kind, gate_closes_at_river_stage_m,
description):

| id | name | kind | up→down zone | x,y | design | current | blocked | limiting | outfall |
|---|---|---|---|---|---|---|---|---|---|
| D-2 | Civil Lines drain | storm_drain | Z-CL→Z-MW | 6500,5800 | 8 | 8 | 0.00 | – | D-4 |
| D-3 | Old Town main drain | brick_culvert | Z-OT→Z-OT | 6200,3700 | 18 | 14 | 0.10 | BR-5 (bridge) | R-1 |
| D-4 | Market Ward drain | covered_drain | Z-MW→Z-OT | 6200,4900 | 12 | 10 | 0.08 | – | D-3 |
| D-5 | Station Road drain | culvert | Z-SR→Z-SR | 3300,4400 | 9 | 7.5 | 0.12 | TU-1 (tunnel) | R-1 |
| D-7 | Kalinadi drain | lined_channel | Z-HV→Z-RS | 9700,4600 | 42 | 27 | 0.00 | BR-4 (bridge) | R-1 |
| D-8 | Riverside outfall drain | storm_drain | Z-RS→Z-RS | 8800,3600 | 15 | 13 | 0.12 | – (flap gate 4.0 m) | D-7 |
| D-9 | New Colony drain | lined_channel | Z-NC→Z-NC | 6000,2000 | 20 | 20 | 0.00 | – | R-1 |
| D-11 | Lakeside pumped drain | pumped_drain | Z-LK→Z-LK | 2600,2200 | 12 | 9.5 | 0.05 | DM-2 (dam) gravity only < 1.5 m | R-1 |
| D-12 | Mill Road industrial drain | open_channel | Z-MI→Z-MI | 10200,2000 | 16 | 12 | 0.25 | – | R-1 |

D-7 details: built 1994, relined 2016, 4.8 km, catchment CT-2, condition fair, last desilted 2024; the 2025 BR-4
box culvert (2.4 × 1.8 m, was 3.2 × 2.4 m) sets current capacity 27. D-3: 1890, 3.4 km, poor, desilted 2025
(phase 1). D-9: 2019, designed for 35 % impervious catchment. D-11: 1996; 3 fixed pumps × 2.5 + 4.5 gravity = 12;
PU-L2 failed 2024-10-28 → 9.5.

**`pump_units`** (id, name, kind mobile|fixed, capacity_m3s, status available|deployed|failed|maintenance,
location_zone_id, channel_id, x_m, y_m, year_installed, notes): PU-M1..PU-M4 mobile diesel 0.6 each, depot Old
Town works yard (5200,4400), available; PU-L1, PU-L2 (failed), PU-L3 fixed 2.5 each at D-11 station (3000,2350);
PU-T1, PU-T2 fixed 0.4 each at TU-1 sump (3300,4600).

### 5.5 `roads.yaml`
**`roads`** (id, name, kind, zone_id, from_zone_id, to_zone_id, length_m, lanes, width_m, surface, year_built,
last_major_work_year, status open, is_evacuation_route, is_only_access, floods_at_river_stage_m, path, description;
computed min_elevation_m):

| id | name | kind | zone | from→to | len | lanes | evac | only | floods@ | path |
|---|---|---|---|---|---|---|---|---|---|---|
| RD-01 | Hill Road | arterial | Z-HV | Z-RS→Z-TH | 4200 | 2 (4 lower 1.6 km since 2025) | yes | yes | – | (9600,4400)(9800,4900)(10100,5400)(10300,6000)(10200,6400)(10400,7000) |
| RD-02 | Riverside Bypass | arterial | Z-RS | Z-OT→Z-RS | 5600 | 4 | yes | no | 5.6 | (7600,3450)(9000,3500)(11400,3400)(11800,3400) |
| RD-03 | Kalinadi Bridge Road | arterial | Z-OT | Z-OT→Z-NC | 1900 | 2 | yes | no | – (BR-1 closes 5.0) | (6200,3700)(6200,3000)(6200,2400) |
| RD-04 | Station Road | arterial | Z-SR | Z-SR→Z-MW | 3100 | 4 | yes | no | – | (2200,5000)(4800,5000)(6000,5000) |
| RD-05 | Bazaar Lane | local | Z-OT | Z-OT→Z-OT | 1800 | 1 (width 4 m) | no | no | – | (5400,3800)(6200,3900)(7000,4000) |
| RD-06 | Market Ward Main | collector | Z-MW | Z-MW→Z-MW | 2400 | 2 | no | no | – | (4800,5300)(7600,5300) |
| RD-07 | Lakeside Ring Road | collector | Z-LK | Z-LK→Z-LK | 6800 | 2 | yes | no | 4.5 | (600,600)(3000,600)(3000,2400)(600,2400)(600,600) |
| RD-08 | Mill Road | arterial | Z-MI | Z-MI→Z-MI | 3600 | 4 | yes | no | – | (8400,1600)(12000,1600) |
| RD-09 | New Colony Avenue | collector | Z-NC | Z-NC→Z-NC | 3900 | 2 | no | no | – | (3600,1200)(8400,1200) |
| RD-10 | Civil Lines Road | arterial | Z-CL | Z-SR→Z-RS | 5400 | 2 | yes | no | – | (4800,6200)(8200,6400)(8600,5600)(9600,4400) |
| RD-11 | Tekri Quarry Road | local | Z-TH | Z-TH→Z-TH | 5200 | 1 | no | no | – | (10400,7000)(10200,7400)(10800,7800)(12000,8200) |
| RD-12 | Eastern Highway Link | highway | Z-MI | Z-MI→Z-RS | 2800 | 4 | yes | no | – | (11800,1600)(11800,2700)(11800,3400) |
| RD-13 | Rail Underpass Road | collector | Z-SR | Z-SR→Z-SR | 900 | 2 | no | no | – (TU-1 floods when D-5 surcharges) | (3300,4200)(3300,5100) |
| RD-14 | Lake Causeway | collector | Z-LK | Z-LK→Z-NC | 1400 | 2 | yes | no | 5.2 | (2800,2300)(3600,2300)(4200,2000) |

Hill Road is the only paved access to Hillview and Tekri Heights from the city (RD-11 leaves the city eastward,
unpaved, landslide-prone). RD-10 ends at the foot of Hill Road in Riverside; it does not reach Hillview.
Road `zone_id` is the primary zone; path vertices may cross other zones (roads are exempt from the in-bbox test).

**`bridges`** (id, name, road_id, crosses_kind river|channel, crosses_id, zone_id, x_m, y_m, year_built,
year_rebuilt, length_m, load_rating_t, condition, scour_risk, clearance_m, waterway_area_m2, closes_at_river_stage_m,
last_inspection, description): BR-1 Kalinadi Bridge (RD-03, R-1, Z-OT, 6200,3300 [south edge of Z-OT bbox], 1962, 310 m, 40 t, fair, high
scour (pier 3 undermined 2021), 6.2 m, closes 5.0, 2025-11-12); BR-2 Eastern Bridge (RD-12, R-1, Z-RS, 11000,3300,
2023, 380 m, 70 t, good, low, 8.0 m); BR-3 Lake Causeway Bridge (RD-14, D-11, Z-LK, 3200,2300, 1996, 24 m, 30 t,
fair, waterway 9 m²); BR-4 Hill Road D-7 culvert crossing (RD-01, D-7, Z-HV, 9800,4900, built 1994 rebuilt 2025,
14 m, 60 t, good, waterway 4.32 m² (was 7.68)); BR-5 Bazaar arch bridge (RD-05, D-3, Z-OT, 6200,3900, 1901,
9 m, 10 t, poor, waterway 6.5 m², heritage).

**`tunnels`** (id, name, kind road|water_conveyance, road_id, zone_id, x_m, y_m, length_m, year_built,
depth_below_grade_m, condition, sump_pump_ids, floods_when, description; computed low_point_elevation_m):
TU-1 Station Road rail underpass (road, RD-13, Z-SR, 3300,4600, 180 m, 1974, 4.5 m, fair, [PU-T1, PU-T2],
"D-5 surcharge"; flooded 2018 and 2021); TU-2 Kalinadi intake tunnel (water_conveyance, null, Z-SR, 2000,5600,
1900 m, 1985, 12 m, fair, [], null; DM-1 → WF-1).

### 5.6 `utilities.yaml`
**`dams`** (id, name, kind barrage|gated_weir|check_dam, river_id, channel_id, zone_id nullable, x_m, y_m,
year_built, height_m, storage_mcm, spillway_capacity_m3s, gates, condition, silted_pct, closes_at_river_stage_m,
downstream_zone_ids, operator, description): DM-1 Kalinadi Barrage (barrage, R-1, null zone, 400,2760, 1985, 9 m,
4.2, 1800, 12 gates, fair, 35 %, downstream all riverine zones, "Kalinadi Irrigation Division"); DM-2 Nandi Lake
Regulator (gated_weir, R-3, D-11, Z-LK, 3000,2350, 1996, 3.5 m, 1.9, 40, 2 gates, fair, closes 2.5 m, [Z-LK]);
DM-3 Tekri check dams (check_dam, R-2, null, Z-TH, 11500,7600, 2008, 4 m, 0.06, 25, 0, fair, 60 % silted, [Z-RS]).

**`power_substations`** (id, name, zone_id, x_m, y_m, voltage_kv, capacity_mva, year_built, serves_zone_ids,
fed_from_substation_id, flood_protected, platform_raised_m, status normal, description):
PS-1 Civil Lines Grid Substation (Z-CL, 6000,6800, "132/33", 150, 1972, all zones, null, true, 0);
PS-2 Riverside (Z-RS, 8600,3700, "33/11", 40, 1998, [Z-RS, Z-HV, Z-TH], PS-1, false, 0; flooded 2021 38 h outage);
PS-3 Mill Road (Z-MI, 10400,1400, "33/11", 60, 1980, [Z-MI], PS-1, partial bund 2022, 0);
PS-4 Station Road (Z-SR, 3000,5400, "33/11", 50, 1965, [Z-SR, Z-OT, Z-MW], PS-1, true, 0);
PS-5 New Colony (Z-NC, 5200,1000, "33/11", 40, 2021, [Z-NC, Z-LK], PS-1, true, 1.2; feeds D-11 pumps and H-4).

**`water_facilities`** (id, name, kind treatment_plant|intake|reservoir|storage|pumping_station|sewage_treatment,
zone_id, x_m, y_m, capacity_mld, storage_ml, year_built, year_expanded, serves_zone_ids, substation_id,
backup_power_hours, flood_exposure none|low|moderate|high, description):
WF-1 Kalinadi WTP (treatment_plant, Z-CL, 5200,6400, 120, null, 1985, null, all, PS-1, 24, none; fed by TU-2 from DM-1);
WF-2 Riverside raw-water intake (intake, Z-RS, 8200,3450, 40, null, 1998, null, [Z-RS, Z-HV], PS-2, 0, high; flooded 2021, 4 days out);
WF-3 Tekri Hill Reservoir (reservoir, Z-TH, 9900,6500, null, 12, 1990, 2022, [Z-HV, Z-RS], null, null, none;
gravity storage 400 m upslope of SL-HV-1; minor leak 2023-08 repaired);
WF-4 Old Town overhead tanks (storage, Z-OT, 5600,4200, null, 4, 1955, null, [Z-OT], PS-4, null, low);
WF-5 New Colony booster station (pumping_station, Z-NC, 5600,1400, 20, null, 2021, null, [Z-NC], PS-5, 8, moderate);
WF-6 Mill Road STP (sewage_treatment, Z-MI, 11200,800, 45, null, 2005, null, [Z-MI, Z-NC], PS-3, 4, high; flooded 2021 → contamination in New Colony).

**`projects`** (id, name, kind, zone_id, slope_id, status planned|active|halted|completed, start_date,
planned_end_date, completed_date, excavation_depth_m, planned_depth_m, area_m2, permit_number, permit_doc_id,
developer, flood_plain_id, nearest_channel_id, distance_to_channel_m, hazard_review_status none|pending|approved|approved_with_conditions,
x_m, y_m, description):

| id | name | kind | zone | slope | status | start | exc/planned m | permit | review | x,y |
|---|---|---|---|---|---|---|---|---|---|---|
| PR-HT2 | Hillview Terrace Phase 2 | residential | Z-HV | SL-HV-1 | active | 2026-03-02 (end 2027-06-30) | 2.5 / 6.0 | HT-2026-014 → doc permit-ht-2026-014 | approved_with_conditions | 9700,5450 |
| PR-HT1 | Hillview Terrace Phase 1 | residential | Z-HV | SL-HV-2 | completed 2022-11-10 | 2020-10-05 | 4.0 / 4.0 | HT-2020-007 (no doc) | none | 9350,5150 |
| PR-HRW | Hill Road Widening | road | Z-HV | – | completed 2025-05-20 | 2024-09-15 | – | RW-2024-031 | none | 9800,4900 |
| PR-NCH | New Colony Housing Scheme | residential | Z-NC | – | completed 2023-08-25 | 2019-02-01 | – ; area 1,450,000 | NHB-2018-002 | none | 6000,1300 |
| PR-EB2 | Eastern Bridge | bridge | Z-MI | – | completed 2023-04-15 | 2021-01-10 | – | – | approved | 11000,2500 |
| PR-D3R | D-3 desilting and relining | drainage | Z-OT | – | active | 2025-01-15 (end 2026-12-31) | – | – | approved | 6200,3700 |
| PR-TQ | Tekri Quarry expansion | quarry | Z-TH | SL-TH-1 | active | 2019-06-15 | 35 / 45 | TQ-2019-3 | pending | 10600,7200 |
| PR-RSE | Riverside embankment raising | embankment | Z-RS | – | planned | 2027-01-01 | – | – | none | 9000,3400 |
| PR-MWM | Market Ward Mall | commercial | Z-MW | – | active | 2024-06-03 (end 2026-12-31) | 8.0 / 8.0 | MW-2024-011 | approved_with_conditions | 6600,5000 |

PR-HT2: nearest channel D-7 at 60 m, developer "Nandi Hills Developers", area 18,500 m². PR-MWM: nearest D-4 at
25 m, dewatering 0.4 m³/s into D-4. PR-NCH on FP-2. PR-HRW replaced the BR-4 culvert without a hydraulic review.

**`critical_infrastructure`** (id CI-01.., name, category health|power|water|transport|emergency|drainage,
asset_kind, asset_id, zone_id, tier 1|2|3, backup_power_hours, depends_on_substation_id, depends_on_water_facility_id,
access_road_id, flood_exposure, notes): H-1 (1, PS-1, WF-1, RD-10, none); H-2 (1, PS-2, WF-2, RD-02, high);
H-5 (2, PS-3, WF-1, RD-08, moderate); PS-1 (1); PS-2 (1, high); PS-5 (2, low); WF-1 (1, PS-1); WF-2 (2, PS-2, high);
WF-3 (2, slope hazard); BR-1 (1); RD-01 Hill Road (1, only access); D-7 (1); D-11 pumping station via PU-L1 (2, PS-5);
FS-1 (1); TU-1 (3, high). `asset_kind` ∈ hospital|power_substation|water_facility|bridge|road|drainage_channel|
fire_station|pump_unit|tunnel; polymorphic, resolved by a test.

**`sensors`** (id, kind rain_gauge|soil_moisture|channel_level|river_level|wind|lake_level, name, zone_id, x_m,
y_m, unit, installed_year, channel_id, slope_id, river_id, status active, description): RG-01 Tekri (Z-TH,
10600,7400, mm), RG-02 Hillview (Z-HV, 9700,5600), RG-03 Old Town (Z-OT, 6000,4000), RG-04 Lakeside (Z-LK,
1800,1800), RG-05 New Colony (Z-NC, 6000,1400); SM-01 SL-HV-1 upper (9720,5560, saturation fraction, 2020),
SM-02 SL-HV-1 toe (9680,5400, 2020), SM-03 SL-HV-2 (9350,5200, 2020), SM-04 SL-TH-1 crest (10600,7300, 2024);
CL-D7 at BR-4 (Z-HV, 9800,4900, m), CL-D3 at BR-5 (Z-OT, 6200,3900), CL-D11 at DM-2 (Z-LK, 3000,2350); RV-01
Kalinadi at BR-1 (Z-OT, 6200,3300, m stage), RV-02 Kalinadi at barrage (zone null, 400,2760); WS-01 wind Civil
Lines (Z-CL, 6000,6800, km/h); LL-01 Nandi Lake level (Z-LK, 2000,1600, m).

### 5.7 `emergency.yaml`
**`hospitals`** (id, name, kind tertiary|community|district|private|specialist, zone_id, x_m, y_m, year_built,
floors, has_burn_unit, has_helipad, backup_power_hours, access_road_id, substation_id, water_facility_id,
status normal|on_generator|evacuated|closed, description):

| id | name | kind | zone | x,y | built | backup h | road | PS | WF | beds (general/icu/emergency/pediatric/burn/maternity) |
|---|---|---|---|---|---|---|---|---|---|---|
| H-1 | Nandipur District Hospital | tertiary | Z-CL | 6400,6600 | 1968 | 72 | RD-10 | PS-1 | WF-1 | 300/40/30/30/0/20 = 420 |
| H-2 | Riverside Community Hospital | community | Z-RS | 8800,3800 | 1996 | 12 | RD-02 | PS-2 | WF-2 | 56/6/10/8/0/0 = 80 |
| H-3 | Railway Hospital | district | Z-SR | 2800,5200 | 1948 | 24 | RD-04 | PS-4 | WF-1 | 44/4/8/4/0/0 = 60 |
| H-4 | Lakeview Hospital | private | Z-LK | 1400,2200 | 2009 | 36 | RD-07 | PS-5 | WF-5 | 80/16/12/12/0/0 = 120 |
| H-5 | Mill Road Workers' Hospital | specialist | Z-MI | 10000,1900 | 1984 | 48 | RD-08 | PS-3 | WF-1 | 60/12/12/0/16/0 = 100 |

**`hospital_beds`** (id "<hospital>-<type>", hospital_id, bed_type general|icu|emergency|pediatric|burn|maternity,
total, available) — one row per non-zero type above; `available` ≈ 15–30 % of total.

**`ambulances`** (id AMB-01.., hospital_id, kind ALS|BLS, status available|dispatched|maintenance,
location_zone_id): H-1 ×5 (2 ALS), H-2 ×2 (BLS), H-3 ×2 (1 ALS), H-4 ×3 (1 ALS), H-5 ×2 (1 ALS) = 14; one of
H-1's in maintenance.

**`fire_stations`** (id, name, zone_id, x_m, y_m, year_built, staff_on_shift, coverage_zone_ids, access_road_id,
has_foam_capability, description): FS-1 Central Fire Station (Z-MW, 5200,4700, 1958, 24, [Z-OT, Z-MW, Z-SR,
Z-CL, Z-RS, Z-HV, Z-TH], RD-06, false; Hillview via Hill Road ≥ 25 min); FS-2 Mill Road Fire Station (Z-MI,
9600,1400, 1986, 18, [Z-MI, Z-NC, Z-RS], RD-08, true); FS-3 New Colony Fire Station (Z-NC, 5000,1600, 2022, 12,
[Z-NC, Z-LK], RD-09, false).

**`fire_trucks`** (id FT-01.., station_id, kind pumper|ladder|water_tender|rescue_tender|foam_tender|mini_pumper,
water_capacity_l, foam_capacity_l, min_road_width_m, status available|dispatched|maintenance, location_zone_id):
FS-1: FT-01 pumper 4500 L, FT-02 pumper 4500, FT-03 ladder (42 m) 1500 (min width 6.0 m — cannot enter Bazaar Lane),
FT-04 water_tender 12000, FT-05 rescue_tender 0; FS-2: FT-06 pumper 4500, FT-07 foam_tender 3000/1500 foam,
FT-08 water_tender 12000; FS-3: FT-09 pumper 4500, FT-10 mini_pumper 1200 (min width 3.0 m).

**`police_stations`** (id, name, zone_id, x_m, y_m, personnel, jurisdiction_zone_ids, has_control_room, description):
PL-1 Kotwali (Z-OT, 5800,4000, 120, [Z-OT, Z-MW], true — city control room 112); PL-2 Station Road (Z-SR,
3200,5000, 80, [Z-SR, Z-CL], false); PL-3 Riverside (Z-RS, 9000,3900, 60, [Z-RS, Z-HV, Z-TH], false); PL-4 Mill
Road (Z-MI, 10600,1800, 55, [Z-MI], false); PL-5 Lakeside (Z-LK, 1200,1800, 45, [Z-LK, Z-NC], false).

**`crews`** (id, name, kind rescue|drainage|road|hill_rescue|medical|electrical|boat|volunteer, members,
base_zone_id, location_zone_id, x_m, y_m, status available|dispatched|busy|off_duty, capabilities (list),
equipment, baseline_response_min, description): C-1 Rescue Alpha (rescue, 24, Z-CL, 5800,6200, ropes/cutting/
2 boats/first aid, 20); C-2 Drainage Crew Old Town (drainage, 14, Z-OT depot 5200,4400, operates PU-M1..PU-M4,
30); C-3 Road Maintenance Crew (road, 16, Z-SR, 2600,4600, excavator/barricades/dump trucks, 35); C-4 Hill Rescue
Team (hill_rescue, 12, Z-RS, 9600,4500, rope rescue/slope inspection, 25; formed 2020); C-5 Medical Response Team
(medical, 10, Z-CL at H-1 6400,6600, 15); C-6 Electrical Repair Crew (electrical, 9, Z-CL at PS-1 6000,6800, 40);
C-7 Boat Rescue Unit (boat, 8, Z-LK, 1600,2400, 4 boats, 20); C-8 New Colony Volunteer Team (volunteer, 30, Z-NC,
5400,1300, door-to-door warning/sandbags, 15; trained 2023).

**`shelters`** (id, name, kind community_hall|school|stadium|temple_hall|marriage_hall|club, zone_id, x_m, y_m,
capacity_persons, current_occupancy 0, status closed|open|full, floors, has_generator, water_supply_days,
has_kitchen, flood_plain_id, school_id, access_road_id, managed_by, description):

| id | name | kind | zone | x,y | cap | gen | FP | school | road |
|---|---|---|---|---|---|---|---|---|---|
| S-1 | Civil Lines Community Hall | community_hall | Z-CL | 6200,6400 | 800 | yes | – | – | RD-10 |
| S-2 | Govt Higher Secondary School Market Ward | school | Z-MW | 5600,5400 | 600 | no | – | SC-05 | RD-06 |
| S-3 | Station Road Sports Complex | stadium | Z-SR | 3800,5600 | 1500 | yes | – | – | RD-04 |
| S-4 | New Colony Community Centre | community_hall | Z-NC | 5800,1100 | 400 | no | FP-2 | – | RD-09 |
| S-5 | Riverside Primary School | school | Z-RS | 9200,3900 | 300 | no | FP-1 | SC-08 | RD-02 |
| S-6 | Tekri Devi Temple Hall | temple_hall | Z-TH | 10400,6800 | 200 | no | – | – | RD-01 |
| S-7 | Lakeside Marriage Hall | marriage_hall | Z-LK | 1000,1200 | 500 | no | FP-4 | – | RD-07 |
| S-8 | Mill Road Workers' Club | club | Z-MI | 9800,1000 | 350 | yes | FP-2 | – | RD-08 |

Total capacity 4,650 against 14,000 residents on FP-1 alone (a gap to discover, never stated).

### 5.8 `population.yaml`
**`zone_yearly_stats`** (id "<zone>-<year>", zone_id, year 2018..2026, population, households, children_under_5,
elderly_over_65, persons_with_disability, informal_settlement_population, low_income_households,
impermeable_surface_pct, built_up_pct, green_cover_pct, avg_building_storeys; computed density_per_km2). 90 rows.
Anchors (interpolate plausibly; New Colony steps in 2019, 2021, 2023 with PR-NCH phases; Hillview +3,200 in 2022
with PR-HT1; Riverside informal grows along D-8; Old Town declines slightly):

| zone | pop 2018 → 2026 | impermeable % 2018 → 2026 | informal pop 2018 → 2026 |
|---|---|---|---|
| Z-HV | 11,200 → 18,500 | 22 → 36 | 900 → 2,600 |
| Z-TH | 3,100 → 4,200 | 6 → 12 | 400 → 700 |
| Z-RS | 39,500 → 46,000 | 48 → 55 | 6,800 → 9,400 |
| Z-OT | 64,000 → 62,000 | 78 → 80 | 3,000 → 2,600 |
| Z-MW | 33,000 → 38,000 | 82 → 88 | 1,200 → 1,100 |
| Z-SR | 37,000 → 41,000 | 61 → 66 | 4,500 → 5,200 |
| Z-CL | 18,500 → 21,000 | 35 → 41 | 300 → 300 |
| Z-LK | 29,000 → 34,000 | 40 → 49 | 5,600 → 7,300 |
| Z-NC | 9,000 → 58,000 | 14 → 62 | 800 → 3,800 |
| Z-MI | 19,000 → 22,000 | 55 → 64 | 3,900 → 4,600 |

Totals: 263,300 (2018) → 344,700 (2026). Children 8–11 %, elderly 6–12 % (Old Town, Civil Lines highest),
disability 2–3 %, households ≈ population / 4.3.

**`residential_areas`** (id RA-01.., name, zone_id, kind apartment_blocks|informal_settlement|planned_colony|
row_houses|villas|worker_housing|mixed|village, households, population, year_established, storeys,
building_quality poor|fair|good, slope_id, flood_plain_id, nearest_channel_id, distance_to_channel_m, x_m, y_m,
description). 22 rows: RA-01 Hillview Terrace Phase 1 (Z-HV, apartment_blocks, 3,200, 2022, SL-HV-2, D-7 140 m,
9350,5150); RA-02 Kalinadi Drain settlement (Z-HV, informal, 2,600, D-7 5 m, 9600,4700; grew 1,900→2,600 in 2026);
RA-03 Riverside Old Village (Z-RS, row_houses, 12,000, FP-1, D-7 200 m, 9400,3800); RA-04 Riverside Bypass Colony
(Z-RS, planned_colony, 9,000, 2017, FP-1, 8400,3900); RA-05 D-8 settlement (Z-RS, informal, 3,400, FP-1, D-8 0 m,
8800,3650); RA-06 Old Town core (Z-OT, row_houses, 40,000, storeys 3, poor, FP-3 part, D-3, 6000,4100); RA-07
Bazaar quarters (Z-OT, mixed, 15,000, 6600,3900); RA-08 Market Ward flats (Z-MW, apartment_blocks, 22,000,
6000,5500); RA-09 Railway Colony (Z-SR, worker_housing, 8,000, 2600,5400); RA-10 Station Road settlement (Z-SR,
informal, 5,200, D-5 10 m, 3200,4300); RA-11 Civil Lines bungalows (Z-CL, villas, 6,000, 6800,7000); RA-12 Civil
Lines flats (Z-CL, apartment_blocks, 9,000, 5600,6600); RA-13 Lakeside Old Village (Z-LK, village, 12,000, FP-4,
1400,1000); RA-14 Ring Road settlement (Z-LK, informal, 7,300, FP-4, D-11 20 m, 2800,2200; lowest ground); RA-15
Lakeview Apartments (Z-LK, apartment_blocks, 8,000, 2012, 1200,2300); RA-16 New Colony Sector 1 (Z-NC,
planned_colony, 14,000, 2019, FP-2, D-9 80 m, 5000,1800); RA-17 Sector 2 (18,000, 2021, FP-2, 6400,1800); RA-18
Sector 3 (16,000, 2023, FP-2, 7600,1400); RA-19 New Colony old village (Z-NC, village, 6,000, 4200,600); RA-20
Mill Road labour lines (Z-MI, worker_housing, 9,000, FP-2, 9200,2200); RA-21 Mill Road settlement (Z-MI,
informal, 4,600, D-12 0 m, 10400,2100); RA-22 Tekri village (Z-TH, village, 3,000, near quarry, 10000,7200).
Population per zone across RA rows ≈ zone 2026 population.

**`schools`** (id SC-01.., name, zone_id, level primary|secondary|higher_secondary|college, students, staff,
floors, shelter_id, flood_plain_id, slope_id, x_m, y_m, description). 16 rows including: SC-03 Hillview Primary
(Z-HV, 420 students, 9650,5300 — 180 m downslope of SL-HV-1); SC-05 Govt HSS Market Ward (S-2, 1,400); SC-08
Riverside Primary (S-5, 380, FP-1); SC-12 New Colony Public School (FP-2, 1,600); SC-14 Lakeside Govt School
(FP-4, 900); SC-01 Nandipur College (Z-CL, 3,200); plus 10 more spread over zones.

### 5.9 `infrastructure_changes.yaml` — table `infrastructure_changes` (29 rows)
Columns: id, effective_date, kind drainage_capacity|road_construction|hillside_construction|land_use|urbanization|
embankment|utility|pump|bridge|quarry|encroachment|desilting|monitoring|commercial_construction, zone_id, asset_kind,
asset_id, project_id, description, metric, value_before, value_after, unit, hazard_review_done, approved_by,
document_id (= changelog-infra-2018-2026), related_incident_id, notes.

| id | date | kind | zone | asset | metric before→after | review |
|---|---|---|---|---|---|---|
| CH-2018-01 | 2018-11-20 | desilting | Z-SR | D-5 | capacity 6.5→8.0 m³/s (after HI-2018-FF-01) | yes |
| CH-2019-01 | 2019-02-01 | land_use | Z-NC | PR-NCH | land use agricultural→residential, 1,450,000 m² on FP-2 | no |
| CH-2019-02 | 2019-03-30 | drainage_capacity | Z-NC | D-9 | design capacity 0→20 (for 35 % impervious) | yes |
| CH-2019-03 | 2019-06-15 | quarry | Z-TH | PR-TQ / SL-TH-1 | vegetation 65→30 % | no |
| CH-2019-04 | 2019-09-05 | monitoring | Z-SR | TU-1 | automatic barrier + PU-T2 (after HI-2018-FF-01) | yes |
| CH-2020-01 | 2020-01-20 | monitoring | Z-HV | SM-01..SM-03 | probes installed; C-4 formed (after HI-2019-LS-01) | yes |
| CH-2020-02 | 2020-04-12 | hillside_construction | Z-HV | SL-HV-3 | rockfall mesh installed | yes |
| CH-2020-03 | 2020-10-05 | hillside_construction | Z-HV | PR-HT1 / SL-HV-2 | cut angle 28→34 °, 4 m | no |
| CH-2020-04 | 2020-11-30 | road_construction | Z-NC | RD-09 | New Colony Avenue opened | no |
| CH-2021-01 | 2021-03-18 | urbanization | Z-NC | RA-17 | impervious 35→52 % | no |
| CH-2021-02 | 2021-06-30 | utility | Z-NC | PS-5 | commissioned, platform +1.2 m; D-11 pumps re-fed from PS-5 | yes |
| CH-2022-01 | 2022-04-20 | embankment | Z-OT | FP-3 | crest 214.0→214.6 m (after HI-2021-FL-01) | yes |
| CH-2022-02 | 2022-05-15 | utility | Z-TH | WF-3 | storage 8→12 ML, 400 m upslope of SL-HV-1 | structural only |
| CH-2022-03 | 2022-11-10 | hillside_construction | Z-HV | PR-HT1 / SL-HV-2 | retaining wall 6 m; stability marginal→stabilised | yes |
| CH-2022-04 | 2022-12-01 | utility | Z-NC | FS-3 | fire station opened; FT-09, FT-10 | n/a |
| CH-2023-01 | 2023-04-15 | bridge | Z-MI | BR-2 / RD-12 | second river crossing opened | yes |
| CH-2023-02 | 2023-08-25 | urbanization | Z-NC | RA-18 | impervious 52→62 %; population +16,000; D-9 unchanged | no |
| CH-2023-03 | 2023-10-10 | pump | Z-LK | PU-L3 | replaced after 2021 overheating; D-11 back to 12 | yes |
| CH-2024-01 | 2024-06-03 | commercial_construction | Z-MW | PR-MWM | basement 8 m, 25 m from D-4; dewatering 0.4 m³/s into D-4 | yes (conditions) |
| CH-2024-02 | 2024-09-20 | road_construction | Z-TH | RD-11 | regraded, ditches (after HI-2024-LS-01) | yes |
| CH-2024-03 | 2024-10-28 | pump | Z-LK | PU-L2 | failed during Cyclone Meher; D-11 12→9.5; not repaired | n/a |
| CH-2025-01 | 2025-01-15 | desilting | Z-OT | D-3 / PR-D3R | capacity 12→14 | yes |
| CH-2025-02 | 2025-05-20 | drainage_capacity | Z-HV | D-7 / BR-4 / PR-HRW | culvert 3.2×2.4→2.4×1.8 m; capacity 42→27 | **no** |
| CH-2025-03 | 2025-05-20 | road_construction | Z-HV | RD-01 / PR-HRW | lanes 2→4 on lower 1.6 km; impervious 33→36 % | no |
| CH-2025-04 | 2025-08-12 | drainage_capacity | Z-MI | D-12 | survey: capacity 16→12, blocked 0.25 | n/a |
| CH-2025-05 | 2025-12-01 | encroachment | Z-RS | D-8 / RA-05 | width −15 %; capacity 15→13 | n/a |
| CH-2026-01 | 2026-01-20 | hillside_construction | Z-HV | PR-HT2 | permit HT-2026-014 issued with conditions | yes (conditions) |
| CH-2026-02 | 2026-03-02 | hillside_construction | Z-HV | PR-HT2 / SL-HV-1 | excavation began; vegetation 45→20 % | yes (conditions) |
| CH-2026-03 | 2026-05-10 | encroachment | Z-HV | RA-02 | settlement along D-7 upper reach 1,900→2,600 people | n/a |

### 5.10 Disaster history — table `historical_incidents` (17 rows) + `historical_incident_impacts`
Source of truth is the **front matter of the report document** (§7), block `incident:`; the seed parses it. Columns:
id, hazard flood|flash_flood|landslide|cyclone|urban_fire, title, started_on, ended_on, primary_zone_id, zone_ids,
slope_id, location_description, x_m, y_m, rainfall_24h_mm, rainfall_72h_mm, peak_intensity_mm_h, wind_speed_kmh,
wind_gust_kmh, river_stage_m, antecedent_conditions, infrastructure_state, severity 1..5, severity_label
minor|moderate|major|severe|catastrophic, affected_population, evacuated, deaths, injured, houses_damaged,
houses_destroyed, damage_estimate_million, response_summary, outcome_summary, lessons, document_id.
`historical_incident_impacts` (id "<incident>-<n>", incident_id, asset_kind, asset_id, impact
closed|blocked|overflowed|surcharged|flooded|damaged|destroyed|outage|failed|opened|evacuated|deployed|saturated,
detail, duration_hours nullable, depth_m nullable).

| id | hazard | title | date(s) | zone(s) | rain 24h/72h mm | other | sev | affected / evac / deaths | key impacts |
|---|---|---|---|---|---|---|---|---|---|
| HI-2012-FL-01 | flood | Kalinadi monsoon flood 2012 | 2012-08-18..22 | Z-RS; RS, OT, LK | 140/260 | stage 5.1 | 4 | 12,000 / 4,500 / 2 | D-3 overflowed; RD-07 closed; BR-1 closed 30 h; S-1, S-3 opened; OT embankment (crest 214.0) held |
| HI-2013-CY-01 | cyclone | Cyclone Taraka | 2013-10-24..26 | Z-LK; all | 120/– | wind 105 gust 130, stage 3.8 | 3 | 25,000 / 1,200 / 3 | PS-2 outage 20 h; PS-4 outage 9 h; RD-01 blocked 14 h (trees); H-4 on generator |
| HI-2014-LS-01 | landslide | Tekri Quarry Road landslide | 2014-07-29 | Z-TH; SL-TH-3 | 165/240 | – | 4 | 600 / 200 / 3 | RD-11 blocked 9 days; RA-22 11 houses destroyed; no hairpin drainage then |
| HI-2015-UF-01 | urban_fire | Market Ward cloth market fire | 2015-03-14 | Z-MW (6000,5100) | dry, wind 20 | – | 3 | 1,200 / 0 / 0, 12 injured | 140 shops destroyed; WF-4 tanks at 30 % → low hydrant pressure; FS-1 6 h |
| HI-2016-FL-01 | flood | Nandi Lake pump-failure flood | 2016-09-08..12 | Z-LK | 95/210 | stage 4.6 (DM-2 closed) | 3 | 9,000 / 2,200 / 1 | PU-L1 failed → D-11 12→7; RD-07 closed; H-4 ground floor 0.4 m; S-7 opened with 0.2 m water inside |
| HI-2017-UF-01 | urban_fire | Old Town Bazaar Lane fire | 2017-11-02 | Z-OT (6100,3900) | – | – | 4 | 2,500 / 600 / 6, 30 injured | RD-05 4 m width → FT-03 could not enter; 38 houses destroyed, 90 damaged; FS-2 via BR-1; 9 h |
| HI-2018-FF-01 | flash_flood | Station Road underpass flash flood | 2018-07-21 | Z-SR | 130/– , 78 mm/h | D-5 capacity 8, blocked 0.2 | 3 | 3,500 / 300 / 2 | TU-1 flooded 2.1 m (PU-T1 alone failed); RD-13 closed; RD-04 closed 6 h |
| HI-2019-CY-01 | cyclone | Cyclone Viraj | 2019-05-03..05 | Z-RS; all | 85/– | wind 110 gust 140, stage 3.2 | 3 | 30,000 / 2,500 / 2 | PS-2 outage 26 h; H-2 on generator 12 h (limit reached); RD-01 blocked 10 h; S-1, S-2, S-3 opened |
| HI-2019-LS-01 | landslide | Hill Road cut landslide | 2019-08-11 | Z-HV; SL-HV-3; RS ponding | 172/295 | D-7 current 38 then | 4 | 6,000 / 1,100 / 1 | 1,800 m³ debris → D-7 blocked 0.45 for 72 h; RD-01 closed 72 h; RA-03 flooded 0.5 m; S-5 opened; no soil probes existed |
| HI-2020-FF-01 | flash_flood | New Colony Sector 1 flash flood | 2020-08-30 | Z-NC | 110/– , 62 mm/h | D-9 design 35 % imperv., catchment 44 % | 2 | 6,000 / 500 / 0 | RD-09 flooded 0.4 m; S-4 opened with 0.1 m water; D-9 surcharged |
| HI-2020-UF-01 | urban_fire | Mill Road solvent warehouse fire | 2020-12-19 | Z-MI (10800,1500) | – | – | 3 | 3,000 / 3,000 / 1, 22 injured | FT-07 foam; PS-3 precautionary shutdown 6 h → WF-6 stopped; H-5 burn beds (16) full, overflow to H-1; RD-08 closed 14 h; S-8 opened |
| HI-2021-FL-01 | flood | Great Kalinadi flood 2021 | 2021-09-12..19 | Z-RS; RS, OT, LK, NC, MI, HV(lower) | 210/410 | stage 5.8 record; DM-1 releasing 1,650 | 5 | 41,000 / 15,500 / 9 | OT embankment overtopped 0.3 m; PS-2 flooded, outage 38 h; WF-2 out 4 days; H-2 evacuated 36 patients to H-1; S-5 flooded 0.9 m while occupied (210 moved to S-1); D-3 overflowed; D-8 gate closed 120 h; D-11 pumps 7 days, PU-L3 overheated; BR-1 closed 52 h, pier 3 scour found; TU-1 flooded; WF-6 flooded → contamination; RA-16, RA-17 flooded 0.6 m |
| HI-2022-LS-01 | landslide | Hillview Terrace Phase 1 cut-slope failure | 2022-07-16 | Z-HV; SL-HV-2 | 118/205 | SM-03 saturation 0.86; 4 m cut at 34 ° unsupported 3 weeks | 3 | 350 / 350 / 1, 6 injured | PR-HT1 halted 4 months; RD-01 partially blocked 24 h; retaining wall built |
| HI-2023-UF-01 | urban_fire | Station Road goods warehouse fire | 2023-04-08 | Z-SR (2400,4500) | – | – | 2 | 800 / 200 / 0, 4 injured | RD-13 closed 8 h; rail suspended 6 h; FS-1 arrived 12 min |
| HI-2024-LS-01 | landslide | Tekri quarry bench slide | 2024-09-02 | Z-TH; SL-TH-1 | 140/260 | SM-04 saturation 0.80 | 2 | 300 / 60 / 0, 2 injured | RD-11 blocked 96 h; 900 m³ debris into D-7 head reach → blocked 0.15 for 2 weeks; RA-22 12 houses evacuated; hazard review ordered for PR-TQ |
| HI-2024-CY-01 | cyclone | Cyclone Meher | 2024-10-27..29 | Z-LK; all | 190/310 | wind 95 gust 125, stage 4.9 | 4 | 28,000 / 6,000 / 4 | PU-L2 failed (D-11 12→9.5); PS-5 held; PS-2 outage 8 h; RD-07 closed 48 h; H-4 ground floor 0.3 m; S-7 NOT opened (policy), S-1, S-3 used; BR-1 closed 20 h |
| HI-2025-FF-01 | flash_flood | Riverside flash flood after culvert narrowing | 2025-07-19 | Z-RS; HV lower | 96/– , 55 mm/h | stage 3.4; D-7 flow ≈ 31 vs capacity 27; CL-D7 2.9 m (soffit 1.8) | 2 | 2,400 / 400 / 0, 3 injured | D-7 surcharged at BR-4; RD-01 closed 5 h; RA-02 flooded 0.6 m; S-5 opened; PU-M1, PU-M2 deployed at D-7 outfall |

## 6. Knowledge tables

**`documents`** (id, title, kind policy|sop|report|permit|change_log|profile, source, version, effective_date,
hazards (list), zone_ids (list), supersedes, summary, source_path). **`document_sections`** (id
"<doc>#<section>", document_id, section e.g. `s4.2`, heading, text, position). **`policy_thresholds`** (id PT-01..,
document_id, section, hazard, metric landslide_index|flood_index|rain_24h_mm|rain_1h_mm|saturation|river_stage_m|
wind_kmh|channel_flow_ratio|water_depth_m, band watch|warning|critical|halt|close|activate, applies_to, operator,
value, unit, note) seeded from `policy_thresholds.yaml`; each value must appear verbatim in the cited section.

Threshold set (the numbers the detector will load later, all stated in `dmp-2024` §4 and repeated in the SOPs):
landslide_index watch ≥ 0.35, warning ≥ 0.55, critical ≥ 0.75; flood_index watch ≥ 0.30, warning ≥ 0.50, critical
≥ 0.70; slopes above 25°: rain_24h watch ≥ 65 mm, warning ≥ 115 mm, critical ≥ 175 mm; saturation warning ≥ 0.70,
critical ≥ 0.85; construction halt on slopes > 25° when rain_24h ≥ 65 mm or saturation ≥ 0.70; flash flood
rain_1h watch ≥ 30 mm/h, warning ≥ 50 mm/h; river stage RV-01 watch 4.2 m, warning 5.0 m (BR-1 closes), critical
5.5 m; floodplain shelters not activated at stage ≥ 4.5 m; channel flow/capacity ratio watch ≥ 0.8, overflow ≥ 1.0;
wind watch ≥ 62 km/h, warning ≥ 89, critical ≥ 118; road closure at water depth ≥ 0.3 m.

## 7. Corpus (33 Markdown documents in `backend/data/corpus/`)

Front matter (YAML between `---` lines): `document_id`, `title`, `kind`, `source`, `version` (string),
`effective_date`, `hazards`, `zone_ids`, `supersedes` (optional), `summary`; reports add an `incident:` block with
every `historical_incidents` column except document_id, plus `impacts: [{asset_kind, asset_id, impact, detail,
duration_hours?, depth_m?}]`. Body: numbered `## N Title` or `## N.M Title` headings → section id `sN` / `sN.M`;
text before the first heading becomes `s0` if non-empty; `###` stays inside its parent section. Citation ID of a
section is `[<document_id>#<section>]`, e.g. `[dmp-2024#s4.2]`.

| document_id | kind | title | version / effective | source |
|---|---|---|---|---|
| dmp-2024 | policy | Nandipur Disaster Management Policy | 3.0 / 2024-04-01 (supersedes dmp-2019) | NMC Disaster Management Cell |
| sop-emergency-ops-2023 | sop | Emergency Operations Standard Operating Procedures | 2.1 / 2023-06-01 | NMC-DMC, Emergency Operations Centre |
| pol-flood-response-2024 | policy | Flood Response Policy | 2.0 / 2024-05-15 | NMC-DMC |
| sop-landslide-prevention-2023 | sop | Landslide Prevention and Slope Monitoring SOP | 1.2 / 2023-08-01 | NMC-DMC with State Geological Survey |
| pol-evacuation-2022 | policy | Evacuation Policy | 1.1 / 2022-03-01 | NMC-DMC |
| pol-shelter-activation-2024 | policy | Shelter Activation Policy | 2.0 / 2024-02-01 | NMC-DMC |
| pol-resource-allocation-2023 | policy | Emergency Resource Allocation Policy | 1.3 / 2023-09-01 | NMC-DMC |
| pol-road-closure-2021 | policy | Road Closure and Traffic Management Policy | 1.0 / 2021-11-01 | NMC Roads Division with City Police |
| pol-construction-hazard-2025 | policy | Construction Hazard Policy | 1.0 / 2025-02-01 | NMC Town Planning Department |
| pol-incident-escalation-2024 | policy | Incident Escalation Policy | 2.0 / 2024-03-01 | NMC-DMC |
| sop-crew-dispatch-2023 | sop | Crew Dispatch SOP | 1.0 / 2023-05-01 | NMC-DMC |
| sop-pump-deployment-2022 | sop | Mobile Pump Deployment SOP | 1.1 / 2022-07-01 | NMC Drainage Division |
| permit-ht-2026-014 | permit | Construction Permit HT-2026-014 — Hillview Terrace Phase 2 | 1.0 / 2026-01-20 | NMC Town Planning Department |
| changelog-infra-2018-2026 | change_log | Infrastructure Change Log 2018–2026 | 2026.09 / 2026-09-01 | NMC Engineering Department |
| geo-profiles-2020 | profile | Zone Geotechnical Profiles | 1.0 / 2020-06-01 | State Geological Survey, Nandipur District Office |
| city-profile-2026 | profile | Nandipur City Profile 2026 | 2026 / 2026-06-30 | NMC Planning Department |
| rep-2012-fl-01 … rep-2025-ff-01 (17) | report | Post-incident review: <incident title> | 1.0 / 3–8 weeks after the incident | NMC-DMC Post-Incident Review Board |

Report section plan: 1 Summary, 2 Weather and hydrological conditions, 3 Infrastructure state at the time,
4 Impact, 5 Response, 6 Outcome, 7 Lessons and recommendations. Reports state facts and what was done; they do not
draw the cross-incident conclusions the agent is meant to draw. Policy documents state rules and thresholds with
numbered sections so each rule is citable. The permit lists conditions (max 6.0 m in 1.5 m benches; halt when
RG-02 24 h rainfall ≥ 65 mm or SM-01/SM-02 saturation ≥ 0.70; retaining wall before 2026-06-15 — not yet built at
seed time; no spoil within 30 m of D-7; weekly monitoring reports). The change log has one section per year
(`s2018`…`s2026`) naming every CH id. Geo profiles: `s0` intro then `s1`…`s10`, one per zone in §5.2 order.

## 8. Seed and tests

Seed (`gridline/db/seed/seed.py`): `create_schema(engine)`, `drop_schema(engine)`, `seed(session, data_dir) ->
SeedSummary` (row counts per table). Order: city, geological_zones, catchments, rivers, hills, zones (drains_to
null), soil_profiles, slopes, flood_plains, drainage_channels, zones second pass, pump_units, roads, bridges,
tunnels, dams, power_substations, water_facilities, documents + sections (corpus), projects, critical_infrastructure,
sensors, hospitals, hospital_beds, ambulances, fire_stations, fire_trucks, police_stations, crews, schools, shelters,
zone_yearly_stats, residential_areas, infrastructure_changes, historical_incidents + impacts, policy_thresholds,
elevation_points. Loader (`loader.py`) validates YAML through the Pydantic models in `gridline/city/schema_*.py`
and resolves every reference before any DB write (fails fast with the offending id). CLI:
`python -m gridline.db.seed [--reset] [--database-url URL] [--data-dir PATH]`.

Tests (pytest, pytest-asyncio; session-scoped engine on `TEST_DATABASE_URL`; schema dropped/created and seeded once):
- `test_schema.py`: all expected tables exist with key columns; FKs present; create is idempotent.
- `test_seed.py`: counts per table match the YAML/corpus; reset+reseed yields identical counts.
- `test_relationships.py`: Hillview → D-7 → Riverside chain; every project slope/zone/permit resolves; every
  incident impact and change asset resolves (polymorphic); critical infrastructure dependencies resolve; shelter ↔
  school; hospital → substation → fed_from PS-1; policy_thresholds cite existing sections and values appear in text.
- `test_queries.py`: shelter capacity vs floodplain residents per zone; channels below design capacity; slopes
  above 25° with active projects; hospitals on flood-exposed substations; incidents by hazard; changes touching D-7;
  documents by kind; yearly population growth for New Colony.
- `test_corpus.py`: all 33 documents parse; section ids well-formed; reports carry complete incident blocks.
- `test_consistency.py` (pure Python, no DB): every cross-reference resolves; assets lie inside their zone bbox;
  elevations equal terrain; R-1 path follows `river_y`; zone RA populations ≈ zone 2026 population (±10 %);
  yearly stats years complete; change log mentions every CH id; each incident's report front matter id matches.

## 9. Relationships the data supports without stating them

Hillview Terrace Phase 2 excavates a 32° marginal slope whose toe is 60 m from D-7, whose culvert was narrowed
in 2025 without hydraulic review (CH-2025-02) and already surcharged in 2025 (HI-2025-FF-01); a 2019 slide on the
same ridge blocked D-7 and ponded Riverside (HI-2019-LS-01); Riverside's hospital H-2 sits on substation PS-2 that
floods, with 12 h of backup that ran out in 2019; the only road to Hillview is Hill Road; shelter S-5 on FP-1 was
flooded while occupied in 2021; New Colony grew from 9,000 to 58,000 on FP-2 while D-9 kept its 35 % design; the
Lakeside basin drains only by pumps fed from PS-5 with one pump already failed; the WF-3 reservoir sits 400 m
upslope of the active excavation; the permit's retaining-wall deadline (2026-06-15) has passed.
