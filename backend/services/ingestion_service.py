"""
backend.services.ingestion_service
----------------------------------
Orchestrates the process of fetching, processing, and storing data
for software repositories and their related entities from external sources,
primarily GitHub.
"""

import logging
import re
import json
from typing import Optional, List, Dict, Any, Tuple
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import HTTPException, status

# Import utilities and clients
from backend.utils import github_utils
from backend.external import GitHubClient, ApiClientError

# Import models
from backend.data.models import (
    Repository, Owner, Contributor, DiscoveryChain, RepositoryContributorAssociation,
    SoftwareDependency,
    # --- ADDED MODELS ---
    Issue, PullRequest, IssueComment, PRReviewComment
    # --- END ADDED ---
)
# Import repositories
from backend.data.repositories import (
    RepositoryRepository,
    OwnerRepository,
    ContributorRepository,
    SoftwareDependencyRepository,
    # --- ADDED REPOS ---
    IssueRepository,
    PullRequestRepository,
    IssueCommentRepository,
    PRReviewCommentRepository
    # --- END ADDED ---
)

# Import other services
from .base_service import BaseService
from .discovery_chain_service import DiscoveryChainService
from .doi_processing_service import DOIProcessingService

# Import date/time utilities
from datetime import datetime, timezone, timedelta # Added timedelta
import dateutil.parser # Import dateutil.parser for robust timestamp parsing

# Import SessionLocal for creating isolated sessions in specific failure handling scenarios
from backend.data.database import SessionLocal


logger = logging.getLogger(__name__)


# --- Helper function to parse GitHub timestamps ---
def _parse_github_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
    """
    Safely parses ISO 8601 formatted timestamp strings commonly returned by GitHub API.

    Args:
        timestamp_str: The timestamp string from GitHub API (e.g., "2023-01-01T12:00:00Z").

    Returns:
        A timezone-aware datetime object (UTC) if parsing is successful, otherwise None.
    """
    if not timestamp_str:
        return None
    try:
        # Use dateutil.parser for flexibility with ISO 8601 variations
        dt = dateutil.parser.isoparse(timestamp_str)
        # Standardize to UTC if timezone information is missing (though GitHub usually provides it)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError) as e:
        # Log a warning if parsing fails, but don't interrupt the process
        logger.warning(f"Could not parse timestamp string '{timestamp_str}': {e}")
        return None
# --- End Helper ---

class IngestionService(BaseService):
    """
    Coordinates the ingestion workflow for a single software repository.

    This service fetches metadata, contributors, dependencies, and activity data
    (issues, pull requests, comments) from GitHub for a specified repository URL.
    It utilizes various repository patterns and other services (DiscoveryChainService,
    DOIProcessingService) to persist the fetched information into the database,
    tracking the provenance of the data through discovery chains.

    Key responsibilities:
    - Parsing GitHub repository URLs.
    - Fetching repository and owner metadata via GitHub API.
    - Fetching contributor information and storing contribution counts.
    - Identifying and parsing common dependency files (e.g., requirements.txt, package.json).
    - Fetching and storing repository activity: issues, pull requests, and their comments.
    - Triggering DOI extraction and processing from relevant files (e.g., README).
    - Managing the overall database transaction for a single repository ingestion.
    - Creating and managing discovery chains to track the ingestion process steps.
    """
    def __init__(self):
        """Initializes the IngestionService with its dependencies."""
        super().__init__()
        # Instantiate clients and services needed for the ingestion process
        self.github_client = GitHubClient()
        self.discovery_chain_service = DiscoveryChainService()
        self.doi_processing_service = DOIProcessingService()

    def _extract_repo_data_from_github(self, repo_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts and transforms relevant fields from the GitHub repository metadata response.

        Args:
            repo_meta: The dictionary representing the repository metadata from GitHub API.

        Returns:
            A dictionary containing structured data suitable for creating or updating
            a local Repository database record. Includes parsed timestamps, topics, and license info.
        """
        license_data = repo_meta.get("license") # May be None or a dictionary
        topics_list = repo_meta.get("topics", [])
        # Ensure topics is always a list, even if GitHub returns null
        if topics_list is None: topics_list = []

        # Map GitHub API fields to local database model fields
        return {
            "github_id": repo_meta.get("id"),
            "name": repo_meta.get("name"),
            "full_name": repo_meta.get("full_name"),
            "description": repo_meta.get("description"),
            "homepage": repo_meta.get("homepage"),
            "html_url": repo_meta.get("html_url"),
            "api_url": repo_meta.get("url"), # GitHub's API URL for the repo
            "language": repo_meta.get("language"),
            "default_branch": repo_meta.get("default_branch"),
            "stargazers_count": repo_meta.get("stargazers_count", 0),
            "watchers_count": repo_meta.get("subscribers_count", 0), # Note: 'subscribers_count' often reflects watchers
            "forks_count": repo_meta.get("forks_count", 0),
            "open_issues_count": repo_meta.get("open_issues_count", 0),
            "is_fork": repo_meta.get("fork", False),
            "gh_created_at": _parse_github_timestamp(repo_meta.get("created_at")), # Use helper for robust parsing
            "gh_updated_at": _parse_github_timestamp(repo_meta.get("updated_at")), # Use helper
            "gh_pushed_at": _parse_github_timestamp(repo_meta.get("pushed_at")),   # Use helper
            "topics": topics_list, # Store the list of topic strings
            "license": license_data, # Store the license sub-dictionary or None
        }

    def _extract_owner_data_from_github(self, owner_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts and transforms relevant fields from the GitHub owner metadata response.

        Args:
            owner_meta: The dictionary representing the owner (User or Organization)
                       metadata from the GitHub API (usually nested within repo metadata).

        Returns:
            A dictionary containing structured data suitable for creating or updating
            a local Owner database record.
        """
        # Map GitHub API fields to local database model fields
        return {
            "github_id": owner_meta.get("id"),
            "login": owner_meta.get("login"), # User or Org name
            "type": owner_meta.get("type"), # e.g., "User", "Organization"
            "avatar_url": owner_meta.get("avatar_url"),
            "html_url": owner_meta.get("html_url"), # URL to GitHub profile/page
            "api_url": owner_meta.get("url"), # GitHub's API URL for the owner
        }

    def _extract_contributor_data_from_github(self, contrib_meta: Dict[str, Any]) -> Dict[str, Any]:
         """
         Extracts and transforms relevant fields from the GitHub contributor list item.

         Args:
             contrib_meta: A dictionary representing a single contributor from the
                           GitHub API's contributors list endpoint response.

         Returns:
             A dictionary containing structured data suitable for creating or updating
             a local Contributor database record, including their contribution count.
         """
         # Map GitHub API fields to local database model fields
         return {
            "github_id": contrib_meta.get("id"),
            "login": contrib_meta.get("login"),
            "type": contrib_meta.get("type"), # Usually "User"
            "avatar_url": contrib_meta.get("avatar_url"),
            "html_url": contrib_meta.get("html_url"),
            "api_url": contrib_meta.get("url"),
            "contributions_count": contrib_meta.get("contributions") # Specific to contributor endpoint
         }

    # --- ADDED HELPER for activity user data ---
    def _extract_activity_user_data(self, user_meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
         """
         Extracts relevant user fields from GitHub activity items like issues, PRs, or comments.

         This is similar to contributor extraction but uses the 'user' sub-object found
         in issue/PR/comment payloads, which might not include contribution counts.

         Args:
             user_meta: The dictionary representing the 'user' associated with an
                        activity item (e.g., issue author, commenter).

         Returns:
             A dictionary containing structured data suitable for creating or updating
             a local Contributor record (acting as the user/author), or None if input is invalid.
         """
         if not user_meta or not isinstance(user_meta, dict):
             return None
         # Map GitHub API fields to local database model fields
         return {
            "github_id": user_meta.get("id"),
            "login": user_meta.get("login"),
            "type": user_meta.get("type"), # Usually 'User' or potentially 'Bot'
            "avatar_url": user_meta.get("avatar_url"),
            "html_url": user_meta.get("html_url"),
            "api_url": user_meta.get("url"), # User-specific API URL
         }
    # --- END ADDED HELPER ---


    def _parse_requirements_txt(self, content: str) -> List[Tuple[str, Optional[str]]]:
        """
        Performs basic parsing of a requirements.txt file content.

        Extracts package names and optional version constraints. Handles comments
        and blank lines. This is a simplified parser and may not cover all pip syntax edge cases.

        Args:
            content: The string content of the requirements.txt file.

        Returns:
            A list of tuples, where each tuple contains (package_name, version_constraint_string | None).
            Package names are lowercased.
        """
        dependencies = []
        # Regex to capture the package name (group 1) at the start of a line,
        # optionally followed by version specifiers, ignoring comments.
        # Allows letters, numbers, underscore, dot, hyphen in package names.
        pattern = re.compile(r"^\s*([a-zA-Z0-9_.-]+)\s*(?:[!=<>~]=?.*)?(?=\s*(?:#.*)?$)")
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            # Skip empty lines and lines that are purely comments
            if not line or line.startswith('#'):
                continue

            match = pattern.match(line)
            if match:
                dep_name = match.group(1).lower() # Normalize package name to lowercase
                # Attempt to find any version constraint part in the original line
                constraint_match = re.search(r"[!=<>~]=?.*", line)
                constraint = constraint_match.group(0).strip() if constraint_match else None
                dependencies.append((dep_name, constraint))
            else:
                 # Log lines that couldn't be parsed by the simple regex
                 logger.debug(f"Could not parse line in requirements.txt: '{line}'")
        return dependencies

    def _parse_package_json(self, content: str) -> List[Tuple[str, Optional[str], bool]]:
        """
        Parses package.json content to extract dependencies and devDependencies.

        Args:
            content: The JSON string content of the package.json file.

        Returns:
            A list of tuples, where each tuple contains
            (package_name, version_constraint_string | None, is_dev_dependency).
            Package names are lowercased. Returns an empty list if JSON parsing fails.
        """
        dependencies = []
        try:
            data = json.loads(content)

            # Process regular dependencies
            deps = data.get("dependencies", {})
            if isinstance(deps, dict): # Ensure it's a dictionary
                for name, version in deps.items():
                    # Normalize name and store version string
                    dependencies.append((name.lower(), str(version) if version else None, False)) # is_dev = False

            # Process development dependencies
            dev_deps = data.get("devDependencies", {})
            if isinstance(dev_deps, dict): # Ensure it's a dictionary
                for name, version in dev_deps.items():
                     # Normalize name and store version string
                    dependencies.append((name.lower(), str(version) if version else None, True)) # is_dev = True

        except json.JSONDecodeError:
            # Log specific error for invalid JSON
            logger.error("Failed to parse package.json content as JSON.")
        except Exception as e:
            # Catch other potential errors during processing (e.g., unexpected data types)
            logger.error(f"Error processing package.json data: {e}", exc_info=True)
        return dependencies

    def _process_dependencies(
        self,
        db: Session,
        repository: Repository,
        parent_chain: DiscoveryChain,
        owner_login: str,
        repo_name: str
    ) -> bool:
        """
        Fetches and processes common software dependency files (e.g., requirements.txt, package.json).

        Creates SoftwareDependency records for identified dependencies and associates
        them with the repository and relevant discovery chains.

        Args:
            db: The database session.
            repository: The Repository database object.
            parent_chain: The parent DiscoveryChain (typically the root ingestion chain).
            owner_login: The login name of the repository owner.
            repo_name: The name of the repository.

        Returns:
            True if dependency processing completed without fatal errors, False otherwise.
            Note: Individual file fetch/parse errors are logged but may not cause a False return unless critical.
        """
        dep_chain: Optional[DiscoveryChain] = None # Chain for the overall dependency process
        processing_successful = True # Flag to track overall success

        try:
            # Create a discovery chain specifically for dependency processing
            dep_chain = self.discovery_chain_service.create_child_chain(
                db=db, parent_chain=parent_chain, discovery_type='PROCESS_DEPENDENCIES',
                parameters={'repo_id': repository.id} )
            self.discovery_chain_service.start_chain(db, dep_chain)
            dep_repo = SoftwareDependencyRepository(db)

            # Define files to check and their associated type and parser function
            files_to_check = {
                "requirements.txt": ("pypi", self._parse_requirements_txt),
                "package.json": ("npm", self._parse_package_json),
                # Add other dependency file types here (e.g., pom.xml, Gemfile)
            }

            dependencies_to_add = [] # Accumulate dependency objects before flushing

            # Iterate through the files we know how to parse
            for file_path, (dep_type, parser_func) in files_to_check.items():
                content: Optional[str] = None
                file_chain: Optional[DiscoveryChain] = None # Chain for processing a single file
                try:
                    # Create a sub-chain for processing this specific dependency file
                    file_chain = self.discovery_chain_service.create_child_chain(
                        db=db, parent_chain=dep_chain,
                        discovery_type=f'PARSE_DEPENDENCY_FILE',
                        parameters={'file_path': file_path}
                    )
                    self.discovery_chain_service.start_chain(db, file_chain)

                    logger.debug(f"Attempting to fetch dependency file: {owner_login}/{repo_name}/{file_path}")
                    # Fetch file content using the GitHub client
                    content = self.github_client.get_file_content(owner_login, repo_name, file_path)

                    if content:
                        logger.info(f"Parsing '{file_path}' for {dep_type} dependencies...")
                        # Use the appropriate parser function for the file type
                        parsed_deps = parser_func(content)
                        logger.info(f"Found {len(parsed_deps)} potential dependencies in {file_path}.")

                        # Process each parsed dependency
                        for dep_data in parsed_deps:
                            is_dev = False # Default for non-npm types
                            # Unpack data based on parser return type
                            if dep_type == "npm":
                                dep_name, version_constraint, is_dev = dep_data
                            else: # requirements.txt format
                                dep_name, version_constraint = dep_data

                            if not dep_name: continue # Skip if name is empty/invalid

                            # Prepare data for SoftwareDependency record
                            dependency_input = {
                                "repository_id": repository.id,
                                "dependency_name": dep_name,
                                "version_constraint": version_constraint,
                                "source_file": file_path,
                                "dependency_type": dep_type,
                                "is_dev_dependency": is_dev if dep_type == "npm" else None, # Applicable only to npm
                            }
                            # Get existing or prepare new dependency object (without committing)
                            dep_db = dep_repo.get_or_create(obj_in_data=dependency_input)
                            dependencies_to_add.append(dep_db) # Add to list for bulk flush/association

                        # Mark the file processing chain as complete
                        self.discovery_chain_service.complete_chain(db, file_chain)
                    else:
                        # File exists but is empty, or fetch returned None gracefully (e.g., API error handled)
                        logger.debug(f"Dependency file '{file_path}' not found or empty.")
                        # Mark the file processing chain as failed due to missing file
                        self.discovery_chain_service.fail_chain(db, file_chain, error_message="File not found or empty")

                except ApiClientError as e:
                    # Handle specific API errors during file fetch
                    if e.status_code == 404:
                        logger.debug(f"Dependency file not found via API: {owner_login}/{repo_name}/{file_path} (404)")
                    else:
                        # Log other API errors but potentially continue with other files
                        logger.error(f"API Error fetching dep file {file_path}: {e}", exc_info=False)
                        processing_successful = False # Mark overall process as having issues
                    if file_chain:
                        # Mark file chain as failed due to API error
                        self.discovery_chain_service.fail_chain(db, file_chain, error_message=f"API Error {e.status_code}")
                except Exception as e:
                    # Catch unexpected errors during parsing or processing
                    logger.error(f"Error processing dependency file {file_path}: {e}", exc_info=True)
                    processing_successful = False # Mark overall process as having issues
                    if file_chain:
                         # Mark file chain as failed due to processing error
                        self.discovery_chain_service.fail_chain(db, file_chain, error_message=f"Processing error: {str(e)[:50]}")

            # --- Flush accumulated dependencies ---
            # After processing all files, flush the session to assign IDs to new dependencies
            if dependencies_to_add:
                logger.info(f"Flushing {len(dependencies_to_add)} dependency objects...")
                try:
                    db.flush() # Persist new/updated dependency records
                    logger.info("Dependency flush successful.")
                    # Now associate the flushed entities with their respective file chains
                    for dep_db in dependencies_to_add:
                         if dep_db.id: # Check if ID was assigned after flush
                             # Find the corresponding file processing chain again
                             # This requires querying based on parameters stored in the chain
                             # Note: This lookup might be inefficient if parameters are complex. Consider storing file_chain_id temporarily.
                             file_chain_for_assoc = db.query(DiscoveryChain).filter(
                                 DiscoveryChain.parent_chain_id == dep_chain.id,
                                 # Assuming 'file_path' is stored reliably in parameters as text
                                 DiscoveryChain.parameters['file_path'].astext == dep_db.source_file
                             ).first()

                             if file_chain_for_assoc:
                                 # Link the dependency record to the chain for the file it came from
                                 self.discovery_chain_service.associate_entity(db, file_chain_for_assoc, dep_db, is_direct=True)
                             else:
                                 # Log if the corresponding file chain couldn't be found
                                 logger.warning(f"Could not find file_chain for dependency {dep_db.dependency_name} from {dep_db.source_file} to associate.")
                         else:
                             # This indicates a problem with the flush or session state
                             logger.error(f"Dependency {dep_db.dependency_name} from {dep_db.source_file} missing ID after flush.")
                             processing_successful = False
                except (IntegrityError, SQLAlchemyError) as flush_err:
                     # Catch errors during the flush operation itself
                     logger.error(f"Error during dependency flush: {flush_err}", exc_info=True)
                     processing_successful = False # Mark overall process as failed

            # Finalize the main dependency processing chain based on overall success
            if processing_successful:
                self.discovery_chain_service.complete_chain(db, dep_chain)
            else:
                self.discovery_chain_service.fail_chain(db, dep_chain, error_message="One or more errors during dependency processing/flush.")

        except Exception as main_dep_err:
            # Catch errors in the setup phase of dependency processing
            logger.error(f"Fatal error during dependency processing setup for repo {repository.id}: {main_dep_err}", exc_info=True)
            if dep_chain:
                # Attempt to mark the main dependency chain as failed
                try: self.discovery_chain_service.fail_chain(db, dep_chain, error_message="Fatal setup error")
                except Exception: pass # Ignore errors during this final failure handling
            return False # Indicate a fatal setup error occurred

        return processing_successful


    def ingest_repository_by_url(
        self, db: Session, repo_url: str
    ) -> Optional[DiscoveryChain]:
        """
        Performs the complete ingestion process for a single repository identified by its URL.

        This is the main entry point for ingesting a repository. It handles:
        1. Parsing the URL.
        2. Creating a root discovery chain.
        3. Fetching and storing Repository and Owner metadata.
        4. Fetching and storing Contributor data and associations.
        5. Processing software dependencies.
        6. Processing specified files (e.g., README) for DOIs.
        7. Fetching and storing Issues and Issue Comments.
        8. Fetching and storing Pull Requests and PR Review Comments.
        9. Committing the transaction upon successful completion or rolling back on failure.
        10. Managing discovery chains for each step.

        Args:
            db: The SQLAlchemy database session to use for the entire operation.
            repo_url: The URL of the GitHub repository to ingest.

        Returns:
            The root DiscoveryChain object if ingestion setup was successful (the chain status
            will reflect the final outcome: COMPLETED or FAILED), or None if URL parsing failed initially.

        Raises:
            RuntimeError: If a critical error occurs during ingestion, preventing completion.
                          The underlying exception (e.g., ApiClientError, SQLAlchemyError) is chained.
        """
        root_chain: Optional[DiscoveryChain] = None
        # Chains for specific sub-processes
        files_chain: Optional[DiscoveryChain] = None
        contrib_chain: Optional[DiscoveryChain] = None
        issues_chain: Optional[DiscoveryChain] = None
        prs_chain: Optional[DiscoveryChain] = None
        # Repository identifiers
        owner_login: Optional[str] = None
        repo_name: Optional[str] = None
        # Database objects
        repo_db: Optional[Repository] = None
        owner_db: Optional[Owner] = None

        try:
            # --- Step 1: Parse URL ---
            self.logger.info(f"Attempting ingestion for URL: {repo_url}")
            parsed_info = github_utils.parse_github_url(repo_url)
            if not parsed_info:
                self.logger.error(f"Invalid GitHub URL format: {repo_url}")
                # Cannot proceed without valid owner/repo names
                return None
            owner_login, repo_name = parsed_info
            self.logger.info(f"Parsed URL: Owner='{owner_login}', Repo='{repo_name}'")

            # --- Step 2: Create Root Discovery Chain ---
            # Tracks the overall ingestion process initiated by this URL.
            root_chain = self.discovery_chain_service.create_root_chain(
                db=db, discovery_type='DIRECT_URL',
                parameters={'url': repo_url, 'owner': owner_login, 'repo': repo_name} )
            # Mark the chain as started
            self.discovery_chain_service.start_chain(db, root_chain)

            # Instantiate repository access objects
            owner_repo = OwnerRepository(db)
            repo_repo = RepositoryRepository(db)
            contrib_repo = ContributorRepository(db)
            issue_repo = IssueRepository(db)
            pr_repo = PullRequestRepository(db)
            issue_comment_repo = IssueCommentRepository(db)
            pr_comment_repo = PRReviewCommentRepository(db)

            # --- Step 3: Fetch Repository Metadata & Owner ---
            self.logger.info(f"Fetching repository metadata for {owner_login}/{repo_name}")
            repo_meta = self.github_client.get_repository_metadata(owner_login, repo_name)
            # Handle case where repository is not found or API fails
            if not repo_meta:
                raise ValueError(f"Repository {owner_login}/{repo_name} not found or inaccessible via API.")
            owner_meta = repo_meta.get("owner")
            if not owner_meta or not owner_meta.get("id"):
                 raise ValueError(f"Could not extract valid owner data for {owner_login}/{repo_name}.")

            # Process and store Owner
            owner_data = self._extract_owner_data_from_github(owner_meta)
            owner_db = owner_repo.get_or_create_by_github_id(github_id=owner_data["github_id"], obj_in_data=owner_data)
            if not owner_db:
                # This should ideally not happen with get_or_create logic, but check defensively
                raise RuntimeError(f"Failed to get or create Owner object for GH ID {owner_data.get('github_id')}")
            try:
                # Flush early to ensure owner_db gets an ID if newly created
                logger.debug(f"Flushing Owner object (GH ID {owner_db.github_id})..."); db.flush(); logger.debug(f"Owner flushed successfully (DB ID: {owner_db.id})")
            except (IntegrityError, SQLAlchemyError) as owner_flush_e:
                logger.error(f"Error during Owner flush: {owner_flush_e}", exc_info=True)
                raise owner_flush_e
            if owner_db.id is None:
                # ID should be assigned after flush
                raise RuntimeError("Owner ID is still None after explicit flush.")

            # Process and store Repository, linking to the Owner
            repo_data = self._extract_repo_data_from_github(repo_meta)
            # Pass the owner_obj to establish the relationship during creation/update
            repo_db = repo_repo.get_or_create_by_github_id(github_id=repo_data["github_id"], obj_in_data=repo_data, owner_obj=owner_db)
            if not repo_db or repo_db.id is None:
                # Repository should always have an ID after get_or_create and potential flush
                 raise RuntimeError("Repository ID not available after get_or_create.")
            self.logger.info(f"Owner ID: {owner_db.id}, Repo ID: {repo_db.id}, Repo Owner ID field: {repo_db.owner_id} obtained/set.")

            # Associate the discovered Owner and Repository with the root chain
            self.discovery_chain_service.associate_entity(db, root_chain, owner_db, is_direct=False) # Owner is related, not direct result
            self.discovery_chain_service.associate_entity(db, root_chain, repo_db, is_direct=True) # Repository is the direct result

            # --- Step 4: Fetch Contributors & Store Associations ---
            contrib_chain = self.discovery_chain_service.create_child_chain(db, root_chain, 'FETCH_CONTRIBUTORS', {'repo_id': repo_db.id})
            self.discovery_chain_service.start_chain(db, contrib_chain)
            contributors_processed_successfully = True # Track success within this step
            contributors_to_add = [] # Accumulate Contributor objects
            associations_to_add_or_update = [] # Accumulate association data

            try:
                # Fetch list of contributors from GitHub API
                contributors_meta = self.github_client.get_contributors(owner_login, repo_name)
                if contributors_meta:
                    self.logger.info(f"Processing {len(contributors_meta)} contributors for {repo_db.full_name}")
                    for contrib_meta in contributors_meta:
                         # Basic validation of contributor data from API
                         if not contrib_meta or not contrib_meta.get("id"):
                             logger.warning(f"Skipping invalid contributor data: {contrib_meta}")
                             continue

                         # Extract contributor data and contribution count
                         contrib_data = self._extract_contributor_data_from_github(contrib_meta)
                         contributions_count = contrib_data.pop("contributions_count", None) # Remove count before passing to repo

                         # Get or create the Contributor record
                         contrib_db = contrib_repo.get_or_create_by_github_id(github_id=contrib_data["github_id"], obj_in_data=contrib_data)
                         contributors_to_add.append(contrib_db) # Add to list for bulk flush

                         # Prepare data for the association link (Repository <-> Contributor)
                         associations_to_add_or_update.append({
                            "repository_id": repo_db.id,
                            "contributor": contrib_db, # Keep the object reference
                            "contributions_count": contributions_count
                         })
                else:
                    logger.info(f"No contributors found or returned for {repo_db.full_name}")

                # Flush new/updated Contributor objects to get their IDs
                if contributors_to_add:
                     self.logger.info(f"Flushing {len(contributors_to_add)} contributor objects...")
                     try:
                         db.flush(); self.logger.info("Contributor flush successful.")
                     except (IntegrityError, SQLAlchemyError) as contrib_flush_err:
                         logger.error(f"Error during contributor flush: {contrib_flush_err}", exc_info=True)
                         contributors_processed_successfully = False # Mark step as failed

                # Process associations only if contributor flush was okay
                if contributors_processed_successfully:
                    self.logger.info(f"Processing {len(associations_to_add_or_update)} contributor associations...")
                    for assoc_data in associations_to_add_or_update:
                        contrib_obj = assoc_data["contributor"]
                        # Ensure the contributor object has an ID after the flush
                        if not contrib_obj or contrib_obj.id is None:
                            logger.error(f"Contributor object missing or has no ID after flush: {contrib_obj}")
                            contributors_processed_successfully = False
                            continue

                        # Check if association already exists
                        association = db.query(RepositoryContributorAssociation).filter_by(
                            repository_id=assoc_data["repository_id"],
                            contributor_id=contrib_obj.id
                        ).first()

                        if association:
                            # Update contribution count if it changed
                            if association.contributions_count != assoc_data["contributions_count"]:
                                association.contributions_count = assoc_data["contributions_count"]
                                db.add(association) # Mark for update
                                logger.debug(f"Updated contribution count for Repo {assoc_data['repository_id']} / Contrib {contrib_obj.id} to {assoc_data['contributions_count']}")
                        else:
                            # Create new association record
                            association = RepositoryContributorAssociation(
                                repository_id=assoc_data["repository_id"],
                                contributor_id=contrib_obj.id,
                                contributions_count=assoc_data["contributions_count"]
                            )
                            db.add(association) # Mark for insertion
                            logger.debug(f"Prepared new association for Repo {assoc_data['repository_id']} / Contrib {contrib_obj.id} with count {assoc_data['contributions_count']}")

                        # Associate the Contributor entity (not the association link) with the contributor chain
                        self.discovery_chain_service.associate_entity(db, contrib_chain, contrib_obj, is_direct=True)

                # Flush association changes (updates/inserts)
                if contributors_processed_successfully:
                     try:
                         logger.debug("Flushing contributor associations..."); db.flush(); logger.debug("Contributor associations flushed.")
                     except (IntegrityError, SQLAlchemyError) as assoc_flush_err:
                         logger.error(f"Error during contributor association flush: {assoc_flush_err}", exc_info=True)
                         contributors_processed_successfully = False # Mark step as failed

                # Finalize contributor chain status
                if contributors_processed_successfully:
                    self.discovery_chain_service.complete_chain(db, contrib_chain)
                else:
                    self.discovery_chain_service.fail_chain(db, contrib_chain, error_message="One or more errors during contributor/association processing.")

            except (ApiClientError, Exception) as contrib_e:
                # Catch errors during the initial contributor fetch
                logger.error(f"Failed fetching contributors list for {repo_db.full_name}: {contrib_e}", exc_info=True)
                contributors_processed_successfully = False # Mark step as failed
                if contrib_chain:
                    try:
                        # Attempt to mark chain as failed due to fetch error
                        self.discovery_chain_service.fail_chain(db, contrib_chain, error_message=f"Failed to fetch list: {str(contrib_e)[:100]}")
                    except Exception as chain_fail_err:
                        # Log error during failure handling itself
                        logger.error(f"Error trying to fail contributor chain {contrib_chain.id} after fetch error: {chain_fail_err}")


            # --- Step 5: Process Dependencies ---
            # Delegate dependency file processing to the helper method
            self.logger.info(f"Initiating dependency processing for {repo_db.full_name}...")
            self._process_dependencies(
                db=db, repository=repo_db, parent_chain=root_chain,
                owner_login=owner_login, repo_name=repo_name
            )
            self.logger.info(f"Dependency processing step finished for {repo_db.full_name}.")

            # --- Step 6: Process DOI Files ---
            # Create chain for DOI processing step
            files_chain = self.discovery_chain_service.create_child_chain(
                 db=db, parent_chain=root_chain, discovery_type='PROCESS_DOI_FILES',
                 parameters={'repo_id': repo_db.id}
            )
            self.discovery_chain_service.start_chain(db, files_chain)
            # Define common files where DOIs might be found
            files_to_check = ["README.md", "README", "README.rst", "CITATION.cff"]
            files_processed_without_errors = True # Track success within this step

            self.logger.info(f"Processing files {files_to_check} for DOIs in {repo_db.full_name}")
            for file_path in files_to_check:
                content: Optional[str] = None
                try:
                    # Fetch file content
                    logger.debug(f"Attempting to fetch file: {owner_login}/{repo_name}/{file_path}")
                    content = self.github_client.get_file_content(owner_login, repo_name, file_path)
                    logger.debug(f"Fetch attempt for {file_path} completed.")
                except ApiClientError as e:
                    # Handle API errors (e.g., 404 Not Found) gracefully
                    if e.status_code == 404:
                        logger.debug(f"File not found via API: {owner_login}/{repo_name}/{file_path} (404)")
                    else:
                        # Log other API errors and mark step as having issues
                        logger.error(f"API Error fetching file {file_path}: {e}", exc_info=False)
                        files_processed_without_errors = False
                    continue # Move to the next file
                except ValueError as ve:
                     # Catch potential errors decoding content (if applicable in get_file_content)
                     logger.error(f"Content processing error for file {file_path}: {ve}", exc_info=True)
                     files_processed_without_errors = False
                     continue
                except Exception as e:
                     # Catch unexpected errors during file fetch/processing
                     logger.error(f"Unexpected Error fetching/processing file {file_path}: {e}", exc_info=True)
                     files_processed_without_errors = False
                     continue

                # If content was successfully fetched
                if content:
                    self.logger.info(f"Found {file_path}, triggering DOI processing...")
                    try:
                        # Delegate DOI extraction, resolution, and storage to DOIProcessingService
                        # This service manages its own savepoints and commits internally.
                        self.doi_processing_service.extract_resolve_and_store_dois(
                            db=db, # Pass the main session
                            parent_chain=files_chain, # Link DOI chains to this file chain
                            repository=repo_db,
                            file_content=content,
                            source_file=file_path
                        )
                    except Exception as doi_proc_e:
                        # Catch errors originating from the DOI service call itself
                        logger.error(f"Error occurred during DOI processing trigger/setup for file {file_path}: {doi_proc_e}", exc_info=True)
                        files_processed_without_errors = False
                else:
                    # Log cases where file was found but empty, or fetch failed gracefully
                    logger.debug(f"File found but content was empty or fetch failed gracefully (e.g. 404), skipping DOI processing: {file_path}")

            # Finalize the DOI file processing chain status
            try:
                db.add(files_chain) # Ensure chain is in session
                if files_processed_without_errors:
                    self.discovery_chain_service.complete_chain(db, files_chain)
                else:
                    self.discovery_chain_service.fail_chain(db, files_chain, error_message="One or more errors during file/DOI processing trigger.")
                db.flush() # Persist chain status update
            except Exception as files_chain_update_e:
                 # Log error if updating the chain status fails
                 logger.error(f"Failed to update final status for files_chain {files_chain.id}: {files_chain_update_e}")


            # --- Step 7: Process Issues and Comments ---
            self.logger.info(f"Initiating issue processing for {repo_db.full_name}...")
            issues_processed_successfully = True # Track success for this step
            issues_chain = self.discovery_chain_service.create_child_chain(db, root_chain, 'FETCH_ISSUES', {'repo_id': repo_db.id})
            self.discovery_chain_service.start_chain(db, issues_chain)
            try:
                # Fetch issues (potentially paginated by the client) - assumes fetching all states
                issues_meta = self.github_client.get_issues(owner_login, repo_name)
                self.logger.info(f"Fetched {len(issues_meta)} issues for {repo_db.full_name}.")

                for issue_meta in issues_meta:
                    # Extract key identifiers and user data
                    issue_gh_id = issue_meta.get('id')
                    issue_user_data = self._extract_activity_user_data(issue_meta.get('user'))
                    # Basic validation
                    if not issue_gh_id or not issue_user_data or not issue_user_data.get('github_id'):
                        logger.warning(f"Skipping issue due to missing ID or user data: Issue number {issue_meta.get('number')}")
                        continue

                    issue_chain: Optional[DiscoveryChain] = None # Chain for processing this single issue
                    try:
                        # Create a sub-chain for this specific issue
                        issue_chain = self.discovery_chain_service.create_child_chain(db, issues_chain, 'PROCESS_ISSUE', {'issue_gh_id': issue_gh_id})
                        self.discovery_chain_service.start_chain(db, issue_chain)

                        # Get/Create the author (as a Contributor record)
                        issue_author_db = contrib_repo.get_or_create_by_github_id(github_id=issue_user_data['github_id'], obj_in_data=issue_user_data)
                        db.flush() # Ensure author has an ID
                        if issue_author_db.id is None:
                            raise RuntimeError(f"Issue author Contributor ID is None after flush for GH ID {issue_user_data['github_id']}")
                        # Associate author with the issue chain (indirect discovery)
                        self.discovery_chain_service.associate_entity(db, issue_chain, issue_author_db, is_direct=False)

                        # Prepare data for the Issue record
                        issue_input = {
                            "github_id": issue_gh_id,
                            "repository_id": repo_db.id,
                            "user_id": issue_author_db.id, # Link to Contributor record
                            "number": issue_meta.get('number'),
                            "title": issue_meta.get('title'),
                            "state": issue_meta.get('state'), # e.g., 'open', 'closed'
                            "gh_created_at": _parse_github_timestamp(issue_meta.get("created_at")),
                            "gh_updated_at": _parse_github_timestamp(issue_meta.get("updated_at")),
                            "gh_closed_at": _parse_github_timestamp(issue_meta.get("closed_at")),
                        }
                        # Get or create the Issue record
                        issue_db = issue_repo.get_or_create_by_github_id(github_id=issue_gh_id, obj_in_data=issue_input)
                        db.flush() # Ensure issue has an ID
                        if issue_db.id is None:
                            raise RuntimeError(f"Issue ID is None after flush for GH ID {issue_gh_id}")
                        # Associate the Issue with its processing chain (direct discovery)
                        self.discovery_chain_service.associate_entity(db, issue_chain, issue_db, is_direct=True)

                        # --- Process Issue Comments ---
                        # Fetch comments for this specific issue number
                        comments_meta = self.github_client.get_issue_comments(owner_login, repo_name, issue_number=issue_db.number)
                        logger.debug(f"Fetched {len(comments_meta)} comments for Issue #{issue_db.number}")
                        for comment_meta in comments_meta:
                             # Extract key identifiers and user data for the comment
                             comment_gh_id = comment_meta.get('id')
                             comment_user_data = self._extract_activity_user_data(comment_meta.get('user'))
                             # Basic validation
                             if not comment_gh_id or not comment_user_data or not comment_user_data.get('github_id'):
                                  logger.warning(f"Skipping issue comment due to missing ID or user data on Issue #{issue_db.number}")
                                  continue

                             # Get/Create the comment author (as Contributor)
                             comment_author_db = contrib_repo.get_or_create_by_github_id(github_id=comment_user_data['github_id'], obj_in_data=comment_user_data)
                             db.flush() # Ensure author has ID
                             if comment_author_db.id is None:
                                 logger.error(f"Comment author Contributor ID is None for GH ID {comment_user_data['github_id']}")
                                 continue # Skip this comment if author failed

                             # Prepare data for IssueComment record
                             comment_input = {
                                 "github_id": comment_gh_id,
                                 "issue_id": issue_db.id, # Link to the parent Issue
                                 "user_id": comment_author_db.id, # Link to the author Contributor
                                 "body": comment_meta.get('body'), # Comment text
                                 "gh_created_at": _parse_github_timestamp(comment_meta.get("created_at")),
                                 "gh_updated_at": _parse_github_timestamp(comment_meta.get("updated_at")),
                             }
                             # Get or create the IssueComment record
                             comment_db = issue_comment_repo.get_or_create_by_github_id(github_id=comment_gh_id, obj_in_data=comment_input)
                             # Associate comment with the *issue* chain (indirect discovery via issue)
                             self.discovery_chain_service.associate_entity(db, issue_chain, comment_db, is_direct=False)

                        # Mark the individual issue processing chain as complete
                        self.discovery_chain_service.complete_chain(db, issue_chain)

                    except (ApiClientError, IntegrityError, SQLAlchemyError, ValueError, RuntimeError) as issue_err:
                        # Catch errors related to processing a single issue or its comments
                        logger.error(f"Error processing issue GH ID {issue_gh_id} or its comments: {issue_err}", exc_info=False)
                        issues_processed_successfully = False # Mark overall issue step as having issues
                        if issue_chain:
                            try:
                                # Attempt to mark the specific issue chain as failed
                                self.discovery_chain_service.fail_chain(db, issue_chain, error_message=f"Issue/Comment processing error: {str(issue_err)[:100]}")
                            except Exception as chain_fail_err:
                                logger.error(f"Error failing issue chain {issue_chain.id}: {chain_fail_err}")

            except (ApiClientError, Exception) as e:
                # Catch errors during the initial fetch of the issues list
                logger.error(f"Failed fetching issues list for {repo_db.full_name}: {e}", exc_info=True)
                issues_processed_successfully = False # Mark step as failed
            finally:
                # Finalize the main issues processing chain status
                if issues_chain:
                    if issues_processed_successfully:
                        self.discovery_chain_service.complete_chain(db, issues_chain)
                    else:
                        self.discovery_chain_service.fail_chain(db, issues_chain, "One or more errors during issue/comment processing.")
                    try:
                        db.flush() # Persist final chain status
                    except Exception as flush_err:
                        logger.error(f"Error flushing issues chain final status: {flush_err}")

            # --- Step 8: Process Pull Requests and Comments ---
            # This section mirrors the structure of Issue processing
            self.logger.info(f"Initiating pull request processing for {repo_db.full_name}...")
            prs_processed_successfully = True # Track success for this step
            prs_chain = self.discovery_chain_service.create_child_chain(db, root_chain, 'FETCH_PULL_REQUESTS', {'repo_id': repo_db.id})
            self.discovery_chain_service.start_chain(db, prs_chain)
            try:
                # Fetch pull requests (potentially paginated) - assumes fetching all states
                prs_meta = self.github_client.get_pull_requests(owner_login, repo_name)
                self.logger.info(f"Fetched {len(prs_meta)} pull requests for {repo_db.full_name}.")

                for pr_meta in prs_meta:
                    # Extract key identifiers and user data
                    pr_gh_id = pr_meta.get('id')
                    pr_user_data = self._extract_activity_user_data(pr_meta.get('user'))
                    # Basic validation
                    if not pr_gh_id or not pr_user_data or not pr_user_data.get('github_id'):
                        logger.warning(f"Skipping PR due to missing ID or user data: PR number {pr_meta.get('number')}")
                        continue

                    pr_chain: Optional[DiscoveryChain] = None # Chain for processing this single PR
                    try:
                        # Create a sub-chain for this specific PR
                        pr_chain = self.discovery_chain_service.create_child_chain(db, prs_chain, 'PROCESS_PULL_REQUEST', {'pr_gh_id': pr_gh_id})
                        self.discovery_chain_service.start_chain(db, pr_chain)

                        # Get/Create the author (as Contributor)
                        pr_author_db = contrib_repo.get_or_create_by_github_id(github_id=pr_user_data['github_id'], obj_in_data=pr_user_data)
                        db.flush() # Ensure author has ID
                        if pr_author_db.id is None:
                            raise RuntimeError(f"PR author Contributor ID is None after flush for GH ID {pr_user_data['github_id']}")
                        # Associate author with the PR chain (indirect discovery)
                        self.discovery_chain_service.associate_entity(db, pr_chain, pr_author_db, is_direct=False)

                        # Prepare data for PullRequest record
                        pr_input = {
                            "github_id": pr_gh_id,
                            "repository_id": repo_db.id,
                            "user_id": pr_author_db.id, # Link to author Contributor
                            "number": pr_meta.get('number'),
                            "title": pr_meta.get('title'),
                            "state": pr_meta.get('state'), # e.g., 'open', 'closed', 'merged'
                            "gh_created_at": _parse_github_timestamp(pr_meta.get("created_at")),
                            "gh_updated_at": _parse_github_timestamp(pr_meta.get("updated_at")),
                            "gh_closed_at": _parse_github_timestamp(pr_meta.get("closed_at")),
                            "gh_merged_at": _parse_github_timestamp(pr_meta.get("merged_at")), # Specific to PRs
                        }
                        # Get or create the PullRequest record
                        pr_db = pr_repo.get_or_create_by_github_id(github_id=pr_gh_id, obj_in_data=pr_input)
                        db.flush() # Ensure PR has ID
                        if pr_db.id is None:
                            raise RuntimeError(f"PullRequest ID is None after flush for GH ID {pr_gh_id}")
                        # Associate PullRequest with its chain (direct discovery)
                        self.discovery_chain_service.associate_entity(db, pr_chain, pr_db, is_direct=True)

                        # --- Process PR Review Comments ---
                        # Fetch review comments specific to this PR number
                        pr_comments_meta = self.github_client.get_pr_review_comments(owner_login, repo_name, pull_number=pr_db.number)
                        logger.debug(f"Fetched {len(pr_comments_meta)} comments for PR #{pr_db.number}")
                        for pr_comment_meta in pr_comments_meta:
                             # Extract key identifiers and user data
                             pr_comment_gh_id = pr_comment_meta.get('id')
                             pr_comment_user_data = self._extract_activity_user_data(pr_comment_meta.get('user'))
                             # Basic validation
                             if not pr_comment_gh_id or not pr_comment_user_data or not pr_comment_user_data.get('github_id'):
                                logger.warning(f"Skipping PR comment due to missing ID or user data on PR #{pr_db.number}")
                                continue

                             # Get/Create comment author (as Contributor)
                             pr_comment_author_db = contrib_repo.get_or_create_by_github_id(github_id=pr_comment_user_data['github_id'], obj_in_data=pr_comment_user_data)
                             db.flush() # Ensure author has ID
                             if pr_comment_author_db.id is None:
                                 logger.error(f"PR Comment author Contributor ID is None for GH ID {pr_comment_user_data['github_id']}")
                                 continue # Skip comment if author failed

                             # Prepare data for PRReviewComment record
                             pr_comment_input = {
                                 "github_id": pr_comment_gh_id,
                                 "pr_id": pr_db.id, # Link to parent PullRequest
                                 "user_id": pr_comment_author_db.id, # Link to author Contributor
                                 "pull_request_review_id": pr_comment_meta.get('pull_request_review_id'), # ID of the review it belongs to
                                 "body": pr_comment_meta.get('body'), # Comment text
                                 "gh_created_at": _parse_github_timestamp(pr_comment_meta.get("created_at")),
                                 "gh_updated_at": _parse_github_timestamp(pr_comment_meta.get("updated_at")),
                             }
                             # Get or create the PRReviewComment record
                             pr_comment_db = pr_comment_repo.get_or_create_by_github_id(github_id=pr_comment_gh_id, obj_in_data=pr_comment_input)
                             # Associate comment with the *PR* chain (indirect discovery via PR)
                             self.discovery_chain_service.associate_entity(db, pr_chain, pr_comment_db, is_direct=False)

                        # Mark the individual PR processing chain as complete
                        self.discovery_chain_service.complete_chain(db, pr_chain)

                    except (ApiClientError, IntegrityError, SQLAlchemyError, ValueError, RuntimeError) as pr_err:
                        # Catch errors during processing of a single PR or its comments
                        logger.error(f"Error processing PR GH ID {pr_gh_id} or its comments: {pr_err}", exc_info=False)
                        prs_processed_successfully = False # Mark overall PR step as having issues
                        if pr_chain:
                            try:
                                # Attempt to mark the specific PR chain as failed
                                self.discovery_chain_service.fail_chain(db, pr_chain, error_message=f"PR/Comment processing error: {str(pr_err)[:100]}")
                            except Exception as chain_fail_err:
                                logger.error(f"Error failing PR chain {pr_chain.id}: {chain_fail_err}")

            except (ApiClientError, Exception) as e:
                # Catch errors during the initial fetch of the PR list
                logger.error(f"Failed fetching pull requests list for {repo_db.full_name}: {e}", exc_info=True)
                prs_processed_successfully = False # Mark step as failed
            finally:
                 # Finalize the main PR processing chain status
                 if prs_chain:
                    if prs_processed_successfully:
                        self.discovery_chain_service.complete_chain(db, prs_chain)
                    else:
                        self.discovery_chain_service.fail_chain(db, prs_chain, "One or more errors during PR/comment processing.")
                    try:
                        db.flush() # Persist final chain status
                    except Exception as flush_err:
                        logger.error(f"Error flushing PRs chain final status: {flush_err}")


            # --- Step 9: Finalize Root Chain and Commit ---
            # If all steps completed or handled errors gracefully, mark root chain complete
            # Note: Individual sub-chains might be marked as FAILED, but the overall
            # ingestion process for the URL itself is considered complete at this point.
            # The status of the root chain indicates if the *entire* workflow triggered by the URL finished.
            self.discovery_chain_service.complete_chain(db, root_chain)
            self.logger.info(f"Successfully completed all ingestion steps setup for {repo_url}, chain {root_chain.id}")

            # Commit the entire transaction for this repository ingestion
            db.commit()
            self.logger.info("Main ingestion transaction committed successfully.")
            logger.info(f"ACTION COMPLETE - Synchronous ingestion steps for URL '{repo_url}' (Chain: {root_chain.id}) finished.")

        except (ApiClientError, ValueError, IntegrityError, SQLAlchemyError, Exception) as e:
            # --- Global Error Handling ---
            # Catch any unhandled exceptions from the steps above
            self.logger.error(f"Ingestion failed for URL {repo_url}: {e}", exc_info=True)
            db.rollback() # Roll back the entire transaction on any critical failure
            self.logger.warning("Main ingestion transaction rolled back due to error.")

            # Attempt to mark the root chain as FAILED (best-effort using a separate session)
            if root_chain and root_chain.id:
                 try:
                      # Use a new session to avoid issues with the rolled-back main session state
                      fail_db = SessionLocal();
                      try:
                          # Re-fetch the chain in the new session
                          failed_chain = self.discovery_chain_service.get_by_uuid(fail_db, root_chain.id)
                          # Update status only if it's not already failed
                          if failed_chain and failed_chain.status != 'FAILED':
                              self.discovery_chain_service.fail_chain(fail_db, failed_chain, error_message=f"Outer transaction failed: {str(e)[:200]}")
                              fail_db.commit() # Commit the failure status update
                          elif not failed_chain:
                              logger.error(f"Could not find root chain {root_chain.id} to mark as failed after error.")
                          else: # Chain was already FAILED, possibly from an earlier step
                              logger.warning(f"Root chain {root_chain.id} was already marked as FAILED.")
                      except Exception as fail_e:
                          logger.error(f"Failed to mark root chain {root_chain.id} as FAILED after outer error: {fail_e}", exc_info=True)
                          fail_db.rollback() # Rollback the attempt to mark as failed
                      finally:
                          fail_db.close() # Close the temporary session
                 except Exception as final_fail_e:
                     # Log errors occurring during the failure marking process itself
                     logger.error(f"Further error during root chain failure marking: {final_fail_e}")

            # Re-raise the exception as a RuntimeError to signal failure to the caller
            raise RuntimeError(f"Ingestion failed for {repo_url}") from e
        finally:
            # The main session 'db' closure is handled by the caller (e.g., the API endpoint or task runner)
            pass

        return root_chain