"""Goals CRUD — and by extension tasks (docs/DESIGN.md §4)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, CurrentUserDep
from app.db.session import AuthedDB
from app.schemas.goal import GoalCreateIn, GoalOut, GoalPatchIn, TaskCreateIn, TaskOut

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _user_id(db: AsyncSession, eid: str) -> str:
    row = await db.execute(text("SELECT id FROM users WHERE external_auth_id = :eid"), {"eid": eid})
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return str(r[0])


@router.get("", response_model=list[GoalOut])
async def list_goals(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> list[GoalOut]:
    uid = await _user_id(db, current_user.external_auth_id)
    rows = await db.execute(
        text("""
            SELECT id, title, description, horizon, status, progress, importance,
                   target_date, domain_id
            FROM goals WHERE user_id = :uid::uuid AND status != 'dropped'
            ORDER BY importance DESC, created_at
        """),
        {"uid": uid},
    )
    return [
        GoalOut(
            id=str(r[0]),
            title=r[1],
            description=r[2],
            horizon=r[3],
            status=r[4],
            progress=r[5],
            importance=r[6],
            target_date=r[7],
            domain_id=str(r[8]) if r[8] else None,
        )
        for r in rows.fetchall()
    ]


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreateIn,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> GoalOut:
    uid = await _user_id(db, current_user.external_auth_id)
    goal_id = str(uuid.uuid4())
    await db.execute(
        text("""
            INSERT INTO goals (id, user_id, title, description, horizon,
                               target_date, importance, domain_id)
            VALUES (:id::uuid, :uid::uuid, :title, :desc, :horizon,
                    :td, :imp, :did::uuid)
        """),
        {
            "id": goal_id,
            "uid": uid,
            "title": body.title,
            "desc": body.description,
            "horizon": body.horizon,
            "td": str(body.target_date) if body.target_date else None,
            "imp": body.importance,
            "did": str(body.domain_id) if body.domain_id else None,
        },
    )
    await db.commit()
    logger.info("goal.created", user_id=uid, goal_id=goal_id)
    return GoalOut(
        id=goal_id,
        title=body.title,
        description=body.description,
        horizon=body.horizon,
        status="active",
        progress=0.0,
        importance=body.importance,
        target_date=body.target_date,
        domain_id=body.domain_id,
    )


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: str,
    body: GoalPatchIn,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> GoalOut:
    uid = await _user_id(db, current_user.external_auth_id)
    updates: list[str] = []
    params: dict = {"gid": goal_id, "uid": uid}

    if body.title is not None:
        updates.append("title = :title")
        params["title"] = body.title
    if body.status is not None:
        updates.append("status = :status")
        params["status"] = body.status
    if body.progress is not None:
        updates.append("progress = :progress")
        params["progress"] = body.progress
    if body.importance is not None:
        updates.append("importance = :importance")
        params["importance"] = body.importance
    if body.target_date is not None:
        updates.append("target_date = :td")
        params["td"] = str(body.target_date)

    if updates:
        await db.execute(
            text(
                "UPDATE goals"
                f" SET {', '.join(updates)}, updated_at = now()"
                " WHERE id = :gid::uuid AND user_id = :uid::uuid"
            ),
            params,
        )
        await db.commit()

    row = await db.execute(
        text("""
            SELECT id, title, description, horizon, status, progress, importance,
                   target_date, domain_id
            FROM goals WHERE id = :gid::uuid AND user_id = :uid::uuid
        """),
        {"gid": goal_id, "uid": uid},
    )
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    return GoalOut(
        id=str(r[0]),
        title=r[1],
        description=r[2],
        horizon=r[3],
        status=r[4],
        progress=r[5],
        importance=r[6],
        target_date=r[7],
        domain_id=str(r[8]) if r[8] else None,
    )


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateIn,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> TaskOut:
    uid = await _user_id(db, current_user.external_auth_id)
    task_id = str(uuid.uuid4())
    await db.execute(
        text("""
            INSERT INTO tasks (id, user_id, title, due_date, milestone_id, goal_id, source)
            VALUES (:id::uuid, :uid::uuid, :title, :td, :mid::uuid, :gid::uuid, :source)
        """),
        {
            "id": task_id,
            "uid": uid,
            "title": body.title,
            "td": str(body.due_date) if body.due_date else None,
            "mid": str(body.milestone_id) if body.milestone_id else None,
            "gid": str(body.goal_id) if body.goal_id else None,
            "source": body.source,
        },
    )
    await db.commit()
    return TaskOut(
        id=task_id,
        title=body.title,
        status="todo",
        source=body.source,
        due_date=body.due_date,
        milestone_id=body.milestone_id,
        goal_id=body.goal_id,
    )
