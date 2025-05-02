# --- NEW FILE: contrib/queries/citation_community_detection_v1.py ---

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional

# --- Path Setup ---
# Assuming this script is in contrib/queries/
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Setup ---

# --- Dependencies ---
try:
    import networkx as nx
    from community import community_louvain # Use python-louvain library
except ImportError as e:
    print(f"Error importing dependencies: {e}. Please install networkx and python-louvain.")
    print("pip install networkx python-louvain")
    sys.exit(1)
# --- End Dependencies ---

from sqlalchemy import create_engine, select, union_all
from sqlalchemy.orm import sessionmaker, Session

# Import required MOSS models
from backend.data.models import Work, WorkCitation

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] [citation_community_v1] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def fetch_citation_network(db: Session, seed_work_id: int, depth: int) -> Tuple[Set[int], Set[Tuple[int, int]]]:
    """
    Fetches work IDs (nodes) and citation links (edges) within a specified depth
    from a seed work using breadth-first search.
    """
    if depth < 0:
        return set(), set()

    nodes: Set[int] = {seed_work_id}
    edges: Set[Tuple[int, int]] = set()
    current_frontier: Set[int] = {seed_work_id}
    visited_nodes: Set[int] = {seed_work_id} # Include seed node initially

    for current_depth in range(depth):
        if not current_frontier:
            break # No more nodes to expand

        next_frontier: Set[int] = set()

        # Find works directly citing or cited by the current frontier nodes
        # Fetch both directions in one go for undirected graph
        citing_stmt = (
            select(WorkCitation.citing_work_id, WorkCitation.cited_work_id)
            .where(WorkCitation.cited_work_id.in_(current_frontier))
        )
        cited_stmt = (
            select(WorkCitation.citing_work_id, WorkCitation.cited_work_id)
            .where(WorkCitation.citing_work_id.in_(current_frontier))
        )

        # Combine results - use session.execute for simpler iteration
        combined_results = db.execute(citing_stmt).all() + db.execute(cited_stmt).all()

        for citer, cited in combined_results:
            # Add edge (always store as tuple for undirected graph)
            edge = tuple(sorted((citer, cited))) # Ensure consistent edge representation
            edges.add(edge)

            # Add newly discovered nodes to nodes set and next frontier if not visited
            neighbor_nodes = {citer, cited}
            for node in neighbor_nodes:
                if node not in visited_nodes:
                    nodes.add(node)
                    next_frontier.add(node)
                    visited_nodes.add(node) # Mark as visited here

        current_frontier = next_frontier # Move to the next level

    logger.info(f"Fetched network: {len(nodes)} nodes, {len(edges)} edges.")
    return nodes, edges


def run_analysis(
    db_conn_str: str,
    seed_work_id: int,
    depth: int = 1
) -> Dict[str, Any]:
    """
    Performs community detection on the citation graph starting from a seed work.

    Uses the Louvain algorithm implemented in the `python-louvain` library.

    Params:
        - db_conn_str: str (Database connection string)
        - seed_work_id: int (The internal DB ID of the work to start the graph traversal from)
        - depth: int (How many citation steps away from the seed work to explore, default 1)

    Returns:
        - Dict[str, Any]: Contains result_type ('value' or 'error') and data.
                         If successful, data contains 'communities' (list of lists of work IDs)
                         and 'modularity' score.
                         If error, data contains error details.
    """
    logger.info(f"Starting citation_community_detection_v1 analysis for seed_work_id={seed_work_id}, depth={depth}")

    if depth < 0:
         return {"result_type": "error", "data": {"error": "ValueError", "message": "Depth cannot be negative."}}

    engine = None
    db: Session | None = None
    communities_result: List[List[int]] = []
    modularity_score: Optional[float] = None

    try:
        engine = create_engine(db_conn_str)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Check if seed work exists
        seed_work = db.get(Work, seed_work_id)
        if not seed_work:
             return {"result_type": "error", "data": {"error": "NotFound", "message": f"Seed work with ID {seed_work_id} not found."}}

        # Fetch the network data
        nodes, edges = fetch_citation_network(db, seed_work_id, depth)

        if not nodes or not edges:
            logger.info("No citation network found within the specified depth.")
            # Return empty communities if no network is found
            return {"result_type": "value", "data": {"communities": [], "modularity": None}}

        # Build the NetworkX graph
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        logger.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

        # Check if graph is connected (Louvain works better on connected components)
        if not nx.is_connected(G):
            logger.warning("Graph is not connected. Louvain will run on the largest connected component.")
            # Optionally run on each component, but for simplicity, run on largest
            largest_cc = max(nx.connected_components(G), key=len)
            G_comp = G.subgraph(largest_cc).copy() # Create a subgraph copy
            logger.info(f"Running Louvain on largest component ({len(G_comp.nodes())} nodes).")
        else:
            G_comp = G # Use the whole graph if connected

        # Perform community detection using Louvain
        logger.info("Running Louvain algorithm...")
        partition = community_louvain.best_partition(G_comp)
        modularity_score = community_louvain.modularity(partition, G_comp)
        logger.info(f"Louvain completed. Modularity: {modularity_score:.4f}")

        # Group nodes by community ID
        community_map: Dict[int, List[int]] = {}
        for node_id, community_id in partition.items():
            if community_id not in community_map:
                community_map[community_id] = []
            community_map[community_id].append(node_id)

        communities_result = list(community_map.values())

        # Sort communities by size (descending) for consistent output
        communities_result.sort(key=len, reverse=True)

        logger.info(f"Detected {len(communities_result)} communities.")

    except ImportError:
         # Already checked at top, but good practice
         return {"result_type": "error", "data": {"error": "ImportError", "message": "NetworkX or python-louvain not installed."}}
    except Exception as e:
        logger.exception(f"Error during citation_community_detection_v1 execution: {e}")
        return {"result_type": "error", "data": {"error": type(e).__name__, "message": str(e)}}
    finally:
        if db:
            db.close()
        if engine:
            engine.dispose()

    return {
        "result_type": "value",
        "data": {
            "communities": communities_result,
            "modularity": round(modularity_score, 5) if modularity_score is not None else None
        }
    }