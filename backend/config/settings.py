"""
backend.config.settings
-----------------------
Handles application configuration settings management.

This module defines the `Settings` class responsible for loading configuration
parameters from environment variables or a `.env` file located at the project root.
It provides a centralized point of access for configuration values like database URLs,
API keys, and service endpoints.
"""

import os
import logging
from dotenv import load_dotenv

# --- Project Root Determination ---
# Assume settings.py is located in 'backend/config'. Navigate up two levels to find the project root.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# Construct the full path to the .env file in the project root.
DOTENV_PATH = os.path.join(PROJECT_ROOT, '.env')

# --- Load Environment Variables ---
# Attempt to load the .env file if it exists. Variables defined in the environment
# will typically override those in the .env file.
if os.path.exists(DOTENV_PATH):
    load_dotenv(dotenv_path=DOTENV_PATH)
    # Optional: Log that the .env file was loaded.
    # logging.getLogger(__name__).info(f"Loaded environment variables from: {DOTENV_PATH}")
else:
    # If .env is missing, the application will rely solely on system environment variables.
    # A warning could be logged here if a .env file is expected.
    pass

# Get a logger instance specific to this module.
logger = logging.getLogger(__name__)

class Settings:
    """
    Application settings loaded from environment variables.

    Reads configuration values required by the application from the environment,
    using a `.env` file as a potential source. Performs basic validation to ensure
    critical settings are present.
    """
    # --- Database Configuration ---
    DATABASE_URL: str | None = None # Connection string for the primary database.

    # --- External Service API Keys ---
    GITHUB_API_TOKEN: str | None = None # Token for authenticating with the GitHub API.
    OPENALEX_EMAIL: str | None = None   # Email address for identifying requests to the OpenAlex API (polite pool).

    # --- Celery Configuration (Task Queue) ---
    CELERY_BROKER_URL: str | None = None       # URL for the Celery message broker (e.g., Redis, RabbitMQ).
    CELERY_RESULT_BACKEND_URL: str | None = None # URL for the Celery result backend (e.g., Redis, database).

    def __init__(self):
        """
        Initializes the Settings instance by loading values from the environment
        and performing validation checks.
        """
        # Load core settings from environment variables.
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")
        self.OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL")

        # Load Celery settings, providing defaults suitable for local development if not set.
        self.CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        self.CELERY_RESULT_BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND_URL", "redis://localhost:6379/1")

        # --- Validation ---
        # Define settings considered essential for the application to run correctly.
        # Celery URLs have defaults, so they are not strictly required here but might be elsewhere.
        required_settings = {
            "DATABASE_URL": self.DATABASE_URL,
            "GITHUB_API_TOKEN": self.GITHUB_API_TOKEN,
            "OPENALEX_EMAIL": self.OPENALEX_EMAIL,
        }
        # Identify any required settings that are missing (None or empty string).
        missing = [key for key, value in required_settings.items() if not value]
        if missing:
            # Construct a helpful error message if required settings are absent.
            error_message = (
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Ensure they are set in the system environment or in '{DOTENV_PATH}'."
            )
            logger.error(error_message)
            # Raise an exception to prevent the application from starting with invalid config.
            raise ValueError(error_message)

        logger.info("Application settings loaded successfully.")
        # Log the status of loaded settings for debugging, avoiding sensitive values.
        # Indicate whether a value was explicitly set or if a default is being used (for Celery).
        logger.debug(f"DATABASE_URL: {'Set' if self.DATABASE_URL else 'Not Set'}")
        logger.debug(f"GITHUB_API_TOKEN: {'Set' if self.GITHUB_API_TOKEN else 'Not Set'}")
        logger.debug(f"OPENALEX_EMAIL: {self.OPENALEX_EMAIL or 'Not Set'}")
        logger.debug(f"CELERY_BROKER_URL: {'Set from environment' if os.getenv('CELERY_BROKER_URL') else 'Using Default/Loaded'}")
        logger.debug(f"CELERY_RESULT_BACKEND_URL: {'Set from environment' if os.getenv('CELERY_RESULT_BACKEND_URL') else 'Using Default/Loaded'}")


# Create a single, globally accessible instance of the Settings class.
# Other modules can import this instance directly: `from backend.config.settings import settings`
settings = Settings()