"""
backend.external.openalex_client

Provides a client for interacting with the OpenAlex API (https://openalex.org).
This client facilitates searching and retrieving scholarly data, including works
(publications), authors, institutions, concepts, and their relationships. It leverages
the `ClientBase` for handling HTTP requests and rate limiting. It encourages
providing an email address (via `settings.OPENALEX_EMAIL`) to join the OpenAlex
"polite pool" for potentially higher rate limits.
"""

import logging
import urllib.parse
import requests
import re # Used in helper function
import time
from typing import Optional, Dict, Any, List

# Import base client and custom errors
from .client_base import ClientBase, ApiClientError
# Import settings to access OPENALEX_EMAIL
from backend.config.settings import settings
# Note: The dependency on ScholarlyProcessingService._get_id_from_oa_url was removed
# by duplicating the helper function here. Consider moving the helper to a
# common utility module if used elsewhere.

logger = logging.getLogger(__name__)

class OpenAlexClient(ClientBase):
    """
    Client for the OpenAlex scholarly data API.

    Provides methods to resolve DOIs, fetch details about works, and retrieve
    citing works using the OpenAlex API endpoints. It utilizes the base client's
    request handling and incorporates the polite pool email if configured.
    """
    def __init__(self):
        """
        Initializes the OpenAlexClient.

        Sets the base URL for the OpenAlex API and checks for the presence of
        `OPENALEX_EMAIL` in settings, logging a warning if it's not set.
        """
        super().__init__(base_url="https://api.openalex.org")
        if not self.settings.OPENALEX_EMAIL:
            logger.warning("OPENALEX_EMAIL is not set in settings. Providing an email to OpenAlex is recommended for the polite pool (potentially higher rate limits).")
        else:
             logger.info(f"OpenAlexClient initialized. Using email '{self.settings.OPENALEX_EMAIL}' for the polite pool.")
        logger.info("OpenAlexClient initialized.")


    def _get_id_from_oa_url(self, url: Optional[str]) -> Optional[str]:
        """
        Extracts the OpenAlex ID (e.g., 'W123456789') from a full OpenAlex URL.

        Args:
            url: The full OpenAlex entity URL (e.g., "https://openalex.org/W123...").

        Returns:
            The extracted OpenAlex ID string (like 'W123...') if found and valid,
            otherwise None.
        """
        if not url or not isinstance(url, str) or not url.startswith("https://openalex.org/"):
            return None
        try:
            # Get the last part of the URL path
            id_part = url.split('/')[-1]
            # Basic validation: starts with 'W' (for works) followed by digits
            # TODO: Extend this for other entity types (A, I, C, S, F) if needed.
            if id_part and id_part[0].isalpha() and id_part[1:].isdigit():
                return id_part
            else:
                 logger.debug(f"Extracted part '{id_part}' from URL '{url}' does not look like a valid OpenAlex ID.")
        except Exception as e:
            # Catch potential errors during splitting or indexing
            logger.warning(f"Error parsing OpenAlex ID from URL '{url}': {e}", exc_info=False)
        return None

    def resolve_doi_to_work(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Finds an OpenAlex work entity corresponding to a given DOI.

        Args:
            doi: The Digital Object Identifier (DOI) string (e.g., "10.1234/journal.xyz").

        Returns:
            A dictionary containing the OpenAlex work data if found, including
            an added 'openalex_id' field (e.g., 'W123...') extracted from the
            'id' URL. Returns None if the DOI is not found (404) or if an
            error occurs.

        Raises:
            ValueError: If the DOI contains characters invalid for URL encoding.
            ApiClientError: If the API request fails after retries.
            Exception: For other unexpected errors.
        """
        if not doi:
            logger.warning("Attempted to resolve an empty or null DOI string.")
            return None
        try:
            # DOIs can contain special characters like '/' which need encoding
            # when used as part of a URL path segment.
            encoded_doi = urllib.parse.quote(doi, safe='') # Use quote() for path segments
            # Construct the endpoint using the DOI resolver format
            endpoint = f"/works/https://doi.org/{encoded_doi}"
        except Exception as e:
             # Catch potential encoding errors, although unlikely with standard DOIs
             logger.error(f"Failed to URL-encode DOI '{doi}': {e}", exc_info=True)
             raise ValueError(f"Invalid characters in DOI for URL encoding: {doi}") from e

        params = {}
        # Add email to params for polite pool access
        if self.settings.OPENALEX_EMAIL:
             params["mailto"] = self.settings.OPENALEX_EMAIL
        logger.info(f"Resolving DOI '{doi}' via OpenAlex endpoint: {endpoint}")

        try:
            response = self._request("GET", endpoint, params=params)

            if response.status_code == 404:
                logger.info(f"DOI not found in OpenAlex: {doi} (404)")
                return None
            # Check for other non-successful status codes
            elif not response.ok:
                logger.error(f"OpenAlex API error resolving DOI {doi}. Status: {response.status_code}, Response: {response.text[:200]}")
                # Depending on policy, could raise ApiClientError here or just return None
                return None # Fail gracefully for now

            # If response is OK, attempt to parse JSON
            try:
                work_data = response.json()
                # Basic validation of the response structure
                if work_data and isinstance(work_data, dict) and work_data.get('id'):
                    # Extract the 'W...' ID from the full ID URL for convenience
                    oa_id_from_url = self._get_id_from_oa_url(work_data.get('id'))
                    if oa_id_from_url:
                         work_data['openalex_id'] = oa_id_from_url
                    else:
                         logger.warning(f"Could not extract OpenAlex ID from work ID URL: {work_data.get('id')}")
                    return work_data
                else:
                    logger.warning(f"Received unexpected or incomplete JSON structure from OpenAlex for DOI {doi}: {str(work_data)[:200]}")
                    return None
            except requests.exceptions.JSONDecodeError as json_err:
                # Handle cases where response status was OK but body is not valid JSON
                logger.error(f"Failed to parse JSON response from OpenAlex for DOI {doi} (Status: {response.status_code}): {json_err}", exc_info=True)
                logger.debug(f"Response text causing decode error: {response.text[:500]}")
                return None

        except ApiClientError as e:
            # Catch errors raised by _request (connection, timeout, retries exceeded)
            logger.error(f"OpenAlex API client error resolving DOI {doi}: {e}")
            raise # Re-raise client errors
        except ValueError as e:
            # Catch the ValueError from DOI encoding failure
            logger.error(f"Value error related to DOI {doi}: {e}")
            raise # Re-raise value errors
        except Exception as e:
            # Catch any other unexpected errors during the process
            logger.exception(f"Unexpected error resolving DOI {doi} via OpenAlex")
            raise # Re-raise unexpected errors


    def get_work_details(self, openalex_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the full details for a specific OpenAlex work using its ID.

        Accepts either the full OpenAlex URL or just the ID part (e.g., 'W123...').

        Args:
            openalex_id: The OpenAlex Work ID (e.g., 'W123456789') or the full
                         OpenAlex URL (e.g., 'https://openalex.org/W123...').

        Returns:
            A dictionary containing the full work data from OpenAlex, including
            an added 'openalex_id' field (e.g., 'W123...') extracted from the
            'id' URL. Returns None if the work is not found (404) or an error occurs.

        Raises:
            ValueError: If the provided `openalex_id` is empty or has an invalid format.
            ApiClientError: If the API request fails after retries.
            Exception: For other unexpected errors.
        """
        if not openalex_id: raise ValueError("OpenAlex ID cannot be empty.")

        # Extract the 'W...' part if a full URL is provided
        if openalex_id.startswith("https://openalex.org/"):
             work_id_part = self._get_id_from_oa_url(openalex_id)
        else:
             work_id_part = openalex_id

        # Validate the extracted/provided ID format (basic check)
        if not work_id_part or not work_id_part.startswith('W') or not work_id_part[1:].isdigit():
             logger.error(f"Invalid OpenAlex Work ID format provided: '{openalex_id}' (parsed as '{work_id_part}')")
             raise ValueError(f"Invalid OpenAlex Work ID format: {openalex_id}")

        endpoint = f"/works/{work_id_part}"
        params = {}
        if self.settings.OPENALEX_EMAIL: params["mailto"] = self.settings.OPENALEX_EMAIL
        logger.info(f"Fetching full work details for OpenAlex ID: {work_id_part}")

        try:
            response = self._request("GET", endpoint, params=params)

            if response.status_code == 404:
                logger.info(f"Work not found in OpenAlex: {work_id_part} (404)")
                return None
            elif not response.ok:
                logger.error(f"OpenAlex API error getting details for work {work_id_part}. Status: {response.status_code}, Response: {response.text[:200]}")
                return None # Fail gracefully

            try:
                work_data = response.json()
                # Verify the response contains an ID and it matches the requested ID
                if work_data and isinstance(work_data, dict) and work_data.get('id') and work_data['id'].endswith(work_id_part):
                    # Add the extracted 'W...' ID for consistency
                    oa_id_from_url = self._get_id_from_oa_url(work_data.get('id'))
                    if oa_id_from_url: work_data['openalex_id'] = oa_id_from_url
                    return work_data
                else:
                    logger.warning(f"Received unexpected JSON structure or mismatched ID from OpenAlex for {work_id_part}: {str(work_data)[:200]}")
                    return None
            except requests.exceptions.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response from OpenAlex for work {work_id_part} (Status: {response.status_code}): {json_err}", exc_info=True)
                logger.debug(f"Response text causing decode error: {response.text[:500]}")
                return None

        except ApiClientError as e:
            logger.error(f"OpenAlex API client error getting details for work {work_id_part}: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting details for work {work_id_part} via OpenAlex")
            raise


    def get_citing_works(
        self, citing_works_url: str, per_page: int = 200, max_results: int = 1000
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches works that cite a target work, using the 'cited_by_api_url'
        provided by OpenAlex work objects. Handles pagination.

        This method expects the full API URL provided by OpenAlex, which already
        contains the necessary filter (e.g., `filter=cites:W123...`). It requests
        only essential fields (`id`, `doi`, `title`, `publication_year`) to
        minimize response size.

        Args:
            citing_works_url: The full URL provided by OpenAlex in the
                              `cited_by_api_url` field of a work object.
            per_page: Number of results per page (max 200 for OpenAlex).
            max_results: The maximum total number of citing works to retrieve.

        Returns:
            A list of dictionaries, each representing a citing work with basic
            metadata ('id', 'doi', 'title', 'publication_year', 'openalex_id').
            Returns None if the initial URL is invalid or a significant error
            occurs during fetching. Returns an empty list if no citing works are found.

        Raises:
            ValueError: If the provided `citing_works_url` is invalid or cannot be parsed.
            ApiClientError: If an API request fails after retries.
            Exception: For other unexpected errors.
        """
        if not citing_works_url or not citing_works_url.startswith("https://api.openalex.org/works"):
            logger.error(f"Invalid or missing citing_works_url provided: '{citing_works_url}'")
            raise ValueError(f"Invalid citing_works_url provided: {citing_works_url}")

        all_results: List[Dict[str, Any]] = []
        page = 1
        processed_count = 0
        # Define the specific fields to select for citing works
        select_fields = "id,doi,title,publication_year"

        try:
            # Parse the base URL and existing query parameters from the provided URL
            parsed_url = urllib.parse.urlparse(citing_works_url)
            base_endpoint = parsed_url.path # Should be '/works'
            initial_params = urllib.parse.parse_qs(parsed_url.query) # Contains the 'filter' param
        except Exception as parse_e:
             logger.error(f"Failed to parse provided cited_by_api_url '{citing_works_url}': {parse_e}", exc_info=True)
             raise ValueError(f"Could not parse cited_by_api_url: {citing_works_url}") from parse_e

        # Cap per_page at OpenAlex maximum
        per_page = min(per_page, 200)

        logger.info(f"Fetching citing works from URL: {citing_works_url} (max_results={max_results}, per_page={per_page})")

        while processed_count < max_results:
            # Prepare parameters for the current page request
            current_params = initial_params.copy() # Start with base filter params
            current_params['page'] = [str(page)]
            current_params['per_page'] = [str(per_page)]
            # Add/overwrite the 'select' parameter to fetch only needed fields
            current_params['select'] = [select_fields]
            # Add email for polite pool if not already present
            if self.settings.OPENALEX_EMAIL and 'mailto' not in current_params:
                current_params['mailto'] = [self.settings.OPENALEX_EMAIL]

            # Log the request details (use base_endpoint as it's relative)
            logger.debug(f"Fetching citing works page {page} using endpoint {base_endpoint} with params {current_params}")

            try:
                # Make the request using the base endpoint and constructed params
                response = self._request("GET", base_endpoint, params=current_params)

                if not response.ok:
                    # Log details if the request failed
                    error_msg = response.text[:200] # Basic error snippet
                    try:
                        # Attempt to get a more specific message from JSON error response
                        error_json = response.json()
                        error_msg = error_json.get('message', error_msg)
                    except requests.exceptions.JSONDecodeError:
                        pass # Ignore if response wasn't JSON
                    logger.error(
                        f"OpenAlex API error fetching citing works page {page} from {citing_works_url}. "
                        f"Status: {response.status_code}, Error: {error_msg}"
                    )
                    # Indicate failure by returning None; could also return partial results if desired
                    return None

                # If response is OK, process the JSON data
                try:
                    data = response.json()
                    results = data.get("results", []) # List of citing works

                    # Validate the results format
                    if not isinstance(results, list):
                         logger.error(f"Unexpected 'results' format in citing works response (page {page}, expected list, got {type(results)}).")
                         return None # Cannot process invalid format

                    # If no results are returned on the current page, we've reached the end
                    if not results:
                        logger.debug(f"No more citing works found on page {page} for URL {citing_works_url}. Ending fetch.")
                        break # Exit the pagination loop

                    # Process the fetched items: add 'openalex_id' and respect max_results
                    cleaned_results = []
                    for item in results:
                        if processed_count >= max_results: break # Stop adding if max reached mid-page
                        # Ensure item has an ID before processing
                        if item and isinstance(item, dict) and item.get('id'):
                            oa_id_from_url = self._get_id_from_oa_url(item.get('id'))
                            if oa_id_from_url:
                                item['openalex_id'] = oa_id_from_url # Add the 'W...' ID
                                cleaned_results.append(item)
                                processed_count += 1
                            else:
                                logger.warning(f"Could not parse OpenAlex ID from citing work item: {item.get('id')}")
                        else:
                             logger.warning(f"Skipping invalid item in citing works response: {item}")


                    all_results.extend(cleaned_results)
                    logger.debug(f"Page {page}: fetched {len(results)} items, added {len(cleaned_results)}. Total collected: {processed_count}")

                    # Check if we've hit the max_results limit after processing the page
                    if processed_count >= max_results:
                         logger.info(f"Reached max_results ({max_results}) while fetching citing works from {citing_works_url}.")
                         break # Exit the pagination loop

                    # Prepare for the next page
                    page += 1
                    # Add a small delay to be polite to the API
                    time.sleep(0.1)

                except requests.exceptions.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse JSON citing works response (page {page}) from {citing_works_url}: {json_err}", exc_info=True)
                    logger.debug(f"Response text causing decode error: {response.text[:500]}")
                    return None # Cannot proceed if JSON is invalid

            except ApiClientError as api_err:
                 # Propagate client-level errors
                 logger.error(f"API client error during citing works fetch (page {page}) from {citing_works_url}: {api_err}")
                 raise
            except Exception as e:
                 # Catch unexpected errors during the loop
                 logger.exception(f"Unexpected error during citing works fetch (page {page}) from {citing_works_url}")
                 raise

        logger.info(f"Finished fetching citing works from {citing_works_url}. Retrieved {len(all_results)} results (processed count: {processed_count}).")
        return all_results


    def get_work_basic_metadata(self, openalex_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a minimal set of metadata for a specific OpenAlex work using its ID.

        This method is optimized to retrieve only essential fields: 'id', 'doi',
        'title', and 'publication_year'. Accepts only the ID part (e.g., 'W123...').

        Args:
            openalex_id: The OpenAlex Work ID (e.g., 'W123456789'). Must be the ID,
                         not the full URL.

        Returns:
            A dictionary containing the basic work metadata ('id', 'doi', 'title',
            'publication_year', 'openalex_id'), or None if the work is not found
            (404) or an error occurs.

        Raises:
            ValueError: If the provided `openalex_id` is empty or has an invalid format.
            ApiClientError: If the API request fails after retries.
            Exception: For other unexpected errors.
        """
        if not openalex_id: raise ValueError("OpenAlex ID cannot be empty.")
        # Validate ID format strictly for this method (expects 'W...' format)
        if not openalex_id.startswith('W') or not openalex_id[1:].isdigit():
             logger.error(f"Invalid OpenAlex Work ID format provided for basic fetch: '{openalex_id}'. Expected 'W' followed by digits.")
             raise ValueError(f"Invalid OpenAlex Work ID format for basic fetch: {openalex_id}")

        endpoint = f"/works/{openalex_id}"
        # Define the minimal set of fields required
        select_fields = "id,doi,title,publication_year"
        params = {"select": select_fields}
        if self.settings.OPENALEX_EMAIL: params["mailto"] = self.settings.OPENALEX_EMAIL

        logger.info(f"Fetching basic metadata for OpenAlex ID {openalex_id} (fields: {select_fields})")

        try:
            response = self._request("GET", endpoint, params=params)

            if response.status_code == 404:
                logger.info(f"Work not found in OpenAlex (basic fetch): {openalex_id} (404)")
                return None
            elif not response.ok:
                 # Log specific error message if available
                 error_msg = response.text[:200]
                 try:
                     error_json = response.json()
                     error_msg = error_json.get('message', error_msg)
                 except requests.exceptions.JSONDecodeError: pass
                 logger.error(
                     f"OpenAlex API error getting basic details for work {openalex_id}. "
                     f"Status: {response.status_code}, Error: {error_msg}"
                 )
                 return None # Fail gracefully

            # Process successful response
            try:
                work_data = response.json()
                # Verify the response contains an ID and it matches
                if work_data and isinstance(work_data, dict) and work_data.get('id') and work_data['id'].endswith(openalex_id):
                     # Add the cleaned 'openalex_id' field for consistency
                     oa_id_from_url = self._get_id_from_oa_url(work_data.get('id'))
                     if oa_id_from_url:
                          work_data['openalex_id'] = oa_id_from_url
                     else:
                          # Should ideally always be parseable if ID matched endswith
                          logger.warning(f"Could not parse OpenAlex ID from work ID URL during basic fetch: {work_data.get('id')}")
                     return work_data
                else:
                     logger.warning(f"Received unexpected JSON structure or mismatched ID from basic fetch for {openalex_id}: {str(work_data)[:200]}")
                     return None
            except requests.exceptions.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response from OpenAlex basic fetch for work {openalex_id} (Status: {response.status_code}): {json_err}", exc_info=True)
                logger.debug(f"Response text causing decode error: {response.text[:500]}")
                return None

        except ApiClientError as e:
            logger.error(f"OpenAlex API client error getting basic details for work {openalex_id}: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting basic details for work {openalex_id} via OpenAlex")
            raise