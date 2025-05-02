# --- UPDATED FILE: backend/data/repositories/__init__.py ---

from .base_repository import BaseRepository
from .owner_repo import OwnerRepository
from .contributor_repo import ContributorRepository
from .repository_repo import RepositoryRepository
from .work_repo import WorkRepository
from .doi_reference_repo import DOIReferenceRepository
from .discovery_chain_repo import DiscoveryChainRepository
from .entity_discovery_repo import EntityDiscoveryAssociationRepository
from .keyword_search_session_repo import KeywordSearchSessionRepository
from .keyword_repository_association_repo import KeywordRepositoryAssociationRepository
from .person_repo import PersonRepository
from .institution_repo import InstitutionRepository
from .repository_institution_affiliation_repo import RepositoryInstitutionAffiliationRepository
from .software_dependency_repo import SoftwareDependencyRepository
from .domain_repo import DomainRepository
from .field_repo import FieldRepository
from .subfield_repo import SubfieldRepository
from .topic_repo import TopicRepository
from .pull_request_repo import PullRequestRepository
from .issue_repo import IssueRepository
# --- ADDED ---
from .issue_comment_repo import IssueCommentRepository
from .pr_review_comment_repo import PRReviewCommentRepository
# --- END ADDED ---

# Optionally define __all__ for explicit exports
__all__ = [
    "BaseRepository",
    "OwnerRepository",
    "ContributorRepository",
    "RepositoryRepository",
    "WorkRepository",
    "DOIReferenceRepository",
    "DiscoveryChainRepository",
    "EntityDiscoveryAssociationRepository",
    "KeywordSearchSessionRepository",
    "KeywordRepositoryAssociationRepository",
    "PersonRepository",
    "InstitutionRepository",
    "RepositoryInstitutionAffiliationRepository",
    "SoftwareDependencyRepository",
    "DomainRepository",
    "FieldRepository",
    "SubfieldRepository",
    "TopicRepository",
    "PullRequestRepository",
    "IssueRepository",
    "IssueCommentRepository",       # <<< Added
    "PRReviewCommentRepository",    # <<< Added
]