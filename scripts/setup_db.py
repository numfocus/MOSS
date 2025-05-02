import os
import sys
import logging

# Ensure the backend package is discoverable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alembic.config import Config
from alembic import command
from backend.config.logging_config import setup_logging # Use our logging setup
# Import settings to ensure .env is loaded if alembic.ini relies on it indirectly
# (Although our current env.py loads it directly)
try:
    from backend.config import settings
except ValueError as e:
    print(f"ERROR: Could not load settings. Is .env configured correctly? Details: {e}")
    sys.exit(1)
except ImportError as e:
     print(f"ERROR: Could not import settings. Path issue? Details: {e}")
     sys.exit(1)


# Set up logging for the script
setup_logging()
logger = logging.getLogger(__name__)

def main():
    """Applies Alembic migrations to the database."""
    logger.info("Starting database setup/migration...")

    # Construct the absolute path to alembic.ini relative to this script
    # Assumes this script is in moss/scripts/ and alembic.ini is in moss/
    alembic_ini_path = os.path.join(PROJECT_ROOT, 'alembic.ini')
    logger.info(f"Using Alembic config: {alembic_ini_path}")

    if not os.path.exists(alembic_ini_path):
        logger.error(f"Alembic config file not found at {alembic_ini_path}")
        return False

    try:
        # Create Alembic Config object
        alembic_cfg = Config(alembic_ini_path)

        # Set the script location programmatically if needed,
        # though it should be picked up from alembic.ini
        # script_location = os.path.join(PROJECT_ROOT, 'backend', 'data', 'migrations')
        # alembic_cfg.set_main_option("script_location", script_location)

        logger.info("Applying migrations (upgrade head)...")
        # Apply migrations up to 'head' (the latest revision)
        command.upgrade(alembic_cfg, "head")

        logger.info("Database migrations applied successfully.")
        return True
    except Exception as e:
        logger.error(f"Error applying database migrations: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    if main():
        print("Database setup script completed successfully.")
        sys.exit(0)
    else:
        print("Database setup script failed.")
        sys.exit(1)