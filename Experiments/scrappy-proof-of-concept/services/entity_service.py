# services/entity_service.py
import logging
from datetime import datetime, timezone

from utils.common import save_json_field, parse_datetime, get_current_time
from models.models import User, Organization, Repository, DOI
from services.discovery import record_discovery

logger = logging.getLogger(__name__)

def update_or_create_user(session, client, user_data, discovery_method="direct_ingestion", 
                          discovery_details=None, trigger_input=None, keyword=None, 
                          chain_id=None, branch_id=None, step=1):
    """
    Create or update a User record.
    """
    if not user_data:
        logger.warning("No user data provided; skipping user creation.")
        return None
    
    login = user_data.get('login', 'Unknown')
    if discovery_details is None:
        discovery_details = f"User '{login}' discovered during repository ingestion."
    
    logger.info(f"Updating or creating user: {login}")
    user = session.query(User).filter_by(id=user_data["id"]).first()
    detailed_data = client.get_user(login)
    
    if detailed_data:
        if user:
            user.login = detailed_data.get("login")
            user.name = detailed_data.get("name")
            user.bio = detailed_data.get("bio")
            user.avatar_url = detailed_data.get("avatar_url")
            user.html_url = detailed_data.get("html_url")
            user.type = detailed_data.get("type", "User")
            user.site_admin = detailed_data.get("site_admin", False)
            user.created_at = parse_datetime(detailed_data.get("created_at"))
            user.updated_at = parse_datetime(detailed_data.get("updated_at"))
            user.public_repos = detailed_data.get("public_repos")
            user.public_gists = detailed_data.get("public_gists")
            user.followers = detailed_data.get("followers")
            user.following = detailed_data.get("following")
            user.email = detailed_data.get("email")
            user.blog = detailed_data.get("blog")
            user.company = detailed_data.get("company")
            user.location = detailed_data.get("location")
            user.twitter_username = detailed_data.get("twitter_username")
            user.raw_data = save_json_field(detailed_data)
            user.ingested_at = get_current_time()
        else:
            user = User(
                id=detailed_data["id"],
                login=detailed_data["login"],
                name=detailed_data.get("name"),
                bio=detailed_data.get("bio"),
                avatar_url=detailed_data.get("avatar_url"),
                html_url=detailed_data.get("html_url"),
                type=detailed_data.get("type", "User"),
                site_admin=detailed_data.get("site_admin", False),
                created_at=parse_datetime(detailed_data.get("created_at")),
                updated_at=parse_datetime(detailed_data.get("updated_at")),
                public_repos=detailed_data.get("public_repos"),
                public_gists=detailed_data.get("public_gists"),
                followers=detailed_data.get("followers"),
                following=detailed_data.get("following"),
                email=detailed_data.get("email"),
                blog=detailed_data.get("blog"),
                company=detailed_data.get("company"),
                location=detailed_data.get("location"),
                twitter_username=detailed_data.get("twitter_username"),
                raw_data=save_json_field(detailed_data)
            )
            user.ingested_at = get_current_time()
            session.add(user)
        session.commit()
        record_discovery(user, discovery_method, discovery_details, 
                        trigger_input=trigger_input, keyword=keyword,
                        chain_id=chain_id, branch_id=branch_id, step=step)
        return user
    
    if not user:
        user = User(
            id=user_data["id"],
            login=user_data["login"],
            raw_data=save_json_field(user_data)
        )
        user.ingested_at = get_current_time()
        session.add(user)
        session.commit()
        record_discovery(user, discovery_method, discovery_details, 
                        trigger_input=trigger_input, keyword=keyword,
                        chain_id=chain_id, branch_id=branch_id, step=step)
    return user

def update_or_create_org(session, client, org_data, discovery_method="direct_ingestion", 
                        discovery_details="Organization discovered during repository ingestion", 
                        trigger_input=None, keyword=None, chain_id=None, branch_id=None, step=1):
    """
    Create or update an Organization record.
    """
    logger.info(f"Updating or creating organization: {org_data['login']}")
    org = session.query(Organization).filter_by(id=org_data["id"]).first()
    detailed_data = client.get_organization(org_data["login"])
    
    if detailed_data:
        if org:
            org.login = detailed_data.get("login")
            org.name = detailed_data.get("name")
            org.description = detailed_data.get("description")
            org.raw_data = save_json_field(detailed_data)
            org.ingested_at = get_current_time()
        else:
            org = Organization(
                id=detailed_data["id"],
                login=detailed_data.get("login"),
                name=detailed_data.get("name"),
                description=detailed_data.get("description"),
                raw_data=save_json_field(detailed_data)
            )
            org.ingested_at = get_current_time()
            session.add(org)
        session.commit()
        record_discovery(org, discovery_method, discovery_details, 
                        trigger_input=trigger_input, keyword=keyword,
                        chain_id=chain_id, branch_id=branch_id, step=step)
        return org
    
    if not org:
        org = Organization(
            id=org_data["id"],
            login=org_data["login"],
            raw_data=save_json_field(org_data)
        )
        org.ingested_at = get_current_time()
        session.add(org)
        session.commit()
        record_discovery(org, discovery_method, discovery_details, 
                        trigger_input=trigger_input, keyword=keyword,
                        chain_id=chain_id, branch_id=branch_id, step=step)
    return org

def update_or_create_repository(session, client, repo_data, discovery_method="direct_ingestion", 
                               discovery_details=None, trigger_input=None, keyword=None,
                               chain_id=None, branch_id=None, step=1):
    """
    Create or update a Repository record.
    """
    repo_id = repo_data["id"]
    full_name = repo_data.get('full_name')
    logger.info(f"Updating or creating repository id={repo_id}, full_name={full_name}")
    
    if discovery_details is None:
        discovery_details = f"Repository {full_name} discovered during ingestion"
        
    topics = ",".join(repo_data.get("topics", []))
    repository = session.query(Repository).filter_by(id=repo_id).first()
    
    if repository:
        repository.name = repo_data.get("name")
        repository.full_name = repo_data.get("full_name")
        repository.owner_id = repo_data["owner"]["id"]
        repository.private = repo_data.get("private", False)
        repository.description = repo_data.get("description")
        repository.homepage = repo_data.get("homepage")
        repository.language = repo_data.get("language")
        repository.topics = topics
        repository.license = save_json_field(repo_data.get("license"))
        repository.visibility = repo_data.get("visibility")
        repository.default_branch = repo_data.get("default_branch")
        repository.archived = repo_data.get("archived", False)
        repository.disabled = repo_data.get("disabled", False)
        repository.fork = repo_data.get("fork", False)
        repository.forks_count = repo_data.get("forks_count")
        repository.network_count = repo_data.get("network_count")
        repository.watchers_count = repo_data.get("watchers_count")
        repository.stargazers_count = repo_data.get("stargazers_count")
        repository.subscribers_count = repo_data.get("subscribers_count")
        repository.html_url = repo_data.get("html_url")
        repository.clone_url = repo_data.get("clone_url")
        repository.ssh_url = repo_data.get("ssh_url")
        repository.svn_url = repo_data.get("svn_url")
        repository.git_url = repo_data.get("git_url")
        repository.mirror_url = repo_data.get("mirror_url")
        repository.issues_url = repo_data.get("issues_url")
        repository.pulls_url = repo_data.get("pulls_url")
        repository.commits_url = repo_data.get("commits_url")
        repository.branches_url = repo_data.get("branches_url")
        repository.tags_url = repo_data.get("tags_url")
        repository.contributors_url = repo_data.get("contributors_url")
        repository.collaborators_url = repo_data.get("collaborators_url")
        repository.downloads_url = repo_data.get("downloads_url")
        repository.size = repo_data.get("size")
        repository.open_issues_count = repo_data.get("open_issues_count")
        repository.has_issues = repo_data.get("has_issues", False)
        repository.has_wiki = repo_data.get("has_wiki", False)
        repository.has_downloads = repo_data.get("has_downloads", False)
        repository.has_projects = repo_data.get("has_projects", False)
        repository.has_pages = repo_data.get("has_pages", False)
        repository.is_template = repo_data.get("is_template", False)
        repository.raw_data = save_json_field(repo_data)
        repository.ingested_at = get_current_time()
    else:
        repository = Repository(
            id=repo_data["id"],
            name=repo_data.get("name"),
            full_name=repo_data.get("full_name"),
            owner_id=repo_data["owner"]["id"],
            private=repo_data.get("private", False),
            description=repo_data.get("description"),
            homepage=repo_data.get("homepage"),
            language=repo_data.get("language"),
            topics=topics,
            license=save_json_field(repo_data.get("license")),
            visibility=repo_data.get("visibility"),
            default_branch=repo_data.get("default_branch"),
            archived=repo_data.get("archived", False),
            disabled=repo_data.get("disabled", False),
            fork=repo_data.get("fork", False),
            forks_count=repo_data.get("forks_count"),
            network_count=repo_data.get("network_count"),
            watchers_count=repo_data.get("watchers_count"),
            stargazers_count=repo_data.get("stargazers_count"),
            subscribers_count=repo_data.get("subscribers_count"),
            html_url=repo_data.get("html_url"),
            clone_url=repo_data.get("clone_url"),
            ssh_url=repo_data.get("ssh_url"),
            svn_url=repo_data.get("svn_url"),
            git_url=repo_data.get("git_url"),
            mirror_url=repo_data.get("mirror_url"),
            issues_url=repo_data.get("issues_url"),
            pulls_url=repo_data.get("pulls_url"),
            commits_url=repo_data.get("commits_url"),
            branches_url=repo_data.get("branches_url"),
            tags_url=repo_data.get("tags_url"),
            contributors_url=repo_data.get("contributors_url"),
            collaborators_url=repo_data.get("collaborators_url"),
            downloads_url=repo_data.get("downloads_url"),
            size=repo_data.get("size"),
            open_issues_count=repo_data.get("open_issues_count"),
            has_issues=repo_data.get("has_issues", False),
            has_wiki=repo_data.get("has_wiki", False),
            has_downloads=repo_data.get("has_downloads", False),
            has_projects=repo_data.get("has_projects", False),
            has_pages=repo_data.get("has_pages", False),
            is_template=repo_data.get("is_template", False),
            raw_data=save_json_field(repo_data)
        )
        repository.ingested_at = get_current_time()
        session.add(repository)
    
    session.commit()
    record_discovery(repository, discovery_method, discovery_details, 
                    trigger_input=trigger_input, keyword=keyword,
                    chain_id=chain_id, branch_id=branch_id, step=step)
    return repository

def store_doi(session, repository_id, doi_string, source="UNKNOWN", doi_metadata=None,
             discovery_method="direct_ingestion", discovery_details=None, 
             trigger_input=None, keyword=None, chain_id=None, branch_id=None, step=1):
    """
    Create or update a DOI record.
    """
    from utils.common import clean_doi
    
    doi_string = clean_doi(doi_string)
    
    if discovery_details is None:
        repository = session.query(Repository).filter_by(id=repository_id).first()
        repo_name = repository.full_name if repository else f"repository ID {repository_id}"
        discovery_details = f"DOI '{doi_string}' discovered from {source} in {repo_name}"
    
    existing = session.query(DOI).filter_by(repository_id=repository_id, doi=doi_string).first()
    if not existing:
        new_doi = DOI(
            repository_id=repository_id,
            doi=doi_string,
            source=source,
            doi_metadata=doi_metadata
        )
        new_doi.ingested_at = get_current_time()
        session.add(new_doi)
        session.commit()
        logger.info(f"Stored new DOI '{doi_string}' for repo={repository_id} from {source}")
        
        record_discovery(new_doi, discovery_method, discovery_details, 
                        trigger_input=trigger_input, keyword=keyword,
                        chain_id=chain_id, branch_id=branch_id, step=step)
        return new_doi
    else:
        logger.info(f"DOI '{doi_string}' already exists for repo={repository_id}; skipping.")
        return existing