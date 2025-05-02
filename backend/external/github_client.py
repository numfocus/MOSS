"""
backend.external.github_client

Provides a client for interacting with the GitHub REST API (v3). This client
builds upon the `ClientBase` to handle HTTP requests, authentication, and
rate limiting, while offering specific methods for accessing GitHub resources
like repository metadata, contributors, file contents, search, pull requests,
issues, and comments. It handles pagination for endpoints that return multiple
results.
"""

import logging
import base64
import binascii
import requests
import re # Used for parsing Link headers
from typing import Optional, List, Dict, Any, Tuple

# Import base client and custom errors
from .client_base import ClientBase, ApiClientError

logger = logging.getLogger(__name__)

class GitHubClient(ClientBase):
    """
    Client for the GitHub REST API v3.

    Handles authentication using a personal access token (PAT) provided via
    settings (`GITHUB_API_TOKEN`). Implements methods for common GitHub API
    interactions, including automatic pagination handling for list endpoints.
    Leverages `ClientBase` for underlying request execution, retries, and
    rate limit handling.
    """
    def __init__(self):
        """
        Initializes the GitHubClient.

        Sets the base URL for the GitHub API and configures authentication
        headers using the token from application settings.

        Raises:
            ValueError: If `GITHUB_API_TOKEN` is not found in the settings.
        """
        super().__init__(base_url="https://api.github.com")
        self.token = self.settings.GITHUB_API_TOKEN
        if not self.token:
            logger.error("GITHUB_API_TOKEN is not configured in settings. GitHubClient requires a token.")
            raise ValueError("GitHub API token is required but not set.")
        # Prepare authentication and API version headers for GitHub requests
        self.auth_headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json", # Request standard JSON format
            "X-GitHub-Api-Version": "2022-11-28",      # Pin to a specific API version
        }
        logger.info("GitHubClient initialized successfully.")

    def _parse_link_header(self, headers: requests.structures.CaseInsensitiveDict) -> Dict[str, str]:
        """
        Parses the 'Link' HTTP header returned by GitHub API pagination responses.

        Extracts URLs for related pages (like 'next', 'last', 'first', 'prev')
        into a dictionary.

        Example Link header: '<url1>; rel="next", <url2>; rel="last"'

        Args:
            headers: A dictionary-like object representing the response headers
                     (case-insensitive recommended, like `requests.Response.headers`).

        Returns:
            A dictionary where keys are relationship types ('next', 'last', etc.)
            and values are the corresponding URLs. Returns an empty dictionary
            if the 'Link' header is not present or cannot be parsed.
        """
        links = {}
        link_header = headers.get('Link')
        if link_header:
            # Split the header into individual link parts (separated by commas)
            parts = link_header.split(',')
            for part in parts:
                # Use regex to extract the URL and the relation type ('rel')
                match = re.match(r'<\s*(.*?)\s*>;\s*rel="?(\w+)"?', part.strip())
                if match:
                    url, rel = match.groups()
                    links[rel] = url
        return links

    def _fetch_paginated_results(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all results from a paginated GitHub API endpoint.

        Automatically follows 'next' links provided in the 'Link' header
        until all pages have been fetched. Sets 'per_page' to 100 (maximum)
        to minimize the number of requests.

        Args:
            endpoint: The relative API endpoint path (e.g., '/repos/owner/repo/issues').
            params: Optional dictionary of initial query parameters for the first request.
                    The 'per_page' parameter will be added or overwritten.

        Returns:
            A list containing all items fetched across all pages.

        Raises:
            ApiClientError: If an API request fails (after retries) during
                            pagination, or if the response format is unexpected.
        """
        if params is None:
            params = {}
        params["per_page"] = 100 # Request the maximum number of items per page

        all_items: List[Dict[str, Any]] = []
        # Start with the initial endpoint URL constructed from the base URL
        current_url: Optional[str] = self._construct_url(endpoint)
        page_num = 1

        while current_url:
            logger.debug(f"Fetching page {page_num} for endpoint '{endpoint}' from URL: {current_url}")
            try:
                # Make the request. For subsequent pages (page_num > 1),
                # current_url is an absolute URL from the Link header, so pass
                # endpoint=current_url and params=None. For the first page,
                # pass the relative endpoint and initial params.
                response = self._request(
                    "GET",
                    current_url,
                    params=params if page_num == 1 else None,
                    headers=self.auth_headers
                )

                # Handle specific non-OK statuses during pagination
                if response.status_code == 404:
                     logger.warning(f"Endpoint not found (404) during pagination: {current_url}. Stopping pagination.")
                     break # Stop if the resource disappears mid-fetch

                # Let ClientBase._request handle retries for 429/5xx.
                # If we get here and it's not OK, it's likely a persistent issue.
                elif not response.ok:
                    logger.error(f"GitHub API error fetching paginated results (page {page_num}, URL: {current_url}). Status: {response.status_code}, Response: {response.text[:200]}")
                    # Raise an error to signal failure to the caller
                    raise ApiClientError(f"Failed to fetch page {page_num} from {endpoint}", status_code=response.status_code)

                try:
                    page_data = response.json()
                    # Expect a list of items from paginated endpoints
                    if not isinstance(page_data, list):
                        logger.error(f"Unexpected response format (expected list, got {type(page_data)}) for paginated results: {current_url}. Response: {str(page_data)[:200]}")
                        raise ApiClientError(f"Unexpected response format from {endpoint}", status_code=response.status_code)

                    all_items.extend(page_data)
                    logger.debug(f"Fetched {len(page_data)} items on page {page_num}. Total items so far: {len(all_items)}")

                    # Parse the Link header to find the URL for the next page
                    links = self._parse_link_header(response.headers)
                    current_url = links.get("next") # Will be None if no 'next' link

                    if current_url:
                        page_num += 1
                    else:
                        logger.debug(f"No 'next' link found. Reached end of results for {endpoint}.")

                except requests.exceptions.JSONDecodeError as json_err:
                    logger.error(f"Failed to decode JSON response from {current_url} (page {page_num}): {json_err}", exc_info=True)
                    raise ApiClientError(f"Failed to decode JSON from {endpoint}", status_code=response.status_code) from json_err

            except ApiClientError as e:
                 # Propagate API client errors (connection, timeout after retries, etc.)
                 logger.error(f"API Client error during pagination for {endpoint} (page {page_num}): {e}")
                 raise e
            except Exception as e:
                 # Catch any other unexpected errors during the loop
                 logger.exception(f"Unexpected error during pagination fetch for {endpoint} (page {page_num})")
                 # Wrap in ApiClientError for consistent error handling upstream
                 raise ApiClientError(f"Unexpected error during pagination for {endpoint}: {e}") from e

        logger.info(f"Finished fetching paginated results for {endpoint}. Total items retrieved: {len(all_items)}")
        return all_items

    def get_repository_metadata(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a specific GitHub repository.

        Args:
            owner: The login name of the repository owner (user or organization).
            repo: The name of the repository.

        Returns:
            A dictionary containing the repository metadata, or None if the
            repository is not found (404) or another error occurs.

        Raises:
            ValueError: If owner or repo is empty.
            ApiClientError: If access is forbidden (403) or if a request fails
                            after retries.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name cannot be empty.")
        endpoint = f"/repos/{owner}/{repo}"
        logger.info(f"Fetching metadata for repository: {owner}/{repo}")
        try:
            response = self._request("GET", endpoint, headers=self.auth_headers)

            if response.status_code == 404:
                logger.warning(f"Repository not found: {owner}/{repo} (404)")
                return None
            elif response.status_code == 403:
                 logger.error(f"Access forbidden for repository: {owner}/{repo} (403). Check token permissions or rate limits.")
                 # Raise a specific error for auth/permission issues
                 raise ApiClientError(f"Access forbidden for repository {owner}/{repo} (403). Check token permissions.", status_code=403)
            elif not response.ok:
                # Log other non-404, non-403 errors but return None for now
                logger.error(f"Failed to get repository metadata for {owner}/{repo}. Status: {response.status_code}, Response: {response.text[:200]}")
                return None # Or consider raising ApiClientError for unexpected non-ok statuses

            # Attempt to parse JSON only if the request was successful
            return response.json()

        except requests.exceptions.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON response for {owner}/{repo} metadata: {json_err}", exc_info=True)
            return None # Return None on decode error
        except ApiClientError: # Catch client errors raised by _request or the 403 block
            raise # Re-raise client errors
        except Exception as e:
             # Catch any other unexpected errors during processing
             logger.exception(f"Unexpected error processing repository metadata for {owner}/{repo}")
             raise # Re-raise unexpected errors

    def get_contributors(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        Fetches the list of contributors for a specific repository.

        Note: Currently retrieves only the first page (up to 100 contributors)
        for simplicity. Pagination is not yet implemented for this specific method.

        Args:
            owner: The login name of the repository owner.
            repo: The name of the repository.

        Returns:
            A list of dictionaries, each representing a contributor, or an
            empty list if the repository is not found or an error occurs.

        Raises:
            ValueError: If owner or repo is empty.
            ApiClientError: If access is forbidden (403) or if a request fails
                            after retries.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name cannot be empty.")
        endpoint = f"/repos/{owner}/{repo}/contributors"
        # Parameters to fetch maximum per page and exclude anonymous contributors
        params = {"per_page": 100, "anon": "false"}
        logger.info(f"Fetching contributors (first page) for repository: {owner}/{repo}")
        try:
            # Fetch only the first page for now
            response = self._request("GET", endpoint, headers=self.auth_headers, params=params)

            if response.status_code == 404:
                logger.warning(f"Repository not found when fetching contributors: {owner}/{repo} (404)")
                return []
            elif response.status_code == 403:
                 logger.error(f"Access forbidden for contributors: {owner}/{repo} (403).")
                 raise ApiClientError(f"Access forbidden for contributors {owner}/{repo} (403). Check token permissions.", status_code=403)
            elif not response.ok:
                logger.error(f"Failed to get contributors for {owner}/{repo}. Status: {response.status_code}, Response: {response.text[:200]}")
                return [] # Return empty list on other errors for now

            contributors = response.json()
            # Ensure the response is a list as expected
            return contributors if isinstance(contributors, list) else []

        except requests.exceptions.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON response for {owner}/{repo} contributors: {json_err}", exc_info=True)
            return []
        except ApiClientError:
            raise # Re-raise client errors
        except Exception as e:
             logger.exception(f"Unexpected error processing contributors for {owner}/{repo}")
             raise # Re-raise unexpected errors

    def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        Fetches the content of a specific file from a repository.

        Handles base64 encoded content returned by the GitHub API and decodes it.
        Attempts UTF-8 decoding first, then falls back to latin-1 if needed.

        Args:
            owner: The login name of the repository owner.
            repo: The name of the repository.
            path: The full path to the file within the repository.

        Returns:
            The decoded content of the file as a string, or None if the file
            is not found, the path points to a directory, decoding fails,
            or another error occurs.

        Raises:
            ValueError: If owner, repo, or path is empty, or if base64 decoding fails.
            ApiClientError: If access is forbidden (403) or if a request fails
                            after retries.
        """
        if not owner or not repo or not path:
            raise ValueError("Owner, repository name, and file path cannot be empty.")
        endpoint = f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}"
        logger.info(f"Fetching file content for: {owner}/{repo}/{path}")
        try:
            # Use a slightly longer timeout for potentially large file content
            response = self._request("GET", endpoint, headers=self.auth_headers, timeout=45)

            if response.status_code == 404:
                logger.warning(f"File or repository not found: {owner}/{repo}/{path} (404)")
                return None
            elif response.status_code == 403:
                 logger.error(f"Access forbidden for file content: {owner}/{repo}/{path} (403).")
                 raise ApiClientError(f"Access forbidden for file content {owner}/{repo}/{path} (403).", status_code=403)
            elif not response.ok:
                 # Log other non-404, non-403 errors
                 logger.error(f"HTTP error {response.status_code} fetching file content for {owner}/{repo}/{path}: {response.text[:200]}")
                 return None # Return None for now

            try:
                file_data = response.json()
            except requests.exceptions.JSONDecodeError as json_err:
                # Handle cases where the response is not valid JSON
                logger.error(f"Failed to decode JSON response for file {owner}/{repo}/{path}: {json_err}", exc_info=True)
                logger.debug(f"Response text causing decode error: {response.text[:500]}")
                return None

            # Check if the response indicates a directory listing instead of file content
            if isinstance(file_data, list) or (isinstance(file_data, dict) and file_data.get('type') == 'dir'):
                logger.warning(f"Path provided points to a directory, not a file: {owner}/{repo}/{path}")
                return None
            # Ensure the response is a dictionary for file content
            if not isinstance(file_data, dict):
                 logger.error(f"Unexpected response format (not a dict/list) for file content: {owner}/{repo}/{path}. Got {type(file_data)}")
                 return None

            encoding = file_data.get("encoding")
            content = file_data.get("content") # Base64 encoded string or potentially null

            if encoding == "base64":
                if not content or not isinstance(content, str):
                    logger.warning(f"Expected base64 content string, but found none or invalid type for {owner}/{repo}/{path}")
                    return None
                try:
                    # Decode the base64 string into bytes
                    decoded_bytes = base64.b64decode(content)
                    try:
                        # Try decoding bytes as UTF-8 first
                        return decoded_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        # Fallback to latin-1 if UTF-8 fails (common for some legacy files)
                        logger.warning(f"UTF-8 decoding failed for {owner}/{repo}/{path}. Attempting latin-1 decoding.")
                        return decoded_bytes.decode("latin-1")
                except (binascii.Error, ValueError) as decode_error:
                    # Handle errors during base64 decoding itself
                    logger.error(f"Base64 decoding failed for {owner}/{repo}/{path}: {decode_error}")
                    # Raise a specific error indicating decoding failure
                    raise ValueError(f"Failed to decode base64 content for file {path}") from decode_error

            elif content is not None:
                 # Handle cases where encoding is not base64 (e.g., 'none' or potentially others)
                 # Treat the content as a plain string if available.
                 logger.info(f"File {owner}/{repo}/{path} has encoding '{encoding}'. Returning content directly.")
                 return str(content)
            else:
                 # Handle cases where content is missing or null
                 logger.warning(f"No content found (encoding: {encoding}) in response for {owner}/{repo}/{path}")
                 return None

        except ApiClientError:
            raise # Re-raise client-level errors
        except ValueError as ve:
             # Catch the ValueError raised by decoding failure
             logger.error(f"Data processing error for file {owner}/{repo}/{path}: {ve}", exc_info=False)
             raise ve # Re-raise the specific ValueError
        except Exception as e:
             # Catch any other unexpected errors
             logger.exception(f"Unexpected error fetching file content for {owner}/{repo}/{path}")
             raise # Re-raise unexpected errors

    def search_repositories(
        self, query: str, max_results: int = 1000
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """
        Searches for GitHub repositories matching a given query.

        Uses the GitHub Search API and handles pagination. Note that the GitHub
        API limits search results to the first 1000 items, regardless of the
        actual total count. This method respects both the `max_results` parameter
        and the GitHub API limit.

        Args:
            query: The search query string (e.g., 'language:python stars:>1000').
                   See GitHub search syntax documentation.
            max_results: The maximum number of repository results to retrieve.
                         Capped at 1000 due to GitHub API limitations.

        Returns:
            A tuple containing:
            - A list of dictionaries, each representing a found repository.
            - An integer representing the total number of repositories GitHub
              reported for the query (which might be > 1000).
            Returns None if the query is invalid (422) or a significant error occurs.

        Raises:
            ValueError: If the query string is empty.
            ApiClientError: If access is forbidden (403) or if a request fails
                            after retries.
        """
        if not query:
            raise ValueError("Search query cannot be empty.")

        endpoint = "/search/repositories"
        page = 1
        per_page = 100 # Use max allowed per page by GitHub API
        all_items = []
        total_count = 0
        # GitHub Search API limitation: only first 1000 results are accessible
        github_max_results = 1000
        # Calculate max pages needed based on GitHub limit, not total_count
        max_pages = (github_max_results + per_page - 1) // per_page # Typically 10 pages

        # Adjust max_results if it exceeds the GitHub limit
        effective_max_results = min(max_results, github_max_results)
        logger.info(f"Searching repositories with query: '{query}'. Target results: {max_results}, Effective limit: {effective_max_results}")

        next_url: Optional[str] = None # Store the next page URL from Link header

        # Loop until we reach the desired number of results, the GitHub limit,
        # or run out of pages.
        while len(all_items) < effective_max_results and page <= max_pages:
            # Prepare parameters only for the first request or if not using next_url
            params = None
            if not next_url:
                 params = {
                    "q": query,
                    "page": page,
                    "per_page": per_page,
                }

            # Use the absolute URL from 'next' link if available, otherwise use the base endpoint
            current_url = next_url if next_url else self._construct_url(endpoint)
            request_endpoint = next_url if next_url else endpoint # Use for logging clarity

            logger.debug(f"Fetching search results page {page} for query '{query}' (URL: {current_url})")

            try:
                response = self._request(
                    "GET",
                    request_endpoint, # Pass relative endpoint or absolute URL
                    params=params,    # Pass params only if not using next_url
                    headers=self.auth_headers
                )

                # Handle specific error codes for search API
                if response.status_code == 403:
                    # Could be rate limits, token issues, or abuse detection
                    logger.error(f"Access forbidden (403) during repository search (page {page}, query='{query}'). Check token, rate limits, or potential abuse flags.")
                    raise ApiClientError(f"Access forbidden during repository search (page {page}).", status_code=403)
                elif response.status_code == 422:
                    # Often indicates an invalid or unprocessable search query
                    logger.error(f"Unprocessable search query '{query}' (page {page}). Status: 422. Response: {response.text[:200]}")
                    return None # Cannot proceed with an invalid query
                elif not response.ok:
                    # Handle other unexpected non-ok statuses
                    logger.error(f"GitHub API error searching repositories (page {page}, query='{query}'). Status: {response.status_code}, Response: {response.text[:200]}")
                    # Fail the search for now, could potentially return partial results
                    return None

                try:
                    data = response.json()
                    page_items = data.get("items", [])

                    # Validate the structure of the response
                    if not isinstance(page_items, list):
                        logger.error(f"Unexpected 'items' format in search response (page {page}, expected list, got {type(page_items)}).")
                        return None # Cannot process invalid format

                    # Get the total count from the first page's response only
                    if page == 1:
                        total_count = data.get("total_count", 0)
                        incomplete_results = data.get("incomplete_results", False)
                        logger.info(f"GitHub reported total_count: {total_count} for query '{query}'. Incomplete results: {incomplete_results}")
                        # Check if total_count exceeds GitHub's accessible limit
                        if total_count > github_max_results:
                             logger.warning(f"Query '{query}' has {total_count} results, but GitHub API only allows access to the first {github_max_results}.")

                    # Add items from the current page, respecting the effective_max_results limit
                    num_needed = effective_max_results - len(all_items)
                    items_to_add = page_items[:num_needed]
                    all_items.extend(items_to_add)

                    logger.debug(f"Fetched {len(page_items)} items on page {page}. Added {len(items_to_add)}. Total items collected: {len(all_items)}")

                    # Check if we've reached the limit
                    if len(all_items) >= effective_max_results:
                         logger.info(f"Reached effective result limit ({effective_max_results} items). Stopping pagination.")
                         break # Exit loop

                    # --- Pagination Logic ---
                    links = self._parse_link_header(response.headers)
                    next_url = links.get("next")

                    if not next_url:
                        logger.debug("No 'next' link found in header. Reached end of accessible results.")
                        break # Exit loop if no more pages are available

                    page += 1 # Increment page number for the next iteration

                except requests.exceptions.JSONDecodeError as json_err:
                     logger.error(f"Failed to decode JSON search response (page {page}): {json_err}", exc_info=True)
                     return None # Cannot proceed if JSON is invalid

            except ApiClientError as api_err:
                # Propagate client-level errors (connection, timeout, 403, etc.)
                logger.error(f"API client error during search pagination (page {page}): {api_err}")
                raise
            except Exception as e:
                # Catch any other unexpected errors
                logger.exception(f"Unexpected error during search pagination (page {page})")
                raise # Propagate unexpected errors

        logger.info(f"Finished repository search for '{query}'. Fetched {len(all_items)} items across {page if not next_url else page-1} pages. GitHub total count: {total_count}.")
        # Return the aggregated list and the total count reported by GitHub
        return all_items, total_count

    def get_pull_requests(self, owner: str, repo: str, state: str = 'all', per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches pull requests for a repository, handling pagination.

        Args:
            owner: The login name of the repository owner.
            repo: The name of the repository.
            state: Filter PRs by state ('open', 'closed', or 'all'). Defaults to 'all'.
            per_page: Number of items to fetch per page (max 100). Passed to pagination helper.

        Returns:
            A list of dictionaries, each representing a pull request.

        Raises:
            ValueError: If owner or repo is empty.
            ApiClientError: If the request fails after retries.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name cannot be empty.")
        endpoint = f"/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": per_page, "sort": "created", "direction": "desc"}
        logger.info(f"Fetching pull requests for {owner}/{repo} (state={state})...")
        try:
            # Use the generic pagination helper
            all_prs = self._fetch_paginated_results(endpoint, params)
            return all_prs
        except ApiClientError as e:
            # Log the error specific to this operation before re-raising
            logger.error(f"Failed to fetch pull requests for {owner}/{repo}: {e}")
            raise e # Re-raise the error for upstream handling

    def get_issues(self, owner: str, repo: str, state: str = 'all', per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches issues for a repository, handling pagination.
        Note: This fetches both issues and pull requests, as GitHub treats
              pull requests as a type of issue via this endpoint.

        Args:
            owner: The login name of the repository owner.
            repo: The name of the repository.
            state: Filter issues by state ('open', 'closed', or 'all'). Defaults to 'all'.
            per_page: Number of items to fetch per page (max 100). Passed to pagination helper.
                   Consider adding a 'since' parameter for incremental fetching.

        Returns:
            A list of dictionaries, each representing an issue or pull request.

        Raises:
            ValueError: If owner or repo is empty.
            ApiClientError: If the request fails after retries.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name cannot be empty.")
        endpoint = f"/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": per_page, "sort": "created", "direction": "desc"}
        logger.info(f"Fetching issues (and PRs) for {owner}/{repo} (state={state})...")
        try:
            # Use the generic pagination helper
            all_issues = self._fetch_paginated_results(endpoint, params)
            return all_issues
        except ApiClientError as e:
            logger.error(f"Failed to fetch issues for {owner}/{repo}: {e}")
            raise e # Re-raise the error

    # --- Methods for Fetching Comments ---

    def get_issue_comments(self, owner: str, repo: str, issue_number: Optional[int] = None, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches comments on issues within a repository, handling pagination.

        Can fetch comments for a single specific issue or for all issues in the
        repository. Comments are fetched sorted by creation date (ascending).

        Args:
            owner: The login name of the repository owner.
            repo: The name of the repository.
            issue_number: If provided, fetches comments only for this specific issue number.
                          If None (default), fetches comments across all issues in the repository.
            per_page: Number of comments to fetch per page (max 100).

        Returns:
            A list of dictionaries, each representing an issue comment.

        Raises:
            ValueError: If owner or repo is empty.
            ApiClientError: If the request fails after retries.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name cannot be empty.")

        if issue_number is not None:
            # Endpoint for comments on a specific issue
            endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
            log_msg = f"Fetching comments for issue #{issue_number} in {owner}/{repo}..."
        else:
            # Endpoint for comments across all issues in the repo
            endpoint = f"/repos/{owner}/{repo}/issues/comments"
            log_msg = f"Fetching comments for all issues in {owner}/{repo}..."

        # Fetch comments oldest first
        params = {"per_page": per_page, "sort": "created", "direction": "asc"}
        logger.info(log_msg)
        try:
            # Use the generic pagination helper
            all_comments = self._fetch_paginated_results(endpoint, params)
            return all_comments
        except ApiClientError as e:
            issue_id = f"issue #{issue_number}" if issue_number else "all issues"
            logger.error(f"Failed to fetch issue comments for {owner}/{repo} ({issue_id}): {e}")
            raise e

    def get_pr_review_comments(self, owner: str, repo: str, pull_number: Optional[int] = None, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches review comments on pull requests within a repository, handling pagination.

        These are comments made on specific code lines during a review, distinct
        from general issue comments on the PR conversation thread. Can fetch
        comments for a single specific PR or for all PRs in the repository.
        Comments are fetched sorted by creation date (ascending).

        Args:
            owner: The login name of the repository owner.
            repo: The name of the repository.
            pull_number: If provided, fetches review comments only for this specific PR number.
                         If None (default), fetches review comments across all PRs in the repository.
            per_page: Number of comments to fetch per page (max 100).

        Returns:
            A list of dictionaries, each representing a PR review comment.

        Raises:
            ValueError: If owner or repo is empty.
            ApiClientError: If the request fails after retries.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name cannot be empty.")

        if pull_number is not None:
            # Endpoint for review comments on a specific PR
            endpoint = f"/repos/{owner}/{repo}/pulls/{pull_number}/comments"
            log_msg = f"Fetching review comments for PR #{pull_number} in {owner}/{repo}..."
        else:
            # Endpoint for review comments across all PRs in the repo
            endpoint = f"/repos/{owner}/{repo}/pulls/comments"
            log_msg = f"Fetching review comments for all PRs in {owner}/{repo}..."

        # Fetch comments oldest first
        params = {"per_page": per_page, "sort": "created", "direction": "asc"}
        logger.info(log_msg)
        try:
            # Use the generic pagination helper
            all_comments = self._fetch_paginated_results(endpoint, params)
            return all_comments
        except ApiClientError as e:
            pr_id = f"PR #{pull_number}" if pull_number else "all PRs"
            logger.error(f"Failed to fetch PR review comments for {owner}/{repo} ({pr_id}): {e}")
            raise e