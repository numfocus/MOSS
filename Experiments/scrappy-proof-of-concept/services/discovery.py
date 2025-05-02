# services/discovery.py
import uuid
import logging
from datetime import datetime, timezone
from db.database import get_db_session
from models.models import DiscoveryEvent

logger = logging.getLogger(__name__)

def start_new_chain():
    """
    Start a new discovery chain by generating a new UUID.
    Returns the new chain id.
    """
    new_chain_id = str(uuid.uuid4())
    logger.info(f"Started new discovery chain: {new_chain_id}")
    return new_chain_id

def record_discovery(record, method, details, trigger_input=None, keyword=None, chain_id=None, branch_id=None, step=1):
    """
    Record a discovery event into the audit table using an explicit step number.
    This function adds a DiscoveryEvent to the session for the given record.
    """
    from sqlalchemy.orm import object_session
    session = object_session(record)
    if session is None:
        session = get_db_session().__enter__()
    
    ingestion_type = None
    if trigger_input:
        ingestion_type = "keyword ingestion" if keyword else "direct ingestion"

    object_type = record.__class__.__name__
    object_id = getattr(record, "id", None)
    if object_id is None and hasattr(record, "sha"):
        object_id = record.sha
    if object_id is None:
        object_id = "unknown"

    if branch_id is None:
        branch_id = str(uuid.uuid4())
    
    if chain_id is None:
        chain_id = "unknown"
    
    event = DiscoveryEvent(
        chain_id=chain_id,
        branch_id=branch_id,
        step_number=step,
        discovery_method=method,
        details=details,
        timestamp=datetime.now(timezone.utc),
        ingestion_type=ingestion_type,
        url=trigger_input if ingestion_type == "direct ingestion" else None,
        keyword=keyword if ingestion_type == "keyword ingestion" else None,
        object_type=object_type,
        object_id=str(object_id)
    )
    
    session.add(event)
    logger.info(f"Queued discovery event: {event}")
    # Do not commit here; rely on the outer session