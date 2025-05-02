"""
backend.data.models.pr_review_comment
-------------------------------------
This module defines the PRReviewComment model, representing a specific comment
made as part of a code review on a GitHub Pull Request.
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
    from .pull_request import PullRequest
    from .contributor import Contributor # Assumes the comment author is stored as a Contributor

logger = logging.getLogger(__name__)

class PRReviewComment(BaseModel, Base):
    """
    Represents a comment made during a GitHub Pull Request code review.

    This model stores details about a single comment that is part of a larger
    Pull Request review conversation. It links the comment to the specific
    Pull Request, the user (Contributor) who made the comment, and potentially
    the overall review it belongs to.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to this specific comment.
        pull_request_review_id: The GitHub ID of the parent review object this comment is part of (optional).
        pr_id: Foreign key linking to the PullRequest this comment is associated with.
        user_id: Foreign key linking to the Contributor who wrote the comment.
        body: The text content of the review comment.
        gh_created_at: Timestamp when the comment was created on GitHub.
        gh_updated_at: Timestamp when the comment was last updated on GitHub.
        pull_request: Relationship back to the parent PullRequest object.
        user: Relationship back to the Contributor (author) object.
    """
    __tablename__ = "pr_review_comments"

    # --- GitHub Identifiers ---
    # Unique IDs connecting this record to the source GitHub data.

    # GitHub's unique ID for this specific review comment. Indexed.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # The ID of the overarching review summary/submission this comment belongs to.
    # Can be nullable as some comments might exist outside a formal review submission. Indexed.
    pull_request_review_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # --- Foreign Keys ---
    # Links to the parent Pull Request and the authoring Contributor.

    # Link to the Pull Request the comment is on. Indexed. Cascade delete ensures
    # review comments are removed if their parent PR is deleted.
    pr_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Link to the Contributor record representing the comment's author. Indexed.
    # Assumes the author exists in the 'contributors' table.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("contributors.id"), index=True, nullable=False
    )

    # --- Comment Content ---
    # The actual text of the review comment.
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Use Text for potentially long comments.

    # --- GitHub Timestamps ---
    # Stores the original timestamps from GitHub, preserving timezone information.

    # When the comment was created on GitHub.
    gh_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the comment was last updated on GitHub.
    gh_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    # Define relationships for navigating from a PRReviewComment instance.

    # Relationship to the parent Pull Request.
    # Consider adding `back_populates="review_comments"` if PullRequest needs this link.
    pull_request: Mapped["PullRequest"] = relationship()

    # Relationship to the Contributor who authored the comment.
    # Consider adding `back_populates="pr_review_comments"` if Contributor needs this link.
    user: Mapped["Contributor"] = relationship()

    # --- Table Arguments ---
    # Define indexes to optimize common query patterns.
    __table_args__ = (
        # Index on the foreign key to Pull Request.
        Index('ix_pr_review_comments_pr_id', 'pr_id'),
        # Index on the foreign key to the user (author).
        Index('ix_pr_review_comments_user_id', 'user_id'),
        # Index on the GitHub review ID (pull_request_review_id). Useful if querying comments by review.
        # This index was already present via `index=True` on the column, but explicit definition is fine.
        Index('ix_pr_review_comments_review_id', 'pull_request_review_id'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        return (f"<PRReviewComment(id={obj_id}, gh_id={self.github_id}, "
                f"pr_id={self.pr_id}, user_id={self.user_id})>")