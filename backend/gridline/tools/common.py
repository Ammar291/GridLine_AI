"""Shared tool helpers: ids, clock, lookups raising ``ToolRejected``, access roads, tasks and checks."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.db.base import Base
from gridline.db.models import Incident, Road, Task
from gridline.tools.base import ActionResult, EntityKind, ToolRejected, VerificationCheck, VerificationResult
from gridline.tools.vocab import Priority, TargetKind, TaskKind


def new_id(prefix: str) -> str:
    """A server-generated id such as ``task_1a2b3c4d5e6f``."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


async def fetch_all[M: Base](session: AsyncSession, stmt: Select[M]) -> Sequence[M]:
    """Rows of ``stmt`` refreshed from the database, even if older copies sit in the identity map."""
    return (await session.scalars(stmt.execution_options(populate_existing=True))).all()


async def reread[M: Base](session: AsyncSession, model: type[M], row_id: str) -> M | None:
    """A row as the database has it now (``verify`` never trusts the identity map)."""
    return await session.get(model, row_id, populate_existing=True)


async def require[M: Base](
    session: AsyncSession, model: type[M], row_id: str, kind: str, *, lock: bool = False
) -> M:
    """The row (locked ``FOR UPDATE`` if the action changes it), else ``"<kind> '<id>' not found"``."""
    row = await session.get(model, row_id, with_for_update=lock)
    if row is None:
        raise ToolRejected(f"{kind} '{row_id}' not found")
    return row


async def require_open_incident(session: AsyncSession, incident_id: str) -> Incident:
    incident = await require(session, Incident, incident_id, "incident")
    if incident.status != "open":
        raise ToolRejected(f"incident '{incident_id}' is {incident.status}")
    return incident


async def open_access_roads(session: AsyncSession, zone_id: str) -> list[Road]:
    """Open roads that link ``zone_id`` to another zone (a road local to one zone is no way in or out)."""
    touching = or_(Road.zone_id == zone_id, Road.from_zone_id == zone_id, Road.to_zone_id == zone_id)
    roads = await fetch_all(session, select(Road).where(touching, Road.status == "open").order_by(Road.id))
    return [r for r in roads if len({r.zone_id, r.from_zone_id, r.to_zone_id}) > 1]


async def require_open_access(session: AsyncSession, zone_id: str) -> None:
    if not await open_access_roads(session, zone_id):
        raise ToolRejected(f"zone '{zone_id}' has no open access road")


async def require_road_open(session: AsyncSession, road_id: str, owner: str) -> None:
    """Reject when ``owner`` (e.g. ``"shelter 'S-6'"``) is reached over a road that is not open."""
    road = await session.get(Road, road_id)
    if road is not None and road.status != "open":
        raise ToolRejected(f"{owner} access road '{road_id}' is {road.status}")


async def first_open_task(session: AsyncSession, kind: TaskKind, *where: ColumnElement[bool]) -> Task | None:
    """The oldest open task of ``kind`` matching ``where`` (used for the "unchanged" rules)."""
    stmt = select(Task).where(Task.kind == kind, Task.status == "open", *where).order_by(Task.created_at)
    rows = await fetch_all(session, stmt.limit(1))
    return rows[0] if rows else None


@dataclass(frozen=True)
class TaskPlan:
    """What a task tool's ``check`` found: an equivalent open task (``unchanged``) and the task's zone."""

    existing: Task | None
    zone_id: str | None


def create_task(
    session: AsyncSession,
    *,
    kind: TaskKind,
    title: str,
    description: str,
    priority: Priority,
    zone_id: str | None,
    created_by: str,
    target_kind: TargetKind | None = None,
    target_id: str | None = None,
    metric: str | None = None,
    interval_minutes: int | None = None,
    assigned_crew_id: str | None = None,
    incident_id: str | None = None,
    evacuation_order_id: str | None = None,
) -> Task:
    """The single insertion point for the four task kinds; the row is added to the session, not flushed."""
    task = Task(
        id=new_id("task"),
        kind=kind,
        title=title,
        description=description,
        priority=priority,
        status="open",
        zone_id=zone_id,
        target_kind=target_kind,
        target_id=target_id,
        metric=metric,
        interval_minutes=interval_minutes,
        assigned_crew_id=assigned_crew_id,
        incident_id=incident_id,
        evacuation_order_id=evacuation_order_id,
        created_by=created_by,
        created_at=utcnow(),
        completed_at=None,
    )
    session.add(task)
    return task


def check(name: str, expected: Any, observed: Any) -> VerificationCheck:
    return VerificationCheck(name=name, passed=expected == observed, expected=expected, observed=observed)


def verification(*checks: VerificationCheck) -> VerificationResult:
    """``verified`` only when there is at least one check and every check passed."""
    passed = bool(checks) and all(c.passed for c in checks)
    return VerificationResult(status="verified" if passed else "failed", checks=list(checks))


def ids_in(result: ActionResult, kind: EntityKind) -> list[str]:
    """Ids of ``kind`` in a result's after-snapshot: created rows, or the row an unchanged call found."""
    prefix = f"{kind}:"
    return [key.removeprefix(prefix) for key in result.after if key.startswith(prefix)]


async def verify_open_task(
    session: AsyncSession, result: ActionResult, **expected: Any
) -> VerificationResult:
    """Post-condition shared by the task tools: the task in the result is open and has ``expected`` values."""
    ids = ids_in(result, "task")
    task = await reread(session, Task, ids[0]) if ids else None
    checks = [check("task open", "open", task.status if task else None)]
    checks += [check(f"task {name}", value, getattr(task, name, None)) for name, value in expected.items()]
    return verification(*checks)
