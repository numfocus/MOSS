# --- UPDATED FILE: contrib/queries/repo_health_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional # Added Optional
from datetime import datetime, timezone, timedelta

# --- Path Setup ---
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, text, Integer, cast
from sqlalchemy.orm import sessionmaker, Session
from backend.data.models import Repository # Import model directly

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [repo_health_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

def calculate_repo_health(repo: Repository) -> Dict[str, Any]:
    """Calculates health score and metrics for a single Repository object."""
    metrics = {}
    score_components = {}

    # Metric 1: Has Description?
    metrics['has_description'] = bool(repo.description and len(repo.description) > 10)
    score_components['description'] = 0.1 if metrics['has_description'] else 0.0

    # Metric 2: Has License?
    metrics['has_license'] = bool(repo.license and repo.license.get('key') != 'other')
    score_components['license'] = 0.15 if metrics['has_license'] else 0.0

    # Metric 3: Recently Pushed? (e.g., within last 6 months)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    metrics['recently_pushed'] = bool(repo.gh_pushed_at and repo.gh_pushed_at > cutoff_date)
    score_components['activity'] = 0.25 if metrics['recently_pushed'] else 0.05 # Some score even if old

    # Metric 4: Star Score (simple scaling)
    stars = repo.stargazers_count or 0
    metrics['stars'] = stars
    # Simple log scale, capping score contribution
    score_components['stars'] = min(0.25 * ( (stars / 100) if stars < 100 else (1 + (stars-100)**0.2 / 5)), 0.25)

    # Metric 5: Fork Score (simple scaling)
    forks = repo.forks_count or 0
    metrics['forks'] = forks
    score_components['forks'] = min(0.10 * ( (forks / 20) if forks < 20 else (1 + (forks-20)**0.2 / 10) ), 0.10)

    # Metric 6: Open Issues vs Watchers (basic proxy for engagement vs. potential issues)
    # Avoid division by zero
    open_issues = repo.open_issues_count or 0
    watchers = repo.watchers_count or 0 # Note: GitHub API v3 'watchers' is actually 'subscribers'
    metrics['open_issues'] = open_issues
    metrics['subscribers'] = watchers
    issue_ratio = open_issues / (watchers + 1) # Add 1 to avoid zero division
    # Lower ratio is better, capped score
    score_components['issues'] = max(0.15 * (1 - min(issue_ratio, 1.0)), 0)


    # Calculate final score (sum of components, max 1.0)
    total_score = sum(score_components.values())

    return {
        "repository_id": repo.id,
        "full_name": repo.full_name,
        "score": round(total_score, 3),
        "metrics": metrics,
        "score_components": {k: round(v, 3) for k, v in score_components.items()} # Rounded components
    }


# --- UPDATED Function Signature and Logic ---
def run_analysis(
    db_conn_str: str,
    repository_id: Optional[int] = None,
    repository_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Calculates a basic health score for one or more GitHub repositories.

    Accepts either a single repository_id or a list of repository_ids.
    If repository_ids is provided, it takes precedence.

    Params:
        - db_conn_str: str (Database connection string)
        - repository_id: Optional[int] (ID of a single repository)
        - repository_ids: Optional[List[int]] (List of repository IDs)

    Returns:
        - Dict[str, Any]: Contains result_type and data.
                         If successful, data is a list of health score dictionaries.
                         If error, data contains error details.
    """
    logger.info("Starting repo_health_v1 analysis...")

    if not repository_ids and repository_id is None:
        logger.error("Missing required parameter: provide either repository_id or repository_ids.")
        return {"result_type": "error", "data": {"error": "ValueError", "message": "Missing required parameter: provide either repository_id or repository_ids."}}

    target_ids: List[int] = []
    if repository_ids:
        logger.info(f"Processing list of {len(repository_ids)} repository IDs.")
        # Ensure IDs are integers
        try:
            target_ids = [int(rid) for rid in repository_ids]
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid format for repository_ids: {e}")
            return {"result_type": "error", "data": {"error": "TypeError", "message": f"Invalid repository_ids format: {e}"}}
    elif repository_id is not None:
        logger.info(f"Processing single repository ID: {repository_id}")
        try:
            target_ids = [int(repository_id)]
        except (ValueError, TypeError) as e:
             logger.error(f"Invalid format for repository_id: {e}")
             return {"result_type": "error", "data": {"error": "TypeError", "message": f"Invalid repository_id format: {e}"}}

    if not target_ids:
         return {"result_type": "table", "data": []} # Return empty if no valid IDs

    engine = None
    db: Session | None = None
    results_list: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Fetch all target repositories in one query
        stmt = select(Repository).where(Repository.id.in_(target_ids))
        repos_found = db.execute(stmt).scalars().all()
        found_ids = {repo.id for repo in repos_found}

        logger.info(f"Found {len(repos_found)} repositories in the database out of {len(target_ids)} requested.")

        # Check for missing repos
        missing_ids = set(target_ids) - found_ids
        if missing_ids:
            msg = f"Repositories not found for IDs: {', '.join(map(str, missing_ids))}"
            logger.warning(msg)
            errors.append(msg) # Add to overall errors/notes

        # Calculate health for found repos
        for repo in repos_found:
            try:
                health_data = calculate_repo_health(repo)
                results_list.append(health_data)
            except Exception as calc_err:
                logger.error(f"Error calculating health for repo {repo.id}: {calc_err}", exc_info=True)
                errors.append(f"Error calculating health for repo {repo.id}: {calc_err}")
                # Optionally add a partial error entry to results_list
                results_list.append({
                    "repository_id": repo.id,
                    "full_name": repo.full_name,
                    "score": None,
                    "error": str(calc_err)
                })


    except Exception as e:
        logger.exception(f"Error during repo_health_v1 execution: {e}")
        # Return a general error if DB connection or main query fails
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    logger.info(f"Repo_health_v1 analysis finished. Calculated health for {len(results_list)} repositories.")
    # Return as a table, include errors/notes if any occurred
    return {
        "result_type": "table",
        "data": results_list,
        "notes": errors if errors else None # Add notes field for missing IDs or calculation errors
    }