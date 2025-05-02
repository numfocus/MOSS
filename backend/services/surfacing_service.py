"""
backend.services.surfacing_service
----------------------------------
Provides methods for querying and retrieving relationships and aggregated data
from the knowledge graph constructed from repositories, scholarly works,
people, institutions, and their connections.
"""

import logging
from typing import List, Optional, Dict, Any # Add Optional, Dict, Any

from sqlalchemy.orm import Session, aliased, joinedload, contains_eager
from sqlalchemy import func, distinct, select, and_ # Add and_

# Import necessary models representing graph entities and relationships
from backend.data.models import (
    Work, Repository, WorkCitation, DOIReference, Contributor, Person, Institution,
    RepositoryContributorAssociation, Authorship, Affiliation,
    RepositoryInstitutionAffiliation, # Model for stored affiliation predictions
    SoftwareDependency # Model for dependencies
)
# Import Repositories for direct data access where needed
from backend.data.repositories import (
    DOIReferenceRepository, SoftwareDependencyRepository
)
from .base_service import BaseService

logger = logging.getLogger(__name__)

class SurfacingService(BaseService):
    """
    Service layer for retrieving connected information from the MOSS knowledge graph.

    Offers methods to query various relationships, such as:
    - Works associated with a repository.
    - Repositories associated with a work.
    - Citation relationships between works.
    - Aggregated citation counts for repositories.
    - Repositories sharing contributors or works.
    - People or institutions involved in citing specific works.
    - Repositories linked to institutions via author affiliations.
    - Works authored by a specific person.
    - Repositories linked to a specific contributor.
    - Stored repository-institution affiliation predictions.
    - Software dependencies for a repository.

    These methods typically encapsulate SQLAlchemy queries to traverse the
    relationships defined in the data models.
    """

    # --- Methods for Repository <-> Work Connections ---

    def get_works_for_repository(self, db: Session, repository_id: int) -> List[Work]:
        """
        Retrieves all unique Works directly associated with a given Repository ID
        via DOIReferences found in the repository's files.

        Args:
            db: SQLAlchemy database session.
            repository_id: The ID of the target Repository.

        Returns:
            A list of unique Work objects linked to the repository.
        """
        logger.info(f"Getting Works associated with Repository ID: {repository_id}")
        # Use DOIReferenceRepository to find links
        doi_ref_repo = DOIReferenceRepository(db)
        references = doi_ref_repo.find_by_repository(repository_id=repository_id)

        # Collect unique works from the references
        unique_work_ids = set()
        works = []
        for ref in references:
            # Ensure the reference links to a work and it hasn't been added already
            if ref.work and ref.work.id not in unique_work_ids:
                works.append(ref.work)
                unique_work_ids.add(ref.work.id)

        logger.info(f"Found {len(works)} unique Works for Repository ID: {repository_id}")
        return works


    def get_repositories_for_work(self, db: Session, work_id: int) -> List[Repository]:
        """
        Retrieves all unique Repositories where a reference to a given Work ID
        was found (via DOIReferences).

        Args:
            db: SQLAlchemy database session.
            work_id: The ID of the target Work.

        Returns:
            A list of unique Repository objects linked to the work.
        """
        logger.info(f"Getting Repositories associated with Work ID: {work_id}")
        # Use DOIReferenceRepository to find links
        doi_ref_repo = DOIReferenceRepository(db)
        references = doi_ref_repo.find_by_work_id(work_id=work_id)

        # Collect unique repositories from the references
        unique_repo_ids = set()
        repositories = []
        for ref in references:
             # Ensure the reference links to a repository and it hasn't been added already
            if ref.repository and ref.repository.id not in unique_repo_ids:
                repositories.append(ref.repository)
                unique_repo_ids.add(ref.repository.id)

        logger.info(f"Found {len(repositories)} unique Repositories for Work ID: {work_id}")
        return repositories

    # --- Methods for Work <-> Work Citation Connections ---

    def get_works_cited_by(self, db: Session, work_id: int) -> List[Work]:
        """
        Retrieves all unique Works that cite the given Work ID.
        (Finds Wc where Wc -> work_id)

        Args:
            db: SQLAlchemy database session.
            work_id: The ID of the Work that is cited.

        Returns:
            A list of unique Work objects that cite the target work.
        """
        logger.info(f"Getting Works that cite Work ID: {work_id}")
        unique_citing_work_ids = set()
        citing_works = []

        # Query the WorkCitation link table, filtering by the 'cited_work_id'
        # Eager load the 'citing_work' relationship to avoid N+1 queries if accessing citing work details later.
        citations = db.query(WorkCitation)\
                      .filter(WorkCitation.cited_work_id == work_id)\
                      .options(joinedload(WorkCitation.citing_work))\
                      .all()

        if citations:
             for citation_link in citations:
                 # Add the citing work if it exists and hasn't been added yet
                 if citation_link.citing_work and citation_link.citing_work.id not in unique_citing_work_ids:
                     citing_works.append(citation_link.citing_work)
                     unique_citing_work_ids.add(citation_link.citing_work.id)

        logger.info(f"Found {len(citing_works)} unique Works citing Work ID: {work_id}")
        return citing_works

    def get_works_citing(self, db: Session, work_id: int) -> List[Work]:
        """
        Retrieves all unique Works that are cited by the given Work ID.
        (Finds W_cited where work_id -> W_cited)

        Args:
            db: SQLAlchemy database session.
            work_id: The ID of the Work that is citing others.

        Returns:
            A list of unique Work objects cited by the target work.
        """
        logger.info(f"Getting Works cited by Work ID: {work_id}")
        unique_cited_work_ids = set()
        cited_works = []

        # Query the WorkCitation link table, filtering by the 'citing_work_id'
        # Eager load the 'cited_work' relationship.
        references = db.query(WorkCitation)\
                       .filter(WorkCitation.citing_work_id == work_id)\
                       .options(joinedload(WorkCitation.cited_work))\
                       .all()

        if references:
             for reference_link in references:
                 # Add the cited work if it exists and hasn't been added yet
                 if reference_link.cited_work and reference_link.cited_work.id not in unique_cited_work_ids:
                     cited_works.append(reference_link.cited_work)
                     unique_cited_work_ids.add(reference_link.cited_work.id)

        logger.info(f"Found {len(cited_works)} unique Works cited by Work ID: {work_id}")
        return cited_works

    # --- Methods for Aggregated Data ---

    def get_repository_aggregated_citations(self, db: Session, repository_id: int) -> Dict[str, int]:
        """
        Calculates citation counts for a repository based on its linked works.

        Provides two counts:
        1. `openalex_aggregated_citations`: Sum of `cited_by_count` from OpenAlex
           for all unique works linked to the repository.
        2. `moss_discovered_citations`: Count of unique works discovered within MOSS
           that cite any of the works linked to the repository.

        Args:
            db: SQLAlchemy database session.
            repository_id: The ID of the repository.

        Returns:
            A dictionary containing `repository_id`, `openalex_aggregated_citations`,
            and `moss_discovered_citations`. Returns counts of 0 if the repository
            is not found or has no linked works.
        """
        logger.info(f"Calculating aggregated and discovered citations for Repository ID: {repository_id}")

        # Step 1: Find all unique Work IDs linked to this repository via DOI references.
        linked_work_ids_query = (
            select(distinct(DOIReference.work_id))
            .where(DOIReference.repository_id == repository_id)
            .where(DOIReference.work_id.isnot(None)) # Exclude references not linked to a work
        )
        linked_work_ids_result = db.execute(linked_work_ids_query).scalars().all()
        linked_work_ids = set(linked_work_ids_result) # Use a set for efficient lookup

        # Handle case where repository has no linked works
        if not linked_work_ids:
            logger.info(f"No linked works found for Repository ID {repository_id}.")
            return {
                "repository_id": repository_id,
                "openalex_aggregated_citations": 0,
                "moss_discovered_citations": 0
            }

        # Step 2: Calculate OpenAlex aggregated citations.
        # Sum the 'cited_by_count' field from the Work records linked to the repository.
        openalex_citations_query = (
            select(func.sum(Work.cited_by_count)) # Sum the counts
            .where(Work.id.in_(linked_work_ids)) # Filter for linked works
        )
        openalex_citations_result = db.execute(openalex_citations_query).scalar()
        # Handle potential None result if sum is over zero rows or contains nulls
        openalex_aggregated_citations = openalex_citations_result if openalex_citations_result is not None else 0
        logger.info(f"OpenAlex Aggregated Citations for Repo {repository_id}: {openalex_aggregated_citations}")

        # Step 3: Calculate MOSS discovered citations.
        # Count distinct citing works found in the WorkCitation table where the cited work is one linked to the repository.
        moss_citations_query = (
            select(func.count(distinct(WorkCitation.citing_work_id))) # Count unique citing work IDs
            .where(WorkCitation.cited_work_id.in_(linked_work_ids)) # Where the cited work is linked to our repo
        )
        moss_citations_result = db.execute(moss_citations_query).scalar()
        moss_discovered_citations = moss_citations_result if moss_citations_result is not None else 0
        logger.info(f"MOSS Discovered Citations for Repo {repository_id}: {moss_discovered_citations}")

        return {
            "repository_id": repository_id,
            "openalex_aggregated_citations": openalex_aggregated_citations,
            "moss_discovered_citations": moss_discovered_citations
        }

    # --- Methods for Repository <-> Repository Connections ---

    def get_repositories_sharing_contributors(self, db: Session, repository_id: int) -> List[Repository]:
        """
        Finds other repositories that share at least one contributor with the target repository.

        Args:
            db: SQLAlchemy database session.
            repository_id: The ID of the target repository.

        Returns:
            A list of unique Repository objects that share contributors, excluding the target repository itself.
        """
        logger.info(f"Finding repositories sharing contributors with Repository ID: {repository_id}")

        # Step 1: Get IDs of all contributors associated with the target repository.
        target_contributor_ids = (
            select(RepositoryContributorAssociation.contributor_id)
            .where(RepositoryContributorAssociation.repository_id == repository_id)
            .subquery() # Use as a subquery for efficient filtering
        )

        # Step 2: Find distinct repositories associated with any of those contributors,
        # excluding the original target repository.
        RepoAlias = aliased(Repository) # Use alias to avoid ambiguity if joining Repository multiple times
        shared_repos_query = (
            select(RepoAlias).distinct() # Select distinct repositories
            .join(
                RepositoryContributorAssociation, # Join Repository to the association table
                RepoAlias.id == RepositoryContributorAssociation.repository_id
            )
            .where(
                # Filter for associations involving contributors from the target repo
                RepositoryContributorAssociation.contributor_id.in_(target_contributor_ids)
            )
            .where(
                RepoAlias.id != repository_id # Exclude the target repository itself
            )
        )
        results = db.execute(shared_repos_query).scalars().all()
        logger.info(f"Found {len(results)} repositories sharing contributors with Repository ID: {repository_id}")
        return list(results)

    def get_repositories_sharing_works(self, db: Session, repository_id: int) -> List[Repository]:
        """
        Finds other repositories that have references to at least one of the same Works
        as the target repository.

        Args:
            db: SQLAlchemy database session.
            repository_id: The ID of the target repository.

        Returns:
            A list of unique Repository objects that share linked works, excluding the target repository itself.
        """
        logger.info(f"Finding repositories sharing works with Repository ID: {repository_id}")

        # Step 1: Get IDs of all Works linked to the target repository via DOIReferences.
        target_work_ids = (
            select(DOIReference.work_id)
            .where(DOIReference.repository_id == repository_id)
            .where(DOIReference.work_id.isnot(None)) # Ensure the reference is linked to a work
            .subquery() # Use as a subquery
        )

        # Step 2: Find distinct repositories that also have DOIReferences pointing to any of those Works,
        # excluding the original target repository.
        RepoAlias = aliased(Repository) # Use alias
        shared_repos_query = (
            select(RepoAlias).distinct() # Select distinct repositories
            .join(
                DOIReference, # Join Repository to DOIReference table
                RepoAlias.id == DOIReference.repository_id
            )
            .where(
                # Filter for references involving works linked to the target repo
                DOIReference.work_id.in_(target_work_ids)
            )
            .where(
                RepoAlias.id != repository_id # Exclude the target repository itself
            )
        )
        results = db.execute(shared_repos_query).scalars().all()
        logger.info(f"Found {len(results)} repositories sharing works with Repository ID: {repository_id}")
        return list(results)

    # --- Methods involving Persons and Institutions ---

    def get_people_citing_work(self, db: Session, work_id: int) -> List[Person]:
        """
        Finds unique Persons who have authored any Work that cites the target Work ID.

        This traverses Work -> WorkCitation (citing) -> Authorship -> Person.

        Args:
            db: SQLAlchemy database session.
            work_id: The ID of the Work that is cited.

        Returns:
            A list of unique Person objects who authored citing works.
        """
        logger.info(f"Finding people who authored works citing Work ID: {work_id}")

        # Alias Work to distinguish the citing work from the cited work if needed, though not strictly required here
        CitingWork = aliased(Work)
        # Construct the query joining through the citation and authorship links
        people_query = (
            select(Person).distinct() # Select distinct Person objects
            .join(Authorship, Person.id == Authorship.person_id) # Person -> Authorship
            .join(CitingWork, Authorship.work_id == CitingWork.id) # Authorship -> Citing Work
            .join(WorkCitation, CitingWork.id == WorkCitation.citing_work_id) # Citing Work -> Citation Link
            .where(WorkCitation.cited_work_id == work_id) # Filter for citations of the target work
        )
        results = db.execute(people_query).scalars().all()
        logger.info(f"Found {len(results)} unique people citing Work ID: {work_id}")
        return list(results)

    def get_institutions_citing_work(self, db: Session, work_id: int) -> List[Institution]:
        """
        Finds unique Institutions affiliated with authors of Works that cite the target Work ID.

        This traverses Work -> WorkCitation (citing) -> Authorship -> Affiliation -> Institution.

        Args:
            db: SQLAlchemy database session.
            work_id: The ID of the Work that is cited.

        Returns:
            A list of unique Institution objects affiliated with authors of citing works.
        """
        logger.info(f"Finding institutions affiliated with authors citing Work ID: {work_id}")

        CitingWork = aliased(Work) # Alias for clarity
        # Construct the query joining through citations, authorships, and affiliations
        institution_query = (
            select(Institution).distinct() # Select distinct Institution objects
            # Join Institution -> Affiliation -> Authorship -> CitingWork -> WorkCitation
            .join(Affiliation, Institution.id == Affiliation.institution_id)
            # Join Affiliation to Authorship using the composite foreign key
            .join(Authorship, and_(Affiliation.authorship_work_id == Authorship.work_id,
                                   Affiliation.authorship_person_id == Authorship.person_id))
            .join(CitingWork, Authorship.work_id == CitingWork.id) # Link Authorship to the Citing Work
            .join(WorkCitation, CitingWork.id == WorkCitation.citing_work_id) # Link Citing Work via citation
            .where(WorkCitation.cited_work_id == work_id) # Filter for citations of the target work
        )
        results = db.execute(institution_query).scalars().all()
        logger.info(f"Found {len(results)} unique institutions citing Work ID: {work_id}")
        return list(results)

    def get_repositories_by_institution(self, db: Session, institution_id: int) -> List[Repository]:
        """
        Finds unique Repositories linked (via DOIReferences) to Works authored by
        people affiliated with the given Institution ID at the time of authorship.

        This traverses Institution -> Affiliation -> Authorship -> Work -> DOIReference -> Repository.

        Args:
            db: SQLAlchemy database session.
            institution_id: The ID of the target Institution.

        Returns:
            A list of unique Repository objects linked to the institution.
        """
        logger.info(f"Finding repositories associated with Institution ID: {institution_id}")
        # Construct the query joining through affiliations, authorships, works, and references
        repo_query = (
            select(Repository).distinct() # Select distinct Repository objects
            # Join Repository -> DOIReference -> Work -> Authorship -> Affiliation
            .join(DOIReference, Repository.id == DOIReference.repository_id)
            .join(Work, DOIReference.work_id == Work.id)
            .join(Authorship, Work.id == Authorship.work_id)
            # Join Authorship to Affiliation using composite key
            .join(Affiliation, and_(Authorship.work_id == Affiliation.authorship_work_id,
                                   Authorship.person_id == Affiliation.authorship_person_id))
            .where(Affiliation.institution_id == institution_id) # Filter by the target institution
        )
        results = db.execute(repo_query).scalars().all()
        logger.info(f"Found {len(results)} unique repositories linked to Institution ID: {institution_id}")
        return list(results)

    def get_works_by_person(self, db: Session, person_id: int) -> List[Work]:
        """
        Finds all unique Works authored by the given Person ID.

        Traverses Person -> Authorship -> Work.

        Args:
            db: SQLAlchemy database session.
            person_id: The ID of the target Person.

        Returns:
            A list of unique Work objects authored by the person.
        """
        logger.info(f"Finding works associated with Person ID: {person_id}")
        # Construct the query joining Work to Authorship
        work_query = (
            select(Work).distinct() # Select distinct Work objects
            .join(Authorship, Work.id == Authorship.work_id) # Join Work -> Authorship
            .where(Authorship.person_id == person_id) # Filter by the target person
        )
        results = db.execute(work_query).scalars().all()
        logger.info(f"Found {len(results)} unique works linked to Person ID: {person_id}")
        return list(results)

    # --- Methods for Stored Affiliation Predictions ---

    def get_affiliations_for_repository(
        self, db: Session, repository_id: int, min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves stored repository-institution affiliation predictions for a repository.

        Fetches records from the `RepositoryInstitutionAffiliation` table, which
        stores results from potentially complex affiliation detection algorithms.
        Optionally filters by a minimum confidence score.

        Args:
            db: SQLAlchemy database session.
            repository_id: The ID of the target repository.
            min_confidence: The minimum confidence score for affiliations to include (default 0.0).

        Returns:
            A list of dictionaries, each representing an affiliation record,
            including resolved institution and repository names.
        """
        logger.info(f"Getting affiliations for Repository ID: {repository_id} (min_confidence: {min_confidence})")
        # Query the affiliation prediction table, joining to get names
        query = (
            select(
                RepositoryInstitutionAffiliation, # Select the main affiliation model object
                Institution.display_name.label("institution_name"), # Get institution name
                Repository.full_name.label("repository_name") # Get repository name
            )
            .join(Institution, RepositoryInstitutionAffiliation.institution_id == Institution.id)
            .join(Repository, RepositoryInstitutionAffiliation.repository_id == Repository.id)
            .where(RepositoryInstitutionAffiliation.repository_id == repository_id) # Filter by repo ID
            .where(RepositoryInstitutionAffiliation.confidence_score >= min_confidence) # Filter by confidence
            .order_by(RepositoryInstitutionAffiliation.confidence_score.desc()) # Order by confidence
        )
        results = db.execute(query).all() # Fetch all matching rows

        # Format results into dictionaries for API response or further use
        affiliation_responses = []
        for row in results:
            affil_model: RepositoryInstitutionAffiliation = row.RepositoryInstitutionAffiliation
            inst_name = row.institution_name
            repo_name = row.repository_name
            affiliation_responses.append({
                "repository_id": affil_model.repository_id,
                "institution_id": affil_model.institution_id,
                "algorithm_name": affil_model.algorithm_name,
                "algorithm_version": affil_model.algorithm_version,
                "confidence_score": affil_model.confidence_score,
                "evidence": affil_model.evidence, # Raw evidence data stored by algorithm
                "parameters_used": affil_model.parameters_used, # Parameters used by algorithm run
                "calculated_at": affil_model.calculated_at,
                "repository_name": repo_name, # Included for convenience
                "institution_name": inst_name, # Included for convenience
            })
        logger.info(f"Found {len(affiliation_responses)} affiliations for Repository ID {repository_id} meeting criteria.")
        return affiliation_responses

    def get_affiliations_for_institution(
        self, db: Session, institution_id: int, min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves stored repository-institution affiliation predictions for an institution.

        Fetches records from the `RepositoryInstitutionAffiliation` table, filtering
        by the institution ID and optionally by minimum confidence score.

        Args:
            db: SQLAlchemy database session.
            institution_id: The ID of the target institution.
            min_confidence: The minimum confidence score for affiliations to include (default 0.0).

        Returns:
            A list of dictionaries, each representing an affiliation record,
            including resolved institution and repository names.
        """
        logger.info(f"Getting affiliations for Institution ID: {institution_id} (min_confidence: {min_confidence})")
         # Query the affiliation prediction table, joining to get names
        query = (
             select(
                RepositoryInstitutionAffiliation, # Select the main affiliation model object
                Repository.full_name.label("repository_name"), # Get repository name
                Institution.display_name.label("institution_name") # Get institution name (might seem redundant but good practice)
            )
            .join(Repository, RepositoryInstitutionAffiliation.repository_id == Repository.id)
            .join(Institution, RepositoryInstitutionAffiliation.institution_id == Institution.id)
            .where(RepositoryInstitutionAffiliation.institution_id == institution_id) # Filter by institution ID
            .where(RepositoryInstitutionAffiliation.confidence_score >= min_confidence) # Filter by confidence
            .order_by(RepositoryInstitutionAffiliation.confidence_score.desc()) # Order by confidence
        )
        results = db.execute(query).all() # Fetch all matching rows

        # Format results into dictionaries
        affiliation_responses = []
        for row in results:
            affil_model: RepositoryInstitutionAffiliation = row.RepositoryInstitutionAffiliation
            repo_name = row.repository_name
            inst_name = row.institution_name
            affiliation_responses.append({
                "repository_id": affil_model.repository_id,
                "institution_id": affil_model.institution_id,
                "algorithm_name": affil_model.algorithm_name,
                "algorithm_version": affil_model.algorithm_version,
                "confidence_score": affil_model.confidence_score,
                "evidence": affil_model.evidence,
                "parameters_used": affil_model.parameters_used,
                "calculated_at": affil_model.calculated_at,
                "repository_name": repo_name, # Included for convenience
                "institution_name": inst_name, # Included for convenience
            })
        logger.info(f"Found {len(affiliation_responses)} affiliations for Institution ID {institution_id} meeting criteria.")
        return affiliation_responses

    # --- Methods for Contributor Connections ---

    def get_shared_contributors_details(
        self, db: Session, repo_id_1: int, repo_id_2: int
    ) -> List[Contributor]:
        """
        Finds the specific Contributor objects shared between two given repositories.

        Args:
            db: SQLAlchemy database session.
            repo_id_1: ID of the first repository.
            repo_id_2: ID of the second repository.

        Returns:
            A list of Contributor objects associated with *both* repo_id_1 and repo_id_2.
        """
        logger.info(f"Finding shared contributor details between Repository ID {repo_id_1} and {repo_id_2}")

        # Efficiently find shared contributors using subqueries and joins
        shared_contributors_query = (
            select(Contributor) # Select the Contributor object
            # Join Contributor to the association table
            .join(RepositoryContributorAssociation, Contributor.id == RepositoryContributorAssociation.contributor_id)
            .where(
                # Filter for contributors associated with the first repository...
                RepositoryContributorAssociation.repository_id == repo_id_1,
                # ...AND whose ID exists in the set of contributors associated with the second repository.
                Contributor.id.in_(
                    select(RepositoryContributorAssociation.contributor_id) # Subquery: Get contributor IDs for repo_id_2
                    .where(RepositoryContributorAssociation.repository_id == repo_id_2)
                )
            )
            .distinct() # Ensure each shared contributor is returned only once
            .order_by(Contributor.login) # Optional: Order by login name
        )
        shared_contributors = db.execute(shared_contributors_query).scalars().all()
        logger.info(f"Retrieved details for {len(shared_contributors)} shared contributors.")
        return list(shared_contributors)


    def get_repositories_by_contributor(self, db: Session, contributor_id: int) -> List[Repository]:
        """
        Finds all repositories associated with a specific contributor ID.

        Args:
            db: SQLAlchemy database session.
            contributor_id: The ID of the contributor.

        Returns:
            A list of Repository objects the contributor is associated with.
        """
        logger.info(f"Finding repositories associated with Contributor ID: {contributor_id}")

        # Query the Repository table, joining through the association table
        repo_query = (
            select(Repository)
            .join(RepositoryContributorAssociation, Repository.id == RepositoryContributorAssociation.repository_id) # Join Repo -> Association
            .where(RepositoryContributorAssociation.contributor_id == contributor_id) # Filter by contributor ID
            .order_by(Repository.full_name) # Optional: Order results for consistency
            # Example of eager loading the owner if needed often (can impact performance):
            # .options(joinedload(Repository.owner))
        )

        repositories = db.execute(repo_query).scalars().all()
        logger.info(f"Found {len(repositories)} repositories for Contributor ID {contributor_id}.")
        return list(repositories)

    # --- Methods for Software Dependencies ---

    def get_dependencies_for_repository(self, db: Session, repository_id: int) -> List[SoftwareDependency]:
        """
        Retrieves stored software dependencies recorded for a given repository ID.

        Args:
            db: SQLAlchemy database session.
            repository_id: The ID of the target repository.

        Returns:
            A list of SoftwareDependency objects associated with the repository.
        """
        logger.info(f"Getting dependencies for Repository ID: {repository_id}")
        # Use the dedicated repository for SoftwareDependency for optimized access
        dep_repo = SoftwareDependencyRepository(db)
        dependencies = dep_repo.find_by_repository(repository_id=repository_id)
        logger.info(f"Found {len(dependencies)} dependencies for Repository ID {repository_id}.")
        return dependencies