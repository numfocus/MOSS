"""
backend.api.v1.endpoints.retrieval
----------------------------------
Defines API endpoints for retrieving detailed information about specific
data entities (Repositories, Works, People, etc.) by their unique
database identifiers.
"""

import logging
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, select
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

# Internal dependencies for database access, schemas, repositories, and models
from backend.api.deps import get_db_session
from backend.schemas.responses import (
    RepositoryResponse, OwnerResponse, ContributorResponse, WorkResponse,
    PersonResponse, InstitutionResponse,
    TopicSummary, SubfieldSummary, FieldSummary, DomainSummary, PrimaryTopicResponse
)
from backend.data.repositories import (
    RepositoryRepository, OwnerRepository, ContributorRepository, WorkRepository,
    PersonRepository, InstitutionRepository
)
from backend.data.models import (
    Work, WorkTopic, Topic, Subfield, Field, Domain,
    Person, Institution, Contributor, Repository
)

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for retrieval endpoints
router = APIRouter()


# --- Helper Functions ---
# These functions provide a standard way to fetch an entity by ID
# or raise an HTTP 404 Not Found error if it doesn't exist.

def _get_repository_or_404(db: Session, repo_id: int) -> Repository:
    """Fetches a Repository by ID or raises HTTP 404."""
    repo_repo = RepositoryRepository(db=db)
    repository = repo_repo.get(id=repo_id)
    if not repository:
        logger.warning(f"Repository with id {repo_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id {repo_id} not found",
        )
    return repository

def _get_work_or_404(db: Session, work_id: int) -> Work:
    """Fetches a Work by ID or raises HTTP 404."""
    # Note: This specific helper might not be used by the main get_work below
    # due to its custom loading logic, but retained for potential other uses.
    work_repo = WorkRepository(db=db)
    work = work_repo.get(id=work_id)
    if not work:
        logger.warning(f"Work with id {work_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work with id {work_id} not found",
        )
    return work

def _get_institution_or_404(db: Session, institution_id: int) -> Institution:
    """Fetches an Institution by ID or raises HTTP 404."""
    inst_repo = InstitutionRepository(db=db)
    institution = inst_repo.get(id=institution_id)
    if not institution:
        logger.warning(f"Institution with id {institution_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution with id {institution_id} not found",
        )
    return institution

def _get_person_or_404(db: Session, person_id: int) -> Person:
    """Fetches a Person by ID or raises HTTP 404."""
    person_repo = PersonRepository(db=db)
    person = person_repo.get(id=person_id)
    if not person:
        logger.warning(f"Person with id {person_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {person_id} not found",
        )
    return person

def _get_contributor_or_404(db: Session, contributor_id: int) -> Contributor:
    """Fetches a Contributor by ID or raises HTTP 404."""
    contrib_repo = ContributorRepository(db=db)
    contributor = contrib_repo.get(id=contributor_id)
    if not contributor:
        logger.warning(f"Contributor with id {contributor_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contributor with id {contributor_id} not found",
        )
    return contributor
# --- End Helper Functions ---


# --- Entity Retrieval Endpoints ---

@router.get(
    "/repositories/{id}",
    response_model=RepositoryResponse, # Use the detailed response model
    summary="Get Repository by ID"
)
def get_repository(
    id: int,
    db: Session = Depends(get_db_session)
):
    """
    Retrieves detailed information for a specific repository using its
    internal database ID.

    Args:
        id (int): The database ID of the repository.
        db (Session): The SQLAlchemy database session.

    Returns:
        RepositoryResponse: Detailed information about the repository.

    Raises:
        HTTPException: 404 Not Found if the repository ID does not exist.
    """
    logger.debug(f"Retrieving repository with id: {id}")
    # Use the helper to fetch or raise 404
    repository = _get_repository_or_404(db, id)
    # FastAPI automatically maps the SQLAlchemy model to the Pydantic response model
    return repository

@router.get(
    "/owners/{id}",
    response_model=OwnerResponse,
    summary="Get Owner by ID"
)
def get_owner(
    id: int,
    db: Session = Depends(get_db_session)
):
    """
    Retrieves detailed information for a specific repository owner (User or Organization)
    using its internal database ID.

    Args:
        id (int): The database ID of the owner.
        db (Session): The SQLAlchemy database session.

    Returns:
        OwnerResponse: Detailed information about the owner.

    Raises:
        HTTPException: 404 Not Found if the owner ID does not exist.
    """
    logger.debug(f"Retrieving owner with id: {id}")
    owner_repo = OwnerRepository(db=db)
    owner = owner_repo.get(id=id)
    if not owner:
        logger.warning(f"Owner with id {id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Owner with id {id} not found",
        )
    return owner

@router.get(
    "/contributors/{id}",
    response_model=ContributorResponse,
    summary="Get Contributor by ID"
)
def get_contributor(
    id: int,
    db: Session = Depends(get_db_session)
):
    """
    Retrieves detailed information for a specific contributor (GitHub user linked
    to a repository) using its internal database ID.

    Args:
        id (int): The database ID of the contributor record.
        db (Session): The SQLAlchemy database session.

    Returns:
        ContributorResponse: Detailed information about the contributor.

    Raises:
        HTTPException: 404 Not Found if the contributor ID does not exist.
    """
    logger.debug(f"Retrieving contributor with id: {id}")
    # Use the helper to fetch or raise 404
    contributor = _get_contributor_or_404(db, id)
    return contributor

# --- FINAL REVISED /works/{id} ENDPOINT ---
@router.get(
    "/works/{id}",
    response_model=WorkResponse, # Use the detailed Work response model
    summary="Get Work by ID"
)
def get_work(
    id: int,
    db: Session = Depends(get_db_session)
) -> WorkResponse: # Explicitly type hint the return as the Pydantic model for clarity
    """
    Retrieves detailed information for a specific scholarly work by its internal
    database ID. This includes the work's metadata, its primary topic (with its
    full hierarchy: subfield, field, domain), and a summary list of all associated topics.

    Args:
        id (int): The database ID of the work.
        db (Session): The SQLAlchemy database session.

    Returns:
        WorkResponse: Detailed information about the work, including topics.

    Raises:
        HTTPException:
            - 404 Not Found: If the work ID does not exist.
            - 500 Internal Server Error: If fetching or processing related topic data fails.
    """
    logger.debug(f"Retrieving work with id: {id}")

    # Step 1: Fetch the core Work object using its repository
    work_repo = WorkRepository(db=db)
    work = work_repo.get(id=id)

    # Handle work not found
    if not work:
        logger.warning(f"Work with id {id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work with id {id} not found",
        )

    # Step 2: Initialize structures to hold topic information
    primary_topic_response: Optional[PrimaryTopicResponse] = None
    topic_summaries: List[TopicSummary] = []
    processed_topic_ids: set[int] = set() # Track processed topics to avoid duplicates if needed

    try:
        # Step 2a: Query for all WorkTopic associations for this work.
        # Eagerly load the related Topic and its full hierarchy (Subfield, Field, Domain)
        # using joinedload/selectinload for efficiency.
        work_topic_query = (
            db.query(WorkTopic)
            .options(
                # Load the Topic related to the association
                joinedload(WorkTopic.topic)
                # From the Topic, load its Subfield
                .selectinload(Topic.subfield)
                # From the Subfield, load its Field
                .selectinload(Subfield.field)
                # From the Field, load its Domain
                .selectinload(Field.domain)
            )
            # Filter for the specific work ID
            .filter(WorkTopic.work_id == id)
        )
        work_topic_associations = work_topic_query.all() # Execute the query

        # Step 3: Process the fetched associations to build the response structure
        for wt in work_topic_associations:
            topic = wt.topic # The actual Topic object
            # Ensure the topic exists and hasn't been processed already
            if topic and topic.id not in processed_topic_ids:
                processed_topic_ids.add(topic.id)
                try:
                    # Create a basic summary for every associated topic.
                    # Use Pydantic's model_validate to create the summary object
                    # from the SQLAlchemy Topic model, ensuring schema compliance.
                    topic_summary = TopicSummary.model_validate(topic)
                    topic_summaries.append(topic_summary)

                    # If this association marks the topic as primary, build the detailed
                    # primary topic response including its hierarchy.
                    if wt.is_primary:
                        # Initialize hierarchy summaries
                        subfield_summary: Optional[SubfieldSummary] = None
                        field_summary: Optional[FieldSummary] = None
                        domain_summary: Optional[DomainSummary] = None

                        # Build summaries for each level of the hierarchy if they exist
                        if topic.subfield:
                            # Validate each level against its Pydantic summary model
                            subfield_summary = SubfieldSummary.model_validate(topic.subfield)
                            if topic.subfield.field:
                                field_summary = FieldSummary.model_validate(topic.subfield.field)
                                if topic.subfield.field.domain:
                                    domain_summary = DomainSummary.model_validate(topic.subfield.field.domain)

                        # Construct the PrimaryTopicResponse using the validated topic summary
                        # and the hierarchy summaries. Include the score from the association.
                        primary_topic_response = PrimaryTopicResponse(
                            id=topic_summary.id,                # From validated summary
                            openalex_id=topic_summary.openalex_id, # From validated summary
                            display_name=topic_summary.display_name, # From validated summary
                            created_at=topic_summary.created_at, # From validated summary
                            updated_at=topic_summary.updated_at, # From validated summary
                            score=wt.score,                     # Score from the WorkTopic link
                            subfield=subfield_summary,          # Populated if exists
                            field=field_summary,                # Populated if exists
                            domain=domain_summary               # Populated if exists
                        )
                except Exception as e:
                    # Log errors during processing/validation of a single topic, but continue
                    logger.error(f"Error processing/validating topic {getattr(topic, 'id', 'N/A')} for work {id}: {e}", exc_info=True)
                    # Decide whether to raise, skip, or partially include data based on requirements

    except Exception as e:
        # Catch broader errors during the database query for topics
        logger.exception(f"Database error fetching topic data for work {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve associated topic data for the work."
        )

    # Step 4: Manually construct the dictionary for the final WorkResponse.
    # This provides explicit control over the fields included, ensuring alignment
    # with the WorkResponse Pydantic model.
    work_data_for_validation = {
        "id": work.id,
        "created_at": work.created_at,
        "updated_at": work.updated_at,
        "openalex_id": work.openalex_id,
        "doi": work.doi,
        "title": work.title,
        "publication_year": work.publication_year,
        "type": work.type,
        "cited_by_count": work.cited_by_count,
        "host_venue_display_name": work.host_venue_display_name,
        "openalex_url": work.openalex_url,
        # Add the processed topic data
        "primary_topic": primary_topic_response, # Populated if a primary topic was found
        "topics": topic_summaries if topic_summaries else None # List of all topic summaries, or None if empty
    }


    # Step 5: Validate the constructed dictionary against the WorkResponse Pydantic model.
    # This ensures the final structure matches the defined schema before returning.
    try:
        response_obj = WorkResponse.model_validate(work_data_for_validation)
        # Return the validated Pydantic model instance
        return response_obj
    except Exception as e:
        # Catch validation errors if the manually constructed dict doesn't match the schema
        logger.exception(f"Error validating final WorkResponse data for work {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to format the final work data into the expected response structure."
        )
# --- END FINAL REVISED ENDPOINT ---


@router.get(
    "/persons/{id}",
    response_model=PersonResponse,
    summary="Get Person by ID"
)
def get_person(
    id: int,
    db: Session = Depends(get_db_session)
):
    """
    Retrieves detailed information for a specific person (author/researcher)
    using their internal database ID.

    Args:
        id (int): The database ID of the person.
        db (Session): The SQLAlchemy database session.

    Returns:
        PersonResponse: Detailed information about the person.

    Raises:
        HTTPException: 404 Not Found if the person ID does not exist.
    """
    logger.debug(f"Retrieving person with id: {id}")
    # Use the helper to fetch or raise 404
    person = _get_person_or_404(db, id)
    return person

@router.get(
    "/institutions/{id}",
    response_model=InstitutionResponse,
    summary="Get Institution by ID"
)
def get_institution(
    id: int,
    db: Session = Depends(get_db_session)
):
    """
    Retrieves detailed information for a specific institution using its
    internal database ID.

    Args:
        id (int): The database ID of the institution.
        db (Session): The SQLAlchemy database session.

    Returns:
        InstitutionResponse: Detailed information about the institution.

    Raises:
        HTTPException: 404 Not Found if the institution ID does not exist.
    """
    logger.debug(f"Retrieving institution with id: {id}")
    # Use the helper to fetch or raise 404
    institution = _get_institution_or_404(db, id)
    return institution