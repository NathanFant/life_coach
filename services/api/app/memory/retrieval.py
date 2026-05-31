"""Hybrid retrieval pipeline + token-budget assembler (docs/DESIGN.md §5.4).

1. classify intent  2. always-load core  3. vector recall  4. structured recall
5. rank + MMR fuse  6. assemble within token budget → ContextBundle
"""

# TODO (Phase 1): implement the pipeline. Keep vector search filtered by user_id.
