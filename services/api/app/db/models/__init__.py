"""
SQLAlchemy ORM models — single source of truth for the life-coach schema.

All models are declared here and imported by Alembic's env.py so autogenerate
can detect schema changes.  See docs/DESIGN.md §4 for the full entity diagram.

Import order matters for FK resolution — keep it alphabetical within each layer.
"""

from app.db.models.audit import AuditEvent
from app.db.models.coaching_session import CoachingSession
from app.db.models.conversation import Conversation, Message
from app.db.models.embedding import Embedding
from app.db.models.goal import Goal, Milestone, Project, Task
from app.db.models.life_profile import Domain, LifeProfile
from app.db.models.memory import EpisodicMemory, Preference, SemanticFact
from app.db.models.relationship import Insight, Relationship, TimelineEvent
from app.db.models.user import User

__all__ = [
    "AuditEvent",
    "CoachingSession",
    "Conversation",
    "Domain",
    "Embedding",
    "EpisodicMemory",
    "Goal",
    "Insight",
    "LifeProfile",
    "Message",
    "Milestone",
    "Preference",
    "Project",
    "Relationship",
    "SemanticFact",
    "Task",
    "TimelineEvent",
    "User",
]
