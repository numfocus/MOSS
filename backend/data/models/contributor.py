"""
backend.data.models.contributor
-------------------------------
This module defines the Contributor model, representing a GitHub user or bot
identified as having contributed to a repository tracked by the system.
"""

from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, BigInteger, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .repository import Repository

class Contributor(BaseModel, Base):
    """
    Represents a GitHub User or Bot identified as a contributor.

    This model stores information about individuals or bots retrieved from GitHub
    who have contributed to one or more repositories. It links GitHub's unique
    identifiers and user details to an internal record.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to the user/bot.
        login: The GitHub username (login handle).
        type: The type of GitHub account ('User' or 'Bot').
        avatar_url: URL for the contributor's GitHub avatar image.
        html_url: URL to the contributor's profile page on GitHub.
        api_url: URL to the contributor's data endpoint in the GitHub API.
        repositories: Many-to-many relationship linking this contributor to the
                      Repositories they have contributed to, via the
                      'repository_contributors' association table.
    """
    __tablename__ = "contributors"

    # --- GitHub Identifiers and Details ---
    # Store key information directly retrieved from the GitHub API.

    # GitHub's unique ID for the user or bot. Indexed for fast lookups.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # GitHub login username. Should be unique and indexed.
    login: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Type of account, typically 'User' or 'Bot'. Indexed for filtering.
    type: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Optional profile details from GitHub.
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    html_url: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Link to GitHub profile
    api_url: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Link to GitHub API endpoint

    # --- Relationships ---
    # Define the many-to-many relationship to Repositories.

    # Specifies the relationship to the Repository model.
    # `secondary` points to the name of the association table (`repository_contributors`)
    # that physically links Contributors and Repositories.
    # `back_populates` establishes the bidirectional link to the 'contributors'
    # attribute defined in the Repository model.
    repositories: Mapped[List["Repository"]] = relationship(
        secondary="repository_contributors", # Name of the intermediary association table
        back_populates="contributors" # Connects to Repository.contributors
    )

    # --- Table Arguments ---
    # Define specific database indexes beyond those automatically created
    # for primary/unique keys.
    __table_args__ = (
        # Explicitly create an index on the 'type' column for faster filtering
        # queries based on contributor type (e.g., finding all 'User' contributors).
        Index('ix_contributors_type', 'type'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        return f"<Contributor(id={obj_id}, login='{self.login}', type='{self.type}')>"