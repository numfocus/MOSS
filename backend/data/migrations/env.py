import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- MOSS CONFIGURATION START ---
# Add the project's root directory to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import the Base FIRST
from backend.data.database import Base
# Import your application settings
from backend.config.settings import settings

# ===> Crucially, import all models HERE <===
# This ensures they register with Base.metadata *before* we assign it below
# Wrapped in a try-except just in case there's an import error during testing
try:
    import backend.data.models # This should trigger models/__init__.py
    print("Models package imported successfully in env.py")
except ImportError as e:
    print(f"ERROR importing models package in env.py: {e}", file=sys.stderr)
    # Depending on the error, might want to raise it

# --- MOSS CONFIGURATION END ---


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# --- MOSS CONFIGURATION START ---
# Comment out the fileConfig line
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)
# --- MOSS CONFIGURATION END ---


# add your model's MetaData object here
# for 'autogenerate' support
# --- MOSS CONFIGURATION START ---
# Now assign target_metadata AFTER models have been imported
target_metadata = Base.metadata
# --- MOSS CONFIGURATION END ---


# (Rest of the file remains the same - run_migrations_offline / run_migrations_online)
# ...

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    # ... (rest of docstring) ...
    """
    # --- MOSS MODIFICATION START ---
    if not settings.DATABASE_URL:
         raise ValueError("DATABASE_URL not found in settings for offline migration.")
    url = settings.DATABASE_URL
    # --- MOSS MODIFICATION END ---

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    # ... (rest of docstring) ...
    """
    # --- MOSS MODIFICATION START ---
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
         raise Exception("Alembic config section [alembic] not found in alembic.ini")

    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL not found in settings for online migration.")
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # --- MOSS MODIFICATION END ---


    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()