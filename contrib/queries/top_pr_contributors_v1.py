# --- CORRECTED FILE: contrib/queries/top_pr_contributors_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Path Setup ---
# Ensures the script can find backend modules when run by the executor
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, func, desc
from sqlalchemy.orm import sessionmaker, Session

# Import required MOSS models
from backend.data.models import Contributor, PullRequest

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [top_pr_contrib_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def run_analysis(
    db_conn_str: str,
    repository_id: int,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Identifies the top contributors to a repository based on merged Pull Requests.

    Params:
        - db_conn_str: str (Database connection string)
        - repository_id: int (The internal DB ID of the repository to analyze)
        - limit: int (The maximum number of contributors to return, default 10)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error') and data.
                         If successful, data is a list of dictionaries:
                         [{'contributor_login': str, 'merged_pr_count': int}, ...]
                         ordered by count descending.
                         If error, data contains error details.
    """
    logger.info(f"Starting top_pr_contributors_v1 analysis for repository_id={repository_id}, limit={limit}")

    engine = None
    db: Session | None = None
    results: List[Dict[str, Any]] = []

    if limit <= 0:
         logger.warning("Limit must be a positive integer. Setting limit to 10.")
         limit = 10

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Query to count merged PRs per contributor for the specified repository
        aggregation_stmt = (
            select(
                Contributor.login.label("contributor_login"),
                func.count(PullRequest.id).label("merged_pr_count")
            )
            .select_from(Contributor)
            .join(PullRequest, Contributor.id == PullRequest.user_id)
            .where(PullRequest.repository_id == repository_id)
            # --- FIX: Use correct column name 'gh_merged_at' ---
            .where(PullRequest.gh_merged_at.isnot(None)) # Filter for merged PRs
            # --- END FIX ---
            .group_by(Contributor.login)
            .order_by(desc("merged_pr_count"))
            .limit(limit)
        )

        logger.info("Executing contributor PR count query...")
        aggregation_results = db.execute(aggregation_stmt).mappings().all() # Fetch as dict-like

        # Format results
        results = [dict(row) for row in aggregation_results]

        logger.info(f"Found {len(results)} contributors matching the criteria.")

    except Exception as e:
        logger.exception(f"Error during top_pr_contributors_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {"result_type": "table", "data": results}