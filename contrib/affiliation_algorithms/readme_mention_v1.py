"""
contrib.affiliation_algorithms.readme_mention_v1
------------------------------------------------

This script implements an affiliation algorithm that attempts to link
repositories to institutions by searching for specific keywords within the
content of README files. It fetches README content for repositories stored in the
MOSS database using the GitHub API and assigns a confidence score if matches are found.
"""

import sys
import os
import logging
import re # Import regular expression module for keyword matching
from pathlib import Path
from typing import List, Dict, Any, Set

# --- Path Setup ---
# Determine the project root directory relative to this script's location
# and add it to the system path if necessary. This allows importing modules
# from the main backend application, like data models and the GitHub client.
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
# Import necessary MOSS models and the GitHub client.
from backend.data.models import Repository
from backend.external import GitHubClient, ApiClientError
# Import settings to check for token availability for logging purposes.
from backend.config import settings

# --- Logging Setup ---
# Configure basic logging for the script to report progress, findings,
# and potential issues like API errors or missing tokens.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [readme_mention_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# --- Check for GitHub Token ---
# Log a warning if the GitHub API token doesn't seem to be configured in the
# application settings, as this will likely lead to rate limiting or failures.
if not settings.GITHUB_API_TOKEN:
    logger.warning("GITHUB_API_TOKEN environment variable not found by settings module.")
    logger.warning("GitHub API calls in readme_mention_v1 may fail or be severely rate-limited due to missing authentication.")
# --- End Token Check ---

def calculate_affiliations(
    institution_id: int, # Included for context and consistency with algorithm signature.
    keywords: List[str],
    db_conn_str: str
) -> List[Dict[str, Any]]:
    """
    Identifies potential repository-institution affiliations based on keyword mentions in READMEs.

    This function executes the following steps:
    1. Initializes database connection and GitHub API client.
    2. Prepares keywords for case-insensitive matching using regular expressions.
    3. Fetches IDs and full names of all repositories from the MOSS database.
       (Note: This might be performance-intensive on very large databases).
    4. Iterates through each repository:
        a. Attempts to fetch the content of common README file variants (e.g., README.md, README.rst)
           using the GitHub API client. Handles potential API errors (404 Not Found, 403 Forbidden/Rate Limit).
        b. If README content is successfully retrieved, searches the content for any of the
           provided keywords using case-insensitive, whole-word matching regex.
        c. If one or more keywords are found, creates an affiliation record for the repository
           with a predefined confidence score and evidence detailing the matched keywords and file.
    5. Returns a list of all affiliation records found.

    Args:
        institution_id: The database ID of the institution (used for logging context).
        keywords: A list of strings representing the keywords to search for within README files.
        db_conn_str: The SQLAlchemy database connection string.

    Returns:
        A list of dictionaries, each representing a potential affiliation.
        Structure per dictionary:
        {
            "repository_id": int,
            "confidence_score": float (fixed score, e.g., 0.5),
            "evidence": {
                "signal_type": "readme_mention",
                "matched_keywords": List[str], # Unique keywords found
                "readme_file": str # Path of the README file where match occurred
            }
        }
        Returns an empty list if no keywords are provided, no matches are found,
        or a critical error occurs. May return a list containing error details
        if initialization fails.
    """
    logger.info(f"Starting readme_mention_v1 for Institution ID {institution_id} with keywords: {keywords}")
    if not keywords:
        logger.warning("No keywords provided for README search, returning empty list.")
        return []

    # --- Initialize Clients and DB ---
    engine = None
    db: Session | None = None
    github_client: GitHubClient | None = None
    results_list: List[Dict[str, Any]] = []
    # Define a fixed confidence score for affiliations found via README mention.
    # This score reflects the heuristic nature of keyword matching in text.
    CONFIDENCE_SCORE = 0.5

    # Prepare keywords for efficient, case-insensitive regex matching.
    # Create a list of lowercase keywords.
    lower_keywords = [kw.lower() for kw in keywords]
    # Compile a single regex pattern to find any of the keywords as whole words (\b).
    # re.escape handles special characters in keywords. re.IGNORECASE makes it case-insensitive.
    try:
        keyword_pattern = re.compile(r'\b(' + '|'.join(map(re.escape, lower_keywords)) + r')\b', re.IGNORECASE)
    except re.error as regex_err:
        logger.error(f"Failed to compile keyword regex: {regex_err}. Keywords: {keywords}")
        return [{"error": "RegexCompilationError", "message": str(regex_err)}]

    try:
        # Instantiate GitHub Client. This relies on the environment or settings for authentication.
        try:
             github_client = GitHubClient()
        except ValueError as e:
             # Handle failure to initialize client (e.g., missing token in settings).
             logger.error(f"Failed to initialize GitHubClient, likely missing token: {e}")
             # Return an error structure indicating the failure.
             return [{"error": "GitHub Client Initialization Failed", "message": str(e)}]

        # Establish database connection.
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Step 1: Get all repository IDs and full_names from the database.
        # Performance consideration: Fetching all repositories might be slow for large datasets.
        # Future optimization could involve filtering repositories based on certain criteria.
        repo_stmt = select(Repository.id, Repository.full_name)
        all_repos = db.execute(repo_stmt).mappings().all() # Fetch as dictionary-like mappings
        total_repos = len(all_repos)
        logger.info(f"Found {total_repos} repositories in the database to check for README mentions.")

        # Counters for tracking progress and issues during processing.
        processed_count = 0
        found_count = 0
        api_error_count = 0
        # List of common README filenames to check for each repository.
        readme_files_to_check = ["README.md", "README", "README.rst", "README.txt"] # Added .txt

        # Step 2: Iterate through each repository and check its README.
        for repo_data in all_repos:
            processed_count += 1
            repo_id = repo_data['id']
            full_name = repo_data['full_name']

            # Basic validation of the repository's full name format.
            if not full_name or '/' not in full_name:
                 logger.warning(f"Skipping repo ID {repo_id} due to invalid full_name format: '{full_name}'")
                 continue

            # Log progress periodically.
            if processed_count % 100 == 0:
                 logger.info(f"Processed {processed_count}/{total_repos} repositories...")

            # Extract owner and repo name from the full name.
            try:
                owner, repo_name_only = full_name.split('/', 1)
            except ValueError:
                 logger.warning(f"Skipping repo ID {repo_id} due to unexpected full_name format: '{full_name}'")
                 continue

            readme_content: str | None = None # To store fetched README content
            fetched_readme_path: str | None = None # To store the path of the found README

            # Attempt to fetch content from common README file locations.
            for readme_path in readme_files_to_check:
                try:
                    # Use the GitHub client to get file content.
                    logger.debug(f"Attempting to fetch {readme_path} for {full_name}")
                    # get_file_content should return the decoded content or None/raise error.
                    content_maybe = github_client.get_file_content(owner, repo_name_only, readme_path)

                    if content_maybe:
                        readme_content = content_maybe
                        fetched_readme_path = readme_path
                        logger.debug(f"Successfully fetched content from {readme_path} for {full_name}")
                        break # Found a README, no need to check other variants for this repo.

                except ApiClientError as e:
                    # Handle specific API errors gracefully.
                    if e.status_code == 404:
                        # Common case: the specific README file variant doesn't exist.
                        logger.debug(f"{readme_path} not found for {full_name} (404).")
                    elif e.status_code == 403:
                         # Potential rate limit or permission issue. Log a warning.
                         logger.warning(f"Access denied (403) fetching {readme_path} for {full_name}. Rate limit or permissions issue?")
                         api_error_count += 1
                         # Consider breaking the inner loop (variants) or outer loop (repos) on repeated 403s.
                    else:
                        # Log other unexpected API errors.
                        logger.error(f"API Error {e.status_code} fetching {readme_path} for {full_name}: {e}")
                        api_error_count += 1
                except Exception as e:
                    # Catch any other unexpected errors during file fetching.
                    # Log minimally to avoid flooding logs, but indicate the error.
                    logger.error(f"Unexpected error fetching {readme_path} for {full_name}: {type(e).__name__}", exc_info=False)
                    api_error_count += 1
                    # Stop checking variants for this repo if an unexpected error occurs.
                    break

            # Step 3: If README content was successfully fetched, check it for keywords.
            if readme_content:
                try:
                    # Use the pre-compiled regex pattern to find all keyword occurrences.
                    found_matches = keyword_pattern.findall(readme_content)
                    if found_matches:
                        # Extract unique matched keywords (case-insensitive) for the evidence record.
                        unique_matches = {match.lower() for match in found_matches}
                        logger.info(f"Found keyword match(es): {list(unique_matches)} in '{fetched_readme_path}' for repo {repo_id} ({full_name})")

                        # Structure the evidence for this affiliation finding.
                        evidence = {
                            "signal_type": "readme_mention",
                            "matched_keywords": sorted(list(unique_matches)), # Store unique matches alphabetically
                            "readme_file": fetched_readme_path
                        }
                        # Append the affiliation result to the list.
                        results_list.append({
                            "repository_id": repo_id,
                            "confidence_score": CONFIDENCE_SCORE,
                            "evidence": evidence
                        })
                        found_count += 1
                except Exception as parse_err:
                     logger.error(f"Error processing README content for repo {repo_id} ({full_name}): {parse_err}", exc_info=False)


    except Exception as e:
        # Catch critical errors during the overall process (e.g., database connection failure).
        logger.exception(f"Critical error during readme_mention_v1 execution: {e}")
        # Return an error structure if the entire process fails.
        return [{"error": type(e).__name__, "message": str(e)}]
    finally:
        # Ensure database and potentially client resources are cleaned up.
        if db:
            db.close()
            logger.info("Database session closed.")
        if engine:
            engine.dispose()
            logger.info("Database engine disposed.")
        # Note: GitHubClient session cleanup might be handled within the client itself upon garbage collection.

    logger.info(f"Readme_mention_v1 finished for Inst {institution_id}. Found {found_count} affiliations. API errors encountered: {api_error_count}.")
    return results_list

# --- Example Test Call Block ---
# For development/testing. Requires DATABASE_URL and GITHUB_API_TOKEN environment
# variables and relevant data in the database.
#
# if __name__ == "__main__":
#     TEST_DB_CONN_STR = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")
#     TEST_INST_ID = 1 # Example institution ID (for context)
#     TEST_KEYWORDS = ["university", "research", "institute", "python library"] # Example keywords
#
#     if not TEST_DB_CONN_STR or "user:password" in TEST_DB_CONN_STR:
#         print("Error: DATABASE_URL environment variable not set or using default.", file=sys.stderr)
#     elif not settings.GITHUB_API_TOKEN:
#          print("Error: GITHUB_API_TOKEN environment variable not set; testing requires API access.", file=sys.stderr)
#     else:
#         print(f"Running test for Inst ID: {TEST_INST_ID}, Keywords: {TEST_KEYWORDS}")
#         affiliations = calculate_affiliations(TEST_INST_ID, TEST_KEYWORDS, TEST_DB_CONN_STR)
#         print("\nResults:")
#         import json
#         print(json.dumps(affiliations, indent=2))
# --- End Example Test Call Block ---