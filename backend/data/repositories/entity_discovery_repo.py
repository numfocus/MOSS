# entity_discovery_repo.py

"""
backend.data.repositories.entity_discovery_repo
-----------------------------------------------
Provides data access operations for the EntityDiscoveryAssociation model,
linking various discovered entities (like Repositories, Works) to specific
nodes in a DiscoveryChain.
"""

import logging
import uuid # For handling UUID foreign keys
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import EntityDiscoveryAssociation # The specific model

logger = logging.getLogger(__name__)

class EntityDiscoveryAssociationRepository(BaseRepository[EntityDiscoveryAssociation]):
    """
    Repository for managing EntityDiscoveryAssociation records.

    This repository handles the many-to-many relationship (modeled as an
    association object) between DiscoveryChain nodes and various other
    entities identified during the discovery process. It provides methods
    to find associations based on either the chain or the linked entity.
    """

    def __init__(self, db: Session):
        """
        Initializes the EntityDiscoveryAssociationRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(EntityDiscoveryAssociation, db)

    def find_by_chain_and_entity(
        self, *, discovery_chain_id: uuid.UUID, entity_type: str, entity_id: int
    ) -> Optional[EntityDiscoveryAssociation]:
        """
        Finds a specific association link between one discovery chain node
        and one specific entity instance.

        Args:
            discovery_chain_id: The UUID of the DiscoveryChain node.
            entity_type: A string identifying the type of the linked entity
                         (e.g., 'Repository', 'Work', 'Person'). Must match
                         the value stored in the association table.
            entity_id: The integer primary key of the linked entity instance.

        Returns:
            The EntityDiscoveryAssociation instance representing this specific
            link, or None if no such link exists.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(
            f"Finding specific EntityDiscoveryAssociation for chain {discovery_chain_id}, "
            f"type '{entity_type}', entity_id {entity_id}"
        )
        try:
            # Query based on the composite identifying information.
            return (
                self.db.query(self.model)
                .filter(
                    self.model.discovery_chain_id == discovery_chain_id,
                    self.model.entity_type == entity_type,
                    self.model.entity_id == entity_id,
                )
                .first() # Expecting at most one association for this specific combination.
            )
        except SQLAlchemyError as e:
            logger.error(f"DB error finding association for chain {discovery_chain_id}, entity {entity_type}:{entity_id}: {e}", exc_info=True)
            raise

    def find_by_entity(
        self, *, entity_type: str, entity_id: int
    ) -> List[EntityDiscoveryAssociation]:
        """
        Finds all discovery chain associations linked to a specific entity.

        This is useful for tracing back which discovery processes or steps
        identified or interacted with a particular entity (e.g., which
        discovery runs found a specific Repository).

        Args:
            entity_type: The type identifier string of the entity.
            entity_id: The primary key ID of the entity instance.

        Returns:
            A list of EntityDiscoveryAssociation instances linking the specified
            entity to various discovery chain nodes, or an empty list if none exist.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding EntityDiscoveryAssociations linked to entity type '{entity_type}', id {entity_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(
                    self.model.entity_type == entity_type,
                    self.model.entity_id == entity_id,
                )
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"DB error finding associations for entity {entity_type}:{entity_id}: {e}", exc_info=True)
            raise

    def find_by_chain(
        self, *, discovery_chain_id: uuid.UUID
    ) -> List[EntityDiscoveryAssociation]:
        """
        Finds all entity associations originating from a specific discovery chain node.

        This helps identify all entities (e.g., Repositories, Works) that were
        discovered or processed specifically at this step in the discovery chain.

        Args:
            discovery_chain_id: The UUID of the DiscoveryChain node.

        Returns:
            A list of EntityDiscoveryAssociation instances linked to the specified
            discovery chain node, or an empty list if none exist.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding all EntityDiscoveryAssociations for chain node {discovery_chain_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.discovery_chain_id == discovery_chain_id)
                .all()
            )
        except SQLAlchemyError as e:
             logger.error(f"DB error finding associations for chain {discovery_chain_id}: {e}", exc_info=True)
             raise

    # Additional specific query methods can be added as needed, e.g.,
    # finding associations based on metadata within the association record itself.