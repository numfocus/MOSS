"""
backend.data.models.issue_comment
---------------------------------
This module defines the IssueComment model, representing a comment made on a
GitHub Issue within a tracked Repository.
"""

import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime # Required for DateTime type hints

from sqlalchemy import (
    String, Integer, Text, Boolean, DateTime, BigInteger, ForeignKey, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .issue import Issue
    from .contributor import Contributor # Assumes the comment author is stored as a Contributor

logger = logging.getLogger(__name__)

class IssueComment(BaseModel, Base):
    """
    Represents a comment on a GitHub Issue.

    This model stores information about a single comment posted on an Issue,
    linking it back to the parent Issue and the user (Contributor) who wrote it.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to the comment.
        issue_id: Foreign key linking to the Issue this comment belongs to.
        user_id: Foreign key linking to the Contributor who wrote the comment.
        body: The text content of the comment.
        gh_created_at: Timestamp when the comment was created on GitHub.
        gh_updated_at: Timestamp when the comment was last updated on GitHub.
        issue: Relationship back to the parent Issue object.
        user: Relationship back to the Contributor (author) object.
    """
    __tablename__ = "issue_comments"

    # --- GitHub Identifier ---
    # Unique ID connecting this record to the source GitHub data.

    # GitHub's unique ID for this specific comment. Indexed for efficient lookup.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # --- Foreign Keys ---
    # Links to related entities (Issue, Contributor).

    # Link to the parent Issue. Indexed. Cascade delete ensures comments
    # are removed if their parent issue is deleted.
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Link to the Contributor record representing the comment's author. Indexed.
    # Assumes the author exists in the 'contributors' table.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("contributors.id"), index=True, nullable=False
    )

    # --- Comment Content ---
    # The main textual body of the comment.
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Stored as Text for potentially long comments.

    # --- GitHub Timestamps ---
    # Stores the original timestamps from GitHub, preserving timezone information.

    # When the comment was created on GitHub.
    gh_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the comment was last updated on GitHub.
    gh_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    # Define relationships for navigating from an IssueComment instance.

    # Relationship to the parent Issue.
    # Consider adding `back_populates="comments"` if the Issue model has a 'comments' collection.
    issue: Mapped["Issue"] = relationship()

    # Relationship to the Contributor who authored the comment.
    # Consider adding `back_populates="issue_comments"` if Contributor needs this link.
    user: Mapped["Contributor"] = relationship()

    # --- Table Arguments ---
    # Define indexes to optimize common query patterns, especially filtering by issue or user.
    __table_args__ = (
        Index('ix_issue_comments_issue_id', 'issue_id'), # Index for finding comments by issue
        Index('ix_issue_comments_user_id', 'user_id'),   # Index for finding comments by user
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        return (f"<IssueComment(id={obj_id}, gh_id={self.github_id}, "
                f"issue_id={self.issue_id}, user_id={self.user_id})>")