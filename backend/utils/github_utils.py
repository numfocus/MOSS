# --- START OF FILE github_utils.py ---
"""
backend.utils.github_utils
--------------------------

Provides utility functions specifically for handling GitHub URLs.

Currently includes a function to parse standard GitHub repository URLs
and extract the owner and repository name components.
"""

import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

# Setup logger for this module.
logger = logging.getLogger(__name__)

def parse_github_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Parses a given URL string to extract GitHub owner and repository names.

    This function targets common GitHub repository URL formats, including those
    with or without '.git' suffixes, trailing slashes, and HTTP/HTTPS schemes.
    It validates that the domain is 'github.com' and that the path structure
    corresponds to an owner/repository pattern.

    Examples of handled formats:
        - https://github.com/owner/repo
        - https://github.com/owner/repo/
        - https://github.com/owner/repo.git
        - http://github.com/owner/repo

    Args:
        url: The URL string to parse.

    Returns:
        A tuple containing (owner, repo) as strings if parsing is successful
        and the URL matches the expected format. Returns None if the URL is
        invalid, not a GitHub URL, or does not conform to the owner/repo
        path structure.
    """
    # Basic input validation: Ensure URL is a non-empty string.
    if not isinstance(url, str) or not url:
        logger.warning("Attempted to parse an empty or non-string URL.")
        return None

    try:
        # Use Python's standard URL parsing library.
        parsed_url = urlparse(url)

        # Validate the network location (domain). Must be 'github.com'.
        # Use case-insensitive comparison for robustness.
        if parsed_url.netloc.lower() != 'github.com':
            logger.warning(f"URL rejected: domain is not github.com ('{parsed_url.netloc}'). URL: {url}")
            return None

        # Process the path component of the URL.
        # 1. Remove leading/trailing slashes for consistent processing.
        path = parsed_url.path.strip('/')
        # 2. Remove the '.git' suffix if present (case-insensitive).
        if path.lower().endswith('.git'):
            path = path[:-4] # Slice off the last 4 characters ('.git').

        # Split the cleaned path into segments using '/' as the delimiter.
        parts = path.split('/')

        # Expect exactly two non-empty segments: the owner and the repository name.
        if len(parts) == 2 and all(parts): # `all(parts)` checks for empty strings (e.g., 'owner//repo').
            owner, repo = parts[0], parts[1]
            logger.debug(f"Successfully parsed GitHub URL '{url}' -> owner='{owner}', repo='{repo}'")
            return owner, repo
        else:
            # Log a warning if the path structure doesn't match owner/repo.
            # This handles cases like 'github.com/owner' or 'github.com/owner/repo/tree/main'.
            logger.warning(
                f"Could not extract owner/repo from path structure '{parsed_url.path}' "
                f"(cleaned: '{path}', parts: {len(parts)}). URL: {url}"
            )
            return None

    except Exception as e:
        # Catch any unexpected errors during the parsing process.
        logger.error(f"Unexpected error parsing GitHub URL '{url}': {e}", exc_info=True)
        return None

# --- Example Usage & Basic Tests ---
# This block executes only when the script is run directly.
# It serves as a basic verification of the parse_github_url function.
if __name__ == "__main__":
    urls_to_test = [
        "https://github.com/pallets/flask",          # Standard case
        "https://github.com/pallets/flask/",         # Trailing slash
        "https://github.com/pallets/flask.git",      # .git suffix
        "http://github.com/pallets/flask",           # HTTP scheme
        "HTTPS://GITHUB.COM/USER/REPO",              # Case variation
        "https://github.com/django/django/tree/main", # Invalid structure (too many parts)
        "https://gitlab.com/user/repo",              # Invalid domain
        "https://github.com/just_owner",             # Invalid structure (too few parts)
        "https://github.com//repo",                  # Invalid structure (empty owner part)
        "invalid-url",                               # Not a URL
        "",                                          # Empty string
        None,                                        # None input
    ]

    print("--- Testing GitHub URL Parsing ---")
    for test_url in urls_to_test:
        result = parse_github_url(test_url)
        if result:
            print(f"'{test_url}' -> Owner: {result[0]}, Repo: {result[1]} (Success)")
        else:
            print(f"'{test_url}' -> FAILED to parse")
# --- END OF FILE github_utils.py ---