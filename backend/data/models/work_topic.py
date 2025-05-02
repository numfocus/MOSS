"""
backend.data.models.work_topic
------------------------------
This module defines the WorkTopic model, an association table linking scholarly
Works to their assigned subject Topics (from the OpenAlex hierarchy). It also
stores metadata about the association, like relevance score.
"""

import logging
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, Float, Boolean, ForeignKey, Index, PrimaryKeyConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base is correctly defined elsewhere
# Adjust import path as necessary
from ..database import Base
# This is an association table with a composite PK, so no BaseModel needed.

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .work import Work
    from .topic import Topic

logger = logging.getLogger(__name__)

class WorkTopic(Base):
    """
    Association table linking Works to their assigned OpenAlex Topics.

    This model represents the many-to-many relationship between scholarly Works
    and the subject Topics used to classify them (e.g., from OpenAlex). Each row
    signifies that a specific Work is associated with a specific Topic. It includes
    metadata like the relevance score assigned by the classification system and
    whether the topic is considered primary for the work.

    It uses a composite primary key and inherits directly from `Base`.

    Attributes:
        work_id: Foreign key linking to the Work. Part of the composite PK.
        topic_id: Foreign key linking to the Topic. Part of the composite PK.
        score: The relevance score assigned to this topic association (e.g., by OpenAlex).
        is_primary: Flag indicating if this topic is considered a primary topic for the work.
        work: Relationship back to the Work object.
        topic: Relationship back to the Topic object.
    """
    __tablename__ = "work_topics"

    # --- Composite Primary Key and Foreign Keys ---
    # These two columns together uniquely identify the association between a
    # specific Work and a specific Topic.

    # Foreign key referencing the Work table. Part of the composite PK.
    # `ondelete="CASCADE"` ensures that if the Work is deleted, its topic associations are removed.
    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"), primary_key=True
    )
    # Foreign key referencing the Topic table. Part of the composite PK.
    # `ondelete="CASCADE"` ensures that if the Topic is deleted, links to works are removed.
    # Consider if this cascade is desired - deleting a Topic might invalidate Work classifications.
    # Alternative: Prevent Topic deletion if linked, or set FK to NULL if nullable (not currently).
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )

    # --- Association Metadata ---
    # Stores additional information about the Work-Topic link provided by the source (e.g., OpenAlex).

    # Relevance score assigned by the classification system (e.g., probability, weight).
    # Nullable as not all sources might provide scores.
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Flag indicating if this topic is considered primary among potentially multiple topics
    # assigned to the work. Defaults to False.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Relationships ---
    # Defines relationships back to the Work and Topic models for navigation.

    # Relationship back to the Work.
    # `back_populates="topics"` links this to the 'topics' collection defined on the Work model.
    work: Mapped["Work"] = relationship(back_populates="topics")

    # Relationship back to the Topic.
    # No `back_populates` needed here if the Topic model doesn't require a direct list
    # of its associated WorkTopic entries (navigating Topic -> Works usually happens
    # via a potential relationship defined directly on Topic using `secondary="work_topics"`).
    topic: Mapped["Topic"] = relationship()

    # --- Table Arguments ---
    # Define the primary key constraint explicitly and add indexes.
    __table_args__ = (
        # Explicit definition of the composite primary key.
        PrimaryKeyConstraint('work_id', 'topic_id'),
        # Indexes on individual foreign keys improve performance when querying for
        # all topics of a work, or all works associated with a topic.
        Index('ix_work_topics_work_id', 'work_id'),
        Index('ix_work_topics_topic_id', 'topic_id'),
        # Potentially add index on 'score' or 'is_primary' if frequently used for filtering/sorting.
        # Index('ix_work_topics_is_primary', 'is_primary'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        primary_flag = ", primary" if self.is_primary else ""
        # Format score nicely, handling potential None value.
        score_repr = f", score={self.score:.3f}" if self.score is not None else ""
        return f"<WorkTopic(work={self.work_id}, topic={self.topic_id}{primary_flag}{score_repr})>"