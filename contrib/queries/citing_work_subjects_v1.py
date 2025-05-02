# --- NEW FILE: contrib/queries/citing_work_subjects_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# --- Path Setup ---
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, func, and_, distinct, desc
from sqlalchemy.orm import sessionmaker, Session, aliased, Query

# Import required MOSS models
from backend.data.models import (
    Repository, Work, DOIReference, WorkCitation,
    WorkTopic, Topic, Subfield, Field, Domain
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [citing_work_subjects_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

def run_analysis(
    db_conn_str: str,
    subject_level: str,
    repository_id: Optional[int] = None,
    doi: Optional[str] = None,
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Identifies the top N most frequent subjects (Domains, Fields, Subfields, or Topics)
    associated with scholarly works that cite the work(s) linked to a specific repository or DOI.

    Params:
        - db_conn_str: str (Database connection string)
        - subject_level: str (The level to aggregate subjects: 'domain', 'field', 'subfield', or 'topic')
        - repository_id: Optional[int] (ID of the repository whose linked works' citations are analyzed)
        - doi: Optional[str] (DOI of the specific work whose citations are analyzed)
        - top_n: int (The number of top subjects to return, default 10)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error') and data.
                         If successful, data is a list of subject summary dictionaries.
                         If error, data contains error details.
    """
    logger.info(f"Starting citing_work_subjects_v1 analysis for level='{subject_level}', repo={repository_id}, doi={doi}, top_n={top_n}")

    if not repository_id and not doi:
        return {"result_type": "error", "data": {"error": "ValueError", "message": "Either repository_id or doi must be provided."}}
    if repository_id and doi:
        return {"result_type": "error", "data": {"error": "ValueError", "message": "Provide either repository_id or doi, not both."}}

    valid_levels = ['domain', 'field', 'subfield', 'topic']
    if subject_level not in valid_levels:
        return {"result_type": "error", "data": {"error": "ValueError", "message": f"Invalid subject_level. Choose from: {valid_levels}"}}

    engine = None
    db: Session | None = None
    results: List[Dict[str, Any]] = []
    target_work_ids: Set[int] = set()

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Step 1: Find the target work(s) ID(s)
        if repository_id:
            logger.info(f"Finding works linked to repository_id: {repository_id}")
            stmt = select(distinct(DOIReference.work_id)).where(
                DOIReference.repository_id == repository_id,
                DOIReference.work_id.is_not(None)
            )
            target_work_ids_result = db.execute(stmt).scalars().all()
            target_work_ids = set(target_work_ids_result)
            if not target_work_ids:
                logger.info(f"No resolved works found linked to repository {repository_id}.")
                return {"result_type": "table", "data": []}
        elif doi:
            logger.info(f"Finding work with DOI: {doi}")
            stmt = select(Work.id).where(Work.doi == doi)
            target_work_id = db.execute(stmt).scalar_one_or_none()
            if not target_work_id:
                logger.info(f"Work with DOI {doi} not found.")
                return {"result_type": "table", "data": []}
            target_work_ids = {target_work_id}

        logger.info(f"Found {len(target_work_ids)} target work ID(s).")

        # Step 2: Find works citing the target work(s)
        citing_work_ids_stmt = (
            select(distinct(WorkCitation.citing_work_id))
            .where(WorkCitation.cited_work_id.in_(target_work_ids))
        )
        citing_work_ids_result = db.execute(citing_work_ids_stmt).scalars().all()
        if not citing_work_ids_result:
            logger.info("No citing works found for the target work(s).")
            return {"result_type": "table", "data": []}
        citing_work_ids: Set[int] = set(citing_work_ids_result)
        logger.info(f"Found {len(citing_work_ids)} unique citing works.")

        # Step 3: Join citing works to the hierarchy and aggregate
        # Base query joining citing works through the hierarchy
        base_query = db.query(
            Topic.id.label("topic_id"),
            Subfield.id.label("subfield_id"), Subfield.display_name.label("subfield_name"),
            Field.id.label("field_id"), Field.display_name.label("field_name"),
            Domain.id.label("domain_id"), Domain.display_name.label("domain_name"),
            Topic.display_name.label("topic_name"),
            func.count(distinct(WorkTopic.work_id)).label("citing_work_count") # Count distinct citing works
        ).select_from(WorkTopic)\
            .join(Topic, WorkTopic.topic_id == Topic.id)\
            .join(Subfield, Topic.subfield_id == Subfield.id)\
            .join(Field, Subfield.field_id == Field.id)\
            .join(Domain, Field.domain_id == Domain.id)\
            .filter(WorkTopic.work_id.in_(citing_work_ids)) # Filter for citing works

        # --- Aggregation based on subject_level ---
        if subject_level == 'topic':
            agg_query = base_query.group_by(
                Topic.id, Topic.display_name,
                Subfield.id, Subfield.display_name, # Include parent details
                Field.id, Field.display_name,
                Domain.id, Domain.display_name
            )
            entity_name_col = Topic.display_name
            parent_info = lambda row: f"{row.subfield_name} (Subfield) / {row.field_name} (Field) / {row.domain_name} (Domain)"

        elif subject_level == 'subfield':
            agg_query = base_query.group_by(
                 Subfield.id, Subfield.display_name,
                 Field.id, Field.display_name, # Include parent details
                 Domain.id, Domain.display_name
            )
            entity_name_col = Subfield.display_name
            parent_info = lambda row: f"{row.field_name} (Field) / {row.domain_name} (Domain)"

        elif subject_level == 'field':
            agg_query = base_query.group_by(
                Field.id, Field.display_name,
                Domain.id, Domain.display_name # Include parent details
            )
            entity_name_col = Field.display_name
            parent_info = lambda row: f"{row.domain_name} (Domain)"

        else: # subject_level == 'domain'
            agg_query = base_query.group_by(Domain.id, Domain.display_name)
            entity_name_col = Domain.display_name
            parent_info = lambda row: None


        # Add ordering and limit
        final_query = agg_query.order_by(desc("citing_work_count")).limit(top_n)

        logger.info(f"Executing final aggregation query for level '{subject_level}'...")
        query_results = final_query.all()
        logger.info(f"Aggregation query returned {len(query_results)} results.")

        # Format results
        for row in query_results:
            results.append({
                "subject_level": subject_level,
                "subject_name": getattr(row, f"{subject_level}_name"),
                "subject_id": getattr(row, f"{subject_level}_id"),
                "parent_context": parent_info(row),
                "citing_work_count": row.citing_work_count
            })

    except Exception as e:
        logger.exception(f"Error during citing_work_subjects_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {"result_type": "table", "data": results}