# Makes 'external' a Python package

# Import specific client classes to make them available when importing the package
from .client_base import ClientBase, ApiClientError, RateLimitError
from .github_client import GitHubClient
from .openalex_client import OpenAlexClient

# Optionally define __all__ to control 'from backend.external import *' behavior
__all__ = [
    "ClientBase",
    "ApiClientError",
    "RateLimitError",
    "GitHubClient",
    "OpenAlexClient",
]