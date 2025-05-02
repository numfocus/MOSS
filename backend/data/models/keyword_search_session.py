"""
backend.data.models.keyword_search_session
------------------------------------------
This module defines the KeywordSearchSession model, which records the details
and status of a single execution of a keyword-based repository search operation.
"""

import logging
from datetime import datetime # Required for DateTime type hints
from typing import Optional, TYPE_CHECKING # TYPE_CHECKING if relationships are used
from sqlalchemy import (
    String, Integer, Text, Index, DateTime, func # func needed for server_default
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel # Inherits id, created_at, updated_at
from .types import timestamp_nullable # Import custom type for nullable timestamp

logger = logging.getLogger(__name__)

# Uncomment if relationships to results (e.g., via KeywordRepositoryAssociation) are needed.
# if TYPE_CHECKING:
#    from .keyword_repository_association import KeywordRepositoryAssociation

class KeywordSearchSession(BaseModel, Base):
    """
    Represents a single execution of a keyword search task.

    This model tracks the parameters (keywords used), the execution status
    (pending, running, completed, failed), timing information, and a summary
    of the results (e.g., count of repositories found). It helps monitor and
    manage asynchronous search operations.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        keywords_raw: The raw string or structure of keywords used for this search.
        status: The current execution status of the search task.
        results_count: The total number of repositories found in this session (if completed).
        started_at: Timestamp when the search task processing began.
        completed_at: Timestamp when the search task finished (successfully or failed).
        # repository_associations: Optional relationship to link to the actual results.
    """
    __tablename__ = "keyword_search_sessions"

    # --- Search Parameters ---
    # Stores the input criteria for this specific search execution.
    # Using Text allows for potentially long or complex keyword queries.
    keywords_raw: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Execution Tracking ---
    # Tracks the lifecycle and outcome of the search task.

    # Current status, e.g., 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'. Indexed for easy querying of task states.
    status: Mapped[str] = mapped_column(
        String, index=True, nullable=False, default='PENDING'
    )
    # Stores the number of results found upon successful completion.
    results_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # --- Timestamps ---
    # Records when the search task started and ended, supplementing the standard
    # created_at/updated_at timestamps from BaseModel.

    # Timestamp when the processing of this search task actually began.
    # Uses server_default for reliability, similar to created_at.
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Timestamp when the task concluded (either COMPLETED or FAILED). Null if still PENDING/RUNNING.
    # Uses the custom `timestamp_nullable` type for consistency.
    completed_at: Mapped[timestamp_nullable]

    # --- Relationships (Optional) ---
    # Defines the link to the results found during this session.
    # This relationship links this session to the association records that, in turn,
    # point to the specific repositories found.
    # Uncomment and ensure KeywordRepositoryAssociation has the corresponding `back_populates`.
    # repository_associations: Mapped[List["KeywordRepositoryAssociation"]] = relationship(
    #     back_populates="search_session", cascade="all, delete-orphan"
    #     # Cascade ensures association records are removed if the session is deleted.
    # )

    # --- Table Arguments ---
    # Define indexes to optimize common query patterns.
    __table_args__ = (
        # Index on the 'status' column is crucial for efficiently finding sessions
        # that are pending, running, failed, etc., for monitoring or retries.
        Index('ix_keyword_search_sessions_status', 'status'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        repr_id = getattr(self, 'id', None)
        # Truncate long keyword strings for readability
        keywords_repr = (self.keywords_raw[:50] + '...') if len(self.keywords_raw) > 50 else self.keywords_raw
        return (f"<KeywordSearchSession(id={repr_id}, keywords='{keywords_repr}', "
                f"status='{self.status}')>")