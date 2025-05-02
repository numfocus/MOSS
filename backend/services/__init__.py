# Makes 'services' a Python package

from .base_service import BaseService
from .discovery_chain_service import DiscoveryChainService
from .doi_processing_service import DOIProcessingService
from .ingestion_service import IngestionService
from .keyword_discovery_service import KeywordDiscoveryService
from .scholarly_processing_service import ScholarlyProcessingService
from .surfacing_service import SurfacingService # <-- ADD THIS IMPORT

__all__ = [
    "BaseService",
    "DiscoveryChainService",
    "DOIProcessingService",
    "IngestionService",
    "KeywordDiscoveryService",
    "ScholarlyProcessingService",
    "SurfacingService", # <-- ADD THIS TO LIST
]