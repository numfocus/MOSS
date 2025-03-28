# services/institution_analysis/surfacing.py
"""
Repository and People surfacing algorithms for institution analysis.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union, Set

from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from db.database import get_db_session
from clients.github_client import GitHubClient
from models.models import (
    Repository, User, Organization, OpenAlexAuthor, OpenAlexInstitution,
    OpenAlexWork, AnalysisSession, SurfacingResult, SurfacedRepository,
    SurfacedPerson
)
from services.acf_framework import find_keyword_matches, get_repositories_from_keywords
from utils.repo_finder import search_repositories_by_date_ranges

logger = logging.getLogger(__name__)

class BaseSurfacingAlgorithm(ABC):
    """Base class for all surfacing algorithms."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the algorithm."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of how the algorithm works."""
        pass
    
    @abstractmethod
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """
        Run the surfacing algorithm and store results.
        
        Args:
            session_id: ID of the analysis session
            institution_info: Dictionary with institution information
            parameters: Algorithm-specific parameters
            
        Returns:
            ID of the surfacing result record
        """
        pass


class KeywordRepositorySurfacing(BaseSurfacingAlgorithm):
    """Find repositories using keywords related to the institution."""
    
    @property
    def name(self) -> str:
        return "Keyword Repository Surfacing"
    
    @property
    def description(self) -> str:
        return "Find repositories using keywords related to the institution"
    
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """Run the keyword-based repository surfacing algorithm."""
        institution_name = institution_info.get("name", "")
        if not institution_name:
            raise ValueError("Institution name is required")
        
        # Get keywords from parameters
        keywords = parameters.get("keywords", [])
        if not keywords:
            # Generate default keywords if none provided
            keywords = self._generate_default_keywords(institution_name)
        
        # Record the start of surfacing
        with get_db_session() as session:
            surfacing_result = SurfacingResult(
                session_id=session_id,
                algorithm=self.name,
                parameters=json.dumps(parameters),
                run_at=datetime.now()
            )
            session.add(surfacing_result)
            session.commit()
            surfacing_id = surfacing_result.id
        
        # First, check if these keywords have been used before
        existing_repositories = get_repositories_from_keywords(keywords)
        
        # If a GitHub token is provided, search for additional repositories
        if "github_token" in parameters:
            token = parameters["github_token"]
            client = GitHubClient(token=token)
            
            # For each keyword, search GitHub
            for keyword in keywords:
                # Use the repo_finder module to search repositories
                repo_data_list = search_repositories_by_date_ranges(client, keyword)
                
                for repo_data in repo_data_list:
                    owner = repo_data.get("owner", {}).get("login")
                    name = repo_data.get("name")
                    
                    if owner and name:
                        # Check if we already have this repository in our database
                        with get_db_session() as session:
                            full_name = f"{owner}/{name}"
                            repo = session.query(Repository).filter_by(full_name=full_name).first()
                            
                            if repo:
                                # Check if we already added this repo to the current surfacing
                                existing = session.query(SurfacedRepository).filter_by(
                                    surfacing_id=surfacing_id, repository_id=repo.id
                                ).first()
                                
                                if not existing:
                                    # Add to surfaced repositories
                                    surfaced_repo = SurfacedRepository(
                                        surfacing_id=surfacing_id,
                                        repository_id=repo.id,
                                        discovery_method="keyword_search",
                                        discovery_details=f"Found via keyword search: {keyword}",
                                        surface_score=0.5  # Initial relevance score
                                    )
                                    session.add(surfaced_repo)
        
        # Add all existing repositories from our database that match the keywords
        with get_db_session() as session:
            for repo in existing_repositories:
                # Check if we already added this repo
                existing = session.query(SurfacedRepository).filter_by(
                    surfacing_id=surfacing_id, repository_id=repo.id
                ).first()
                
                if not existing:
                    # Add to surfaced repositories
                    surfaced_repo = SurfacedRepository(
                        surfacing_id=surfacing_id,
                        repository_id=repo.id,
                        discovery_method="keyword_history",
                        discovery_details=f"Found in database from past keyword searches: {', '.join(keywords)}",
                        surface_score=0.7  # Higher score for existing repos
                    )
                    session.add(surfaced_repo)
            
            # Update the result count
            result_count = session.query(SurfacedRepository).filter_by(surfacing_id=surfacing_id).count()
            surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
            if surfacing_result:
                surfacing_result.result_count = result_count
                surfacing_result.result_summary = json.dumps({"keywords": keywords, "count": result_count})
        
        return surfacing_id
    
    def _generate_default_keywords(self, institution_name: str) -> List[str]:
        """Generate default keywords based on institution name."""
        keywords = [institution_name]
        
        # Add variations
        name_parts = institution_name.split()
        if len(name_parts) > 1:
            # Add abbreviation
            abbr = ''.join(part[0] for part in name_parts if part[0].isupper())
            if len(abbr) > 1:
                keywords.append(abbr)
            
            # Add just the first part (often the place name)
            keywords.append(name_parts[0])
        
        return keywords


class DomainRepositorySurfacing(BaseSurfacingAlgorithm):
    """Find repositories with contributors from institution domains."""
    
    @property
    def name(self) -> str:
        return "Domain Repository Surfacing"
    
    @property
    def description(self) -> str:
        return "Find repositories with contributors from institution domains"
    
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """Run the domain-based repository surfacing algorithm."""
        domains = institution_info.get("domains", [])
        if not domains:
            raise ValueError("Institution domains are required for domain surfacing")
        
        # Record the start of surfacing
        with get_db_session() as session:
            surfacing_result = SurfacingResult(
                session_id=session_id,
                algorithm=self.name,
                parameters=json.dumps(parameters),
                run_at=datetime.now()
            )
            session.add(surfacing_result)
            session.commit()
            surfacing_id = surfacing_result.id
        
        # Find users with matching email domains
        with get_db_session() as session:
            matching_users = []
            
            for domain in domains:
                users = session.query(User).filter(
                    User.email.isnot(None),
                    User.email.like(f"%@{domain}")
                ).all()
                
                matching_users.extend(users)
            
            # Find repositories these users have contributed to
            repositories = set()
            
            for user in matching_users:
                # Check pull requests
                prs = session.query(Repository).join(
                    Repository.pull_requests
                ).filter(
                    Repository.pull_requests.any(user_id=user.id)
                ).all()
                
                repositories.update(prs)
                
                # Check issues
                issues = session.query(Repository).join(
                    Repository.issues
                ).filter(
                    Repository.issues.any(user_id=user.id)
                ).all()
                
                repositories.update(issues)
            
            # Add the found repositories to surfaced repositories
            for repo in repositories:
                # Check if we already added this repo
                existing = session.query(SurfacedRepository).filter_by(
                    surfacing_id=surfacing_id, repository_id=repo.id
                ).first()
                
                if not existing:
                    # Add to surfaced repositories
                    surfaced_repo = SurfacedRepository(
                        surfacing_id=surfacing_id,
                        repository_id=repo.id,
                        discovery_method="domain_contributor",
                        discovery_details=f"Found via contributors with institution email domains: {', '.join(domains)}",
                        surface_score=0.8  # High score for domain matches
                    )
                    session.add(surfaced_repo)
            
            # Update the result count
            result_count = session.query(SurfacedRepository).filter_by(surfacing_id=surfacing_id).count()
            surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
            if surfacing_result:
                surfacing_result.result_count = result_count
                surfacing_result.result_summary = json.dumps({"domains": domains, "count": result_count})
        
        return surfacing_id

class DomainPeopleSurfacing(BaseSurfacingAlgorithm):
    """Find people with email domains matching the institution."""
    
    @property
    def name(self) -> str:
        return "Domain People Surfacing"
    
    @property
    def description(self) -> str:
        return "Find GitHub users with email domains matching the institution"
    
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """Run the domain-based people surfacing algorithm."""
        domains = institution_info.get("domains", [])
        if not domains:
            raise ValueError("Institution domains are required for domain people surfacing")
        
        # Record the start of surfacing
        with get_db_session() as session:
            surfacing_result = SurfacingResult(
                session_id=session_id,
                algorithm=self.name,
                parameters=json.dumps(parameters),
                run_at=datetime.now()
            )
            session.add(surfacing_result)
            session.commit()
            surfacing_id = surfacing_result.id
        
        # Find users with matching email domains
        with get_db_session() as session:
            for domain in domains:
                users = session.query(User).filter(
                    User.email.isnot(None),
                    User.email.like(f"%@{domain}")
                ).all()
                
                for user in users:
                    # Add to surfaced people
                    surfaced_person = SurfacedPerson(
                        surfacing_id=surfacing_id,
                        user_id=user.id,
                        name=user.name or user.login,
                        email=user.email,
                        discovery_method="email_domain",
                        discovery_details=f"Email domain match: {domain}",
                        surface_score=0.9  # High score for email domain matches
                    )
                    session.add(surfaced_person)
            
            # Update the result count
            result_count = session.query(SurfacedPerson).filter_by(surfacing_id=surfacing_id).count()
            surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
            if surfacing_result:
                surfacing_result.result_count = result_count
                surfacing_result.result_summary = json.dumps({"domains": domains, "count": result_count})
        
        return surfacing_id


class ProfilePeopleSurfacing(BaseSurfacingAlgorithm):
    """Find people with profiles mentioning the institution."""
    
    @property
    def name(self) -> str:
        return "Profile People Surfacing"
    
    @property
    def description(self) -> str:
        return "Find GitHub users with profiles mentioning the institution"
    
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """Run the profile-based people surfacing algorithm."""
        institution_name = institution_info.get("name", "")
        if not institution_name:
            raise ValueError("Institution name is required")
        
        # Record the start of surfacing
        with get_db_session() as session:
            surfacing_result = SurfacingResult(
                session_id=session_id,
                algorithm=self.name,
                parameters=json.dumps(parameters),
                run_at=datetime.now()
            )
            session.add(surfacing_result)
            session.commit()
            surfacing_id = surfacing_result.id
        
        # Find users with profiles mentioning the institution
        with get_db_session() as session:
            # Search in company field
            company_users = session.query(User).filter(
                User.company.isnot(None),
                User.company.ilike(f"%{institution_name}%")
            ).all()
            
            # Search in bio field
            bio_users = session.query(User).filter(
                User.bio.isnot(None),
                User.bio.ilike(f"%{institution_name}%")
            ).all()
            
            # Search in location field (for universities often named after locations)
            location_users = session.query(User).filter(
                User.location.isnot(None),
                User.location.ilike(f"%{institution_name}%")
            ).all()
            
            # Combine results
            all_users = set(company_users + bio_users + location_users)
            
            for user in all_users:
                # Calculate score and details
                score = 0.0
                details = []
                
                if user.company and institution_name.lower() in user.company.lower():
                    score = max(score, 0.8)
                    details.append(f"Company match: {user.company}")
                
                if user.bio and institution_name.lower() in user.bio.lower():
                    score = max(score, 0.6)
                    details.append(f"Bio match: mentions institution")
                
                if user.location and institution_name.lower() in user.location.lower():
                    score = max(score, 0.4)
                    details.append(f"Location match: {user.location}")
                
                # Add to surfaced people
                surfaced_person = SurfacedPerson(
                    surfacing_id=surfacing_id,
                    user_id=user.id,
                    name=user.name or user.login,
                    email=user.email,
                    discovery_method="profile_mention",
                    discovery_details="; ".join(details),
                    surface_score=score
                )
                session.add(surfaced_person)
            
            # Update the result count
            result_count = session.query(SurfacedPerson).filter_by(surfacing_id=surfacing_id).count()
            surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
            if surfacing_result:
                surfacing_result.result_count = result_count
                surfacing_result.result_summary = json.dumps({"institution": institution_name, "count": result_count})
        
        return surfacing_id


class OpenAlexPeopleSurfacing(BaseSurfacingAlgorithm):
    """Find people from OpenAlex data that are affiliated with the institution."""
    
    @property
    def name(self) -> str:
        return "OpenAlex People Surfacing"
    
    @property
    def description(self) -> str:
        return "Find authors in OpenAlex that are affiliated with the institution"
    
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """Run the OpenAlex-based people surfacing algorithm."""
        institution_name = institution_info.get("name", "")
        if not institution_name:
            raise ValueError("Institution name is required")
        
        # Record the start of surfacing
        with get_db_session() as session:
            surfacing_result = SurfacingResult(
                session_id=session_id,
                algorithm=self.name,
                parameters=json.dumps(parameters),
                run_at=datetime.now()
            )
            session.add(surfacing_result)
            session.commit()
            surfacing_id = surfacing_result.id
        
        # Find OpenAlex institutions matching the name
        with get_db_session() as session:
            openalex_institutions = session.query(OpenAlexInstitution).filter(
                OpenAlexInstitution.display_name.ilike(f"%{institution_name}%")
            ).all()
            
            if not openalex_institutions:
                # No matching institutions found
                surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
                if surfacing_result:
                    surfacing_result.result_count = 0
                    surfacing_result.result_summary = json.dumps({"error": "No matching OpenAlex institutions found"})
                return surfacing_id
            
            # Find authors affiliated with these institutions
            for institution in openalex_institutions:
                authors = session.query(OpenAlexAuthor).filter(
                    OpenAlexAuthor.institutions.any(id=institution.id)
                ).all()
                
                for author in authors:
                    # Add to surfaced people
                    surfaced_person = SurfacedPerson(
                        surfacing_id=surfacing_id,
                        openalex_author_id=author.id,
                        name=author.display_name,
                        discovery_method="openalex_affiliation",
                        discovery_details=f"Affiliated with {institution.display_name} in OpenAlex",
                        surface_score=0.85  # High score for OpenAlex affiliations
                    )
                    session.add(surfaced_person)
            
            # Update the result count
            result_count = session.query(SurfacedPerson).filter_by(surfacing_id=surfacing_id).count()
            surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
            if surfacing_result:
                surfacing_result.result_count = result_count
                surfacing_result.result_summary = json.dumps({
                    "institution": institution_name,
                    "openalex_institutions": [inst.display_name for inst in openalex_institutions],
                    "count": result_count
                })
        
        return surfacing_id
    
class NameRepositorySurfacing(BaseSurfacingAlgorithm):
    """Find repositories with names related to the institution."""
    
    @property
    def name(self) -> str:
        return "Name Repository Surfacing"
    
    @property
    def description(self) -> str:
        return "Find repositories with names or descriptions mentioning the institution"
    
    def run(self, session_id: int, institution_info: Dict[str, Any], parameters: Dict[str, Any]) -> int:
        """Run the name-based repository surfacing algorithm."""
        institution_name = institution_info.get("name", "")
        if not institution_name:
            raise ValueError("Institution name is required")
        
        # Generate variations of the name to search for
        name_variations = self._generate_name_variations(institution_name)
        
        # Record the start of surfacing
        with get_db_session() as session:
            surfacing_result = SurfacingResult(
                session_id=session_id,
                algorithm=self.name,
                parameters=json.dumps(parameters),
                run_at=datetime.now()
            )
            session.add(surfacing_result)
            session.commit()
            surfacing_id = surfacing_result.id
        
        # Search repositories by name and description
        with get_db_session() as session:
            for name_var in name_variations:
                # Search by full_name
                name_repos = session.query(Repository).filter(
                    Repository.full_name.ilike(f"%{name_var}%")
                ).all()
                
                # Search by description
                desc_repos = session.query(Repository).filter(
                    Repository.description.isnot(None),
                    Repository.description.ilike(f"%{name_var}%")
                ).all()
                
                # Combine results
                repositories = set(name_repos + desc_repos)
                
                # Add the found repositories
                for repo in repositories:
                    # Check if we already added this repo
                    existing = session.query(SurfacedRepository).filter_by(
                        surfacing_id=surfacing_id, repository_id=repo.id
                    ).first()
                    
                    if not existing:
                        # Calculate surface score based on match location
                        score = 0.0
                        details = []
                        
                        if repo.full_name and name_var.lower() in repo.full_name.lower():
                            score = max(score, 0.9)
                            details.append(f"Name match: {repo.full_name}")
                        
                        if repo.description and name_var.lower() in repo.description.lower():
                            score = max(score, 0.7)
                            details.append(f"Description match: {name_var} in description")
                        
                        # Add to surfaced repositories
                        surfaced_repo = SurfacedRepository(
                            surfacing_id=surfacing_id,
                            repository_id=repo.id,
                            discovery_method="name_match",
                            discovery_details="; ".join(details),
                            surface_score=score
                        )
                        session.add(surfaced_repo)
            
            # Update the result count
            result_count = session.query(SurfacedRepository).filter_by(surfacing_id=surfacing_id).count()
            surfacing_result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
            if surfacing_result:
                surfacing_result.result_count = result_count
                surfacing_result.result_summary = json.dumps({"name_variations": name_variations, "count": result_count})
        
        return surfacing_id
    
    def _generate_name_variations(self, institution_name: str) -> List[str]:
        """Generate variations of the institution name for searching."""
        variations = [institution_name]
        
        # Add parts of the name
        parts = institution_name.split()
        if len(parts) > 1:
            for part in parts:
                if len(part) > 3:  # Only add parts that are reasonably long
                    variations.append(part)
        
        # Remove duplicates
        return list(set(variations))