"""
backend.data.models.repository_contributor
------------------------------------------
This module defines the RepositoryContributorAssociation model, serving as the
association table for the many-to-many relationship between Repositories
and Contributors.
"""

from typing import Optional
from sqlalchemy import Integer, ForeignKey, UniqueConstraint # UniqueConstraint might be needed elsewhere
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Assuming Base is correctly defined elsewhere
# Adjust import path as necessary
from ..database import Base

class RepositoryContributorAssociation(Base):
    """
    Association table linking Repositories and Contributors (Many-to-Many).

    This model represents the direct link between a repository and a user/bot
    who has contributed to it. It primarily consists of foreign keys forming a
    composite primary key. It can optionally store additional metadata about
    the relationship, such as the number of contributions.

    It inherits directly from `Base` as it uses a composite primary key and
    typically doesn't need separate `id` or standard timestamp columns.

    Attributes:
        repository_id: Foreign key linking to the Repository. Part of the composite PK.
        contributor_id: Foreign key linking to the Contributor. Part of the composite PK.
        contributions_count: Optional field storing the number of contributions made
                             by the contributor to the repository (e.g., from GitHub API).
    """
    __tablename__ = "repository_contributors"

    # --- Composite Primary Key / Foreign Keys ---
    # These two columns together uniquely identify the link between one
    # specific repository and one specific contributor.

    # Foreign key referencing the Repository table. Part of the composite PK.
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), primary_key=True)

    # Foreign key referencing the Contributor table. Part of the composite PK.
    contributor_id: Mapped[int] = mapped_column(ForeignKey("contributors.id"), primary_key=True)

    # --- Optional Association Metadata ---
    # Additional information about the specific contribution relationship.

    # Stores the count of contributions (e.g., commits) fetched from the source API.
    # Nullable if this information isn't always available or tracked.
    contributions_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # --- Table Arguments (Commented Out) ---
    # A UniqueConstraint ('uq_repo_contrib') defined here would be redundant because
    # the composite primary key inherently enforces uniqueness on the combination of
    # (repository_id, contributor_id). Therefore, it's typically omitted or
    # commented out for association tables using a composite PK like this.
    # __table_args__ = (
    #     UniqueConstraint('repository_id', 'contributor_id', name='uq_repo_contrib'),
    # )
    # --- End Commented Out Section ---

    # Relationships are typically defined on the 'many' sides (Repository and Contributor)
    # using the `secondary` argument pointing to this table's name. Direct relationships
    # from the association object itself are less common but possible if needed.

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        count_repr = f", count={self.contributions_count}" if self.contributions_count is not None else ""
        return (f"<RepoContrib(repo_id={self.repository_id}, "
                f"contrib_id={self.contributor_id}{count_repr})>")