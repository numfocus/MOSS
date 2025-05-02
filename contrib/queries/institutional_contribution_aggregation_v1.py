# --- NEW FILE: contrib/queries/institutional_contribution_aggregation_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# --- Path Setup ---
# Assuming this script is in contrib/queries/
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, func, desc
from sqlalchemy.orm import sessionmaker, Session

# Import required MOSS models
from backend.data.models import (
    Repository,
    Institution, # Although not directly queried, good practice
    RepositoryContributorAssociation,
    RepositoryInstitutionAffiliation,
    Contributor # Needed for unique count potentially
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [inst_contrib_agg_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def run_analysis(
    db_conn_str: str,
    institution_id: int,
    min_confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Aggregates contribution counts for repositories affiliated with a specific institution.

    Steps:
    1. Find repositories affiliated with the target institution above a confidence threshold.
    2. For these repositories, query the contributor associations to sum total contributions
       and count unique contributors.
    3. Return a table summarizing contributions per affiliated repository.

    Params:
        - db_conn_str: str (Database connection string)
        - institution_id: int (The internal DB ID of the target institution)
        - min_confidence: float (Minimum confidence score for repository affiliation, default 0.5)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error') and data.
                         If successful, data is a list of repository contribution summary dictionaries.
                         If error, data contains error details.
    """
    logger.info(f"Starting institutional_contribution_aggregation_v1 analysis for institution_id={institution_id}, min_confidence={min_confidence}")

    engine = None
    db: Session | None = None
    results: List[Dict[str, Any]] = []

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Step 1: Find affiliated repository IDs
        affiliated_repo_ids_stmt = (
            select(RepositoryInstitutionAffiliation.repository_id)
            .where(
                RepositoryInstitutionAffiliation.institution_id == institution_id,
                RepositoryInstitutionAffiliation.confidence_score >= min_confidence
            )
            .distinct()
        )
        affiliated_repo_ids_result = db.execute(affiliated_repo_ids_stmt).scalars().all()

        if not affiliated_repo_ids_result:
            logger.info("No repositories found affiliated with the institution above the confidence threshold.")
            return {"result_type": "table", "data": []}
        affiliated_repo_ids: Set[int] = set(affiliated_repo_ids_result)
        logger.info(f"Found {len(affiliated_repo_ids)} affiliated repositories.")

        # Step 2 & 3: Aggregate contributions for these repositories
        RepoContribAssoc = RepositoryContributorAssociation # Alias for brevity

        aggregation_stmt = (
            select(
                Repository.id.label("repository_id"),
                Repository.full_name.label("repository_full_name"),
                func.sum(RepoContribAssoc.contributions_count).label("total_contributions"),
                func.count(RepoContribAssoc.contributor_id).label("unique_contributors_count") # Count distinct contributors associated
            )
            .select_from(Repository)
            .join(RepoContribAssoc, Repository.id == RepoContribAssoc.repository_id)
            .where(Repository.id.in_(affiliated_repo_ids))
            .group_by(Repository.id, Repository.full_name)
            .order_by(desc("total_contributions")) # Order by contribution count
        )

        aggregation_results = db.execute(aggregation_stmt).mappings().all() # Fetch results as dict-like objects

        # Format results into a list of dictionaries
        results = [dict(row) for row in aggregation_results] # Convert RowMapping to dict

        # Optional: Post-process to handle potential NULL sums if no contributions are recorded
        for row in results:
             if row['total_contributions'] is None:
                 row['total_contributions'] = 0 # Replace None sum with 0

        logger.info(f"Aggregated contributions for {len(results)} repositories.")

    except Exception as e:
        logger.exception(f"Error during institutional_contribution_aggregation_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {"result_type": "table", "data": results}