"""
backend.schemas.responses
-------------------------

Pydantic models defining the structure of data returned by the API endpoints.

These models are used for serialization and validation of outgoing responses,
ensuring consistency and providing clear contracts for API consumers. They often
inherit from base models and summary models to promote reusability.
"""

from pydantic import (
    BaseModel, ConfigDict, Field, HttpUrl,
    field_validator,
    ValidationInfo
)
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# --- Base ---
class BaseResponse(BaseModel):
    """
    A base model for API responses, providing common fields and configuration.

    Includes optional database ID and timestamp fields, and configures Pydantic
    to allow population from ORM model attributes.
    """
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int | uuid.UUID] = Field(None, description="Unique identifier for the resource.")
    created_at: Optional[datetime] = Field(None, description="Timestamp of resource creation (UTC).")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of last resource update (UTC).")

# --- Summaries (for lists) ---
class RepositorySummary(BaseResponse):
    """
    A concise representation of a Repository, suitable for list views.
    """
    id: int = Field(..., description="Internal database ID of the repository.")
    full_name: str = Field(..., description="Full name of the repository (e.g., 'owner/repo').")
    stargazers_count: Optional[int] = Field(0, description="Number of users who have starred the repository on GitHub.")
    language: Optional[str] = Field(None, description="Primary programming language detected in the repository.")
    description: Optional[str] = Field(None, description="Description of the repository provided on GitHub.")
    html_url: Optional[HttpUrl] = Field(None, description="URL to the repository's main page on GitHub.")

    @field_validator('html_url', mode='before')
    @classmethod
    def empty_str_to_none_html_url(cls, v: Any):
        """Ensure empty strings for HTML URLs are converted to None."""
        if isinstance(v, str) and v == '':
            return None
        return v

class WorkSummary(BaseResponse):
    """
    A concise representation of a scholarly Work (publication), suitable for list views.
    """
    id: int = Field(..., description="Internal database ID of the work.")
    title: Optional[str] = Field(None, description="Title of the scholarly work.")
    doi: Optional[str] = Field(None, description="Digital Object Identifier (DOI) of the work.")
    publication_year: Optional[int] = Field(None, description="Year the work was published.")

class PersonSummary(BaseResponse):
    """
    A concise representation of a Person (author/contributor), suitable for list views.
    """
    id: int = Field(..., description="Internal database ID of the person.")
    display_name: Optional[str] = Field(None, description="Primary display name of the person.")
    orcid: Optional[str] = Field(None, description="ORCID identifier for the person.")

class InstitutionSummary(BaseResponse):
    """
    A concise representation of an Institution, suitable for list views.
    """
    id: int = Field(..., description="Internal database ID of the institution.")
    display_name: Optional[str] = Field(None, description="Primary display name of the institution.")
    ror: Optional[str] = Field(None, description="Research Organization Registry (ROR) identifier for the institution.")

# --- Topic Hierarchy Summaries ---
class DomainSummary(BaseResponse):
    """
    A concise representation of an OpenAlex Domain, the highest level in the topic hierarchy.
    """
    id: int = Field(..., description="Internal database ID of the domain.")
    openalex_id: str = Field(..., description="OpenAlex ID for the domain.")
    display_name: str = Field(..., description="Display name of the domain.")

class FieldSummary(BaseResponse):
    """
    A concise representation of an OpenAlex Field, nested under a Domain.
    """
    id: int = Field(..., description="Internal database ID of the field.")
    openalex_id: str = Field(..., description="OpenAlex ID for the field.")
    display_name: str = Field(..., description="Display name of the field.")

class SubfieldSummary(BaseResponse):
    """
    A concise representation of an OpenAlex Subfield, nested under a Field.
    """
    id: int = Field(..., description="Internal database ID of the subfield.")
    openalex_id: str = Field(..., description="OpenAlex ID for the subfield.")
    display_name: str = Field(..., description="Display name of the subfield.")

class TopicSummary(BaseResponse):
    """
    A concise representation of an OpenAlex Topic, the most granular level in the hierarchy, nested under a Subfield.
    """
    id: int = Field(..., description="Internal database ID of the topic.")
    openalex_id: str = Field(..., description="OpenAlex ID for the topic.")
    display_name: str = Field(..., description="Display name of the topic.")

class PrimaryTopicResponse(TopicSummary):
    """
    Represents the primary topic associated with a resource (e.g., a Work),
    including its hierarchical context (Subfield, Field, Domain) and relevance score.
    """
    score: Optional[float] = Field(None, description="Relevance score assigned to this topic for the associated resource.")
    subfield: Optional[SubfieldSummary] = Field(None, description="The Subfield this topic belongs to.")
    field: Optional[FieldSummary] = Field(None, description="The Field this topic's Subfield belongs to.")
    domain: Optional[DomainSummary] = Field(None, description="The Domain this topic's Field belongs to.")

# --- Full Responses ---
class OwnerResponse(BaseResponse):
    """
    Detailed representation of a GitHub Owner (User or Organization).
    """
    id: int = Field(..., description="Internal database ID of the owner.")
    github_id: int = Field(..., description="GitHub's unique ID for the owner.")
    login: str = Field(..., description="GitHub username or organization name.")
    type: str = Field(..., description="Type of GitHub account ('User' or 'Organization').")
    avatar_url: Optional[HttpUrl] = Field(None, description="URL of the owner's avatar image on GitHub.")
    html_url: Optional[HttpUrl] = Field(None, description="URL to the owner's profile page on GitHub.")

    @field_validator('avatar_url', 'html_url', mode='before')
    @classmethod
    def empty_str_to_none_owner_urls(cls, v: Any):
        """Ensure empty strings for owner URLs are converted to None."""
        if isinstance(v, str) and v == '':
            return None
        return v


class ContributorResponse(BaseResponse):
    """
    Detailed representation of a GitHub Repository Contributor.
    Note: This structure often mirrors OwnerResponse as contributors are GitHub Users.
    """
    id: int = Field(..., description="Internal database ID of the contributor record (distinct from the user ID).")
    github_id: int = Field(..., description="GitHub's unique ID for the contributor (User).")
    login: str = Field(..., description="GitHub username of the contributor.")
    type: str = Field(..., description="Type of GitHub account (usually 'User').")
    avatar_url: Optional[HttpUrl] = Field(None, description="URL of the contributor's avatar image on GitHub.")
    html_url: Optional[HttpUrl] = Field(None, description="URL to the contributor's profile page on GitHub.")

    @field_validator('avatar_url', 'html_url', mode='before')
    @classmethod
    def empty_str_to_none_contrib_urls(cls, v: Any):
        """Ensure empty strings for contributor URLs are converted to None."""
        if isinstance(v, str) and v == '':
            return None
        return v

class RepositoryResponse(RepositorySummary):
    """
    Detailed representation of a GitHub Repository, extending the summary view.
    """
    github_id: int = Field(..., description="GitHub's unique ID for the repository.")
    name: str = Field(..., description="Name of the repository (without the owner).")
    homepage: Optional[HttpUrl] = Field(None, description="URL of the project's homepage, if specified.")
    api_url: Optional[HttpUrl] = Field(None, description="URL for accessing the repository via the GitHub API.")
    watchers_count: Optional[int] = Field(0, description="Number of users watching the repository on GitHub.")
    forks_count: Optional[int] = Field(0, description="Number of times the repository has been forked on GitHub.")
    open_issues_count: Optional[int] = Field(0, description="Number of open issues in the repository.")
    is_fork: Optional[bool] = Field(False, description="Indicates if the repository is a fork of another repository.")
    gh_created_at: Optional[datetime] = Field(None, description="Timestamp when the repository was created on GitHub (UTC).")
    gh_updated_at: Optional[datetime] = Field(None, description="Timestamp when the repository was last updated on GitHub (UTC).")
    gh_pushed_at: Optional[datetime] = Field(None, description="Timestamp when code was last pushed to the repository on GitHub (UTC).")
    owner_id: Optional[int] = Field(None, description="Internal database ID of the repository's owner.")
    topics: Optional[List[str]] = Field(None, description="List of topics assigned to the repository on GitHub.")
    license: Optional[Dict[str, Any]] = Field(None, description="Details of the repository's license, as detected by GitHub.")

    @field_validator('homepage', 'api_url', mode='before')
    @classmethod
    def empty_str_to_none_repo_urls(cls, v: Any):
        """Ensure empty strings for repository homepage and API URLs are converted to None."""
        if isinstance(v, str) and v == '':
            return None
        return v

class WorkResponse(WorkSummary):
    """
    Detailed representation of a scholarly Work (publication), extending the summary view.
    Includes information from OpenAlex and associated topic data.
    """
    openalex_id: Optional[str] = Field(None, description="OpenAlex ID for the work.")
    type: Optional[str] = Field(None, description="Type of the scholarly work (e.g., 'article', 'book').")
    cited_by_count: Optional[int] = Field(None, description="Number of times this work has been cited by other works, according to OpenAlex.")
    host_venue_display_name: Optional[str] = Field(None, description="Display name of the host venue (e.g., journal, conference) where the work was published.")
    openalex_url: Optional[HttpUrl] = Field(None, description="URL to the work's page on OpenAlex.")
    primary_topic: Optional[PrimaryTopicResponse] = Field(None, description="The primary topic associated with the work, including its hierarchy.")
    topics: Optional[List[TopicSummary]] = Field(None, description="List of all topics associated with the work, represented as summaries.")

    @field_validator('openalex_url', mode='before')
    @classmethod
    def empty_str_to_none_work_urls(cls, v: Any):
        """Ensure empty strings for OpenAlex URLs are converted to None."""
        if isinstance(v, str) and v == '':
            return None
        return v

class PersonResponse(PersonSummary):
    """
    Detailed representation of a Person (author/contributor), extending the summary view.
    """
    openalex_id: Optional[str] = Field(None, description="OpenAlex ID associated with the person.")
    display_name_alternatives: Optional[List[str]] = Field(None, description="Alternative names or spellings associated with the person.")

class InstitutionResponse(InstitutionSummary):
    """
    Detailed representation of an Institution, extending the summary view.
    """
    openalex_id: Optional[str] = Field(None, description="OpenAlex ID associated with the institution.")
    country_code: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country code for the institution's location.")
    type: Optional[str] = Field(None, description="Type of institution (e.g., 'education', 'government').")
    github_organization_logins: Optional[List[str]] = Field(None, description="List of GitHub organization logins potentially associated with this institution.")


# --- Discovery & Search ---
class DiscoveryChainSummary(BaseResponse):
    """
    Summary of a discovery chain process, representing a traversal through related entities.
    """
    id: uuid.UUID = Field(..., description="Unique identifier for this specific discovery chain step or link.")
    root_chain_id: Optional[uuid.UUID] = Field(None, description="Identifier of the initial starting point of the overall discovery process.")
    level: Optional[int] = Field(None, description="Depth or level of this step within the discovery chain.")
    discovery_type: Optional[str] = Field(None, description="Type or method used for this discovery step (e.g., 'REPOSITORY_TO_WORK', 'WORK_TO_AUTHOR').")
    status: Optional[str] = Field(None, description="Current status of this discovery step (e.g., 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED').")
    started_at: Optional[datetime] = Field(None, description="Timestamp when processing for this step started (UTC).")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when processing for this step completed (UTC).")

class KeywordSearchSessionResponse(BaseResponse):
    """
    Represents the results and status of a keyword search session used for ingestion.
    """
    id: int = Field(..., description="Internal database ID for the search session.")
    keywords_raw: str = Field(..., description="The raw keyword string used for the search.")
    status: str = Field(..., description="Current status of the search session (e.g., 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED').")
    results_count: Optional[int] = Field(None, description="Number of relevant items found or processed during the session.")
    started_at: Optional[datetime] = Field(None, description="Timestamp when the search session started (UTC).")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the search session completed (UTC).")

# --- Surfacing ---
class RepositoryCitationCountResponse(BaseModel):
    """
    Provides aggregated citation counts for a specific repository.
    """
    repository_id: int = Field(..., description="Internal database ID of the repository.")
    openalex_aggregated_citations: int = Field(..., description="Total citations of works linked to this repository, based on OpenAlex's cited_by_count.")
    moss_discovered_citations: int = Field(..., description="Count of unique citing works discovered and linked within the MOSS system itself.")
    model_config = ConfigDict(from_attributes=True)


# --- Shared Recipes / Algorithms ---
class RecipeParameterMetadataResponse(BaseModel):
    """
    Metadata describing a single parameter required by a recipe or algorithm.
    """
    name: str = Field(..., description="Name of the parameter.")
    type: str = Field(..., description="Expected data type of the parameter (e.g., 'string', 'integer', 'boolean').")
    description: str = Field(..., description="Description of the parameter's purpose and usage.")

class RecipeMetadataResponse(BaseModel):
    """
    Metadata describing a discoverable recipe or algorithm script.
    """
    name: str = Field(..., description="Unique name identifying the recipe/algorithm.")
    version: str = Field(..., description="Version string for the recipe/algorithm.")
    description: str = Field(..., description="Description of what the recipe/algorithm does.")
    parameters: List[RecipeParameterMetadataResponse] = Field(..., description="List of parameters required to execute the recipe/algorithm.")
    file_path: str = Field(..., description="Relative path to the script file within the recipes directory.")

class RecipeExecutionResponse(BaseModel):
    """
    Standard response structure for the execution of a recipe or algorithm.
    """
    success: bool = Field(..., description="Indicates whether the execution completed successfully.")
    data: Optional[Any] = Field(None, description="Output data generated by the successful execution, structure depends on the recipe.")
    error: Optional[Dict[str, str]] = Field(None, description="Details of any error that occurred during execution (e.g., {'type': '...', 'message': '...'}).")

# --- Affiliation Algorithm Responses ---
class AffiliationResultResponse(BaseResponse):
    """
    Represents a potential affiliation link between a repository and an institution,
    as determined by an affiliation algorithm. Includes evidence and confidence.
    """
    repository_id: int = Field(..., description="Internal database ID of the repository.")
    institution_id: int = Field(..., description="Internal database ID of the institution.")
    algorithm_name: str = Field(..., description="Name of the algorithm that generated this affiliation result.")
    algorithm_version: str = Field(..., description="Version of the algorithm used.")
    confidence_score: float = Field(..., description="A score (typically 0-1) indicating the algorithm's confidence in this affiliation.")
    evidence: Optional[Dict[str, Any]] = Field(None, description="Data used by the algorithm as evidence for this affiliation (structure varies by algorithm).")
    parameters_used: Optional[Dict[str, Any]] = Field(None, description="Parameters provided to the algorithm during this execution.")
    calculated_at: datetime = Field(..., description="Timestamp when this affiliation result was calculated (UTC).")
    # Optional fields for convenience, denormalized from related tables
    repository_name: Optional[str] = Field(None, description="Full name of the associated repository (owner/repo).")
    institution_name: Optional[str] = Field(None, description="Display name of the associated institution.")

class AffiliationExecutionResponse(BaseModel):
    """
    Summarizes the outcome of executing an affiliation algorithm for a specific institution.
    """
    status: str = Field(..., description="Overall status of the algorithm execution (e.g., 'COMPLETED', 'FAILED', 'PARTIAL_SUCCESS').")
    message: str = Field(..., description="A human-readable summary message about the execution process and outcome.")
    processed_count: int = Field(..., description="Number of potential affiliation results generated or evaluated by the algorithm.")
    created_count: int = Field(..., description="Number of new affiliation records created in the database based on the algorithm's findings.")
    updated_count: int = Field(..., description="Number of existing affiliation records updated (e.g., confidence score) based on the algorithm's findings.")


# --- Ingestion History Context ---
class IngestionHistoryContextResponse(BaseModel):
    """
    Provides context about the last ingestion event relevant to a specific parameter
    (e.g., the last time a specific keyword search was run).
    """
    param_type: str = Field(..., description="Type of the parameter being queried (e.g., 'KEYWORD', 'URL').")
    param_value: str = Field(..., description="Value of the parameter (e.g., the specific keyword or URL).")
    last_ingested_at: Optional[datetime] = Field(None, description="Timestamp of the most recent completed ingestion event related to this parameter (UTC).")
    ingestion_type: Optional[str] = Field(None, description="Type of the last ingestion event (e.g., 'KEYWORD_SEARCH', 'DIRECT_URL', 'GITHUB_TRENDING').")


# --- Discovery Algorithm Responses ---
DiscoveryExecutionResponse = List[str]
"""
Type alias for the response of a discovery algorithm execution.
Currently expected to be a list of strings (e.g., URLs or identifiers found).
"""

class SoftwareDependencyResponse(BaseResponse):
    """
    Represents a detected software dependency within a repository's source files.
    """
    id: int = Field(..., description="Internal database ID for this dependency record.")
    repository_id: int = Field(..., description="Internal database ID of the repository containing this dependency.")
    dependency_name: str = Field(..., description="Name of the dependency package or library.")
    version_constraint: Optional[str] = Field(None, description="Version constraint specified for the dependency (e.g., '>=1.0', '^2.1.3').")
    source_file: str = Field(..., description="Path to the file where this dependency was declared (e.g., 'requirements.txt', 'package.json').")
    dependency_type: str = Field(..., description="Type or ecosystem of the dependency (e.g., 'pip', 'npm', 'maven').")
    is_dev_dependency: Optional[bool] = Field(None, description="Indicates if this is classified as a development dependency (vs. runtime).")
    # Timestamps inherited from BaseResponse (created_at, updated_at)
    model_config = ConfigDict(from_attributes=True)