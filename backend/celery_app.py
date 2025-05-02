# --- START OF FILE celery_app.py ---
"""
backend.celery_app
------------------

Configures and initializes the Celery application instance used for background task
processing within the MOSS backend.

This module handles:
- Celery application setup with broker and backend URLs from settings.
- Integration with the application's custom logging configuration, ensuring
  Celery workers use the same logging setup (including process-safe file rotation).
- Disabling Celery's default logging handlers to prevent conflicts.
- Specifying task discovery locations.
- Defining default Celery configuration settings.
"""

import logging
from celery import Celery
# Import Celery signals for hooking into its logging setup process.
from celery.signals import setup_logging as setup_celery_logging_signal
# Import custom logging setup functions and handlers.
from backend.config.logging_config import (
    setup_logging,
    ConcurrentRotatingFileHandler, # Process-safe handler (if available).
    RotatingFileHandler,           # Standard library fallback handler.
    CONCURRENT_HANDLER_AVAILABLE   # Flag indicating which handler is used.
)

# Import application settings to access configuration values like broker URLs.
from backend.config.settings import settings

# --- Configure standard Python logging FIRST ---
# This ensures that logging is set up before Celery attempts its own configuration.

# Determine the appropriate file handler class for Celery logs.
# Prioritize the process-safe ConcurrentRotatingFileHandler if the
# 'concurrent-log-handler' package is installed, as it prevents file access
# conflicts when multiple worker processes write to the same log file,
# especially important on Windows.
if CONCURRENT_HANDLER_AVAILABLE:
    celery_handler_class = ConcurrentRotatingFileHandler
    handler_info = "ConcurrentRotatingFileHandler (process-safe)"
else:
    # Fallback to the standard RotatingFileHandler if the concurrent handler
    # is not available. Log a warning as this might cause issues in
    # multi-process environments on certain platforms.
    # Use a temporary logger instance before the full setup is complete.
    logging.getLogger(__name__).warning(
        "concurrent-log-handler package not found. Falling back to standard "
        "RotatingFileHandler for Celery logs. This may cause issues "
        "(e.g., PermissionErrors) in multi-worker setups on Windows."
    )
    celery_handler_class = RotatingFileHandler
    handler_info = "RotatingFileHandler (standard fallback)"

# Apply the custom logging configuration using the selected handler.
# Logs for Celery workers will be directed to 'moss_celery.log'.
setup_logging(
    log_file_name="moss_celery.log",
    handler_class=celery_handler_class # Pass the chosen handler class.
)

# Obtain the application's logger instance *after* the setup is complete.
logger = logging.getLogger(__name__)
logger.info(f"Celery logging configured using: {handler_info}.")


# --- Prevent Celery from overriding custom logging setup ---
# Connect a handler to Celery's 'setup_logging' signal. By providing a handler
# that does nothing, we effectively disable Celery's default logging configuration,
# ensuring that the custom setup defined above is the only one used.
@setup_celery_logging_signal.connect
def configure_celery_logging(**kwargs):
    """
    Signal handler connected to Celery's setup_logging signal.

    This handler intentionally does nothing, preventing Celery from configuring
    its own log handlers and ensuring our custom setup via `setup_logging`
    persists.
    """
    logger.info("Celery 'setup_logging' signal intercepted. Skipping Celery's default logger setup.")
    pass
# --- End Signal Handler ---


# --- Initialize Celery Application ---
# Create the Celery application instance.
celery_app = Celery(
    __name__,                   # Use the current module name as the app name.
    broker=settings.CELERY_BROKER_URL,        # URL for the message broker (e.g., Redis, RabbitMQ).
    backend=settings.CELERY_RESULT_BACKEND_URL, # URL for storing task results.
    # List of modules Celery should inspect to discover task definitions.
    include=[
        'backend.tasks.scholarly_tasks',    # Tasks related to scholarly data processing.
        'backend.tasks.discovery_tasks',    # Tasks related to repository/keyword discovery.
        # Add other modules containing Celery tasks here.
    ]
)

# --- Apply Celery Configuration ---
# Update the Celery application configuration with specific settings.
celery_app.conf.update(
    task_serializer='json',        # Use JSON for serializing task messages.
    accept_content=['json'],       # Only accept JSON-formatted task messages.
    result_serializer='json',      # Use JSON for serializing task results.
    timezone='UTC',                # Standardize on UTC for time-related operations.
    enable_utc=True,               # Ensure UTC is enabled for scheduling and timestamps.
    task_track_started=True,       # Record when a task begins execution (useful for monitoring).

    # Optional: Retry connecting to the broker on startup if it's not immediately available.
    # Useful in containerized environments where services might start in parallel.
    # broker_connection_retry_on_startup=True,

    # Note: Worker pool and concurrency are often configured via command-line arguments
    # (e.g., `celery -A ... worker -P eventlet -c 4`), but can be set here as defaults.
    # worker_concurrency=4,         # Example: Default number of concurrent worker processes/threads.
    # worker_pool='eventlet',       # Example: Default execution pool (matches '-P eventlet').
)

# Log key Celery configuration details upon initialization.
logger.info(f"Celery application '{celery_app.main}' initialized.")
logger.info(f"Using Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"Using Result Backend URL: {settings.CELERY_RESULT_BACKEND_URL}")
logger.info(f"Included task modules for discovery: {celery_app.conf.include}")

# The '__main__' block is typically used for direct script execution.
# For Celery, workers are usually started via the 'celery' command-line tool.
# This block is generally removed or commented out in production deployments.
# if __name__ == '__main__':
#    # Starting workers this way is not standard practice for production.
#    logger.warning("Attempting to start Celery worker directly from script execution. "
#                   "Use the 'celery' command-line interface instead.")
#    celery_app.start()
# --- END OF FILE celery_app.py ---