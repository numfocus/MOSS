# --- UPDATED FILE: backend/data/models/__init__.py ---

# Import base first if other models rely on it implicitly
from .base import BaseModel
from .types import * # Import custom types

# Import all the models to make them visible to SQLAlchemy and Alembic
from .owner import Owner
from .contributor import Contributor
from .repository import Repository
from .repository_contributor import RepositoryContributorAssociation
from .work import Work
from .doi_reference import DOIReference
from .discovery_chain import DiscoveryChain
from .entity_discovery_association import EntityDiscoveryAssociation
from .keyword_search_session import KeywordSearchSession
from .keyword_repository_association import KeywordRepositoryAssociation
from .person import Person
from .institution import Institution
from .authorship import Authorship
from .affiliation import Affiliation
from .work_citation import WorkCitation
from .repository_institution_affiliation import RepositoryInstitutionAffiliation
from .software_dependency import SoftwareDependency
from .domain import Domain
from .field import Field
from .subfield import Subfield
from .topic import Topic
from .work_topic import WorkTopic
from .pull_request import PullRequest
from .issue import Issue
from .issue_comment import IssueComment # <<< Added
from .pr_review_comment import PRReviewComment # <<< Added


# Optionally define __all__ to control `from backend.data.models import *` behavior
__all__ = [
    "BaseModel",
    "Owner",
    "Contributor",
    "Repository",
    "RepositoryContributorAssociation",
    "Work",
    "DOIReference",
    "DiscoveryChain",
    "EntityDiscoveryAssociation",
    "KeywordSearchSession",
    "KeywordRepositoryAssociation",
    "Person",
    "Institution",
    "Authorship",
    "Affiliation",
    "WorkCitation",
    "RepositoryInstitutionAffiliation",
    "SoftwareDependency",
    "Domain",
    "Field",
    "Subfield",
    "Topic",
    "WorkTopic",
    "PullRequest",
    "Issue",
    "IssueComment", # <<< Added
    "PRReviewComment", # <<< Added
]