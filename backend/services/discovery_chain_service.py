"""
backend.services.discovery_chain_service
----------------------------------------
Manages the creation, lifecycle, and entity associations of DiscoveryChain records.
These chains track the provenance of discovered data points and their relationships.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Type, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# --- Added WorkTopic to model imports ---
from backend.data.models import DiscoveryChain, EntityDiscoveryAssociation, WorkTopic
# --- End Add ---
from backend.data.repositories import (
    DiscoveryChainRepository,
    EntityDiscoveryAssociationRepository,
)
from .base_service import BaseService


class DiscoveryChainService(BaseService):
    """
    Service responsible for handling DiscoveryChain objects.

    Provides methods for creating root and child chains, managing their status
    (PENDING, PROCESSING, COMPLETED, FAILED), and associating other database
    entities with specific discovery steps. It ensures chain IDs are available
    after creation by flushing the session. Transaction management (commit/rollback)
    is generally expected to be handled by the calling service or task, except for
    internal error handling within specific methods.
    """

    def get_by_uuid(self, db: Session, id: uuid.UUID) -> Optional[DiscoveryChain]:
        """
        Retrieves a DiscoveryChain by its UUID primary key.

        Args:
            db: The database session.
            id: The UUID of the DiscoveryChain to retrieve.

        Returns:
            The DiscoveryChain object if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during retrieval.
        """
        self.logger.debug(f"Getting DiscoveryChain by UUID: {id}")
        repo = DiscoveryChainRepository(db)
        try:
             return repo.get(id=id)
        except SQLAlchemyError as e:
            self.logger.error(f"Database error getting DiscoveryChain UUID {id}: {e}", exc_info=True)
            raise

    def create_root_chain(
        self, db: Session, discovery_type: str, parameters: Optional[Dict[str, Any]] = None
    ) -> DiscoveryChain:
        """
        Creates a new root DiscoveryChain (level 0).

        A root chain represents the starting point of a discovery process,
        such as a direct URL ingestion or a keyword search.

        Args:
            db: The database session.
            discovery_type: A string identifying the type of discovery process initiating this chain.
            parameters: An optional dictionary of parameters relevant to this discovery type.

        Returns:
            The newly created and flushed DiscoveryChain object.

        Raises:
            SQLAlchemyError: If a database error occurs during creation or flush.
        """
        self.logger.info(f"Creating root discovery chain: type='{discovery_type}'")
        new_id = uuid.uuid4()
        new_chain = DiscoveryChain(
            id=new_id,
            parent_chain_id=None,
            root_chain_id=new_id, # A root chain is its own root
            level=0,
            discovery_type=discovery_type,
            parameters=parameters,
            status='PENDING', # Initial status
            started_at=datetime.now(timezone.utc)
        )
        try:
            db.add(new_chain)
            db.flush() # Ensure the chain object has its ID assigned before returning
            db.refresh(new_chain) # Load any server-defaults if applicable
            self.logger.info(f"Created and flushed root chain {new_chain.id}")
            return new_chain
        except SQLAlchemyError as e:
            self.logger.error(f"Error creating/flushing root discovery chain: {e}", exc_info=True)
            db.rollback() # Rollback this specific operation on error
            raise

    def create_child_chain(
        self,
        db: Session,
        parent_chain: DiscoveryChain,
        discovery_type: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DiscoveryChain:
        """
        Creates a new child DiscoveryChain linked to a parent chain.

        Child chains represent subsequent steps or related discoveries stemming
        from the parent's process. They inherit the root chain ID and have an
        incremented level.

        Args:
            db: The database session.
            parent_chain: The parent DiscoveryChain object.
            discovery_type: A string identifying the type of discovery process for this child chain.
            parameters: An optional dictionary of parameters relevant to this child discovery.

        Returns:
            The newly created and flushed child DiscoveryChain object.

        Raises:
            ValueError: If the parent chain is missing its ID or root_chain_id.
            SQLAlchemyError: If a database error occurs during creation or flush.
        """
        self.logger.info(f"Creating child chain under {parent_chain.id}: type='{discovery_type}'")

        # Ensure parent chain has necessary IDs (already fetched or refreshed)
        if parent_chain.id is None or parent_chain.root_chain_id is None:
             # Attempt to refresh the parent object state from the DB if IDs are missing
             try:
                 db.refresh(parent_chain)
                 if parent_chain.id is None or parent_chain.root_chain_id is None:
                     # If still missing after refresh, it indicates a problem
                     raise ValueError("Parent chain ID or root ID is None even after refresh.")
             except Exception as refresh_err:
                 self.logger.error(f"Failed to refresh parent chain {parent_chain}: {refresh_err}")
                 raise ValueError("Parent chain must have valid id and root_chain_id, refresh failed.") from refresh_err

        new_chain = DiscoveryChain(
            parent_chain_id=parent_chain.id,
            root_chain_id=parent_chain.root_chain_id, # Inherit root from parent
            level=parent_chain.level + 1, # Increment hierarchy level
            discovery_type=discovery_type,
            parameters=parameters,
            status='PENDING', # Initial status
            started_at=datetime.now(timezone.utc)
        )
        try:
            db.add(new_chain)
            db.flush() # Ensure the chain object has its ID assigned before returning
            db.refresh(new_chain) # Load any server-defaults
            self.logger.info(f"Created and flushed child chain {new_chain.id} under {parent_chain.id}")
            return new_chain
        except SQLAlchemyError as e:
            self.logger.error(
                f"Error creating/flushing child discovery chain under {parent_chain.id}: {e}",
                exc_info=True
            )
            # Let the caller handle transaction rollback as this might be part of a larger operation
            raise

    def _update_chain_status(
        self, db: Session, chain: DiscoveryChain, status: str, timestamp: Optional[datetime] = None
    ) -> DiscoveryChain:
        """
        Internal helper to update the status of a DiscoveryChain and optionally set completion time.

        Args:
            db: The database session.
            chain: The DiscoveryChain object to update.
            status: The new status string (e.g., 'PROCESSING', 'COMPLETED', 'FAILED').
            timestamp: The timestamp to set for completion (used for terminal statuses).

        Returns:
            The updated DiscoveryChain object after flushing changes.

        Raises:
            ValueError: If the chain object does not have an ID.
            SQLAlchemyError: If a database error occurs during the update or flush.
        """
        if chain.id is None:
            # Cannot update a chain that hasn't been persisted and assigned an ID
            raise ValueError("Cannot update status for a chain without an ID.")

        self.logger.debug(f"Updating chain {chain.id} status to {status}")
        chain.status = status
        if timestamp:
             # Set completion timestamp only for terminal states
             if status in ['COMPLETED', 'FAILED', 'PARTIAL']:
                  chain.completed_at = timestamp
        try:
            db.add(chain) # Add to session to ensure changes are tracked
            db.flush()    # Persist status change immediately
            db.refresh(chain) # Refresh to get accurate state from DB, including potential triggers
            return chain
        except SQLAlchemyError as e:
             self.logger.error(f"Error updating/flushing chain {chain.id} status to {status}: {e}", exc_info=True)
             # Let the caller handle transaction rollback
             raise

    def start_chain(self, db: Session, chain: DiscoveryChain) -> DiscoveryChain:
        """Sets the chain status to 'PROCESSING'."""
        return self._update_chain_status(db, chain, 'PROCESSING')

    def complete_chain(self, db: Session, chain: DiscoveryChain) -> DiscoveryChain:
        """Sets the chain status to 'COMPLETED' and records the completion time."""
        return self._update_chain_status(db, chain, 'COMPLETED', datetime.now(timezone.utc))

    def fail_chain(
        self, db: Session, chain: DiscoveryChain, error_message: Optional[str] = None
    ) -> DiscoveryChain:
        """
        Sets the chain status to 'FAILED', records completion time, and logs the error.

        Args:
            db: The database session.
            chain: The DiscoveryChain to mark as failed.
            error_message: An optional message describing the reason for failure.

        Returns:
            The updated DiscoveryChain object.
        """
        self.logger.error(f"Discovery chain {chain.id} failed. Type: {chain.discovery_type}. Error: {error_message or 'N/A'}")
        # Future enhancement: could store error_message in chain.parameters or a dedicated field
        return self._update_chain_status(db, chain, 'FAILED', datetime.now(timezone.utc))

    def associate_entity(
        self, db: Session, chain: DiscoveryChain, entity: Any, is_direct: bool = True
    ) -> Optional[EntityDiscoveryAssociation]:
        """
        Creates an association link between a DiscoveryChain and another database entity.

        This records which entity was discovered or processed during a specific step (chain).
        Handles entities with single integer primary keys and specific types with composite keys.

        Args:
            db: The database session.
            chain: The DiscoveryChain involved in the discovery.
            entity: The database entity object that was discovered or processed.
            is_direct: Boolean flag indicating if this entity was the primary result
                       of this chain's process (True), or a related entity discovered
                       indirectly (False).

        Returns:
            The newly created or existing EntityDiscoveryAssociation object, or None if
            the entity was None.

        Raises:
            ValueError: If the chain or entity lacks a required ID.
            SQLAlchemyError: If a database error occurs during creation or lookup.
        """
        if entity is None:
            # Cannot associate a non-existent entity
            self.logger.warning(f"Attempted to associate a None entity to chain {chain.id}. Skipping.")
            return None

        entity_type = entity.__class__.__name__
        # Define entity types that use composite primary keys and don't have a single 'id' column
        # --- ADDED WorkTopic to this list ---
        association_types_no_id = ('Authorship', 'Affiliation', 'WorkCitation', 'RepositoryContributorAssociation', 'WorkTopic')
        # --- END ADD ---
        entity_id: Optional[int] = None # Standard integer ID

        if entity_type not in association_types_no_id:
            # For standard entities, get the primary key ID
            entity_id = getattr(entity, 'id', None)
            if entity_id is None:
                # Ensure the entity has been flushed and has an ID before associating
                self.logger.error(f"Attempted to associate entity of type {entity_type} without an ID to chain {chain.id}")
                raise ValueError(f"Entity {entity_type} must have an ID before association.")
        # --- Added else block for logging composite PK types ---
        else:
             # For types with composite keys, create a representation for logging
             pk_repr = '[CompositePK]'
             try:
                 # Introspect SQLAlchemy mapper to find primary key columns
                 if hasattr(entity, '__mapper__'):
                     pk_cols = [c.name for c in entity.__mapper__.primary_key]
                     pk_vals = [getattr(entity, c, None) for c in pk_cols]
                     pk_repr = ', '.join(f"{k}={v}" for k, v in zip(pk_cols, pk_vals))
                 self.logger.debug(f"Associating entity type {entity_type} ({pk_repr}) which uses composite PK.")
             except Exception as pk_log_err:
                self.logger.warning(f"Could not fully represent composite PK for {entity_type}: {pk_log_err}")
        # --- End Added ---


        if chain.id is None:
             # The chain must exist in the DB before associations can be made
             raise ValueError("DiscoveryChain must have an ID before association.")

        # --- Adjusted Log Message ---
        # Use the appropriate identifier representation for logging
        entity_id_repr = entity_id if entity_id is not None else pk_repr
        self.logger.debug(f"Associating {entity_type} ({entity_id_repr}) with chain {chain.id} (direct={is_direct})")
        # --- End Adjusted ---


        # Prepare filters to check if this association already exists
        lookup_filters: Dict[str, Any] = {
            "discovery_chain_id": chain.id,
            "entity_type": entity_type,
        }
        # Only filter by entity_id if it's applicable (not a composite PK type)
        if entity_type not in association_types_no_id:
             lookup_filters["entity_id"] = entity_id
        # For composite PK types, we rely on the combination of chain_id and entity_type
        # being unique for the purpose of this lookup. If more complex uniqueness checks
        # involving composite keys are needed, this logic would need enhancement.

        # Data for creating a new association record
        association_data = {
            "discovery_chain_id": chain.id,
            "entity_type": entity_type,
            "entity_id": entity_id, # Store None for composite PK types in this column
            "is_direct_discovery": is_direct,
        }

        try:
             # --- Modified Lookup Logic ---
             # Build the query based on filters
             query = db.query(EntityDiscoveryAssociation).filter_by(
                 discovery_chain_id=lookup_filters["discovery_chain_id"],
                 entity_type=lookup_filters["entity_type"]
             )
             # Add entity_id filter only if applicable
             if "entity_id" in lookup_filters:
                 query = query.filter(EntityDiscoveryAssociation.entity_id == lookup_filters["entity_id"])
             else:
                 # For composite PK types, ensure we match records where entity_id IS NULL
                 query = query.filter(EntityDiscoveryAssociation.entity_id.is_(None))

             existing_assoc = query.first()
             # --- End Modified Lookup ---

             if existing_assoc:
                  # Avoid creating duplicate associations
                  self.logger.debug("Association already exists, skipping creation.")
                  return existing_assoc

             # Create and persist the new association
             new_assoc = EntityDiscoveryAssociation(**association_data)
             db.add(new_assoc)
             db.flush() # Assign primary key to the association record itself
             db.refresh(new_assoc) # Load defaults like created_at
             return new_assoc
        except SQLAlchemyError as e:
             self.logger.error(
                  f"Error creating/flushing {entity_type} ({entity_id_repr}) association with chain {chain.id}: {e}",
                  exc_info=True
             )
             # Let the caller handle transaction rollback
             raise