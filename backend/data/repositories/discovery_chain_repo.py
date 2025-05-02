# discovery_chain_repo.py

"""
backend.data.repositories.discovery_chain_repo
----------------------------------------------
Provides specific data access operations for the DiscoveryChain model,
tracking the lineage and status of data discovery processes.
"""

import logging
import uuid # For handling UUID primary keys
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import DiscoveryChain # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class DiscoveryChainRepository(BaseRepository[DiscoveryChain]):
    """
    Repository for managing DiscoveryChain entities.

    Handles CRUD operations (via BaseRepository) and provides specific methods
    for querying discovery chains, such as finding all nodes related to a
    specific root process.
    """

    def __init__(self, db: Session):
        """
        Initializes the DiscoveryChainRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(DiscoveryChain, db)

    def get_by_uuid(self, *, id: uuid.UUID) -> Optional[DiscoveryChain]:
        """
        Retrieves a specific discovery chain node by its UUID primary key.

        This method leverages the generic `get` method from the BaseRepository,
        which uses `Session.get()` and handles UUID primary keys correctly.

        Args:
            id: The UUID primary key of the DiscoveryChain node to retrieve.

        Returns:
            The DiscoveryChain instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting DiscoveryChain by UUID: {id}")
        # The base class `get` method is suitable for UUID primary keys.
        return self.get(id=id)

    def find_by_root_id(self, *, root_chain_id: uuid.UUID) -> List[DiscoveryChain]:
        """
        Finds all discovery chain nodes that belong to the same root process.

        This is useful for reconstructing the entire history or branching of a
        discovery process initiated by a single root node. The results are
        optionally ordered by level and start time for chronological context.

        Args:
            root_chain_id: The UUID of the root node of the discovery chain.

        Returns:
            A list of DiscoveryChain instances associated with the given root ID.
            The list will be empty if no nodes match the root ID.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding DiscoveryChains sharing root_chain_id: {root_chain_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.root_chain_id == root_chain_id)
                # Order results for better traceability: by depth level, then by start time.
                .order_by(self.model.level, self.model.started_at)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error finding DiscoveryChains for root {root_chain_id}: {e}", exc_info=True)
            raise

    # Potential future methods:
    # - find_children(parent_id: uuid.UUID) -> List[DiscoveryChain]: Get direct children.
    # - find_by_status(status: str) -> List[DiscoveryChain]: Get chains by status.
    # - find_by_entity_association(entity_type: str, entity_id: int): Find chains linked to a specific entity.