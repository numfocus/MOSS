# services/institution_analysis/person_acf.py
"""
Association Confidence Filters (ACF) for people-institution associations.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Union

from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from db.database import get_db_session
from models.models import (
    User, OpenAlexAuthor, OpenAlexInstitution, OpenAlexWork,
    SurfacedPerson, ACFResult, ACFPersonResult
)
from services.acf_base import AssociationConfidenceFilter

logger = logging.getLogger(__name__)

class PersonAssociationConfidenceFilter(AssociationConfidenceFilter):
    """Base class for person-institution association confidence filters."""
    
    @abstractmethod
    def calculate_confidence(self, person: SurfacedPerson, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        """
        Calculate a confidence score (0.0-1.0) that a person is associated with the institution.
        
        Args:
            person: The SurfacedPerson object to analyze
            institution_info: Dictionary containing institution data (name, domains, etc.)
            
        Returns:
            Tuple of (confidence_score, evidence_dict)
            - confidence_score: Float from 0.0 to 1.0
            - evidence_dict: Dictionary explaining the reasoning
        """
        pass


class EmailDomainPersonFilter(PersonAssociationConfidenceFilter):
    """Filter that checks if a person's email domain matches the institution."""
    
    @property
    def name(self) -> str:
        return "Email Domain Person Filter"
    
    @property
    def description(self) -> str:
        return "Checks if the person's email domain matches the institution"
    
    def calculate_confidence(self, person: SurfacedPerson, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        domains = institution_info.get('domains', [])
        if not domains:
            return 0.0, {}
        
        evidence = {}
        
        # Get the user if available
        with get_db_session() as session:
            user = None
            if person.user_id:
                user = session.query(User).filter_by(id=person.user_id).first()
            
            if not user or not user.email:
                return 0.0, {}
            
            # Check if email domain matches any institution domain
            user_domain = user.email.split('@')[-1].lower()
            
            for domain in domains:
                if domain.lower() == user_domain:
                    evidence['email_match'] = {
                        'email': user.email,
                        'matching_domain': domain
                    }
                    return 0.9, evidence  # High confidence for exact domain match
                
                # Check for subdomain match (e.g., cs.stanford.edu matches stanford.edu)
                if user_domain.endswith(f".{domain.lower()}"):
                    evidence['subdomain_match'] = {
                        'email': user.email,
                        'user_domain': user_domain,
                        'institution_domain': domain
                    }
                    return 0.85, evidence  # Slightly lower confidence for subdomain
        
        return 0.0, {}


class ProfilePersonFilter(PersonAssociationConfidenceFilter):
    """Filter that analyzes a person's profile information for institution mentions."""
    
    @property
    def name(self) -> str:
        return "Profile Person Filter"
    
    @property
    def description(self) -> str:
        return "Analyzes a person's profile information for institution mentions"
    
    def calculate_confidence(self, person: SurfacedPerson, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        institution_name = institution_info.get('name', '')
        if not institution_name:
            return 0.0, {}
        
        evidence = {}
        total_score = 0.0
        
        # Get the user if available
        with get_db_session() as session:
            user = None
            if person.user_id:
                user = session.query(User).filter_by(id=person.user_id).first()
            
            if not user:
                return 0.0, {}
            
            # Check company field
            if user.company and institution_name.lower() in user.company.lower():
                company_score = 0.8
                evidence['company_match'] = {
                    'company': user.company,
                    'score': company_score
                }
                total_score = max(total_score, company_score)
            
            # Check bio field
            if user.bio and institution_name.lower() in user.bio.lower():
                bio_score = 0.6
                evidence['bio_match'] = {
                    'bio_excerpt': user.bio[:100] + '...' if len(user.bio) > 100 else user.bio,
                    'score': bio_score
                }
                total_score = max(total_score, bio_score)
            
            # Check location field
            if user.location and institution_name.lower() in user.location.lower():
                location_score = 0.5
                evidence['location_match'] = {
                    'location': user.location,
                    'score': location_score
                }
                total_score = max(total_score, location_score)
        
        if evidence:
            return total_score, evidence
        
        return 0.0, {}


class OpenAlexPersonFilter(PersonAssociationConfidenceFilter):
    """Filter that checks OpenAlex data for institution affiliations."""
    
    @property
    def name(self) -> str:
        return "OpenAlex Person Filter"
    
    @property
    def description(self) -> str:
        return "Checks OpenAlex data for institution affiliations"
    
    def calculate_confidence(self, person: SurfacedPerson, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        institution_name = institution_info.get('name', '')
        if not institution_name:
            return 0.0, {}
        
        evidence = {}
        
        with get_db_session() as session:
            # Get the OpenAlex author if available
            author = None
            if person.openalex_author_id:
                author = session.query(OpenAlexAuthor).options(
                    joinedload(OpenAlexAuthor.institutions),
                    joinedload(OpenAlexAuthor.works)
                ).filter_by(id=person.openalex_author_id).first()
            
            if not author:
                # Try to find the GitHub user in OpenAlex by name
                if person.user_id and person.name:
                    user = session.query(User).filter_by(id=person.user_id).first()
                    if user and user.name:
                        authors = session.query(OpenAlexAuthor).filter(
                            OpenAlexAuthor.display_name.ilike(f"%{user.name}%")
                        ).all()
                        
                        if authors:
                            # Use the first match for simplicity
                            author = authors[0]
            
            if not author:
                return 0.0, {}
            
            # Check for institution affiliations
            for institution in author.institutions:
                if institution_name.lower() in institution.display_name.lower():
                    evidence['institution_affiliation'] = {
                        'institution': institution.display_name,
                        'openalex_id': institution.openalex_id
                    }
                    return 0.9, evidence  # High confidence for institution affiliation
            
            # Check works for institution mentions
            matching_works = []
            for work in author.works:
                # For simplicity, just check if any co-authors are affiliated with the institution
                for coauthor in work.authors:
                    for institution in coauthor.institutions:
                        if institution_name.lower() in institution.display_name.lower():
                            matching_works.append({
                                'title': work.title,
                                'year': work.publication_year,
                                'coauthor': coauthor.display_name
                            })
                            break
                    if matching_works:
                        break
            
            if matching_works:
                evidence['coauthor_affiliations'] = {
                    'matching_works': matching_works[:3]  # Limit to first 3 works
                }
                return 0.7, evidence  # Medium confidence for coauthor affiliations
        
        return 0.0, {}


class CombinedPersonFilter(PersonAssociationConfidenceFilter):
    """Filter that combines multiple methods for a comprehensive person score."""
    
    @property
    def name(self) -> str:
        return "Combined Person Filter"
    
    @property
    def description(self) -> str:
        return "Combines multiple filtering methods for a comprehensive person score"
    
    def calculate_confidence(self, person: SurfacedPerson, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        filters = [
            EmailDomainPersonFilter(),
            ProfilePersonFilter(),
            OpenAlexPersonFilter()
        ]
        
        scores = []
        evidence = {}
        
        for filter_obj in filters:
            score, filter_evidence = filter_obj.calculate_confidence(person, institution_info)
            if score > 0:
                filter_name = filter_obj.name
                scores.append((filter_name, score))
                evidence[filter_name] = filter_evidence
        
        if not scores:
            return 0.0, {}
        
        # Calculate weighted combined score
        weights = {
            "Email Domain Person Filter": 0.5,
            "Profile Person Filter": 0.3,
            "OpenAlex Person Filter": 0.4
        }
        
        weighted_sum = 0
        weight_total = 0
        
        for filter_name, score in scores:
            weight = weights.get(filter_name, 0.3)
            weighted_sum += score * weight
            weight_total += weight
        
        if weight_total == 0:
            return 0.0, {}
        
        # Normalize the final score
        final_score = min(1.0, weighted_sum / weight_total)
        
        # Add individual scores to evidence
        evidence["component_scores"] = {name: score for name, score in scores}
        evidence["final_score"] = final_score
        
        return final_score, evidence