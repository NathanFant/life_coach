"""
Privacy: GDPR export + account deletion pipeline (docs/DESIGN.md §7.6).

POST /v1/account/export    → enqueue export job → return job ID (signed S3 URL in Phase 2)
DELETE /v1/account         → soft-delete user + enqueue hard-delete pipeline

Deletion SLA: complete within 30 days (GDPR), typically within hours.
The hard-delete pipeline is idempotent and audited — see app/workers/tasks.py.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, CurrentUserDep
from app.db.session import AuthedDB

router = APIRouter()
logger = structlog.get_logger(__name__)


class ExportResponse(BaseModel):
    export_id: str
    status: str = "queued"
    message: str = "Your data export has been queued. You will receive a download link via email."


class DeleteResponse(BaseModel):
    status: str = "deleting"
    message: str = (
        "Your account deletion has been initiated. All data will be permanently removed "
        "within 30 days. You have been signed out."
    )


@router.post("/export", response_model=ExportResponse)
async def request_export(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> ExportResponse:
    """
    Enqueue a full-data export job.

    Phase 1: enqueues a Celery task (stubbed).
    Phase 2: task assembles JSON + Markdown archive, uploads to S3, emails signed URL.
    """
    row = await db.execute(
        text("SELECT id FROM users WHERE external_auth_id = :eid"),
        {"eid": current_user.external_auth_id},
    )
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user_id = str(r[0])
    export_id = str(uuid.uuid4())

    # Emit audit event
    await db.execute(
        text("""
            INSERT INTO audit_events (id, user_id, actor, action, metadata)
            VALUES (gen_random_uuid(), :uid::uuid, :uid, 'data.export_requested', :meta::jsonb)
        """),
        {"uid": user_id, "meta": f'{{"export_id": "{export_id}"}}'},
    )
    await db.commit()

    # Enqueue export task
    try:
        from app.workers.tasks import export_account_data

        export_account_data.delay(user_id, export_id)
    except Exception:
        logger.warning("export.enqueue_failed", user_id=user_id)

    logger.info("account.export.requested", user_id=user_id, export_id=export_id)
    return ExportResponse(export_id=export_id)


@router.delete("", response_model=DeleteResponse)
async def delete_account(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> DeleteResponse:
    """
    Initiate account deletion (GDPR right to erasure).

    Immediately marks the user status as 'deleting' (blocks further login)
    and enqueues the hard-delete pipeline in a Celery worker.  The pipeline
    cascades through all user-owned rows, removes embeddings, and writes an
    immutable audit record.
    """
    row = await db.execute(
        text("SELECT id FROM users WHERE external_auth_id = :eid AND status != 'deleting'"),
        {"eid": current_user.external_auth_id},
    )
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found or already deleting")

    user_id = str(r[0])

    # Soft-delete: mark status = deleting (blocks login immediately)
    await db.execute(
        text("UPDATE users SET status = 'deleting', deleted_at = now() WHERE id = :uid::uuid"),
        {"uid": user_id},
    )

    # Audit the deletion request
    await db.execute(
        text("""
            INSERT INTO audit_events (id, user_id, actor, action, metadata)
            VALUES (gen_random_uuid(), :uid::uuid, :uid, 'account.delete_requested', '{}')
        """),
        {"uid": user_id},
    )
    await db.commit()

    # Enqueue hard-delete
    try:
        from app.workers.tasks import hard_delete_account

        hard_delete_account.delay(user_id)
    except Exception:
        logger.warning("account.delete.enqueue_failed", user_id=user_id)

    logger.info("account.delete.initiated", user_id=user_id)
    return DeleteResponse()
