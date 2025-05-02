# --- NEW FILE: contrib/queries/engaged_non_pr_contributors_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# --- Path Setup ---
# Ensures the script can find backend modules when run by the executor
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, func, desc, distinct
from sqlalchemy.orm import sessionmaker, Session

# Import required MOSS models
from backend.data.models import Contributor, PullRequest, Issue

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [engaged_non_pr_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def run_analysis(
    db_conn_str: str,
    repository_id: int
) -> Dict[str, Any]:
    """
    Identifies contributors who have created issues but not pull requests
    for a given repository, and counts their created issues.

    Params:
        - db_conn_str: str (Database connection string)
        - repository_id: int (The internal DB ID of the repository to analyze)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error') and data.
                         If successful, data is a list of dictionaries:
                         [{'contributor_login': str, 'issue_count': int}, ...]
                         ordered by issue count descending.
                         If error, data contains error details.
    """
    logger.info(f"Starting engaged_non_pr_contributors_v1 analysis for repository_id={repository_id}")

    engine = None
    db: Session | None = None
    results: List[Dict[str, Any]] = []

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Step 1: Find contributors who authored PRs for the repo
        pr_authors_stmt = (
            select(distinct(PullRequest.user_id))
            .where(PullRequest.repository_id == repository_id)
        )
        pr_author_ids_result = db.execute(pr_authors_stmt).scalars().all()
        pr_author_ids: Set[int] = set(pr_author_ids_result)
        logger.debug(f"Found {len(pr_author_ids)} distinct PR authors for repo {repository_id}.")

        # Step 2: Find contributors who authored Issues for the repo
        issue_authors_stmt = (
            select(distinct(Issue.user_id))
            .where(Issue.repository_id == repository_id)
        )
        issue_author_ids_result = db.execute(issue_authors_stmt).scalars().all()
        issue_author_ids: Set[int] = set(issue_author_ids_result)
        logger.debug(f"Found {len(issue_author_ids)} distinct Issue authors for repo {repository_id}.")

        # Step 3: Find contributors in the second set but not the first
        non_pr_issue_author_ids = issue_author_ids - pr_author_ids
        logger.info(f"Found {len(non_pr_issue_author_ids)} contributors who authored issues but not PRs.")

        if not non_pr_issue_author_ids:
            logger.info("No contributors found who only authored issues.")
            return {"result_type": "table", "data": []}

        # Step 4: For these contributors, query counts of their Issues in this repo
        aggregation_stmt = (
            select(
                Contributor.login.label("contributor_login"),
                func.count(Issue.id).label("issue_count")
            )
            .select_from(Contributor)
            .join(Issue, Contributor.id == Issue.user_id)
            .where(Contributor.id.in_(non_pr_issue_author_ids))
            .where(Issue.repository_id == repository_id) # Ensure count is only for this repo
            .group_by(Contributor.login)
            .order_by(desc("issue_count"))
        )

        logger.info("Executing non-PR contributor issue count query...")
        aggregation_results = db.execute(aggregation_stmt).mappings().all()

        # Format results
        results = [dict(row) for row in aggregation_results]

        logger.info(f"Aggregated issue counts for {len(results)} non-PR contributors.")

    except Exception as e:
        logger.exception(f"Error during engaged_non_pr_contributors_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {"result_type": "table", "data": results}