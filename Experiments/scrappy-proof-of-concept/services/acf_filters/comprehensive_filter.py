# services/acf_filters/comprehensive_filter.py
import json
import logging
from typing import Dict, Tuple, Any, List

from sqlalchemy.orm import joinedload
from db.database import get_db_session
from models.models import Repository, User, Organization, OpenAlexWork, OpenAlexAuthor
from models.models import PullRequest, Issue, IssueComment, Commit
from services.acf_base import AssociationConfidenceFilter  # Import from base file instead

logger = logging.getLogger(__name__)

class ComprehensiveFilter(AssociationConfidenceFilter):
    """
    A comprehensive filter that implements a hierarchical confidence scoring system
    for determining if a repository is associated with an institution.
    """
    
    @property
    def name(self) -> str:
        return "Comprehensive Filter"
    
    @property
    def description(self) -> str:
        return (
            "Applies a hierarchical confidence scoring system with multiple factors:\n"
            "- Direct ownership (100% confidence): Repository owned by institution GitHub org\n"
            "- Core contributors (up to 90%): Repository maintainers affiliated with institution\n"
            "- High confidence (up to 90%): Email domains match, OpenAlex affiliations\n"
            "- Medium confidence (up to 60%): Institution name in repo name/description\n"
            "- Lower confidence: Topic matches and indirect references"
        )
    
    def calculate_confidence(self, repository: Repository, institution_info: Dict[str, Any]) -> Tuple[float, Dict]:
        """
        Calculate confidence using a hierarchical approach, checking highest confidence
        factors first and returning as soon as a match is found.
        """
        evidence = {}
        
        # Get basic institution info
        institution_name = institution_info.get('name', '')
        domains = institution_info.get('domains', [])
        github_orgs = institution_info.get('github_orgs', [])
        
        if not institution_name:
            return 0.0, {}
            
        # LEVEL 1: Direct ownership (100% confidence)
        direct_ownership = self._check_direct_ownership(repository, github_orgs)
        if direct_ownership:
            evidence['direct_ownership'] = direct_ownership
            return 1.0, evidence
            
        # LEVEL 1.5: Core contributors (high confidence, up to 90%)
        core_contributors = self._check_core_contributors(repository, institution_name, domains)
        if core_contributors and core_contributors.get('score', 0) >= 0.8:
            evidence['core_contributors'] = core_contributors
            return core_contributors.get('score', 0), evidence
            
        # LEVEL 2: High confidence factors (up to 90%)
        email_evidence = self._check_email_domains(repository, domains)
        if email_evidence and email_evidence.get('score', 0) >= 0.7:
            evidence['email_domains'] = email_evidence
            return email_evidence.get('score', 0), evidence
            
        openalex_evidence = self._check_openalex_affiliations(repository, institution_name)
        if openalex_evidence and openalex_evidence.get('score', 0) >= 0.7:
            evidence['openalex_affiliations'] = openalex_evidence
            return openalex_evidence.get('score', 0), evidence
            
        # If we have core contributors and another high factor, combine them
        if core_contributors and core_contributors.get('score', 0) >= 0.5:
            if email_evidence or openalex_evidence:
                evidence['core_contributors'] = core_contributors
                
                if email_evidence:
                    evidence['email_domains'] = email_evidence
                    combined_score = min(0.9, (core_contributors.get('score', 0) * 0.6) + 
                                        (email_evidence.get('score', 0) * 0.4))
                    
                    evidence['combined_high_confidence'] = {
                        'core_contributor_score': core_contributors.get('score', 0),
                        'email_score': email_evidence.get('score', 0),
                        'combined_score': combined_score
                    }
                    
                    if combined_score >= 0.7:
                        return combined_score, evidence
                
                if openalex_evidence:
                    evidence['openalex_affiliations'] = openalex_evidence
                    combined_score = min(0.9, (core_contributors.get('score', 0) * 0.6) + 
                                        (openalex_evidence.get('score', 0) * 0.4))
                    
                    evidence['combined_high_confidence'] = {
                        'core_contributor_score': core_contributors.get('score', 0),
                        'openalex_score': openalex_evidence.get('score', 0),
                        'combined_score': combined_score
                    }
                    
                    if combined_score >= 0.7:
                        return combined_score, evidence
            
        # Continue with existing code...
        if email_evidence and openalex_evidence:
            email_score = email_evidence.get('score', 0)
            openalex_score = openalex_evidence.get('score', 0)
            
            if email_score > 0 and openalex_score > 0:
                combined_score = min(0.9, (email_score * 0.6) + (openalex_score * 0.4))
                if combined_score >= 0.7:
                    evidence['email_domains'] = email_evidence
                    evidence['openalex_affiliations'] = openalex_evidence
                    evidence['combined_high_confidence'] = {
                        'email_score': email_score,
                        'openalex_score': openalex_score,
                        'combined_score': combined_score
                    }
                    return combined_score, evidence
        
        # LEVEL 3: Medium confidence factors (up to 60%)
        naming_evidence = self._check_naming_references(repository, institution_name)
        if naming_evidence and naming_evidence.get('score', 0) >= 0.4:
            evidence['naming_references'] = naming_evidence
            
            # Include any high confidence factors we found (even if they weren't high enough alone)
            if core_contributors:
                evidence['core_contributors'] = core_contributors
            if email_evidence:
                evidence['email_domains'] = email_evidence
            if openalex_evidence:
                evidence['openalex_affiliations'] = openalex_evidence
                
            return naming_evidence.get('score', 0), evidence
            
        # LEVEL 4: Lower confidence factors
        topic_evidence = self._check_topic_matches(repository, institution_name)
        
        # Combine all evidence found for a final score
        combined_score = 0.0
        factors_found = 0
        
        if core_contributors:
            combined_score += core_contributors.get('score', 0) * 0.4  # Strong weight
            evidence['core_contributors'] = core_contributors
            factors_found += 1
            
        if email_evidence:
            combined_score += email_evidence.get('score', 0) * 0.3
            evidence['email_domains'] = email_evidence
            factors_found += 1
            
        if openalex_evidence:
            combined_score += openalex_evidence.get('score', 0) * 0.3
            evidence['openalex_affiliations'] = openalex_evidence
            factors_found += 1
            
        if naming_evidence:
            combined_score += naming_evidence.get('score', 0) * 0.25
            evidence['naming_references'] = naming_evidence
            factors_found += 1
            
        if topic_evidence:
            combined_score += topic_evidence.get('score', 0) * 0.15
            evidence['topic_matches'] = topic_evidence
            factors_found += 1
        
        # Only return a score if we found at least one factor
        if factors_found > 0:
            # Adjust for number of factors - more factors = higher confidence
            if factors_found >= 3:
                combined_score *= 1.2
                evidence['multi_factor_bonus'] = True
                
            final_score = min(0.7, combined_score)  # Cap at 0.7 for combined low confidence
            return final_score, evidence
            
        return 0.0, {}
    
    def _check_direct_ownership(self, repository: Repository, github_orgs: List[str]) -> Dict:
        """Check if the repository is owned by a known institution GitHub organization."""
        with get_db_session() as session:
            owner = None
            org = session.query(Organization).filter_by(id=repository.owner_id).first()
            
            if org:
                owner_login = org.login
                owner_type = "Organization"
            else:
                user = session.query(User).filter_by(id=repository.owner_id).first()
                if user:
                    owner_login = user.login
                    owner_type = "User"
                else:
                    return None
            
            # Check against provided GitHub orgs
            for org_name in github_orgs:
                if org_name and owner_login and org_name.lower() == owner_login.lower():
                    return {
                        'match_type': 'exact_match',
                        'owner_type': owner_type,
                        'owner': owner_login,
                        'matched_org': org_name
                    }
            
            return None
    
    def _check_core_contributors(self, repository: Repository, institution_name: str, institution_domains: List[str] = None) -> Dict:
        """
        Analyze core contributors to determine institutional affiliation.
        Core contributors are identified by their commit volume, PR activity, 
        and other engagement metrics.
        
        Returns higher confidence scores for repositories where core contributors
        have institutional affiliations.
        """
        with get_db_session() as session:
            from sqlalchemy import func, select, or_, desc
            
            # Get repository with eager loading
            repo_id = repository.id
            
            # First, identify core contributors by activity level
            # Count PRs per user
            try:
                # Get PR authors for this repository
                pr_authors = session.query(
                    User,
                    func.count(PullRequest.id).label('pr_count')
                ).join(
                    PullRequest, PullRequest.user_id == User.id
                ).filter(
                    PullRequest.repository_id == repo_id
                ).group_by(
                    User.id
                ).order_by(
                    desc('pr_count')
                ).limit(10).all()
                
                if not pr_authors:
                    return None
                
                # Analyze core contributors for institutional affiliation
                matching_contributors = []
                total_score = 0.0
                
                for user, pr_count in pr_authors:
                    # Calculate "coreness" factor - higher for more active contributors
                    activity_level = pr_count
                    coreness = min(1.0, activity_level / 5)  # Cap at 1.0
                    
                    contributor_evidence = {}
                    contributor_score = 0.0
                    
                    # Check profile data
                    if user.company and institution_name.lower() in user.company.lower():
                        contributor_score += 0.6
                        contributor_evidence["company_match"] = True
                    
                    if user.location and institution_name.lower() in user.location.lower():
                        contributor_score += 0.3
                        contributor_evidence["location_match"] = True
                    
                    # Check email domains if available
                    if user.email and institution_domains:
                        if any(domain.lower() in user.email.lower() for domain in institution_domains):
                            contributor_score += 0.8
                            contributor_evidence["email_domain_match"] = True
                    
                    # If we have some evidence, consider this a matching contributor
                    if contributor_score > 0:
                        # Weight by coreness - core contributors count more
                        weighted_score = contributor_score * coreness
                        
                        matching_contributors.append({
                            "login": user.login,
                            "coreness": coreness,
                            "evidence": contributor_evidence,
                            "score": weighted_score
                        })
                        
                        total_score += weighted_score
                
                # Return results if we found matches
                if matching_contributors:
                    # Scale based on proportion of core contributors that match
                    proportion = len(matching_contributors) / len(pr_authors)
                    final_score = min(0.9, (total_score / len(pr_authors)) * (1 + proportion))
                    
                    return {
                        "matching_core_contributors": len(matching_contributors),
                        "total_core_contributors": len(pr_authors),
                        "contributors": matching_contributors[:5],  # Return top 5 for display
                        "score": final_score
                    }
            
            except Exception as e:
                logger.error(f"Error in core contributor analysis: {e}")
                return None
                
            return None
    
    def _check_email_domains(self, repository: Repository, institution_domains: List[str]) -> Dict:
        """Check email domains of contributors for matches with institution domains."""
        if not institution_domains:
            return None
            
        with get_db_session() as session:
            # Get all contributors with email information
            from sqlalchemy import or_, select
            
            # Create subqueries properly
            try:
                # Use a simpler approach that's less likely to cause errors
                pr_users = session.query(User).join(
                    PullRequest, PullRequest.user_id == User.id
                ).filter(
                    PullRequest.repository_id == repository.id,
                    User.email.isnot(None)
                ).all()
                
                issue_users = session.query(User).join(
                    Issue, Issue.user_id == User.id
                ).filter(
                    Issue.repository_id == repository.id,
                    User.email.isnot(None)
                ).all()
                
                # Combine all contributors
                contributors = list(set(pr_users + issue_users))
                
                total_contributors = len(contributors)
                if total_contributors == 0:
                    return None
                
                # Count contributors with matching domains
                matching_contributors = []
                for contributor in contributors:
                    if any(domain.lower() in contributor.email.lower() for domain in institution_domains):
                        matching_contributors.append(contributor.login)
                
                matching_count = len(matching_contributors)
                if matching_count == 0:
                    return None
                
                # Calculate score based on ratio and absolute numbers
                ratio = matching_count / total_contributors
                
                # Base score calculation
                if matching_count >= 5 and ratio >= 0.5:
                    # Strong signal: 5+ contributors and 50%+ have matching domains
                    score = min(0.9, 0.7 + (ratio * 0.2))
                elif matching_count >= 3 and ratio >= 0.3:
                    # Moderate signal: 3+ contributors and 30%+ have matching domains
                    score = 0.5 + (ratio * 0.3)
                else:
                    # Weaker signal
                    score = 0.3 + (ratio * 0.3)
                
                return {
                    'matching_count': matching_count,
                    'total_contributors': total_contributors,
                    'ratio': ratio,
                    'matching_examples': matching_contributors[:5],
                    'score': score
                }
            except Exception as e:
                logger.error(f"Error in email domain check: {e}")
                return None
    
    def _check_openalex_affiliations(self, repository: Repository, institution_name: str) -> Dict:
        """Check OpenAlex data for authors affiliated with the institution."""
        with get_db_session() as session:
            # Don't rely on lazy loading - get repository with dois explicitly
            repo = session.query(Repository).options(
                joinedload(Repository.dois)
            ).filter(Repository.id == repository.id).first()
            
            if not repo or not repo.dois:
                return None
                
            # Get DOIs for this repository
            doi_strings = [doi.doi for doi in repo.dois]
            
            # Find OpenAlex works with these DOIs
            works = session.query(OpenAlexWork).options(
                joinedload(OpenAlexWork.authors).joinedload(OpenAlexAuthor.institutions)
            ).filter(OpenAlexWork.doi.in_(doi_strings)).all()
            
            if not works:
                return None
            
            total_works = len(works)
            matching_works = 0
            matching_authors = set()
            
            for work in works:
                work_matches = False
                
                # Check all authors of this work
                for author in work.authors:
                    author_matches = False
                    
                    # Check all institutions this author is affiliated with
                    for institution in author.institutions:
                        if institution_name.lower() in institution.display_name.lower():
                            author_matches = True
                            work_matches = True
                            matching_authors.add(author.display_name)
                            break
                    
                    if author_matches:
                        break
                
                if work_matches:
                    matching_works += 1
            
            if matching_works == 0:
                return None
            
            # Calculate score based on ratio and absolute numbers
            ratio = matching_works / total_works
            
            # Base score calculation
            if matching_works >= 2 and ratio == 1.0:
                # All works have institution affiliation and we have 2+ works
                score = 0.9
            elif matching_works >= 1 and ratio >= 0.5:
                # At least half of works have institution affiliation
                score = 0.7 + (ratio * 0.2)
            else:
                # Some works have institution affiliation
                score = 0.5 + (ratio * 0.2)
            
            return {
                'matching_works': matching_works,
                'total_works': total_works,
                'ratio': ratio,
                'matching_authors': list(matching_authors)[:5],
                'score': score
            }
    
    def _check_naming_references(self, repository: Repository, institution_name: str) -> Dict:
        """Check if repository name, description, or README mentions the institution."""
        evidence = {}
        total_score = 0.0
        
        # Check repository name (higher confidence)
        if repository.name and institution_name.lower() in repository.name.lower():
            name_score = 0.5
            total_score += name_score
            evidence['name_match'] = {
                'text': repository.name,
                'score': name_score
            }
        
        # Check repository full name (could include organization)
        elif repository.full_name and institution_name.lower() in repository.full_name.lower():
            fullname_score = 0.4
            total_score += fullname_score
            evidence['fullname_match'] = {
                'text': repository.full_name,
                'score': fullname_score
            }
        
        # Check repository description
        if repository.description and institution_name.lower() in repository.description.lower():
            desc_score = 0.3
            total_score += desc_score
            evidence['description_match'] = {
                'score': desc_score
            }
        
        # Cap at 0.6 for naming references
        final_score = min(0.6, total_score)
        
        if final_score > 0:
            evidence['score'] = final_score
            return evidence
        
        return None
    
    def _check_topic_matches(self, repository: Repository, institution_name: str) -> Dict:
        """Check for topic matches and other indirect references."""
        if not repository.topics:
            return None
            
        topics = repository.topics.split(',')
        matching_topics = []
        
        for topic in topics:
            if institution_name.lower() in topic.lower():
                matching_topics.append(topic)
        
        if matching_topics:
            score = min(0.3, 0.1 + (len(matching_topics) * 0.05))
            return {
                'matching_topics': matching_topics,
                'score': score
            }
        
        return None