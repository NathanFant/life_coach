"""Memory layer (docs/DESIGN.md §5).

The ONLY module that knows memory storage/retrieval internals. Coaching depends
on the `MemoryService` interface, so a pgvector → Qdrant swap stays local.
"""
