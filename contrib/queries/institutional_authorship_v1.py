# --- NEW FILE: contrib/queries/institutional_authorship_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Set

# --- Path Setup ---
# Assuming this script is in contrib/queries/
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, func, distinct, desc, and_
from sqlalchemy.orm import sessionmaker, Session

# Import required MOSS models
from backend.data.models import (
    Repository, Work, DOIReference, Person, Institution, Authorship, Affiliation
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [inst_authorship_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def run_analysis(
    db_conn_str: str,
    repository_id: int
) -> Dict[str, Any]:
    """
    Identifies institutions associated with authors of works linked to a specific repository.

    Counts the number of distinct authors affiliated with each institution whose
    works are referenced (via DOI) within the given repository.

    Params:
        - db_conn_str: str (Database connection string)
        - repository_id: int (The internal DB ID of the repository to analyze)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error') and data.
                         If successful, data is a list of dictionaries:
                         [{'institution_name': str, 'distinct_author_count': int}, ...]
                         ordered by count descending.
                         If error, data contains error details.
    """
    logger.info(f"Starting institutional_authorship_v1 analysis for repository_id={repository_id}")

    engine = None
    db: Session | None = None
    results: List[Dict[str, Any]] = []

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # 1. Find the target Repository
        repo = db.get(Repository, repository_id)
        if not repo:
            logger.error(f"Repository ID {repository_id} not found.")
            return {"result_type": "error", "data": {"error": "NotFound", "message": f"Repository ID {repository_id} not found."}}
        logger.info(f"Found repository: {repo.full_name}")

        # 2. Find all unique Work IDs linked to the repository via DOIReference
        linked_work_ids_stmt = (
            select(distinct(DOIReference.work_id))
            .where(DOIReference.repository_id == repository_id)
            .where(DOIReference.work_id.is_not(None))
        )
        linked_work_ids_result = db.execute(linked_work_ids_stmt).scalars().all()

        if not linked_work_ids_result:
            logger.info(f"No resolved works found linked to repository {repository_id}.")
            return {"result_type": "table", "data": []}

        linked_work_ids: Set[int] = set(linked_work_ids_result)
        logger.info(f"Found {len(linked_work_ids)} unique works linked to repository {repository_id}.")

        # 3. Query Authorship, Affiliation, Institution for these Work IDs
        # 4. Group by Institution and count distinct Persons
        aggregation_stmt = (
            select(
                Institution.display_name.label("institution_name"),
                func.count(distinct(Person.id)).label("distinct_author_count")
            )
            .select_from(Work)
            .join(Authorship, Work.id == Authorship.work_id)
            .join(Person, Authorship.person_id == Person.id)
            # Ensure composite join condition for Authorship -> Affiliation
            .join(Affiliation, and_(
                Authorship.work_id == Affiliation.authorship_work_id,
                Authorship.person_id == Affiliation.authorship_person_id
            ))
            .join(Institution, Affiliation.institution_id == Institution.id)
            .where(Work.id.in_(linked_work_ids))
            .group_by(Institution.display_name)
            .order_by(desc("distinct_author_count"))
        )

        aggregation_results = db.execute(aggregation_stmt).mappings().all() # Fetch as dict-like

        # Format results
        results = [dict(row) for row in aggregation_results]

        logger.info(f"Found {len(results)} institutions associated with authors of linked works.")

    except Exception as e:
        logger.exception(f"Error during institutional_authorship_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {"result_type": "table", "data": results}