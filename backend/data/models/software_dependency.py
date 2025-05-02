"""
backend.data.models.software_dependency
---------------------------------------
This module defines the SoftwareDependency model, representing a single
software package dependency identified within a file in a tracked repository
(e.g., a package listed in requirements.txt or package.json).
"""

import logging
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, Index, Boolean

from sqlalchemy.orm import relationship, Mapped, mapped_column

# Adjust the import path according to your project structure
# Assuming Base is defined in backend.data.database
from backend.data.database import Base
# Assuming BaseModel provides id, created_at, updated_at
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .repository import Repository
    # Potential future link if discovery provenance is tracked per dependency
    # from .discovery_chain import DiscoveryChain

logger = logging.getLogger(__name__)

class SoftwareDependency(BaseModel, Base):
    """
    Represents a software dependency found within a repository file.

    This model captures information about a specific dependency (e.g., a Python
    package, an npm module) declared in a manifest file (like requirements.txt,
    package.json, environment.yml) within a repository.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        repository_id: Foreign key linking to the Repository where the dependency was found.
        dependency_name: The name of the depended-upon package or library.
        version_constraint: The version specifier string (e.g., ">=1.0", "^2.1.0").
        source_file: The path to the manifest file where this dependency was declared.
        dependency_type: The package ecosystem or type (e.g., 'pypi', 'npm', 'conda').
        is_dev_dependency: Flag indicating if this is marked as a development dependency.
        repository: Relationship back to the parent Repository object.
    """
    __tablename__ = "software_dependencies"

    # --- Foreign Key ---
    # Links this dependency record back to the repository it was found in.
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), # Cascade delete if repo is removed
        index=True, # Index for efficient lookup of dependencies by repository
        nullable=False
    )

    # --- Dependency Details ---
    # Core information about the specific software package dependency.

    # Name of the package/library. Indexed for searching dependencies by name.
    dependency_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # The version string as specified in the source file. Nullable if no version was specified.
    # Examples: ">=1.0,<2.0", "1.2.3", "^5.0", "latest"
    version_constraint: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Provenance and Context ---
    # Information about where and how this dependency was declared.

    # Path to the file within the repository where this dependency was found.
    # Example: 'requirements.txt', 'src/package.json', 'environment.yml'
    source_file: Mapped[str] = mapped_column(String, nullable=False)

    # Type identifier for the package management system or ecosystem. Indexed.
    # Helps interpret the dependency name and version constraint.
    # Example: 'pypi', 'npm', 'conda', 'maven', 'gradle', 'cargo'
    dependency_type: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Flag indicating if the dependency is designated for development purposes only
    # (e.g., in 'devDependencies' in package.json). Indexed for filtering.
    # Nullable if the concept doesn't apply or wasn't determined.
    is_dev_dependency: Mapped[Optional[bool]] = mapped_column(Boolean, index=True, nullable=True)

    # --- Relationships ---
    # Define relationship(s) for navigation.

    # Relationship back to the Repository containing this dependency declaration.
    # No `back_populates` is defined here, assuming the Repository model does not
    # need a direct collection of its numerous dependencies.
    repository: Mapped["Repository"] = relationship()

    # --- Table Arguments ---
    # Define explicit indexes to optimize common query patterns.
    __table_args__ = (
        # Index on repository_id (already indexed via column def, but explicit).
        Index('ix_software_dependencies_repo_id', 'repository_id'),
        # Index on dependency_name for finding usage of specific packages across repos.
        Index('ix_software_dependencies_name', 'dependency_name'),
        # Index on dependency_type for filtering by ecosystem.
        Index('ix_software_dependencies_type', 'dependency_type'),
        # Index on is_dev_dependency flag for distinguishing runtime vs dev dependencies.
        Index('ix_software_dependencies_is_dev', 'is_dev_dependency'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        version_str = f", version='{self.version_constraint}'" if self.version_constraint else ""
        dev_flag = ", dev" if self.is_dev_dependency else ""
        return (f"<SoftwareDependency(id={obj_id}, repo={self.repository_id}, "
                f"name='{self.dependency_name}', type='{self.dependency_type}'{version_str}{dev_flag})>")