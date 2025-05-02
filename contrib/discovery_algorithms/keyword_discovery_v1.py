"""
contrib.discovery_algorithms.keyword_discovery_v1
-------------------------------------------------

This script provides functionality to discover potential candidate repositories
on GitHub based on a list of provided keywords. It utilizes the GitHub API
for searching repositories and returns a list of their URLs.
"""

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Path Setup ---
# Determine the project root directory relative to this script's location
# and add it to the system path if necessary. This allows importing modules
# from the main backend application, such as the GitHub client.
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

# Import MOSS components for interacting with external services.
from backend.external import GitHubClient, ApiClientError

# --- Logging Setup ---
# Configure basic logging for the script to provide visibility into the
# discovery process, including search parameters and results.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [discovery_kw_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def find_candidate_repos(
    keywords: List[str],
    max_results: int = 100,
    github_api_token: Optional[str] = None, # Allow passing a specific token
    # db_conn_str is part of the standard runner signature but not used here.
    db_conn_str: Optional[str] = None
) -> List[str]:
    """
    Searches GitHub for repositories matching a given set of keywords.

    Constructs a search query from the keywords and uses the GitHubClient
    to perform the search. Handles authentication using a provided API token
    or falls back to anonymous requests (which are heavily rate-limited).

    Args:
        keywords: A list of strings to use as keywords for the GitHub search query.
        max_results: The maximum number of repository URLs to retrieve (default: 100).
        github_api_token: An optional GitHub Personal Access Token (PAT) for
                          authenticated API requests, increasing rate limits.
                          If None, anonymous access is used.
        db_conn_str: Database connection string (unused in this function).

    Returns:
        A list of strings, where each string is the HTML URL of a repository
        found matching the keywords. Returns an empty list if no keywords are
        provided, no results are found, or an error occurs during the search.
    """
    if not keywords:
        logger.warning("No keywords provided for discovery. Aborting search.")
        return []

    # Construct the search query by joining keywords.
    query = " ".join(keywords)
    logger.info(f"Starting GitHub discovery search with query: '{query}', max_results: {max_results}")

    # Instantiate the GitHub API client.
    # This might raise ValueError if base configuration (e.g., settings) is invalid.
    try:
        github_client = GitHubClient()
    except ValueError as e:
        logger.error(f"Failed to initialize GitHubClient: {e}. Check base configuration or token availability.")
        # Cannot proceed without a client instance.
        return []

    # --- Prepare Headers with Provided Token ---
    # Start with default headers from the client instance (might include base auth).
    request_headers = github_client.auth_headers.copy()
    if github_api_token:
        # If a specific token is provided for this run, use it.
        logger.info("Using provided GitHub API token for authentication.")
        request_headers["Authorization"] = f"Bearer {github_api_token}"
    else:
        # If no specific token is provided, log a warning about rate limits.
        # Ensure anonymous request by removing any default Authorization header.
        logger.warning("No GitHub API token provided to discovery algorithm. Search will be anonymous and heavily rate-limited.")
        if "Authorization" in request_headers:
            del request_headers["Authorization"]
    # --- End Header Prep ---


    repo_urls: List[str] = []
    try:
        # Perform the repository search via the GitHub client.
        # Note: The original implementation included a workaround for potentially
        # passing headers. Ideally, the client's request method should handle
        # custom headers per call. Assuming the workaround is necessary based on
        # the client's implementation details at the time of writing.

        # --- TEMPORARY WORKAROUND for header override ---
        # Store original session headers.
        original_headers = github_client.session.headers.copy()
        # Temporarily update session headers with the prepared ones for this call.
        github_client.session.headers.update(request_headers)
        # Execute the search using the modified session headers.
        search_result_tuple = github_client.search_repositories(query=query, max_results=max_results)
        # Restore the original headers to avoid affecting subsequent uses of the client instance.
        github_client.session.headers = original_headers
        # --- END TEMPORARY WORKAROUND ---

        if search_result_tuple:
            # The search returns a tuple: (items, total_count). We only need items here.
            items, _ = search_result_tuple
            for item in items:
                # Extract the HTML URL for each repository found.
                url = item.get("html_url")
                if url:
                    repo_urls.append(url)
            logger.info(f"Discovery search completed. Found {len(repo_urls)} candidate repository URLs.")
        else:
            # Handle cases where the API call succeeded but returned no items.
            logger.warning("Repository search returned no results or failed to retrieve items.")

    except ApiClientError as e:
        # Handle specific errors raised by the GitHub client (e.g., rate limits, auth errors).
        logger.error(f"API client error during GitHub discovery search: {e}")
        # Return empty list on client errors to indicate failure.
        return []
    except Exception as e:
        # Catch any other unexpected exceptions during the process.
        logger.exception("Unexpected error during GitHub discovery search execution.")
        # Return empty list on unexpected errors.
        return []

    return repo_urls

# --- Example Test Call Block ---
# This section is intended for development or testing purposes.
# It demonstrates how to call the function directly, typically requiring
# environment variables like GITHUB_API_TOKEN to be set for authenticated runs.
#
# if __name__ == "__main__":
#     test_keywords = ["open", "science", "python", "data"]
#     # Example: Attempt to load a token from environment variables for testing.
#     test_token = os.getenv("GITHUB_API_TOKEN")
#
#     print(f"Running test discovery for keywords: {test_keywords}")
#     if not test_token:
#         print("Warning: GITHUB_API_TOKEN environment variable not set for testing. Using anonymous search.")
#
#     candidate_urls = find_candidate_repos(
#         keywords=test_keywords,
#         max_results=20,
#         github_api_token=test_token # Pass the token if available
#     )
#
#     print("\nCandidate URLs Found:")
#     if candidate_urls:
#         for url in candidate_urls:
#             print(f"- {url}")
#     else:
#         print("None found or an error occurred during the search.")
# --- End Example Test Call Block ---