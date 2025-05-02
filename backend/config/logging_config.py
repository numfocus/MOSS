"""
backend.config.logging_config
-----------------------------
Centralized logging configuration for the MOSS application.

This module sets up the root logger and provides utilities to configure
log handlers (console, rotating file) and formatters. It supports standard
`RotatingFileHandler` and optionally `ConcurrentRotatingFileHandler` for
multi-process environments if the library is installed.
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# --- Import for Concurrent Handler ---
# Attempt to import the concurrent log handler for multi-process safety,
# especially on Windows. Fall back to standard RotatingFileHandler if unavailable.
try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
    CONCURRENT_HANDLER_AVAILABLE = True
except ImportError:
    # Use standard RotatingFileHandler as a fallback if concurrent_log_handler is not installed.
    ConcurrentRotatingFileHandler = RotatingFileHandler
    CONCURRENT_HANDLER_AVAILABLE = False
# --- END Import ---

# --- Log Directory Setup ---
# Define the directory where log files will be stored relative to this file's location.
# Assumes this file is in backend/config/
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
# Ensure the log directory exists.
LOG_DIR.mkdir(exist_ok=True)
# --- End Log Directory Setup ---

# Define a standard log format for consistency across handlers.
# Includes timestamp, log level, logger name, process ID, and the message.
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)-5.5s] [%(name)s] [%(process)d] - %(message)s"
)

# --- Function to configure a specific logger ---
def configure_logger(
    logger_instance: logging.Logger,
    log_level_console: int = logging.INFO,
    log_level_file: int = logging.DEBUG,
    log_file_name: str = "moss_app.log",
    max_bytes: int = 10*1024*1024, # 10 MB log file size limit before rotation
    backup_count: int = 5, # Number of backup log files to keep
    handler_class: type[logging.FileHandler] = RotatingFileHandler # Handler class to use (allows selecting ConcurrentRotatingFileHandler)
):
    """
    Configures console and file handlers for a given logger instance.

    Sets formatting, levels, and rotation parameters for the file handler.
    Prevents adding duplicate handlers if already configured. Allows specifying
    the file handler class (e.g., for concurrent logging).

    Args:
        logger_instance: The logging.Logger object to configure.
        log_level_console: The logging level for the console handler.
        log_level_file: The logging level for the file handler.
        log_file_name: The base name for the log file.
        max_bytes: Maximum size of the log file before rotation.
        backup_count: Number of backup log files to retain.
        handler_class: The file handler class to instantiate (e.g., RotatingFileHandler
                       or ConcurrentRotatingFileHandler).
    """

    # Set the logger's effective level to the lowest of the handlers to ensure
    # messages intended for any handler are processed by the logger.
    logger_instance.setLevel(min(log_level_console, log_level_file))
    # Prevent messages from propagating to ancestor loggers (like the root logger)
    # if this logger has its own handlers, avoiding duplicate log entries.
    logger_instance.propagate = False

    # --- Console Handler ---
    # Add a console handler (streaming to stdout) if one doesn't already exist.
    if not any(isinstance(h, logging.StreamHandler) for h in logger_instance.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(log_level_console)
        logger_instance.addHandler(console_handler)

    # --- File Handler (Rotating or Concurrent Rotating) ---
    log_file_path = LOG_DIR / log_file_name
    # Determine which handler class to actually use, falling back if necessary.
    selected_handler_class = handler_class
    if handler_class is ConcurrentRotatingFileHandler and not CONCURRENT_HANDLER_AVAILABLE:
        # Log a warning if the preferred concurrent handler isn't available and we're falling back.
        # This primarily affects multi-process scenarios on Windows.
        logging.warning(
            "concurrent-log-handler not installed. Falling back to standard "
            "RotatingFileHandler. This might cause issues in multi-process "
            "scenarios on Windows."
        )
        selected_handler_class = RotatingFileHandler

    # Check if a file handler of the *selected type* pointing to the *same file*
    # already exists for this logger instance to prevent duplicates.
    handler_exists = any(
        isinstance(h, selected_handler_class) and getattr(h, 'baseFilename', None) == str(log_file_path)
        for h in logger_instance.handlers
    )

    if not handler_exists:
        # Instantiate the chosen file handler (standard or concurrent).
        # Ensure the filename is passed as a string.
        # `delay=True` could be considered for ConcurrentRotatingFileHandler on Windows
        # if file locking issues arise, but default behaviour is usually sufficient.
        file_handler = selected_handler_class(
            filename=str(log_file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
            # delay=True # Optional: Set to True if experiencing file locking issues with ConcurrentRotatingFileHandler
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(log_level_file)
        logger_instance.addHandler(file_handler)

    # Log configuration details only if the logger actually has handlers now.
    # Use basicConfig as a last resort if no handlers were added (shouldn't normally happen here).
    if not logger_instance.hasHandlers():
         logging.basicConfig(level=logging.INFO) # Fallback basic config
    logger_instance.info(
        f"Logger '{logger_instance.name}' configured using {selected_handler_class.__name__}. "
        f"Console Level: {logging.getLevelName(log_level_console)}, "
        f"File Level: {logging.getLevelName(log_level_file)}, "
        f"File Path: {log_file_path}"
    )


# --- Main Setup Function ---
def setup_logging(
    root_log_level_console=logging.INFO,
    root_log_level_file=logging.DEBUG,
    app_log_level_console=logging.INFO, # Parameter kept for potential future granular configuration
    app_log_level_file=logging.DEBUG, # Parameter kept for potential future granular configuration
    log_file_name="moss_app.log",
    handler_class: type[logging.FileHandler] = RotatingFileHandler # Default to standard rotating handler
):
    """
    Configures the root logger for the application.

    Sets up console and file logging using the specified levels and handler class.
    If the root logger is already configured, it attempts to update the file handler's
    level if necessary and checks the handler type.

    Args:
        root_log_level_console: Logging level for console output from the root logger.
        root_log_level_file: Logging level for file output from the root logger.
        app_log_level_console: (Currently unused but available) Console level for specific app loggers.
        app_log_level_file: (Currently unused but available) File level for specific app loggers.
        log_file_name: Name of the log file.
        handler_class: The file handler class to use (e.g., RotatingFileHandler).
    """
    root_logger = logging.getLogger()

    if not root_logger.hasHandlers():
         # If the root logger has no handlers, configure it from scratch.
         # Pass the desired handler class to the configuration function.
         configure_logger(
             root_logger,
             root_log_level_console,
             root_log_level_file,
             log_file_name,
             handler_class=handler_class
        )
    else:
         # If handlers already exist, check if the file handler needs adjustment.
         handler_updated = False
         for handler in root_logger.handlers:
             # Identify the relevant file handler based on its type and filename.
             # Check if it's a FileHandler subclass and has a baseFilename attribute matching the target log file.
             if isinstance(handler, logging.FileHandler) and getattr(handler, 'baseFilename', None) and getattr(handler, 'baseFilename', '').endswith(log_file_name):
                 # Check if the existing handler is of the type we intended to use.
                 if not isinstance(handler, handler_class):
                      root_logger.warning(
                          f"Root logger has existing handler of wrong type ({type(handler).__name__}) "
                          f"for {log_file_name}. Expected {handler_class.__name__}. "
                          "Reconfiguration might be needed manually or on restart."
                        )
                 # Check if the existing handler's level matches the desired file level.
                 elif handler.level != root_log_level_file:
                     root_logger.info(
                         f"Updating existing file handler level for root logger to "
                         f"{logging.getLevelName(root_log_level_file)}"
                    )
                     handler.setLevel(root_log_level_file)
                 handler_updated = True
                 # Assume only one file handler corresponds to this log file name.
                 break

         if handler_updated:
             root_logger.info(
                 f"Root logger already configured. Ensured file level is "
                 f"{logging.getLevelName(root_log_level_file)} for handler type {handler_class.__name__}."
            )
         else:
              # Log a warning if root logger was configured but no matching handler was found to update.
              root_logger.warning(
                  f"Root logger already configured, but no matching file handler found "
                  f"for {log_file_name} and type {handler_class.__name__} to update level."
                )

# --- Example Usage in other modules ---
# import logging
#
# # Get a logger specific to the current module.
# logger = logging.getLogger(__name__)
#
# # Example log messages:
# logger.info("This is an informational message.")
# logger.debug("This is a debug message, typically useful for development.")
# logger.warning("This indicates a potential issue.")
# logger.error("This signals an error that occurred.")
# logger.critical("This indicates a critical failure.")