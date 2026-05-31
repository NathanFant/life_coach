"""Privacy: GDPR export + account deletion pipeline (docs/DESIGN.md §7.6)."""

from fastapi import APIRouter, status

router = APIRouter()


@router.post("/export", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def request_export() -> dict:
    """Enqueue a full-data export job → signed S3 URL (JSON + Markdown)."""
    return {"detail": "not_implemented"}


@router.delete("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_account() -> dict:
    """Enqueue the hard-delete pipeline (purges rows + embeddings, audits)."""
    return {"detail": "not_implemented"}
