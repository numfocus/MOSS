# --- UPDATED FILE: contrib/queries/top_subjects_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

# --- Path Setup ---
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, func, and_, distinct, desc, Column
from sqlalchemy.orm import sessionmaker, Session, aliased, Query

# Import required MOSS models
from backend.data.models import (
    Repository, Work, DOIReference, Institution, Affiliation, Authorship,
    WorkTopic, Topic, Subfield, Field, Domain
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [top_subjects_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# --- Helper function for single level analysis ---
def _get_top_subjects_for_level(
    db: Session,
    level: str,
    top_n: int,
    target_work_ids: Optional[Set[int]] = None
) -> List[Dict[str, Any]]:
    """
    Performs the aggregation for a single subject level.
    """
    logger.debug(f"Calculating top subjects for level: {level}")
    results: List[Dict[str, Any]] = []

    # Base query joining Work through the hierarchy
    base_query_stmt = (
        select(
            # Select necessary IDs and names for grouping and context
            Domain.id.label("domain_id"), Domain.display_name.label("domain_name"),
            Field.id.label("field_id"), Field.display_name.label("field_name"),
            Subfield.id.label("subfield_id"), Subfield.display_name.label("subfield_name"),
            Topic.id.label("topic_id"), Topic.display_name.label("topic_name"),
            func.count(distinct(Work.id)).label("work_count") # Count distinct works
        )
        .select_from(Work)
        .join(WorkTopic, Work.id == WorkTopic.work_id)
        .join(Topic, WorkTopic.topic_id == Topic.id)
        .join(Subfield, Topic.subfield_id == Subfield.id)
        .join(Field, Subfield.field_id == Field.id)
        .join(Domain, Field.domain_id == Domain.id)
    )

    # Apply work ID filter if target_work_ids is not None
    if target_work_ids is not None:
        if not target_work_ids: # Handle empty set case explicitly
            logger.debug(f"Target work ID set is empty for level {level}, returning no results.")
            return []
        base_query_stmt = base_query_stmt.where(Work.id.in_(target_work_ids))

    # --- Dynamic Aggregation based on subject_level ---
    group_by_cols: List[Tuple[Column, str]] = [] # Store tuples of (Column, label_name)
    select_cols: List[Column] = [] # Store columns to select directly

    if level == 'topic':
        group_by_cols = [
            (Topic.id, "topic_id"), (Topic.display_name, "topic_name"),
            (Subfield.id, "subfield_id"), (Subfield.display_name, "subfield_name"),
            (Field.id, "field_id"), (Field.display_name, "field_name"),
            (Domain.id, "domain_id"), (Domain.display_name, "domain_name")
        ]
        select_cols = [col for col, _ in group_by_cols]
        parent_info = lambda row: f"{row.get('subfield_name')} (Subfield) / {row.get('field_name')} (Field) / {row.get('domain_name')} (Domain)" if row.get('subfield_name') else None

    elif level == 'subfield':
        group_by_cols = [
             (Subfield.id, "subfield_id"), (Subfield.display_name, "subfield_name"),
             (Field.id, "field_id"), (Field.display_name, "field_name"),
             (Domain.id, "domain_id"), (Domain.display_name, "domain_name")
        ]
        select_cols = [col for col, _ in group_by_cols]
        parent_info = lambda row: f"{row.get('field_name')} (Field) / {row.get('domain_name')} (Domain)" if row.get('field_name') else None

    elif level == 'field':
        group_by_cols = [
            (Field.id, "field_id"), (Field.display_name, "field_name"),
            (Domain.id, "domain_id"), (Domain.display_name, "domain_name")
        ]
        select_cols = [col for col, _ in group_by_cols]
        parent_info = lambda row: f"{row.get('domain_name')} (Domain)" if row.get('domain_name') else None

    elif level == 'domain':
        group_by_cols = [
             (Domain.id, "domain_id"), (Domain.display_name, "domain_name")
        ]
        select_cols = [col for col, _ in group_by_cols]
        parent_info = lambda row: None
    else:
        # Should not happen due to prior validation, but handle defensively
        raise ValueError(f"Invalid level '{level}' passed to helper function.")

    # Final aggregation query for this level
    final_query_stmt = (
        base_query_stmt
        .group_by(*[col for col, _ in group_by_cols]) # Group by the actual columns
        .order_by(desc("work_count"))
        .limit(top_n)
        # Re-select only the necessary columns for this level + count
        .with_only_columns(
            *[col.label(label) for col, label in group_by_cols], # Select grouped columns with labels
            func.count(distinct(Work.id)).label("work_count") # Select the count again
        )
    )

    logger.debug(f"Executing aggregation query for level '{level}'...")
    query_results = db.execute(final_query_stmt).mappings().all() # Use mappings()
    logger.info(f"Aggregation query for level '{level}' returned {len(query_results)} results.")

    # Format results
    for row_mapping in query_results:
        row_dict = dict(row_mapping) # Convert RowMapping to dict
        results.append({
            "subject_level": level,
            "subject_name": row_dict.get(f"{level}_name"),
            "subject_id": row_dict.get(f"{level}_id"),
            "parent_context": parent_info(row_dict),
            "associated_work_count": row_dict.get("work_count")
        })

    return results
# --- End Helper function ---

def run_analysis(
    db_conn_str: str,
    subject_level: str,
    top_n: int = 10,
    repository_id: Optional[int] = None,
    institution_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Identifies the top N most frequent subjects for one or all levels ('topic',
    'subfield', 'field', 'domain', 'all') associated with scholarly works,
    optionally filtered by a specific repository or institution. Includes filter
    context (repo/inst name) in the output if a filter is applied.

    Params:
        - db_conn_str: str (Database connection string)
        - subject_level: str (Level to aggregate: 'domain', 'field', 'subfield', 'topic', or 'all')
        - top_n: int (The number of top subjects to return per level, default 10)
        - repository_id: Optional[int] (Filter works linked to this repository ID)
        - institution_id: Optional[int] (Filter works linked to authors affiliated with this institution ID)

    Returns:
        - Dict[str, Any]: Contains result_type ('table' or 'error'), data, and optionally filter_context.
                         If successful, data is a list of subject summary dictionaries.
                         If error, data contains error details.
    """
    logger.info(f"Starting top_subjects_v1 analysis for level='{subject_level}', repo={repository_id}, inst={institution_id}, top_n={top_n}")

    if repository_id and institution_id:
        return {"result_type": "error", "data": {"error": "ValueError", "message": "Provide either repository_id or institution_id, not both."}}

    valid_levels = ['domain', 'field', 'subfield', 'topic', 'all']
    if subject_level not in valid_levels:
        return {"result_type": "error", "data": {"error": "ValueError", "message": f"Invalid subject_level. Choose from: {valid_levels}"}}

    engine = None
    db: Session | None = None
    all_results: List[Dict[str, Any]] = []
    target_work_ids: Optional[Set[int]] = None
    filter_context: Optional[Dict[str, Any]] = None

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Step 1: Apply filters (if any) and fetch context
        if repository_id:
            repo = db.get(Repository, repository_id)
            if not repo:
                return {"result_type": "error", "data": {"error": "NotFound", "message": f"Repository ID {repository_id} not found."}}
            filter_context = {"type": "repository", "id": repository_id, "name": repo.full_name}
            logger.info(f"Filtering works linked to repository: {repo.full_name}")
            stmt = select(distinct(DOIReference.work_id)).where(
                DOIReference.repository_id == repository_id,
                DOIReference.work_id.is_not(None)
            )
            work_ids_result = db.execute(stmt).scalars().all()
            target_work_ids = set(work_ids_result)
            if not target_work_ids:
                logger.info(f"No resolved works found linked to repository {repository_id}.")
                return {"result_type": "table", "data": [], "filter_context": filter_context}
            logger.info(f"Found {len(target_work_ids)} target works for repository {repository_id}.")

        elif institution_id:
            inst = db.get(Institution, institution_id)
            if not inst:
                 return {"result_type": "error", "data": {"error": "NotFound", "message": f"Institution ID {institution_id} not found."}}
            filter_context = {"type": "institution", "id": institution_id, "name": inst.display_name}
            logger.info(f"Filtering works linked to institution: {inst.display_name}")
            stmt = (
                 select(distinct(Authorship.work_id))
                .join(Affiliation, and_(Authorship.work_id == Affiliation.authorship_work_id, Authorship.person_id == Affiliation.authorship_person_id))
                .where(Affiliation.institution_id == institution_id)
            )
            work_ids_result = db.execute(stmt).scalars().all()
            target_work_ids = set(work_ids_result)
            if not target_work_ids:
                logger.info(f"No works found linked to institution {institution_id}.")
                return {"result_type": "table", "data": [], "filter_context": filter_context}
            logger.info(f"Found {len(target_work_ids)} target works for institution {institution_id}.")

        # Step 2: Run analysis for the specified level(s)
        if subject_level == 'all':
            levels_to_run = ['topic', 'subfield', 'field', 'domain']
            for level in levels_to_run:
                level_results = _get_top_subjects_for_level(db, level, top_n, target_work_ids)
                all_results.extend(level_results)
        else:
            all_results = _get_top_subjects_for_level(db, subject_level, top_n, target_work_ids)

    except Exception as e:
        logger.exception(f"Error during top_subjects_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {
        "result_type": "table",
        "filter_context": filter_context, # Add the context here
        "data": all_results
        }