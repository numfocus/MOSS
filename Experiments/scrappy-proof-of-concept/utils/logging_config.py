# utils/logging_config.py
import logging
from config import LOG_LEVEL

def setup_logging():
    """
    Configures logging for the application.
    Uses the LOG_LEVEL from the configuration.
    """
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
