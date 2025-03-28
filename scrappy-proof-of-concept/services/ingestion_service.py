# services/ingestion_service.py
import time
import logging
from services.github_ingestion import ingest_github_repository
from services.openalex_ingestion import ingest_openalex_data
from utils.repo_finder import search_repositories_by_date_ranges
from db.database import get_db_session
from models.models import Repository, DiscoveryEvent
from services.discovery import start_new_chain

logger = logging.getLogger(__name__)

def get_ingestion_counts():
    from models.models import Repository, OpenAlexWork, User, Organization, DOI
    with get_db_session() as session:
        counts = {
            "repositories": session.query(Repository).count(),
            "works": session.query(OpenAlexWork).count(),
            "people": session.query(User).count(),
            "organizations": session.query(Organization).count(),
            "dois": session.query(DOI).count()
        }
    return counts

def print_ingestion_summary(pre_counts=None, post_counts=None):
    total_counts = post_counts if post_counts is not None else get_ingestion_counts()
    summary = "\nIngestion Summary:\n"
    summary += f"Total repositories in database: {total_counts['repositories']}\n"
    summary += f"Total works in database: {total_counts['works']}\n"
    summary += f"Total people in database: {total_counts['people']}\n"
    summary += f"Total organizations in database: {total_counts['organizations']}\n"
    summary += f"Total DOIs in database: {total_counts['dois']}\n"

    if pre_counts is not None:
        run_repos = total_counts['repositories'] - pre_counts['repositories']
        run_works = total_counts['works'] - pre_counts['works']
        run_people = total_counts['people'] - pre_counts['people']
        run_orgs = total_counts['organizations'] - pre_counts['organizations']
        run_dois = total_counts['dois'] - pre_counts['dois']
        summary += "\nAdded during most recent run:\n"
        summary += f"Repositories added: {run_repos}\n"
        summary += f"Works added: {run_works}\n"
        summary += f"People added: {run_people}\n"
        summary += f"Organizations added: {run_orgs}\n"
        summary += f"DOIs added: {run_dois}\n"
    return summary

def check_repository_exists(owner, repo_name):
    """
    Check if a repository with the given owner and name exists in the database.
    Returns the Repository object if found, None otherwise.
    """
    with get_db_session() as session:
        full_name = f"{owner}/{repo_name}"
        repo = session.query(Repository).filter_by(full_name=full_name).first()
        return repo

def get_discovery_events(repo_id):
    """
    Get discovery events for a repository.
    Returns a list of DiscoveryEvent objects.
    """
    with get_db_session() as session:
        events = session.query(DiscoveryEvent).filter(
            DiscoveryEvent.object_type == 'Repository',
            DiscoveryEvent.object_id == str(repo_id)
        ).order_by(DiscoveryEvent.timestamp).all()
        return events

def get_repository_doi_counts(repo_id):
    """
    Get counts of DOIs for a repository.
    """
    with get_db_session() as session:
        repo = session.query(Repository).filter_by(id=repo_id).first()
        if not repo:
            return 0
        return len(repo.dois)

def ingest_repository(owner: str, repo_name: str, token: str = None,
                      discovery_method: str = "direct_ingestion",
                      discovery_details: str = None, trigger_input: str = None):
    """
    Ingest a repository by delegating GitHub ingestion to the dedicated module and then
    processing OpenAlex data.
    This function manages a single DB session to ensure repository and related DOIs remain bound.
    """
    # Generate a chain ID for this ingestion session
    chain_id = start_new_chain()
    
    with get_db_session() as session:
        repository, base_branch_id = ingest_github_repository(
            session=session,
            owner=owner,
            repo_name=repo_name,
            token=token,
            discovery_method=discovery_method,
            discovery_details=discovery_details,
            trigger_input=trigger_input,
            chain_id=chain_id
        )

        ingest_openalex_data(
            session=session,
            repository=repository,
            discovery_method=discovery_method,
            discovery_details=discovery_details,
            trigger_input=trigger_input,
            chain_id=chain_id,
            branch_id=base_branch_id,
            keyword=None if discovery_method != "keyword_ingestion" else trigger_input
        )
    
    logging.info(f"Repository {repository.full_name} ingested successfully.")
    return repository

def search_and_ingest_repositories(token: str, keywords: str, trigger_input: str = None):
    from clients.github_client import GitHubClient
    
    client = GitHubClient(token=token, default_timeout=30)
    repositories_data = search_repositories_by_date_ranges(client, keywords)
    ingested = []
    
    # Create a single chain ID for this search session
    chain_id = start_new_chain()

    for repo_data in repositories_data:
        owner = repo_data["owner"]["login"]
        repo_name = repo_data["name"]
        detailed_discovery = f"Repository discovered via keyword search '{keywords}'"

        try:
            with get_db_session() as session:
                repository, base_branch_id = ingest_github_repository(
                    session=session,
                    owner=owner,
                    repo_name=repo_name,
                    token=token,
                    discovery_method="keyword_ingestion",
                    discovery_details=detailed_discovery,
                    trigger_input=trigger_input,
                    chain_id=chain_id,
                    keyword=keywords
                )

                ingest_openalex_data(
                    session=session,
                    repository=repository,
                    discovery_method="keyword_ingestion",
                    discovery_details=detailed_discovery,
                    trigger_input=trigger_input,
                    chain_id=chain_id,
                    branch_id=base_branch_id,
                    keyword=keywords
                )
                
            ingested.append(repository)
        except Exception as e:
            logging.error(f"Error ingesting {owner}/{repo_name}: {e}")

        time.sleep(1)

    return ingested