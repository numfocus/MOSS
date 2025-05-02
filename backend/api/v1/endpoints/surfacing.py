"""
backend.api.v1.endpoints.surfacing
----------------------------------
Defines API endpoints designed to "surface" relationships and connections
between different data entities within the system. For example, finding all
repositories linked to a specific work, or all works citing another work.
Relies heavily on the `SurfacingService` for the underlying logic.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

# Internal dependencies for database access, schemas, services, repositories, and models
from backend.api.deps import get_db_session
# Import required Pydantic response schemas for surfacing results
from backend.schemas.responses import (
    WorkSummary, RepositorySummary, RepositoryCitationCountResponse,
    PersonSummary, InstitutionSummary,
    AffiliationResultResponse,
    ContributorResponse, # Used for shared contributor details
    SoftwareDependencyResponse # Used for repository dependencies
)
# Service layer containing the business logic for surfacing relationships
from backend.services.surfacing_service import SurfacingService
# Repositories are primarily used by helper functions for 404 checks
from backend.data.repositories import (
     RepositoryRepository, WorkRepository, InstitutionRepository, PersonRepository,
     ContributorRepository # Needed for _get_contributor_or_404
)
# Models needed for helper function type hints and potentially by the service
from backend.data.models import Repository, Work, Institution, Person, Contributor, SoftwareDependency # Ensure Contributor is imported

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for surfacing endpoints
router = APIRouter()

# --- Helper Functions (for 404 checks) ---
# These ensure that the primary entity ID provided in the path exists before
# attempting to find related entities.

def _get_repository_or_404(db: Session, repo_id: int) -> Repository:
    """Fetches a Repository by ID or raises HTTP 404."""
    repo_repo = RepositoryRepository(db=db)
    repository = repo_repo.get(id=repo_id)
    if not repository:
        logger.warning(f"Repository with id {repo_id} not found for surfacing operation.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id {repo_id} not found",
        )
    return repository

def _get_work_or_404(db: Session, work_id: int) -> Work:
    """Fetches a Work by ID or raises HTTP 404."""
    work_repo = WorkRepository(db=db)
    work = work_repo.get(id=work_id)
    if not work:
        logger.warning(f"Work with id {work_id} not found for surfacing operation.")
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
        logger.warning(f"Institution with id {institution_id} not found for surfacing operation.")
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
        logger.warning(f"Person with id {person_id} not found for surfacing operation.")
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
        logger.warning(f"Contributor with id {contributor_id} not found for surfacing operation.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contributor with id {contributor_id} not found",
        )
    return contributor
# --- End Helper Functions ---


# --- Surfacing Endpoints ---

@router.get(
    "/repositories/{repo_id}/works",
    response_model=List[WorkSummary], # Returns summaries of related works
    summary="Get Works associated with a Repository"
)
def get_repository_works(
    repo_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject SurfacingService dependency
):
    """
    Retrieves a list of scholarly works (summaries) that have been linked
    to the specified repository ID.

    Args:
        repo_id (int): The database ID of the repository.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[WorkSummary]: A list of work summaries associated with the repository.

    Raises:
        HTTPException: 404 if the repository ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get works for repository ID {repo_id}")
    _get_repository_or_404(db, repo_id) # Ensure repository exists
    try:
        # Delegate the core logic to the surfacing service
        works = service.get_works_for_repository(db=db, repository_id=repo_id)
        # FastAPI handles mapping the Work models returned by the service to WorkSummary
        return works
    except Exception as e:
        logger.exception(f"Error retrieving works for repository {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve associated works."
        )

@router.get(
    "/works/{work_id}/repositories",
    response_model=List[RepositorySummary], # Returns summaries of related repositories
    summary="Get Repositories associated with a Work"
)
def get_work_repositories(
    work_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of repositories (summaries) that have been linked
    to the specified scholarly work ID.

    Args:
        work_id (int): The database ID of the work.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[RepositorySummary]: A list of repository summaries associated with the work.

    Raises:
        HTTPException: 404 if the work ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get repositories for work ID {work_id}")
    _get_work_or_404(db, work_id) # Ensure work exists
    try:
        repositories = service.get_repositories_for_work(db=db, work_id=work_id)
        return repositories
    except Exception as e:
        logger.exception(f"Error retrieving repositories for work {work_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve associated repositories."
        )

@router.get(
    "/works/{work_id}/citations",
    response_model=List[WorkSummary], # Returns summaries of citing works
    summary="Get Works citing a specific Work"
)
def get_work_citations(
    work_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of scholarly works (summaries) that cite the specified work ID.
    This relies on citation links discovered (e.g., from OpenAlex).

    Args:
        work_id (int): The database ID of the cited work.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[WorkSummary]: A list of work summaries that cite the given work.

    Raises:
        HTTPException: 404 if the work ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get citations for work ID {work_id}")
    _get_work_or_404(db, work_id) # Ensure the cited work exists
    try:
        # Service method likely looks up citing works based on stored relationships
        citing_works = service.get_works_cited_by(db=db, work_id=work_id)
        return citing_works
    except Exception as e:
        logger.exception(f"Error retrieving citations for work {work_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve citing works."
        )

@router.get(
    "/works/{work_id}/references",
    response_model=List[WorkSummary], # Returns summaries of referenced works
    summary="Get Works referenced by a specific Work"
)
def get_work_references(
    work_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of scholarly works (summaries) that are referenced by
    (cited by) the specified work ID.

    Args:
        work_id (int): The database ID of the citing work.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[WorkSummary]: A list of work summaries referenced by the given work.

    Raises:
        HTTPException: 404 if the work ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get references for work ID {work_id}")
    _get_work_or_404(db, work_id) # Ensure the citing work exists
    try:
        # Service method likely looks up referenced works based on stored relationships
        referenced_works = service.get_works_citing(db=db, work_id=work_id) # Note: Service method name might seem reversed but implies "works that this work cites"
        return referenced_works
    except Exception as e:
        logger.exception(f"Error retrieving references for work {work_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve referenced works."
        )

@router.get(
    "/repositories/{repo_id}/citation_count",
    response_model=RepositoryCitationCountResponse,
    summary="Get Aggregated and Discovered Citation Counts for a Repository",
    description=(
        "Retrieves citation metrics for a repository: "
        "1. `aggregated_citation_count`: Sum of 'cited_by_count' from OpenAlex for all works linked to the repository. "
        "2. `discovered_citation_count`: Count of unique citing works found within the MOSS database itself that cite any work linked to the repository."
    )
)
def get_repository_citation_counts(
    repo_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Calculates and retrieves citation counts for a given repository. This includes
    an aggregated count based on linked works' external citation metrics (like OpenAlex)
    and a count based on citations discovered *within* the application's data.

    Args:
        repo_id (int): The database ID of the repository.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        RepositoryCitationCountResponse: An object containing the aggregated and
                                         discovered citation counts.

    Raises:
        HTTPException: 404 if the repository ID is not found.
                       500 if an error occurs during calculation.
    """
    logger.info(f"Request received: Get citation counts for repository ID {repo_id}")
    _get_repository_or_404(db, repo_id) # Ensure repository exists
    try:
        citation_counts_dict = service.get_repository_aggregated_citations(db=db, repository_id=repo_id)
        # The service returns a dictionary suitable for the response model
        return citation_counts_dict
    except Exception as e:
        logger.exception(f"Error calculating citation counts for repo {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate citation counts."
        )

@router.get(
    "/repositories/{repo_id}/shared_contributors",
    response_model=List[RepositorySummary], # Returns summaries of related repositories
    summary="Get Repositories sharing Contributors"
)
def get_shared_contributors_repositories(
    repo_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of other repositories (summaries) that share at least one
    contributor with the specified repository ID.

    Args:
        repo_id (int): The database ID of the source repository.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[RepositorySummary]: A list of repository summaries sharing contributors.
                                 Excludes the source repository itself.

    Raises:
        HTTPException: 404 if the repository ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get repositories sharing contributors with repo ID {repo_id}")
    _get_repository_or_404(db, repo_id) # Ensure source repository exists
    try:
        shared_repos = service.get_repositories_sharing_contributors(db=db, repository_id=repo_id)
        return shared_repos
    except Exception as e:
        logger.exception(f"Error finding repositories sharing contributors with repo {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find repositories sharing contributors."
        )

@router.get(
    "/repositories/{repo_id_1}/shared_contributors_with/{repo_id_2}",
    response_model=List[ContributorResponse], # Returns detailed contributor info
    summary="Get Specific Contributors Shared Between Two Repositories",
    tags=["Surfacing", "Contributors"] # Add relevant tags for API documentation
)
def get_shared_contributor_details_between_repos(
    repo_id_1: int,
    repo_id_2: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves the detailed information for contributors who are associated with
    *both* of the specified repository IDs.

    Args:
        repo_id_1 (int): The database ID of the first repository.
        repo_id_2 (int): The database ID of the second repository.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[ContributorResponse]: A list of contributor details for shared contributors.

    Raises:
        HTTPException: 400 if repo_id_1 and repo_id_2 are the same.
                       404 if either repository ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get shared contributor details between repo {repo_id_1} and {repo_id_2}")
    # Check for self-comparison
    if repo_id_1 == repo_id_2:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare a repository with itself for shared contributors.",
        )
    # Ensure both repositories exist
    _get_repository_or_404(db, repo_id_1)
    _get_repository_or_404(db, repo_id_2)
    try:
        # Delegate to the service to find the intersection of contributors
        shared_contributors = service.get_shared_contributors_details(
            db=db, repo_id_1=repo_id_1, repo_id_2=repo_id_2
        )
        # FastAPI maps the Contributor models to ContributorResponse
        return shared_contributors
    except Exception as e:
        logger.exception(f"Error getting shared contributors between {repo_id_1} and {repo_id_2}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shared contributor details."
        )

@router.get(
    "/repositories/{repo_id}/shared_works",
    response_model=List[RepositorySummary], # Returns summaries of related repositories
    summary="Get Repositories sharing linked Works"
)
def get_shared_works_repositories(
    repo_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of other repositories (summaries) that share at least one
    linked scholarly work with the specified repository ID.

    Args:
        repo_id (int): The database ID of the source repository.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[RepositorySummary]: A list of repository summaries sharing linked works.
                                 Excludes the source repository itself.

    Raises:
        HTTPException: 404 if the repository ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get repositories sharing works with repo ID {repo_id}")
    _get_repository_or_404(db, repo_id) # Ensure source repository exists
    try:
        shared_repos = service.get_repositories_sharing_works(db=db, repository_id=repo_id)
        return shared_repos
    except Exception as e:
        logger.exception(f"Error finding repositories sharing works with repo {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find repositories sharing linked works."
        )

@router.get(
    "/works/{work_id}/citing_people",
    response_model=List[PersonSummary], # Returns summaries of people
    summary="Get People who authored works citing this Work"
)
def get_work_citing_people(
    work_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of people (summaries) who are authors of scholarly works
    that cite the specified work ID.

    Args:
        work_id (int): The database ID of the cited work.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[PersonSummary]: A list of person summaries who authored citing works.

    Raises:
        HTTPException: 404 if the work ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get people citing work ID {work_id}")
    _get_work_or_404(db, work_id) # Ensure the cited work exists
    try:
        people = service.get_people_citing_work(db=db, work_id=work_id)
        return people
    except Exception as e:
        logger.exception(f"Error finding people citing work {work_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find people associated with citing works."
        )

@router.get(
    "/works/{work_id}/citing_institutions",
    response_model=List[InstitutionSummary], # Returns summaries of institutions
    summary="Get Institutions affiliated with authors citing this Work"
)
def get_work_citing_institutions(
    work_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of institutions (summaries) that are affiliated with authors
    of scholarly works citing the specified work ID.

    Args:
        work_id (int): The database ID of the cited work.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[InstitutionSummary]: A list of institution summaries linked via citing authors.

    Raises:
        HTTPException: 404 if the work ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get institutions citing work ID {work_id}")
    _get_work_or_404(db, work_id) # Ensure the cited work exists
    try:
        institutions = service.get_institutions_citing_work(db=db, work_id=work_id)
        return institutions
    except Exception as e:
        logger.exception(f"Error finding institutions citing work {work_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find institutions associated with citing works."
        )

@router.get(
    "/institutions/{institution_id}/repositories",
    response_model=List[RepositorySummary], # Returns summaries of repositories
    summary="Get Repositories linked to an Institution"
)
def get_institution_repositories(
    institution_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of repositories (summaries) that have been linked to the
    specified institution ID, typically via affiliation algorithms or contributor links.

    Args:
        institution_id (int): The database ID of the institution.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[RepositorySummary]: A list of repository summaries linked to the institution.

    Raises:
        HTTPException: 404 if the institution ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get repositories for institution ID {institution_id}")
    _get_institution_or_404(db, institution_id) # Ensure institution exists
    try:
        repositories = service.get_repositories_by_institution(db=db, institution_id=institution_id)
        return repositories
    except Exception as e:
        logger.exception(f"Error finding repositories for institution {institution_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find linked repositories for the institution."
        )

@router.get(
    "/persons/{person_id}/works",
    response_model=List[WorkSummary], # Returns summaries of works
    summary="Get Works associated with a Person"
)
def get_person_works(
    person_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of scholarly works (summaries) authored by or associated
    with the specified person ID.

    Args:
        person_id (int): The database ID of the person.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[WorkSummary]: A list of work summaries associated with the person.

    Raises:
        HTTPException: 404 if the person ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get works for person ID {person_id}")
    _get_person_or_404(db, person_id) # Ensure person exists
    try:
        works = service.get_works_by_person(db=db, person_id=person_id)
        return works
    except Exception as e:
        logger.exception(f"Error finding works for person {person_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find works associated with the person."
        )

@router.get(
    "/contributors/{contributor_id}/repositories",
    response_model=List[RepositorySummary], # Returns summaries of repositories
    summary="Get Repositories associated with a Contributor",
    tags=["Surfacing", "Contributors"]
)
def get_contributor_repositories(
    contributor_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of repositories (summaries) that the specified contributor
    (identified by the contributor link ID) has contributed to.

    Args:
        contributor_id (int): The database ID of the contributor link record.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[RepositorySummary]: A list of repository summaries linked to the contributor.

    Raises:
        HTTPException: 404 if the contributor ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get repositories for contributor ID {contributor_id}")
    _get_contributor_or_404(db, contributor_id) # Ensure contributor link exists
    try:
        repositories = service.get_repositories_by_contributor(db=db, contributor_id=contributor_id)
        # FastAPI handles mapping Repository models to RepositorySummary
        return repositories
    except Exception as e:
        logger.exception(f"Error finding repositories for contributor {contributor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find repositories associated with the contributor."
        )


# --- Endpoints related to Affiliations ---

@router.get(
    "/repositories/{repo_id}/affiliations",
    response_model=List[AffiliationResultResponse],
    summary="Get Affiliations for a Repository"
)
def get_repository_affiliations(
    repo_id: int,
    min_confidence: Optional[float] = Query(0.0, ge=0.0, le=1.0, description="Optional minimum confidence score [0.0, 1.0] to filter results."),
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of repository-institution affiliations calculated for the
    specified repository ID. Results can be filtered by a minimum confidence score.

    Args:
        repo_id (int): The database ID of the repository.
        min_confidence (Optional[float]): Minimum confidence score threshold.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[AffiliationResultResponse]: A list of affiliation results meeting the
                                         confidence threshold.

    Raises:
        HTTPException: 404 if the repository ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get affiliations for repository ID {repo_id} (min_conf: {min_confidence})")
    _get_repository_or_404(db, repo_id) # Ensure repository exists
    try:
        affiliations = service.get_affiliations_for_repository(
            db=db, repository_id=repo_id, min_confidence=min_confidence or 0.0 # Use 0.0 if None
        )
        return affiliations
    except Exception as e:
        logger.exception(f"Error getting affiliations for repository {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve repository affiliations."
        )

@router.get(
    "/institutions/{inst_id}/affiliations",
    response_model=List[AffiliationResultResponse],
    summary="Get Affiliations for an Institution (Filtered)"
)
def get_institution_affiliations_filtered(
    inst_id: int,
    min_confidence: Optional[float] = Query(0.0, ge=0.0, le=1.0, description="Optional minimum confidence score [0.0, 1.0] to filter results."),
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of repository-institution affiliations calculated for the
    specified institution ID. Results can be filtered by a minimum confidence score.

    Note: This endpoint is similar to `/institutions/{inst_id}/affiliation_results`
    but explicitly includes the filtering parameter for clarity in API documentation.

    Args:
        inst_id (int): The database ID of the institution.
        min_confidence (Optional[float]): Minimum confidence score threshold.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[AffiliationResultResponse]: A list of affiliation results meeting the
                                         confidence threshold.

    Raises:
        HTTPException: 404 if the institution ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get filtered affiliations for institution ID {inst_id} (min_conf: {min_confidence})")
    _get_institution_or_404(db, inst_id) # Ensure institution exists
    try:
        affiliations = service.get_affiliations_for_institution(
            db=db, institution_id=inst_id, min_confidence=min_confidence or 0.0 # Use 0.0 if None
        )
        return affiliations
    except Exception as e:
        logger.exception(f"Error getting filtered affiliations for institution {inst_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve filtered institution affiliations."
        )

@router.get(
    "/institutions/{inst_id}/affiliation_results",
    response_model=List[AffiliationResultResponse],
    summary="Get All Stored Affiliation Results for an Institution"
)
def get_all_institution_affiliation_results(
    inst_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves *all* stored repository-institution affiliation results associated
    with the specified institution ID, regardless of confidence score.

    Args:
        inst_id (int): The database ID of the institution.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[AffiliationResultResponse]: A list of all affiliation results for the institution.

    Raises:
        HTTPException: 404 if the institution ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get ALL affiliation results for institution ID {inst_id}")
    _get_institution_or_404(db, inst_id) # Ensure institution exists
    try:
        # Call the service method with minimum confidence set to 0 to retrieve all results
        affiliations = service.get_affiliations_for_institution(
            db=db, institution_id=inst_id, min_confidence=0.0
        )
        return affiliations
    except Exception as e:
        logger.exception(f"Error getting all affiliation results for institution {inst_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve all affiliation results for the institution."
        )

# --- Endpoint for Software Dependencies ---
@router.get(
    "/repositories/{repo_id}/dependencies",
    response_model=List[SoftwareDependencyResponse],
    summary="Get Software Dependencies for a Repository",
    tags=["Surfacing", "Dependencies"]
)
def get_repository_dependencies(
    repo_id: int,
    db: Session = Depends(get_db_session),
    service: SurfacingService = Depends() # Inject service
):
    """
    Retrieves a list of software dependencies (e.g., libraries, packages)
    discovered within the specified repository's files (like requirements.txt,
    package.json, etc.).

    Args:
        repo_id (int): The database ID of the repository.
        db (Session): The SQLAlchemy database session.
        service (SurfacingService): Injected service handling the logic.

    Returns:
        List[SoftwareDependencyResponse]: A list of dependencies found in the repository.

    Raises:
        HTTPException: 404 if the repository ID is not found.
                       500 if an error occurs during retrieval.
    """
    logger.info(f"Request received: Get dependencies for repository ID {repo_id}")
    _get_repository_or_404(db, repo_id) # Ensure repository exists
    try:
        dependencies = service.get_dependencies_for_repository(db=db, repository_id=repo_id)
        # FastAPI handles mapping SoftwareDependency models to SoftwareDependencyResponse
        return dependencies
    except Exception as e:
        logger.exception(f"Error finding dependencies for repository {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find dependencies for the repository."
        )
# --- END ADDED ENDPOINT ---