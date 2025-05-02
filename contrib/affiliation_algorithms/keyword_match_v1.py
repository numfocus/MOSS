"""
contrib.affiliation_algorithms.keyword_match_v1
-----------------------------------------------

This script implements an affiliation algorithm designed to identify potential
links between repositories and institutions based on keyword matching within
the MOSS database. It searches for keywords in repository descriptions, topics,
and owner logins, assigning confidence scores based on the match location.
"""

import sys
import os
import logging
import re # Required for potential future regex use, though not used currently
from pathlib import Path
from typing import List, Dict, Any, Set

# --- Path Setup ---
# Determine the project root directory relative to this script's location
# and add it to the system path if necessary. This ensures that necessary
# backend modules, particularly data models, can be imported.
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

# Import necessary SQLAlchemy components for database interaction.
from sqlalchemy import create_engine, or_, select, text
from sqlalchemy.orm import sessionmaker, Session # `joinedload` was removed as it wasn't used.

# Import required MOSS data models.
from backend.data.models import Repository, Owner

# --- Logging Setup ---
# Configure basic logging for the script to provide operational insights,
# such as the keywords being used and the number of potential matches found.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [keyword_match_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def calculate_affiliations(
    institution_id: int, # Included for consistency with the algorithm signature pattern.
    keywords: List[str],
    db_conn_str: str
) -> List[Dict[str, Any]]:
    """
    Calculates repository-institution affiliations by matching keywords in DB metadata.

    This function performs the following steps:
    1. Connects to the database specified by `db_conn_str`.
    2. Prepares search patterns from the provided `keywords` for case-insensitive matching.
    3. Constructs a database query to find repositories where keywords match in the
       `description` field, associated `topics` (JSONB array), or the `login`
       name of the repository's owner.
    4. Executes the query and processes the results.
    5. For each matching repository, assigns a confidence score based on where the
       match occurred (Owner Login > Description > Topic). Higher confidence is given
       to matches in fields considered more indicative of affiliation.
    6. Formats the findings into a list of dictionaries, each containing the
       repository ID, confidence score, and evidence detailing the match.

    Args:
        institution_id: The database ID of the institution. Used here primarily
                        for logging context, as the matching logic itself doesn't
                        directly filter by institution ID in this version.
        keywords: A list of strings to search for within repository metadata.
        db_conn_str: The SQLAlchemy database connection string.

    Returns:
        A list of dictionaries, each representing a potential affiliation found.
        Structure per dictionary:
        {
            "repository_id": int,
            "confidence_score": float (0.0 to 1.0),
            "evidence": {
                "match_type": str ("owner_login", "description", "topic"),
                "matched_keyword": str,
                "matched_value_preview": any (e.g., owner login, description snippet, topic list)
            }
        }
        Returns an empty list if no keywords are provided, no matches are found,
        or an error occurs during processing.
    """
    logger.info(f"Starting keyword_match_v1 for Institution ID {institution_id} with keywords: {keywords}")
    if not keywords:
        logger.warning("No keywords provided, returning empty list.")
        return []

    engine = None
    db: Session | None = None
    results: List[Dict[str, Any]] = []
    # Keep track of repositories already processed to avoid duplicate entries
    # if a repo matches keywords in multiple fields.
    processed_repo_ids: Set[int] = set()

    try:
        # Establish the database connection.
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Prepare filter conditions for the database query.
        filter_conditions = []
        lower_keywords = [kw.lower() for kw in keywords] # Use lowercase for case-insensitive matching

        # Create ILIKE conditions for text fields (description, owner login).
        for kw in lower_keywords:
            like_pattern = f"%{kw}%" # Pattern for substring matching
            filter_conditions.append(Repository.description.ilike(like_pattern))
            filter_conditions.append(Owner.login.ilike(like_pattern))

        # Create condition for JSONB 'topics' array using the '?|' operator (exists any).
        # This checks if any of the keywords exist as elements in the topics array.
        # Note: This requires PostgreSQL and appropriate parameter binding.
        try:
            # Use `text()` to pass the array parameter securely.
            topics_filter = Repository.topics.op('?|')(text('ARRAY[:keywords]'))
            topics_filter = topics_filter.params(keywords=lower_keywords) # Bind the keyword list
            filter_conditions.append(topics_filter)
        except Exception as jsonb_err:
             # Log an error if the JSONB filter setup fails (e.g., unsupported DB, syntax error).
             # The query will proceed without the topics filter in this case.
             logger.error(f"Could not apply JSONB topics filter: {jsonb_err}. Proceeding without topic matching.")

        # Construct the final SQLAlchemy query.
        # Select necessary fields from Repository and its associated Owner.
        # Join Repository to Owner to access the owner's login name.
        # Apply the combined filter conditions using OR logic.
        stmt = (
            select(Repository.id, Repository.description, Repository.topics, Owner.login)
            .join(Repository.owner) # Perform the join to Owner table
            .where(or_(*filter_conditions)) # Apply all filter conditions combined with OR
        )

        logger.info("Executing database query for keyword matches...")
        # Execute the query and fetch results as dictionary-like mappings.
        query_results = db.execute(stmt).mappings().all()
        logger.info(f"Query returned {len(query_results)} potential matches.")

        # Process the query results to assign confidence scores and format output.
        for row in query_results:
            repo_id = row['id']

            # Avoid processing the same repository multiple times if it matched on different fields/keywords.
            if repo_id in processed_repo_ids:
                continue

            description = row['description'] or "" # Handle potential None values
            # Topics can be None if the column is nullable or not populated.
            topics = row['topics'] if row['topics'] is not None else []
            owner_login = row['login'] or "" # Handle potential None values

            best_score = 0.0 # Track the highest confidence score for this repo
            match_type = "none" # Track the type of match yielding the best score
            matched_keyword = None # The specific keyword that resulted in the best match
            matched_value = None # The value where the best match occurred (for evidence)

            # Check for matches in fields, prioritizing owner login (highest confidence).
            for kw in lower_keywords:
                if kw in owner_login.lower():
                    if best_score < 0.9: # Assign owner login match score
                        best_score = 0.9
                        match_type = "owner_login"
                        matched_keyword = kw
                        matched_value = owner_login # Store the login name as evidence
                    # Break inner loop once a match is found in this field for this repo.
                    # We only need one keyword match per field type for scoring.
                    break

            # Check description if no owner match was found (or if owner score is lower, though unlikely here).
            if best_score < 0.9:
                 for kw in lower_keywords:
                      if kw in description.lower():
                          if best_score < 0.6: # Assign description match score
                               best_score = 0.6
                               match_type = "description"
                               matched_keyword = kw
                               # Provide a preview of the description as evidence.
                               matched_value = description[:100] + "..." if len(description)>100 else description
                          break # Break inner loop

            # Check topics if no better match was found yet.
            if best_score < 0.6:
                # Ensure 'topics' is actually a list before iterating.
                if isinstance(topics, list):
                    # Convert topics to lowercase strings for comparison.
                    lower_topics = [str(t).lower() for t in topics]
                    for kw in lower_keywords:
                        if kw in lower_topics:
                            if best_score < 0.4: # Assign topic match score (lowest confidence)
                                best_score = 0.4
                                match_type = "topic"
                                matched_keyword = kw
                                matched_value = topics # Store the original list of topics as evidence
                            break # Break inner loop
                else:
                    # Log a warning if topics data is not in the expected list format.
                    logger.warning(f"Topics data for repo {repo_id} is not a list: {topics}")


            # If any keyword match was found (score > 0), add it to the results.
            if best_score > 0.0:
                evidence = {
                    "match_type": match_type,
                    "matched_keyword": matched_keyword,
                    "matched_value_preview": matched_value # Context where match occurred
                }
                results.append({
                    "repository_id": repo_id,
                    "confidence_score": best_score,
                    "evidence": evidence
                })
                # Mark this repository as processed.
                processed_repo_ids.add(repo_id)


    except Exception as e:
        # Catch and log any unexpected errors during database query or processing.
        logger.exception(f"Error during keyword_match_v1 execution: {e}")
        return [] # Return empty list on error
    finally:
        # Ensure database resources are released.
        if db:
            db.close()
            logger.info("Database session closed.")
        if engine:
            engine.dispose()
            logger.info("Database engine disposed.")

    logger.info(f"Keyword_match_v1 finished. Found {len(results)} affiliations for Inst {institution_id}.")
    return results

# --- Example Test Call Block ---
# Intended for development/testing. Requires setting DATABASE_URL environment variable
# and having relevant data in the database.
#
# if __name__ == "__main__":
#     TEST_DB_CONN_STR = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")
#     TEST_INST_ID = 1 # Example institution ID (used for context)
#     TEST_KEYWORDS = ["visualization", "d3", "geospatial"] # Example keywords
#
#     if not TEST_DB_CONN_STR or "user:password" in TEST_DB_CONN_STR:
#         print("Error: DATABASE_URL environment variable not set or using default.", file=sys.stderr)
#     else:
#         print(f"Running test for Inst ID: {TEST_INST_ID}, Keywords: {TEST_KEYWORDS}")
#         affiliations = calculate_affiliations(TEST_INST_ID, TEST_KEYWORDS, TEST_DB_CONN_STR)
#         print("\nResults:")
#         import json
#         print(json.dumps(affiliations, indent=2)) # Pretty print the results
# --- End Example Test Call Block ---