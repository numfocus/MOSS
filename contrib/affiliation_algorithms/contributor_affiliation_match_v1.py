"""
contrib.affiliation_algorithms.contributor_affiliation_match_v1
-------------------------------------------------------------

This script implements an affiliation algorithm that links repositories to
institutions based on the affiliations of authors whose works are referenced
(via DOI) within those repositories. It assigns a fixed confidence score
to affiliations discovered through this method.
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Set

# --- Path Setup ---
# Determine the project root directory based on the script's location
# and add it to the Python path if not already present. This allows
# for importing modules from the backend.
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

from sqlalchemy import create_engine, select, distinct
from sqlalchemy.orm import sessionmaker, Session

# Import necessary MOSS models for database interaction, covering repositories,
# institutions, authors, works, affiliations, and DOI references.
from backend.data.models import (
    Repository,
    Institution,
    Affiliation,
    Authorship,
    Person,
    Work,
    DOIReference
)

# --- Logging Setup ---
# Configure basic logging to provide visibility into the script's execution.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [contributor_affil_match_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def calculate_affiliations(
    institution_id: int,
    db_conn_str: str
) -> List[Dict[str, Any]]:
    """
    Identifies potential repository-institution affiliations.

    This algorithm works by:
    1. Finding all persons affiliated with the given `institution_id`.
    2. Identifying all works authored by these affiliated persons.
    3. Locating repositories that contain DOI references pointing to these works.
    4. Aggregating these findings by repository, assigning a predefined
       confidence score, and collecting evidence (the specific works linking
       the repository to the institution's authors).

    Args:
        institution_id: The database ID of the institution to find affiliated
                        repositories for.
        db_conn_str: Database connection string.

    Returns:
        A list of dictionaries, where each dictionary represents a potential
        affiliation found by this algorithm. Each dictionary includes:
        - 'repository_id': The ID of the potentially affiliated repository.
        - 'confidence_score': A fixed score (0.7) indicating the confidence
                              assigned by this specific algorithm.
        - 'evidence': A dictionary detailing the reason for the affiliation,
                      including the signal type and examples of linking works/DOIs.
                      Example:
                      {
                          "signal_type": "affiliated_author_work_reference",
                          "details": [
                              {"type": "affiliated_author_work", "work_id": 123, "doi": "10.xxxx/abc"},
                              ... (up to 5 examples)
                          ]
                      }
        Returns an empty list if no affiliations are found or if an error occurs.
    """
    logger.info(f"Starting contributor_affiliation_match_v1 for Institution ID {institution_id}")

    engine = None
    db: Session | None = None
    # Use a dictionary to aggregate evidence per repository ID efficiently.
    # Key: repository_id, Value: {'score': float, 'evidence_list': list}
    results_map: Dict[int, Dict[str, Any]] = {}
    # Define a fixed confidence score for affiliations found by this method.
    # This reflects that the link is strong but indirect (author -> work -> repo).
    CONFIDENCE_SCORE = 0.7

    try:
        # Establish database connection.
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Step 1: Find all unique person IDs linked to the target institution
        # via the Affiliation table.
        person_ids_stmt = (
            select(distinct(Affiliation.authorship_person_id))
            .where(Affiliation.institution_id == institution_id)
        )
        affiliated_person_ids = db.execute(person_ids_stmt).scalars().all()

        if not affiliated_person_ids:
            # If no affiliated persons found, no further links can be made.
            logger.info(f"No persons found affiliated with Institution ID {institution_id}.")
            return []

        logger.info(f"Found {len(affiliated_person_ids)} persons affiliated with Inst ID {institution_id}.")

        # Step 2: Find all unique work IDs associated with these affiliated persons
        # via the Authorship table.
        work_ids_stmt = (
            select(distinct(Authorship.work_id))
            .where(Authorship.person_id.in_(affiliated_person_ids))
        )
        authored_work_ids = db.execute(work_ids_stmt).scalars().all()

        if not authored_work_ids:
            # If these authors have no associated works in the DB, stop.
            logger.info(f"No works found authored by affiliated persons.")
            return []

        logger.info(f"Found {len(authored_work_ids)} works authored by affiliated persons.")

        # Step 3: Find repository links (via DOIReference) to these authored works.
        # Select distinct repository IDs, along with the linking work ID and DOI for evidence.
        repo_link_stmt = (
             select(distinct(DOIReference.repository_id), DOIReference.work_id, DOIReference.doi)
            .where(DOIReference.work_id.in_(authored_work_ids)) # Link to the works found in Step 2
            .where(DOIReference.repository_id.isnot(None)) # Ensure the reference links to a known repository
        )
        # Fetch results as dictionary-like rows for easy access by column name.
        repo_links = db.execute(repo_link_stmt).mappings().all()

        logger.info(f"Found {len(repo_links)} DOI references linking affiliated works to repositories.")

        # Step 4: Aggregate the findings by repository ID.
        for link in repo_links:
            repo_id = link['repository_id']
            work_id = link['work_id']
            doi = link['doi']

            # Structure the evidence for this specific link (work/DOI).
            evidence_item = {
                "type": "affiliated_author_work", # Type of evidence detail
                "work_id": work_id,
                "doi": doi
                # Note: Adding person_id here would require another join or lookup,
                # omitted for simplicity in this version.
            }

            if repo_id not in results_map:
                # First time encountering this repository, initialize its entry.
                results_map[repo_id] = {
                    "score": CONFIDENCE_SCORE, # Assign the predefined score
                    "evidence_list": [evidence_item] # Start the list of evidence
                }
            else:
                # Repository already seen, just add the new piece of evidence.
                # The confidence score remains fixed in this simple model.
                results_map[repo_id]["evidence_list"].append(evidence_item)
                # Limit the number of evidence examples stored per repository for brevity.
                max_evidence = 5
                if len(results_map[repo_id]["evidence_list"]) > max_evidence:
                     # Keep the first few examples and add a truncation indicator.
                     results_map[repo_id]["evidence_list"] = results_map[repo_id]["evidence_list"][:max_evidence] + \
                         [{"type": "truncated", "count": len(results_map[repo_id]["evidence_list"])}]


    except Exception as e:
        # Catch any unexpected errors during execution.
        logger.exception(f"Error during contributor_affiliation_match_v1 execution: {e}")
        return [] # Return empty list on error
    finally:
        # Ensure database resources are released.
        if db:
            db.close()
            logger.info("Database session closed.")
        if engine:
            engine.dispose()
            logger.info("Database engine disposed.")

    # Step 5: Format the aggregated results from the map into the final list structure.
    final_results = []
    for repo_id, data in results_map.items():
        final_results.append({
            "repository_id": repo_id,
            "confidence_score": data["score"],
            "evidence": { # Structure the evidence clearly
                "signal_type": "affiliated_author_work_reference", # Overall type of signal
                "details": data["evidence_list"] # List of specific work/DOI links
                }
        })

    logger.info(f"Contributor_affiliation_match_v1 finished. Found {len(final_results)} potential repository affiliations for Inst {institution_id}.")
    return final_results

# --- Example Test Call Block ---
# This block is typically commented out but can be used for direct script
# execution during development or testing, provided the necessary environment
# variables (like DATABASE_URL) and database state exist.
#
# if __name__ == "__main__":
#     # Example: Load connection string from environment variable
#     TEST_DB_CONN_STR = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")
#     # Example: Set a specific institution ID to test with
#     TEST_INST_ID = 1 # Replace with a valid Institution ID from your DB
#
#     # Basic checks before running the test
#     if not TEST_DB_CONN_STR or "user:password" in TEST_DB_CONN_STR: # Basic check for default placeholder
#         print("Error: DATABASE_URL environment variable not set or using default placeholder.", file=sys.stderr)
#     elif TEST_INST_ID is None:
#          print("Error: TEST_INST_ID not set for testing.", file=sys.stderr)
#     else:
#         print(f"Running test for Inst ID: {TEST_INST_ID}")
#         affiliations = calculate_affiliations(TEST_INST_ID, TEST_DB_CONN_STR)
#         print("\nResults:")
#         # Pretty-print the JSON output for readability
#         import json
#         print(json.dumps(affiliations, indent=2))
# --- End Example Test Call Block ---