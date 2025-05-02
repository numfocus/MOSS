# --- NEW FILE: contrib/queries/works_by_citing_institution_v1.py ---

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

from sqlalchemy import create_engine, select, func, and_, distinct, join, alias
from sqlalchemy.orm import sessionmaker, Session, aliased

# Import required MOSS models
from backend.data.models import (
    Repository,
    Institution,
    Work,
    DOIReference,
    WorkCitation,
    Authorship,
    Affiliation,
    RepositoryInstitutionAffiliation
)
# Import required MOSS schema for structuring output
from backend.schemas.responses import WorkSummary

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [works_by_citing_inst_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def run_analysis(
    db_conn_str: str,
    institution_id: int,
    min_confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Finds scholarly works that cite repositories affiliated with a specific institution,
    where at least one author of the citing work is also affiliated with that same institution.

    Steps:
    1. Find repositories affiliated with the target institution above a confidence threshold.
    2. Find works cited by DOIs found in those repositories.
    3. Find works that cite the works found in step 2.
    4. Filter these citing works to include only those where at least one author
       has an affiliation record linking them to the target institution.
    5. Return a summary list of these filtered citing works.

    Params:
        - db_conn_str: str (Database connection string)
        - institution_id: int (The internal DB ID of the target institution)
        - min_confidence: float (Minimum confidence score for repository affiliation, default 0.5)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error') and data.
                         If successful, data is a list of work summary dictionaries.
                         If error, data contains error details.
    """
    logger.info(f"Starting works_by_citing_institution_v1 analysis for institution_id={institution_id}, min_confidence={min_confidence}")

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

        # Step 2: Find works cited by these repositories (W_cited)
        cited_work_ids_stmt = (
            select(DOIReference.work_id)
            .where(
                DOIReference.repository_id.in_(affiliated_repo_ids),
                DOIReference.work_id.is_not(None) # Ensure the DOI was resolved
            )
            .distinct()
        )
        cited_work_ids_result = db.execute(cited_work_ids_stmt).scalars().all()
        if not cited_work_ids_result:
            logger.info("No cited works found linked to the affiliated repositories.")
            return {"result_type": "table", "data": []}
        cited_work_ids: Set[int] = set(cited_work_ids_result)
        logger.info(f"Found {len(cited_work_ids)} unique works cited by affiliated repositories.")

        # Step 3 & 4: Find citing works (W_citing) whose authors are affiliated with the target institution
        # This is the most complex query. We need W_citing where:
        # - W_citing cites a W_cited from the set above
        # - W_citing has an author (Person) who is affiliated with the target institution_id

        # Aliases can make joins clearer
        WC = WorkCitation
        Aship = Authorship
        Aff = Affiliation

        # Select distinct citing work IDs that meet the criteria
        valid_citing_work_ids_stmt = (
            select(distinct(WC.citing_work_id))
            .select_from(WC)
            .join(Aship, WC.citing_work_id == Aship.work_id)
            .join(Aff, and_(
                Aship.work_id == Aff.authorship_work_id,
                Aship.person_id == Aff.authorship_person_id
            ))
            .where(
                WC.cited_work_id.in_(cited_work_ids),
                Aff.institution_id == institution_id
            )
        )

        valid_citing_work_ids_result = db.execute(valid_citing_work_ids_stmt).scalars().all()
        if not valid_citing_work_ids_result:
            logger.info("No citing works found with authors affiliated with the target institution.")
            return {"result_type": "table", "data": []}
        valid_citing_work_ids: List[int] = valid_citing_work_ids_result
        logger.info(f"Found {len(valid_citing_work_ids)} candidate citing works with relevant author affiliations.")

        # Step 5: Fetch Work details for the valid citing work IDs
        final_works_stmt = (
            select(Work)
            .where(Work.id.in_(valid_citing_work_ids))
            .order_by(Work.publication_year.desc().nulls_last(), Work.title)
        )
        final_works = db.execute(final_works_stmt).scalars().all()

        # Format results using WorkSummary Pydantic model (or manually construct dict)
        for work in final_works:
             # Use the Pydantic model to serialize, handling potential None values
             try:
                 summary = WorkSummary.model_validate(work)
                 results.append(summary.model_dump())
             except Exception as pydantic_err:
                 logger.warning(f"Could not validate Work ID {work.id} for WorkSummary: {pydantic_err}")
                 # Fallback to manual dict creation if validation fails
                 results.append({
                     "id": work.id,
                     "title": work.title,
                     "doi": work.doi,
                     "publication_year": work.publication_year
                 })

        logger.info(f"Returning {len(results)} works.")

    except Exception as e:
        logger.exception(f"Error during works_by_citing_institution_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {"result_type": "table", "data": results}