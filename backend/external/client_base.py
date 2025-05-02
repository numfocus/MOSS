"""
backend.external.client_base

Provides a foundational class for building external API clients. It encapsulates
common functionalities such as HTTP request execution, session management with
automatic retries for transient server errors, and specific handling for
rate limiting (HTTP 429) responses, including respecting 'Retry-After' headers.
"""

import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Tuple, List, Union # Added Union

# Ensure settings are imported to access config like OPENALEX_EMAIL
# This also ensures dotenv is loaded if settings module does it
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# --- Custom Exception Classes ---
class ApiClientError(Exception):
    """
    Represents a general error encountered during API client operations.

    This exception is raised for issues like connection errors, timeouts after
    retries, or unexpected responses that prevent successful completion of a
    request. It may optionally include the HTTP status code if the error
    originated from an HTTP response.
    """
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class RateLimitError(ApiClientError):
    """
    Specific exception raised when an API rate limit (HTTP 429) is encountered
    and persists even after internal retries.

    Attributes:
        retry_after: The suggested wait time in seconds provided by the
                     API's 'Retry-After' header, if available.
    """
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


# --- Base Client Implementation ---
class ClientBase:
    """
    A base HTTP client providing reusable request logic and session handling.

    This class sets up a `requests.Session` configured with automatic retries
    for common server-side errors (5xx status codes) and connection issues,
    using an exponential backoff strategy. It also implements internal retry
    logic specifically for HTTP 429 (Rate Limit Exceeded) responses, honoring
    the `Retry-After` header when present.

    Subclasses should inherit from `ClientBase` to leverage this common
    infrastructure for interacting with specific external APIs.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Union[float, Tuple[float, float]] = (10, 30), # connect, read
        retries: int = 3, # Retries for connection/server errors
        backoff_factor: float = 0.5,
        status_forcelist: Optional[List[int]] = None
    ):
        """
        Initializes the base client and its session.

        Args:
            base_url: The base URL for the target API. If set, relative
                      endpoints passed to request methods will be joined with
                      this URL. If None, endpoints must be absolute URLs.
            headers: A dictionary of default HTTP headers to include in all
                     requests. A standard 'User-Agent' identifying the application
                     and providing contact info (via settings.OPENALEX_EMAIL)
                     is added automatically. Provided headers will update the defaults.
            timeout: A float or tuple specifying the request timeout in seconds.
                     If a tuple, it represents (connect_timeout, read_timeout).
                     Defaults to (10, 30).
            retries: The maximum number of retry attempts for non-429 errors
                     (like 5xx status codes or connection errors) handled by
                     the underlying session adapter.
            backoff_factor: A factor used to calculate the delay between
                            retries for non-429 errors (e.g., delay =
                            backoff_factor * (2 ** (retry_attempt - 1))).
            status_forcelist: A list of HTTP status codes that should trigger
                              a retry by the session adapter. Defaults to
                              [500, 502, 503, 504].
        """
        # Base URL is optional now, can be provided per request or rely on endpoint being full URL
        self.base_url = base_url.rstrip('/') if base_url else None
        self.settings = settings # Access loaded settings instance
        self.default_timeout = timeout
        self.default_headers = {
            "User-Agent": f"MOSS Bot (Map of Open Source Science; mailto:{self.settings.OPENALEX_EMAIL or 'not-set'}) / Python Requests",
        }
        if headers:
            self.default_headers.update(headers)

        # Configure retries for connection/server errors (NOT 429)
        self.status_forcelist = status_forcelist if status_forcelist is not None else [500, 502, 503, 504]
        self.retries_config = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=self.status_forcelist,
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"], # Retry on these methods for server errors
            respect_retry_after_header=True # Good practice for non-429 retries
        )

        self.session = self._create_session()
        logger.info(f"{self.__class__.__name__} initialized for base URL: {self.base_url or 'Not Set'}")

    def _create_session(self) -> requests.Session:
        """
        Creates and configures the `requests.Session` instance.

        Sets up an HTTP adapter with the configured retry strategy for non-429
        errors and mounts it for both HTTP and HTTPS protocols. Default headers
        are also applied to the session.

        Returns:
            A configured `requests.Session` object.
        """
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=self.retries_config)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(self.default_headers)
        logger.debug(f"Requests session created with non-429 retry strategy for {self.__class__.__name__}.")
        return session

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None, # For form data
        json: Optional[Dict[str, Any]] = None, # For JSON body
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        **kwargs  # Allow passing extra arguments like 'files'
    ) -> requests.Response:
        """
        Executes an HTTP request with integrated retry logic for rate limits.

        This method performs the actual HTTP request using the configured session.
        It includes specific logic to handle HTTP 429 (Rate Limit Exceeded)
        responses internally by waiting and retrying, respecting the
        `Retry-After` header if provided, up to a defined maximum number of
        attempts (`MAX_429_RETRIES`).

        For other request failures (connection errors, timeouts, 5xx errors),
        it relies on the retry mechanism configured in the session's
        HTTPAdapter.

        If a request ultimately fails after all retry attempts (both internal
        429 retries and session adapter retries), an `ApiClientError` is raised.

        Args:
            method: The HTTP method (e.g., 'GET', 'POST', 'PUT').
            endpoint: The API endpoint path. Can be relative (if `base_url` is
                      set) or an absolute URL.
            params: A dictionary of query string parameters.
            data: A dictionary of data to be sent in the request body (typically
                  for form-encoded data).
            json: A dictionary of data to be serialized as JSON and sent in the
                  request body.
            headers: A dictionary of additional headers specific to this request,
                     merged with the session's default headers.
            timeout: An optional timeout (float or tuple) for this specific
                     request, overriding the client's default timeout.
            **kwargs: Additional keyword arguments passed directly to the
                      `requests.request` method (e.g., `files`, `stream`).

        Returns:
            The `requests.Response` object. The caller is responsible for
            checking the response status code (`response.ok`, `response.status_code`)
            to determine success or handle non-2xx/non-429 status codes appropriately.

        Raises:
            ApiClientError: If the request fails due to connection issues, timeouts,
                          or exceeding retry limits (both 429 and session retries).
                          The original exception is chained.
            ValueError: If the endpoint is relative but no `base_url` was configured.
            Exception: Catches and logs any unexpected errors during request execution,
                       then wraps and re-raises them as `ApiClientError`.
        """
        full_url = self._construct_url(endpoint)
        request_timeout = timeout if timeout is not None else self.default_timeout

        # Combine session headers with request-specific headers
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        # --- Rate Limit Handling Configuration ---
        MAX_429_RETRIES = 4 # Limit how many times *we* retry on 429 internally
        INITIAL_429_DELAY = 3 # Initial delay (seconds) after a 429 if no Retry-After
        MAX_429_WAIT = 60   # Maximum wait time (seconds) for a single 429 retry delay
        # --- End Rate Limit Configuration ---

        last_exception: Optional[Exception] = None # Store the last exception encountered

        for attempt in range(MAX_429_RETRIES + 1):
            logger.debug(f"Attempt {attempt+1}: {method.upper()} {full_url}")
            if params: logger.debug(f"Params: {params}")

            try:
                response = self.session.request(
                    method=method.upper(),
                    url=full_url,
                    params=params,
                    data=data,
                    json=json,
                    headers=request_headers,
                    timeout=request_timeout,
                    **kwargs
                )

                # --- Specific 429 Rate Limit Handling ---
                if response.status_code == 429:
                    if attempt < MAX_429_RETRIES:
                        retry_after_str = response.headers.get("Retry-After")
                        # Default wait is exponential backoff
                        wait_time = INITIAL_429_DELAY * (2 ** attempt)

                        if retry_after_str:
                            try:
                                # If Retry-After header is present, parse it as seconds
                                wait_time_header = int(retry_after_str)
                                # Use the header value if it's longer than backoff, add buffer
                                wait_time = max(wait_time, wait_time_header) + 1
                                logger.info(f"Rate limit hit. Respecting Retry-After: {wait_time_header}s. Waiting ~{wait_time}s.")
                            except (ValueError, TypeError):
                                logger.warning(f"Could not parse Retry-After header: '{retry_after_str}'. Using exponential backoff ({wait_time:.2f}s).")

                        # Cap the wait time to avoid excessively long waits
                        wait_time = min(wait_time, MAX_429_WAIT)
                        logger.warning(
                            f"Rate limit hit ({response.status_code}) on {method.upper()} {full_url}. "
                            f"Retrying attempt {attempt + 2}/{MAX_429_RETRIES + 1} "
                            f"after {wait_time:.2f} seconds."
                        )
                        time.sleep(wait_time)
                        # Store a dummy exception to indicate a retry occurred
                        last_exception = requests.exceptions.RetryError(f"Rate limited on attempt {attempt+1}")
                        continue # Proceed to the next attempt in the 429 retry loop
                    else:
                        # Exceeded internal retries specifically for 429 errors
                        logger.error(f"Rate limit hit ({response.status_code}) on {method.upper()} {full_url} and exceeded internal retry limit ({MAX_429_RETRIES}). Raising error.")
                        # Use raise_for_status() to create an HTTPError, which will be caught below
                        response.raise_for_status()

                # If not 429, return the response immediately.
                # The caller should check response.ok or response.status_code.
                if response.ok:
                    logger.debug(f"Request successful: {response.status_code} {method.upper()} {full_url}")
                else:
                     # Log non-429 client/server errors handled by the caller
                     logger.warning(
                        f"Request returned non-success status (non-429): {response.status_code} {method.upper()} {full_url}. "
                        f"Response snippet: {response.text[:200]}"
                     )
                # Return the response regardless of non-429 status code; caller decides how to handle.
                return response

            except requests.exceptions.RequestException as e:
                # This block catches:
                # 1. Connection errors, timeouts etc., *after* the session's
                #    Retry mechanism (configured by self.retries_config) is exhausted.
                # 2. The HTTPError explicitly raised above if MAX_429_RETRIES was exceeded.
                logger.error(f"Request failed for {method.upper()} {full_url} after all retries (Session or internal 429): {e}", exc_info=False) # Log only message unless debugging
                logger.debug(f"Underlying exception detail for failed request:", exc_info=True) # Full trace on debug
                last_exception = e # Store the actual exception
                # Break the loop, we will raise ApiClientError outside based on last_exception
                break
            except Exception as e:
                # Catch any other unexpected errors during request setup or execution
                logger.exception(f"Unexpected error during request: {method.upper()} {full_url}")
                last_exception = e
                break # Exit loop on unexpected error

        # If the loop completed without returning a response (i.e., hit break after an exception)
        # Raise a consistent ApiClientError, wrapping the last encountered exception.
        err_msg = f"Request failed for {method.upper()} {full_url} after all retries: {last_exception}"
        status_code = getattr(last_exception, 'response', None)
        status_code = getattr(status_code, 'status_code', None) if status_code else None
        raise ApiClientError(err_msg, status_code=status_code) from last_exception


    def _construct_url(self, endpoint: str) -> str:
        """
        Constructs the full URL for an API request.

        If the provided endpoint starts with 'http://' or 'https://', it's
        treated as an absolute URL and returned directly. Otherwise, it's
        joined with the client's `base_url`.

        Args:
            endpoint: The API endpoint path or absolute URL.

        Returns:
            The fully constructed URL.

        Raises:
            ValueError: If the endpoint is relative and `base_url` is not set.
        """
        if endpoint.lower().startswith(('http://', 'https://')):
            return endpoint
        if not self.base_url:
             logger.error(f"Cannot construct full URL for relative endpoint '{endpoint}' because client base_url is not configured.")
             raise ValueError(f"Endpoint '{endpoint}' is not a full URL and no base_url is configured for this client.")
        # Ensure there's exactly one slash between base_url and endpoint
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # --- Convenience Methods ---
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        """
        Performs an HTTP GET request.

        Args:
            endpoint: The API endpoint path or absolute URL.
            params: Optional dictionary of query string parameters.
            **kwargs: Additional arguments passed to `_request`.

        Returns:
            The `requests.Response` object. Caller must check status.

        Raises:
            ApiClientError: If the request fails after retries.
        """
        return self._request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        """
        Performs an HTTP POST request.

        Args:
            endpoint: The API endpoint path or absolute URL.
            data: Optional dictionary for form-encoded request body.
            json: Optional dictionary for JSON request body.
            **kwargs: Additional arguments passed to `_request`.

        Returns:
            The `requests.Response` object. Caller must check status.

        Raises:
            ApiClientError: If the request fails after retries.
        """
        return self._request("POST", endpoint, data=data, json=json, **kwargs)

    # Add other convenience methods (put, delete, patch, head, options) as needed.