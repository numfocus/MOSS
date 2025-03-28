# services/acf_base.py
"""
Base class for Association Confidence Filters (ACF)
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Any

from models.models import Repository

class AssociationConfidenceFilter(ABC):
    """Base class for all Association Confidence Filters."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the filter."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of how the filter works."""
        pass
    
    @abstractmethod
    def calculate_confidence(self, repository: Repository, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        """
        Calculate a confidence score (0.0-1.0) that a repository is associated with the institution.
        
        Args:
            repository: The Repository object to analyze
            institution_info: Dictionary containing institution data (name, domains, etc.)
            
        Returns:
            Tuple of (confidence_score, evidence_dict)
            - confidence_score: Float from 0.0 to 1.0
            - evidence_dict: Dictionary explaining the reasoning
        """
        pass