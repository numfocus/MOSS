"""
backend.data.models.repository
------------------------------
This module defines the Repository model, representing a single code repository
(e.g., from GitHub) that has been ingested and tracked by the system.
"""

# Import JSONB type for handling JSON data in PostgreSQL (topics, license)
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional, TYPE_CHECKING, Dict, Any
from sqlalchemy import (
    String, Integer, Text, Boolean, DateTime, BigInteger, ForeignKey, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints,
# especially for relationships to Owner, Contributor, and DOIReference.
if TYPE_CHECKING:
    from .owner import Owner
    from .contributor import Contributor
    from .doi_reference import DOIReference
    # If relationships to Issues, PullRequests, etc., are added here, import them too.

class Repository(BaseModel, Base):
    """
    Represents a code repository, typically sourced from platforms like GitHub.

    This model stores core metadata about a repository, including its identifiers,
    descriptive information, basic stats, ownership, and technical details like
    language and timestamps. It serves as a central entity linking to contributors,
    discovered DOIs, and potentially other related data like issues or pull requests.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to the repository.
        name: The repository's name (without the owner part).
        full_name: The full name including the owner (e.g., 'owner/name').
        description: The description text provided for the repository.
        homepage: URL of the project's homepage, if provided.
        html_url: URL to the repository's main page on GitHub.
        api_url: URL to the repository's data endpoint in the GitHub API.
        language: The primary programming language detected by GitHub. Indexed.
        default_branch: The name of the default branch (e.g., 'main', 'master').
        stargazers_count: Number of users who have starred the repository.
        watchers_count: Number of users watching (subscribed to notifications for) the repository.
        forks_count: Number of times the repository has been forked.
        open_issues_count: Number of open issues.
        is_fork: Boolean flag indicating if this repository is a fork of another.
        gh_created_at: Timestamp when the repository was created on GitHub.
        gh_updated_at: Timestamp when the repository metadata was last updated on GitHub.
        gh_pushed_at: Timestamp of the last push event to the repository.
        topics: List of topics assigned to the repository on GitHub, stored as JSON.
        license: Information about the repository's license, stored as a JSON object.
        owner_id: Foreign key linking to the Owner (User or Organization) of this repository.
        owner: Relationship back to the Owner object.
        contributors: Many-to-many relationship linking to Contributors via the association table.
        doi_references: One-to-many relationship linking to DOIReference records found within this repository.
    """
    __tablename__ = "repositories"

    # --- GitHub Identifiers and Core Metadata ---
    # Essential information retrieved directly from the source platform (e.g., GitHub).

    # GitHub's unique numerical ID. Indexed for fast lookups.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    # Repository name (e.g., 'my-project').
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Full name including owner (e.g., 'my-org/my-project'). Unique and indexed.
    full_name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    # User-provided description. Text allows for longer content.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Link to an external project website.
    homepage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Direct link to the repository on the web platform (e.g., GitHub HTML page).
    html_url: Mapped[str] = mapped_column(String, nullable=False)
    # Link to the API endpoint for this repository's data.
    api_url: Mapped[str] = mapped_column(String, nullable=False)

    # --- Technical Details and Stats ---
    # Information about the repository's content, structure, and popularity.

    # Primary programming language detected. Indexed for filtering/analysis by language.
    language: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    # Name of the main branch (often 'main' or 'master').
    default_branch: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Basic engagement metrics from GitHub. Defaults ensure non-null integer values.
    stargazers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    watchers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # GitHub API: 'subscribers_count'
    forks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Flag indicating if the repository is a direct copy (fork) of another.
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- GitHub Timestamps ---
    # Stores key lifecycle timestamps from GitHub, preserving timezone information.
    gh_created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gh_updated_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gh_pushed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Enriched Metadata (Added Fields) ---
    # Storing structured data like topics and license info.

    # List of topics associated with the repo (e.g., ['python', 'data-science']).
    # Stored using JSONB for efficient querying in PostgreSQL.
    topics: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    # Detailed license information, typically mirroring the GitHub license object structure.
    # Stored using JSONB. Example: {'key': 'mit', 'name': 'MIT License', ...}
    license: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # --- Foreign Key to Owner ---
    # Links the repository to its owning User or Organization. Indexed.
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), index=True, nullable=False)

    # --- Relationships ---
    # Defines connections to other related entities.

    # Many-to-One relationship back to the Owner.
    # `back_populates` links to the 'repositories' collection on the Owner model.
    owner: Mapped["Owner"] = relationship(back_populates="repositories")

    # Many-to-Many relationship to Contributors.
    # `secondary` specifies the association table ('repository_contributors').
    # `back_populates` links to the 'repositories' collection on the Contributor model.
    contributors: Mapped[List["Contributor"]] = relationship(
        secondary="repository_contributors",
        back_populates="repositories"
    )

    # One-to-Many relationship to discovered DOI references within this repository.
    # `back_populates` links to the 'repository' attribute on the DOIReference model.
    # `cascade="all, delete-orphan"` ensures that if a Repository is deleted, all
    # associated DOIReference records are also deleted.
    doi_references: Mapped[List["DOIReference"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Define explicit indexes for commonly queried columns.
    __table_args__ = (
        # Index on the primary language for efficient filtering or grouping by language.
        # Note: index=True on the column definition above achieves the same.
        Index('ix_repositories_language', 'language'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        return f"<Repository(id={obj_id}, full_name='{self.full_name}')>"