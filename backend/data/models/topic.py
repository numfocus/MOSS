"""
backend.data.models.topic
-------------------------
This module defines the Topic model, representing the fourth-level subject
classification (Topic) from the OpenAlex dataset, nested under Subfields.
This is often the most granular level of subject classification provided.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .subfield import Subfield # For the many-to-one relationship to Subfield
    # The relationship to WorkTopic (and thus Works) is defined in WorkTopic model.

logger = logging.getLogger(__name__)

class Topic(BaseModel, Base):
    """
    Represents an OpenAlex Topic, the fourth and often most specific tier
    in the subject hierarchy.

    Topics provide fine-grained subject classification (e.g., "Relational databases"
    within the "Data management" Subfield). Each Topic belongs to exactly one Subfield.
    Topics are linked to Works via the `WorkTopic` association table.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: The unique identifier for this Topic in OpenAlex (e.g., "T12345").
        display_name: The human-readable name of the Topic (e.g., "Relational databases").
        description: An optional longer description of the Topic's scope.
        subfield_id: Foreign key linking this Topic to its parent Subfield.
        subfield: Many-to-one relationship back to the parent Subfield object.
        # Note: The link to Works is via the WorkTopic association model.
    """
    __tablename__ = "topics"

    # --- Identifiers and Details ---
    # Core attributes defining the Topic based on OpenAlex data.

    # OpenAlex unique ID for the Topic. Indexed for fast lookups.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Human-readable name. Indexed for searching and display.
    display_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Optional textual description provided by OpenAlex.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Foreign Key to Parent Subfield ---
    # Establishes the hierarchical link within the subject classification.
    subfield_id: Mapped[int] = mapped_column(
        ForeignKey("subfields.id", ondelete="CASCADE"), # Links to the parent Subfield
        index=True, # Index for efficient lookup of Topics within a Subfield
        nullable=False
        # 'ondelete="CASCADE"' ensures that if a Subfield is deleted, all its child Topics
        # are also deleted. This propagates deletions up the hierarchy if a Domain/Field is removed.
    )

    # --- Relationships ---
    # Defines how Topics connect back up the subject hierarchy.

    # Many-to-One relationship: Many Topics belong to one Subfield.
    # `back_populates` establishes the bidirectional link to the 'topics' collection
    # defined in the Subfield model.
    subfield: Mapped["Subfield"] = relationship(back_populates="topics")

    # --- Relationship to Works (via Association Table) ---
    # The many-to-many relationship between Topics and Works is defined in the
    # `WorkTopic` model, which acts as the association table. A relationship
    # definition like the one commented out below could be added here *if* you
    # frequently need to navigate from a Topic directly to its associated Works.
    # It would require `Work` to also define a relationship back to `WorkTopic`.
    # works: Mapped[List["Work"]] = relationship(
    #     secondary="work_topics", # Name of the association table
    #     back_populates="topics"  # Assumes Work has a 'topics' relationship via WorkTopic
    # )

    # --- Table Arguments ---
    # Explicitly define indexes for optimized query performance.
    __table_args__ = (
        # Index on OpenAlex ID (unique already implies index, but explicit).
        Index('ix_topics_openalex_id', 'openalex_id'),
        # Index on display name for text searches or sorting.
        Index('ix_topics_display_name', 'display_name'),
        # Index on the foreign key to the parent Subfield (already indexed via column def, but explicit).
        Index('ix_topics_subfield_id', 'subfield_id'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        return f"<Topic(id={obj_id}, name='{self.display_name}', oa_id='{self.openalex_id}')>"