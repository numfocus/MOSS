"""
backend.data.models.discovery_chain
-----------------------------------
This module defines the DiscoveryChain model, which represents a node in a
provenance graph tracking how various entities (like repositories or works)
were discovered within the system. It forms a hierarchical chain to trace
discovery steps back to their origin.
"""

import uuid
from typing import List, Optional, Any, TYPE_CHECKING
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Index, func # Keep necessary imports
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base is correctly defined elsewhere
# Adjust import path as necessary
from ..database import Base
# Import custom timestamp types for consistency
from .types import timestamp_nullable, timestamp_created, timestamp_updated

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .entity_discovery_association import EntityDiscoveryAssociation

class DiscoveryChain(Base):
    """
    Represents a single step or node in the discovery provenance graph.

    Each instance tracks a specific discovery action (e.g., finding repositories
    via keyword search, finding DOIs within a repository). It forms a directed
    acyclic graph (DAG) or tree structure through parent/child relationships,
    allowing the system to trace how any discovered entity was found, starting
    from an initial seed or action.

    Uses a UUID primary key as discovery chains might be initiated independently
    and merging them later would be complex with sequential IDs. Does not inherit
    from BaseModel due to the UUID primary key.

    Attributes:
        id: UUID primary key, uniquely identifying this discovery step.
        parent_chain_id: Foreign key to the parent DiscoveryChain node (optional).
        root_chain_id: Foreign key to the ultimate root node of this discovery tree.
        level: Depth of this node in the discovery tree (0 for root nodes).
        discovery_type: String identifying the type of discovery action performed.
        parameters: JSONB field storing parameters used for this discovery step.
        status: Current status of the discovery step (e.g., PENDING, RUNNING, COMPLETED).
        started_at: Timestamp when the discovery process for this node began.
        completed_at: Timestamp when the discovery process for this node finished.
        created_at: Timestamp when this record was created.
        updated_at: Timestamp when this record was last updated.
        parent: Relationship to the parent DiscoveryChain node.
        children: Relationship to child DiscoveryChain nodes initiated from this one.
        entity_associations: Relationship to entities discovered during this step.
    """
    __tablename__ = "discovery_chains"

    # --- Core Attributes ---
    # Unique identifier using UUID - more robust for distributed/parallel discovery processes.
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Hierarchy Tracking ---
    # Links to establish the tree/graph structure.
    parent_chain_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("discovery_chains.id"), # Self-referential foreign key
        nullable=True # Root nodes have no parent
    )
    # Storing the root ID allows quick traversal to the origin of any discovery chain.
    # Indexed for efficient lookup of all nodes belonging to the same root process.
    root_chain_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery_chains.id"), # Also self-referential
        index=True, # Index this column
        nullable=False # Every node must belong to a root
    )
    # Level indicates the depth in the discovery hierarchy (0 = root).
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Discovery Process Metadata ---
    # Details about the specific discovery action taken at this node.
    # Type identifier, e.g., 'KEYWORD_SEARCH', 'DOI_EXTRACTION', 'CITATION_GRAPH_TRAVERSAL'.
    discovery_type: Mapped[str] = mapped_column(String, nullable=False)
    # Flexible storage for parameters used, e.g., {'keywords': ['AI', 'HPC'], 'source': 'GitHub'}.
    parameters: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    # Tracks the execution state of this discovery step. Indexed for querying active/failed jobs.
    status: Mapped[str] = mapped_column(String, index=True, nullable=False, default='PENDING')

    # --- Timestamps ---
    # Use custom timestamp types for consistency.
    started_at: Mapped[timestamp_created] # When the task began processing
    completed_at: Mapped[timestamp_nullable] # When the task finished (null if pending/running/failed early)
    created_at: Mapped[timestamp_created] # Standard record creation timestamp
    updated_at: Mapped[timestamp_updated] # Standard record update timestamp

    # --- Relationships ---
    # Define relationships for navigating the discovery graph and associated entities.

    # Relationship to the parent node in the discovery chain.
    # `remote_side=[id]` is needed for self-referential relationships to specify
    # which column on the 'remote' side (the DiscoveryChain table itself) the
    # foreign key points to.
    parent: Mapped[Optional["DiscoveryChain"]] = relationship(
        foreign_keys=[parent_chain_id], # Specifies the FK column for this relationship
        remote_side=[id], # Specifies the PK column on the remote side
        back_populates="children" # Links to the 'children' collection below
    )
    # Relationship to child nodes spawned from this discovery step.
    children: Mapped[List["DiscoveryChain"]] = relationship(
        foreign_keys=[parent_chain_id], # Child nodes point back to this node's ID via parent_chain_id
        back_populates="parent", # Links back to the 'parent' relationship above
        cascade="all, delete-orphan" # If a parent node is deleted, its children are also deleted
    )
    # Relationship to the entities (e.g., Repositories, Works) found during this step.
    # Linked via the EntityDiscoveryAssociation table.
    entity_associations: Mapped[List["EntityDiscoveryAssociation"]] = relationship(
        back_populates="discovery_chain", # Links to the 'discovery_chain' attribute in EntityDiscoveryAssociation
        cascade="all, delete-orphan" # If a discovery node is deleted, its entity links are removed
    )

    # --- Table Arguments ---
    # Explicitly define indexes for commonly queried columns.
    __table_args__ = (
        # Index on 'status' column for efficient querying of jobs by state.
        Index('ix_discovery_chains_status', 'status'),
        # Index on 'root_chain_id' for efficiently finding all nodes in a specific discovery tree.
        Index('ix_discovery_chains_root_id', 'root_chain_id'),
        # Note: The index=True on the root_chain_id column definition above is slightly redundant
        # but kept for clarity; __table_args__ provides central control over indexes.
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Use short UUID representation for brevity
        short_id = str(self.id).split('-')[0] if self.id else None
        return (f"<DiscoveryChain(id={short_id}..., type='{self.discovery_type}', "
                f"level={self.level}, status='{self.status}')>")