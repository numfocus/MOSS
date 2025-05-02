"""
backend.data.models.owner
-------------------------
This module defines the Owner model, representing a GitHub entity (either a
User or an Organization) that can own repositories.
"""

from typing import List, TYPE_CHECKING # TYPE_CHECKING needed for relationship hint
from sqlalchemy import String, BigInteger, Index, ForeignKey # ForeignKey needed if relationships defined on this side
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel # Inherits id, created_at, updated_at

# Use TYPE_CHECKING to prevent circular imports when type hinting the relationship
if TYPE_CHECKING:
    from .repository import Repository # For the one-to-many relationship

class Owner(BaseModel, Base):
    """
    Represents a GitHub User or Organization that owns repositories.

    This model stores information about the GitHub account (User or Organization)
    that serves as the owner of one or more repositories tracked by the system.
    It mirrors key identifiers and details from the GitHub API Owner object.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to the User/Organization.
        login: The GitHub username or organization name (login handle).
        type: The type of GitHub account ('User' or 'Organization').
        avatar_url: URL for the owner's GitHub avatar image.
        html_url: URL to the owner's profile page on GitHub.
        api_url: URL to the owner's data endpoint in the GitHub API.
        repositories: One-to-many relationship linking this owner to the Repositories they own.
    """
    __tablename__ = "owners"

    # --- GitHub Identifiers and Details ---
    # Core information identifying the GitHub owner account.

    # GitHub's unique numerical ID for the User or Organization. Indexed for fast lookups.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # GitHub login name (username or organization name). Must be unique and indexed.
    login: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Type distinguishes between individual users and organizations. Indexed for filtering.
    type: Mapped[str] = mapped_column(String, index=True, nullable=False) # Typically 'User' or 'Organization'

    # Optional profile details retrieved from GitHub.
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True) # Accepts str or None
    html_url: Mapped[str | None] = mapped_column(String, nullable=True)   # Link to GitHub profile page
    api_url: Mapped[str | None] = mapped_column(String, nullable=True)    # Link to GitHub API data for this owner

    # --- Relationships ---
    # Defines the connection to the repositories owned by this entity.

    # One-to-Many relationship: An Owner can own multiple Repositories.
    # `back_populates` establishes the bidirectional link to the 'owner' attribute
    # defined in the Repository model.
    # `cascade="all, delete-orphan"`: If an Owner is deleted, all Repositories owned
    # by them will also be deleted. This is a significant side effect and should be
    # carefully considered. Alternatives might include preventing deletion if
    # repositories exist or setting the repository's owner_id to NULL (if allowed).
    repositories: Mapped[List["Repository"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Define specific database indexes beyond those for primary/unique keys.
    __table_args__ = (
        # Explicitly create an index on the 'type' column. This is useful for queries
        # that specifically target only users or only organizations.
        Index('ix_owners_type', 'type'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        return f"<Owner(id={obj_id}, login='{self.login}', type='{self.type}')>"