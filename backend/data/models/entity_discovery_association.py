"""
backend.data.models.entity_discovery_association
------------------------------------------------
This module defines the EntityDiscoveryAssociation model, acting as an
association table that links a specific node in the DiscoveryChain
provenance graph to an entity (like a Repository or Work) that was
discovered during that step.
"""

import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel # Inherits standard ID/timestamps

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .discovery_chain import DiscoveryChain

class EntityDiscoveryAssociation(BaseModel, Base):
    """
    Association table linking a DiscoveryChain node to a discovered entity.

    This model records the relationship between a specific discovery step (represented
    by a DiscoveryChain node) and a concrete data entity (e.g., a specific Repository,
    Person, Work) identified during that step. It uses a polymorphic approach where
    `entity_type` specifies the kind of entity, and `entity_id` (nullable) points
    to its primary key.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        discovery_chain_id: Foreign key linking to the DiscoveryChain node for this step.
        entity_type: String identifying the type of the discovered entity (e.g., 'Repository', 'Work').
        entity_id: Integer foreign key pointing to the primary key of the discovered entity.
                   This is nullable to accommodate potential entities that might use composite
                   primary keys or cases where the link is conceptual before the entity is fully saved.
        is_direct_discovery: Flag indicating if this entity was directly found by the
                             linked discovery step, or indirectly (e.g., associated via a child step).
        discovery_chain: Relationship back to the DiscoveryChain node.
    """
    __tablename__ = "entity_discovery_associations"

    # --- Foreign Key to Discovery Chain ---
    # Links this association record back to the specific discovery step. Indexed.
    discovery_chain_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), # Match the UUID type of DiscoveryChain.id
        ForeignKey("discovery_chains.id"), # Establishes the foreign key relationship
        index=True, # Index for efficient lookup of entities associated with a chain
        nullable=False
    )

    # --- Polymorphic Link to Discovered Entity ---
    # Uses two columns to identify the associated entity dynamically.

    # Specifies the table/model name of the discovered entity (e.g., 'Repository', 'Work', 'Person'). Indexed.
    entity_type: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # The primary key of the discovered entity. Indexed.
    # --- MODIFICATION NOTE: This column is nullable=True ---
    # This allows flexibility, for example, if an entity uses a composite primary key
    # (which wouldn't fit here directly) or if the association represents a potential
    # link identified before the entity itself has been assigned a final ID.
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    # --- END MODIFICATION NOTE ---

    # --- Association Metadata ---
    # Additional context about the discovery relationship.
    is_direct_discovery: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
        # True if this entity was a primary result of the discovery_chain_id step.
        # False if it's associated indirectly (e.g., discovered by a child step but linked
        # here for aggregation).
    )

    # --- Relationships ---
    # Relationship back to the owning DiscoveryChain node.
    # `back_populates` links this to the 'entity_associations' collection on the DiscoveryChain model.
    discovery_chain: Mapped["DiscoveryChain"] = relationship(
        back_populates="entity_associations"
    )

    # --- Table Arguments ---
    # Define indexes and constraints for data integrity and performance.
    __table_args__ = (
        # Index on discovery_chain_id (already indexed via column definition, but explicit).
        Index('ix_entity_discovery_chain_id', 'discovery_chain_id'),

        # Composite index on the polymorphic entity identifier columns.
        Index('ix_entity_discovery_entity', 'entity_type', 'entity_id'),

        # Unique constraint: Prevents associating the *same entity* with the *same discovery chain*
        # multiple times.
        # Note on NULLs: The behavior of unique constraints with NULL values varies across
        # database systems. In PostgreSQL (common with SQLAlchemy), NULLs are typically
        # treated as distinct, meaning multiple rows can have the same discovery_chain_id
        # and entity_type if entity_id is NULL. This might be acceptable or require
        # application-level checks depending on exact requirements.
        UniqueConstraint(
            'discovery_chain_id',
            'entity_type',
            'entity_id',
            name='uq_discovery_entity'
        ),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' attribute which comes from BaseModel
        assoc_id = getattr(self, 'id', None)
        # Display entity_id appropriately if it's None
        entity_id_repr = self.entity_id if self.entity_id is not None else '[NULL_or_CompositePK]'
        # Use short UUID for chain_id
        short_chain_id = str(self.discovery_chain_id).split('-')[0] + '...' if self.discovery_chain_id else None
        return (f"<EntityAssoc(id={assoc_id}, chain={short_chain_id}, "
                f"type='{self.entity_type}', entity_id={entity_id_repr})>")