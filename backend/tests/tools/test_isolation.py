"""The tool-test fixtures restore the seeded city between tests, so tool tests can commit for real."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from gridline.db.models import Action, Crew, HospitalBed, Incident
from tests.conftest import restore


async def test_restore_undoes_tool_writes(db_engine, baseline, tool_session, check_session):
    now = datetime.now(UTC)
    crew = await tool_session.get(Crew, "C-1")
    assert crew is not None and crew.status == "available"
    tool_session.add(
        Incident(
            id="inc_isolation", zone_id="Z-HV", hazard="landslide", band="watch", status="open",
            title="t", summary="t", opened_at=now, updated_at=now,
        )
    )  # fmt: skip
    await tool_session.flush()
    crew.status, crew.target_zone_id, crew.incident_id = "dispatched", "Z-HV", "inc_isolation"
    bed = await tool_session.get(HospitalBed, "H-1-general")
    assert bed is not None
    bed.available, bed.reserved = bed.available - 5, 5
    tool_session.add(
        Action(
            id="act_isolation", tool="t", status="executed", actor="agent", input_json={}, before_json={},
            after_json={}, affected_entities_json=[], message="t", executed_at=now,
        )
    )  # fmt: skip
    await tool_session.commit()

    await restore(db_engine, baseline)

    crew_back = await check_session.get(Crew, "C-1")
    assert crew_back is not None
    assert (crew_back.status, crew_back.target_zone_id, crew_back.incident_id) == ("available", None, None)
    bed_back = await check_session.get(HospitalBed, "H-1-general")
    assert bed_back is not None and (bed_back.available, bed_back.reserved) == (66, 0)
    for model in (Incident, Action):
        assert (await check_session.execute(select(func.count()).select_from(model))).scalar_one() == 0
