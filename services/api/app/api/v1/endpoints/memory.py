"""Memory browse / correct / forget (docs/DESIGN.md §5.7). Users own their model."""

from fastapi import APIRouter, status

router = APIRouter()


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def browse_memory() -> dict:
    """Search/browse the user's memories across all types."""
    return {"detail": "not_implemented"}


@router.patch("/{memory_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def correct_memory(memory_id: str) -> dict:
    """Correct a fact; provenance + version history preserved."""
    return {"detail": "not_implemented", "memory_id": memory_id}


@router.delete("/{memory_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def forget_memory(memory_id: str) -> dict:
    """Forget a memory (also removes its embedding)."""
    return {"detail": "not_implemented", "memory_id": memory_id}
