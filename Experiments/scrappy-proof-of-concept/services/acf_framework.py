# services/acf_framework.py
# services/acf_framework.py
"""
Association Confidence Filter (ACF) Framework

This module provides a framework for creating and applying filters that determine
how confidently a repository is associated with a specific institution.
"""

import json
import logging
import re
from typing import List, Dict, Tuple, Any

from sqlalchemy.orm import joinedload
from db.database import get_db_session
from models.models import Repository, DiscoveryEvent
from services.acf_base import AssociationConfidenceFilter

logger = logging.getLogger(__name__)

# Import filter classes after importing the base class
from services.acf_filters.comprehensive_filter import ComprehensiveFilter

class NameMatchFilter(AssociationConfidenceFilter):
    """Filter that checks if repository name, description, or README mentions the institution."""
    
    @property
    def name(self) -> str:
        return "Name Match Filter"
    
    @property
    def description(self) -> str:
        return ("Checks if the repository name, description, or README mentions the institution name. "
                "Higher confidence if the match is in the name or owner.")
    
    def calculate_confidence(self, repository: Repository, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        institution_name = institution_info.get('name', '')
        if not institution_name:
            return 0.0, {}
        
        evidence = {}
        total_score = 0.0
        
        # Check owner (organization or user)
        with get_db_session() as session:
            from models.models import User, Organization
            
            owner = None
            org = session.query(Organization).filter_by(id=repository.owner_id).first()
            if org:
                owner = org
                evidence['owner_type'] = 'Organization'
            else:
                user = session.query(User).filter_by(id=repository.owner_id).first()
                if user:
                    owner = user
                    evidence['owner_type'] = 'User'
            
            if owner and institution_name.lower() in owner.login.lower():
                score = 0.9
                total_score += score
                evidence['owner_name_match'] = {
                    'match': owner.login,
                    'score': score
                }
        
        # Check repository name
        if repository.name and institution_name.lower() in repository.name.lower():
            score = 0.7
            total_score += score
            evidence['repo_name_match'] = {
                'match': repository.name,
                'score': score
            }
        
        # Check repository description
        if repository.description and institution_name.lower() in repository.description.lower():
            score = 0.3
            total_score += score
            evidence['description_match'] = {
                'match': True,
                'score': score
            }
        
        # Check repository topics
        if repository.topics:
            topics_list = repository.topics.split(',')
            for topic in topics_list:
                if institution_name.lower() in topic.lower():
                    score = 0.2
                    total_score += score
                    evidence['topic_match'] = {
                        'match': topic,
                        'score': score
                    }
                    break
        
        # Cap the total score at 1.0
        final_score = min(1.0, total_score)
        
        return final_score, evidence


class EmailDomainFilter(AssociationConfidenceFilter):
    """Filter that checks the email domains of contributors against institution domains."""
    
    @property
    def name(self) -> str:
        return "Email Domain Filter"
    
    @property
    def description(self) -> str:
        return ("Analyzes contributor email addresses to identify institutional domains. "
                "Higher confidence with more contributors having matching domains.")
    
    def calculate_confidence(self, repository: Repository, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        domains = institution_info.get('domains', [])
        if not domains:
            return 0.0, {}
        
        evidence = {}
        
        with get_db_session() as session:
            # Get all contributors with email information
            from models.models import User, PullRequest, Issue, IssueComment
            from sqlalchemy import or_
            
            contributors_query = (
                session.query(User)
                .filter(User.email.isnot(None))
            )
            
            # Find users with PRs, issues, or comments on this repo
            pr_users = session.query(User.id).join(PullRequest, PullRequest.user_id == User.id).filter(
                PullRequest.repository_id == repository.id
            ).subquery()
            
            issue_users = session.query(User.id).join(Issue, Issue.user_id == User.id).filter(
                Issue.repository_id == repository.id
            ).subquery()
            
            comment_users = session.query(User.id).join(IssueComment, IssueComment.user_id == User.id).join(
                Issue, IssueComment.issue_id == Issue.id
            ).filter(Issue.repository_id == repository.id).subquery()
            
            contributors = contributors_query.filter(
                or_(
                    User.id.in_(pr_users),
                    User.id.in_(issue_users),
                    User.id.in_(comment_users)
                )
            ).all()
            
            total_contributors = len(contributors)
            if total_contributors == 0:
                return 0.0, {}
            
            # Count contributors with matching domains
            matching_contributors = []
            for contributor in contributors:
                if any(domain.lower() in contributor.email.lower() for domain in domains):
                    matching_contributors.append(contributor.login)
            
            matching_count = len(matching_contributors)
            if matching_count == 0:
                return 0.0, {}
            
            # Calculate score based on ratio of matching contributors
            ratio = matching_count / total_contributors
            
            # Adjust score based on total contributors
            if total_contributors >= 10:
                # More contributors = more confidence in the ratio
                base_score = ratio
            elif total_contributors >= 5:
                base_score = ratio * 0.9
            else:
                base_score = ratio * 0.8
            
            # Higher absolute number of matching contributors increases confidence
            if matching_count >= 5:
                # Scale up to 0.95 max
                final_score = min(0.95, base_score * 1.2)
            else:
                final_score = base_score
            
            evidence = {
                'matching_contributors': matching_count,
                'total_contributors': total_contributors,
                'matching_ratio': ratio,
                'matching_logins': matching_contributors[:5]  # Include first 5 for display
            }
            
            return final_score, evidence


class OpenAlexAffiliationFilter(AssociationConfidenceFilter):
    """Filter that uses OpenAlex data to check for institution affiliations."""
    
    @property
    def name(self) -> str:
        return "OpenAlex Affiliation Filter"
    
    @property
    def description(self) -> str:
        return ("Uses OpenAlex data to identify repositories linked to papers with authors "
                "affiliated with the institution.")
    
    def calculate_confidence(self, repository: Repository, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        institution_name = institution_info.get('name', '')
        if not institution_name or not repository.dois:
            return 0.0, {}
        
        evidence = {}
        
        with get_db_session() as session:
            # Get DOIs for this repository
            doi_strings = [doi.doi for doi in repository.dois]
            
            # Find OpenAlex works with these DOIs
            from models.models import OpenAlexWork
            works = session.query(OpenAlexWork).filter(OpenAlexWork.doi.in_(doi_strings)).all()
            
            if not works:
                return 0.0, {}
            
            total_works = len(works)
            matching_works = 0
            matching_details = []
            
            for work in works:
                work_matches = False
                work_authors = []
                
                # Check all authors of this work
                for author in work.authors:
                    author_matches = False
                    # Check all institutions this author is affiliated with
                    for institution in author.institutions:
                        if institution_name.lower() in institution.display_name.lower():
                            author_matches = True
                            work_matches = True
                            work_authors.append(author.display_name)
                            break
                    
                    if author_matches:
                        break
                
                if work_matches:
                    matching_works += 1
                    matching_details.append({
                        'title': work.title,
                        'doi': work.doi,
                        'authors': work_authors[:3]  # First 3 matching authors
                    })
            
            if matching_works == 0:
                return 0.0, {}
            
            # Calculate score based on ratio of matching works
            ratio = matching_works / total_works
            
            # Adjust score based on number of works
            if total_works >= 3:
                # More works = more confidence
                base_score = ratio
            else:
                base_score = ratio * 0.8
            
            # Cap at 0.95
            final_score = min(0.95, base_score)
            
            evidence = {
                'matching_works': matching_works,
                'total_works': total_works,
                'matching_ratio': ratio,
                'work_details': matching_details[:3]  # Include first 3 for display
            }
            
            return final_score, evidence


class CombinedFilter(AssociationConfidenceFilter):
    """Filter that combines multiple methods for a comprehensive score."""
    
    @property
    def name(self) -> str:
        return "Combined Filter"
    
    @property
    def description(self) -> str:
        return ("Combines multiple filtering methods: name matching, email domains, "
                "and OpenAlex affiliations for a comprehensive score.")
    
    def calculate_confidence(self, repository: Repository, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        filters = [
            NameMatchFilter(),
            EmailDomainFilter(),
            OpenAlexAffiliationFilter()
        ]
        
        scores = []
        evidence = {}
        
        for filter_obj in filters:
            score, filter_evidence = filter_obj.calculate_confidence(repository, institution_info)
            if score > 0:
                filter_name = filter_obj.name
                scores.append((filter_name, score))
                evidence[filter_name] = filter_evidence
        
        if not scores:
            return 0.0, {}
        
        # Calculate weighted combined score
        # Weight OpenAlex higher than email domains, which are weighted higher than name matching
        weights = {
            "Name Match Filter": 0.3,
            "Email Domain Filter": 0.35,
            "OpenAlex Affiliation Filter": 0.45
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

def get_available_filters() -> Dict[str, AssociationConfidenceFilter]:
    """Return a dictionary of all available ACF implementations."""
    filters = {}
    
    # Add all filter implementations
    for filter_class in [
        NameMatchFilter,
        EmailDomainFilter,
        OpenAlexAffiliationFilter,
        CombinedFilter,
        ComprehensiveFilter,  # Add the new comprehensive filter
    ]:
        filter_instance = filter_class()
        filters[filter_instance.name] = filter_instance
    
    return filters

def get_filter_by_name(name: str) -> AssociationConfidenceFilter:
    """Get a specific filter by name."""
    filters = get_available_filters()
    return filters.get(name)

def find_keyword_matches(keywords: List[str]) -> Dict[str, Dict]:
    """
    Find which keywords from the provided list have been used in discovery events.
    
    Args:
        keywords: List of keywords to check
        
    Returns:
        Dictionary mapping each found keyword to its discovery statistics
    """
    results = {}
    
    with get_db_session() as session:
        for keyword in keywords:
            # Find discovery events that used this keyword
            events = session.query(DiscoveryEvent).filter(
                DiscoveryEvent.keyword == keyword
            ).all()
            
            if events:
                # Get list of unique repository IDs discovered with this keyword
                repo_event_ids = [
                    event.object_id for event in events 
                    if event.object_type == 'Repository'
                ]
                
                # Get the most recent discovery date
                latest_event = max(events, key=lambda e: e.timestamp)
                
                results[keyword] = {
                    'last_run': latest_event.timestamp,
                    'repository_count': len(set(repo_event_ids)),
                    'repository_ids': list(set(repo_event_ids))
                }
    
    return results

def get_repositories_from_keywords(keywords: List[str]) -> List[Repository]:
    """
    Get all repositories that were discovered using any of the provided keywords.
    
    Args:
        keywords: List of keywords to check
        
    Returns:
        List of Repository objects
    """
    repo_ids = set()
    
    with get_db_session() as session:
        for keyword in keywords:
            # Find discovery events for this keyword
            events = session.query(DiscoveryEvent).filter(
                DiscoveryEvent.keyword == keyword,
                DiscoveryEvent.object_type == 'Repository'
            ).all()
            
            # Add repository IDs to the set
            for event in events:
                repo_ids.add(event.object_id)
        
        if not repo_ids:
            return []
        
        # Get the actual Repository objects with eager loading of dois relationship
        repositories = session.query(Repository).options(
            joinedload(Repository.dois)
        ).filter(
            Repository.id.in_(list(repo_ids))
        ).all()
    
    return repositories

def apply_filter(filter_name: str, repositories: List[Repository], 
                institution_info: Dict[str, Any], 
                store_results: bool = True,
                keywords: List[str] = None) -> List[Tuple[Repository, float, Dict]]:
    """
    Apply a specific ACF to a list of repositories.
    
    Args:
        filter_name: Name of the filter to apply
        repositories: List of Repository objects to filter
        institution_info: Dictionary with institution information
        store_results: Whether to store the analysis results in the database
        keywords: List of keywords that led to these repositories
        
    Returns:
        List of tuples (repository, confidence_score, evidence_dict)
        sorted by confidence score (highest first)
    """
    filter_instance = get_filter_by_name(filter_name)
    if not filter_instance:
        raise ValueError(f"Filter '{filter_name}' not found")
    
    # Use a session context for calculating confidence scores
    results = []
    with get_db_session() as session:
        # Re-query repositories with all needed relationships eagerly loaded
        repo_ids = [repo.id for repo in repositories]
        if not repo_ids:
            return []
            
        fresh_repos = session.query(Repository).options(
            joinedload(Repository.dois)
        ).filter(
            Repository.id.in_(repo_ids)
        ).all()
        
        for repo in fresh_repos:
            confidence, evidence = filter_instance.calculate_confidence(repo, institution_info)
            if confidence > 0:
                results.append((repo, confidence, evidence))
    
    # Sort by confidence score (highest first)
    sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
    
    # Store the analysis results if requested
    if store_results:
        store_analysis_results(repositories, filter_name, institution_info, results, keywords)
    
    return sorted_results

def store_analysis_results(repositories: List[Repository], 
                       filter_name: str, 
                       institution_info: Dict[str, Any], 
                       results: List[Tuple[Repository, float, Dict]],
                       keywords: List[str] = None):
    """
    Store repository-institution confidence analysis results in the database.
    
    Args:
        repositories: List of all repositories that were analyzed
        filter_name: Name of the filter that was applied
        institution_info: Information about the institution
        results: List of (repository, confidence_score, evidence) tuples
        keywords: List of keywords that led to these repositories
    """
    from models.models import RepositoryInstitutionAnalysis
    
    institution_name = institution_info.get('name', 'Unknown Institution')
    keywords_str = ",".join(keywords) if keywords else None
    
    # Create a dictionary for quick lookup of results
    result_dict = {repo.id: (score, evidence) for repo, score, evidence in results}
    
    with get_db_session() as session:
        # Process each repository that was analyzed
        for repo in repositories:
            # Get the score and evidence if this repository had a non-zero score
            if repo.id in result_dict:
                score, evidence = result_dict[repo.id]
            else:
                # For repositories that didn't meet the threshold, store a 0 score
                score, evidence = 0.0, {}
            
            # Create a new analysis record
            analysis = RepositoryInstitutionAnalysis(
                repository_id=repo.id,
                institution_name=institution_name,
                filter_name=filter_name,
                confidence_score=score,
                evidence=json.dumps(evidence) if evidence else None,
                keywords_used=keywords_str
            )
            
            session.add(analysis)
        
        session.commit()
    
    logger.info(f"Stored analysis results for {len(repositories)} repositories against {institution_name}")

    # Sort by confidence score (highest first)
    return sorted(results, key=lambda x: x[1], reverse=True)