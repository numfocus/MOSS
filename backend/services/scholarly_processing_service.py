"""
backend.services.scholarly_processing_service
---------------------------------------------
Processes detailed scholarly metadata retrieved from external sources (like OpenAlex)
for a given Work entity. Creates and links related entities such as Persons,
Institutions, Authorships, Affiliations, and hierarchical Topics.
"""

import logging
import re
import uuid
from typing import Dict, Any, Optional, List, Tuple, Set # Added Set

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.external import OpenAlexClient
from backend.data.models import (
    Work, Person, Institution, Authorship, Affiliation, WorkCitation, DiscoveryChain,
    Domain, Field, Subfield, Topic, WorkTopic # Topic hierarchy models
)
from backend.data.repositories import (
    PersonRepository, InstitutionRepository, WorkRepository,
    DomainRepository, FieldRepository, SubfieldRepository, TopicRepository # Hierarchy repositories
)
from .base_service import BaseService
from .discovery_chain_service import DiscoveryChainService # Service for managing provenance

logger = logging.getLogger(__name__)

class ScholarlyProcessingService(BaseService):
    """
    Handles the detailed processing of scholarly metadata associated with a Work.

    This service takes comprehensive work data (typically fetched from OpenAlex API)
    and populates the local database with related entities and relationships:
    - Creates or updates `Person` records for authors.
    - Creates or updates `Institution` records for affiliations.
    - Creates `Authorship` links between Works and Persons.
    - Creates `Affiliation` links between Authorships and Institutions.
    - Creates or updates hierarchical topic records (`Domain`, `Field`, `Subfield`, `Topic`).
    - Creates `WorkTopic` links between Works and Topics.
    - Manages `DiscoveryChain` records to trace the origin of each created entity/link.

    Operates within a database session provided by the caller (e.g., DOIProcessingService
    or a background task). Critical database errors are re-raised to allow the caller
    to handle transaction rollback and potential retries.
    """

    def __init__(self):
        """Initializes the ScholarlyProcessingService."""
        super().__init__()
        # Instantiate clients and services needed
        self.openalex_client = OpenAlexClient()
        # DiscoveryChainService is instantiated within the process method
        # to ensure it uses the correct session passed by the caller.
        # self.discovery_chain_service = DiscoveryChainService() # Avoid instantiation here

    def _get_id_from_oa_url(self, url: Optional[str]) -> Optional[str]:
        """
        Helper utility to extract a canonical ID from various OpenAlex entity URLs,
        ORCID URLs, ROR URLs, or DOI URLs. Also handles bare OpenAlex IDs.

        Args:
            url: The URL string or potential bare ID string.

        Returns:
            The extracted identifier string (e.g., OpenAlex ID, ORCID, ROR, DOI string),
            or None if parsing fails or the format is unrecognized.
        """
        # --- Logic unchanged from previous version ---
        if not url or not isinstance(url, str): return None
        try:
            id_part: Optional[str] = None
            # Determine ID type and extract based on URL prefix or pattern
            if url.startswith("https://orcid.org/"):
                 match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', url)
                 id_part = match.group(1) if match else None
            elif url.startswith("https://ror.org/"):
                 id_part = url.split('/')[-1] # ROR ID is the last path segment
            elif url.startswith("https://openalex.org/"):
                 id_part = url.split('/')[-1] # OpenAlex ID is the last path segment
            elif url.startswith("https://doi.org/"):
                 id_part = url[len("https://doi.org/"):] # Extract DOI string after prefix
            elif url and url[0].isalpha() and url[1:].isdigit(): # Check for bare OA ID (e.g., W123)
                 id_part = url
            else:
                 id_part = None # Unrecognized format

            # Basic validation based on expected patterns for the extracted ID part
            is_valid = False
            if id_part:
                if (url.startswith("https://openalex.org/") and id_part[0].isalpha() and id_part[1:].isdigit()): is_valid = True
                elif (url.startswith("https://orcid.org/") and match): is_valid = True # ORCID must match regex
                elif (url.startswith("https://ror.org/") and id_part.startswith('0') and len(id_part) == 9): is_valid = True
                elif url.startswith("https://doi.org/"): is_valid = True # Assume valid DOI string if extracted
                elif (id_part == url and url[0].isalpha() and url[1:].isdigit()): is_valid = True # Valid bare OA ID

            return id_part if is_valid else None # Return ID only if considered valid
        except Exception as e:
             # Log errors during parsing but avoid interrupting the flow
             logger.error(f"Error parsing ID/URL {url}: {e}", exc_info=False)
        return None

    def process_openalex_work_data(
        self,
        db: Session,
        work_db: Work,
        work_api_data: Dict[str, Any],
        parent_chain: DiscoveryChain
    ) -> Tuple[List[str], List[str], Optional[str]]:
        """
        Processes detailed work data from an OpenAlex API response.

        Creates/updates related Person, Institution, Authorship, Affiliation,
        and Topic entities, linking them appropriately and recording discovery provenance.
        Flushes are performed strategically after creating/updating entities to ensure
        dependent objects (like links) have access to necessary foreign keys.

        Args:
            db: The active SQLAlchemy database session.
            work_db: The existing `Work` database object being processed.
            work_api_data: The dictionary containing the full work data from OpenAlex API.
            parent_chain: The parent `DiscoveryChain` under which these discoveries should be nested.

        Returns:
            A tuple containing:
            - List of OpenAlex IDs for works referenced by `work_db`.
            - List of OpenAlex IDs for works related to `work_db`.
            - The `cited_by_api_url` string from the OpenAlex data, if present.

        Raises:
            SQLAlchemyError: If a critical database error occurs during processing,
                             intended to be caught by the caller for transaction rollback.
            ValueError/RuntimeError: For critical data inconsistencies (e.g., missing IDs after flush).
            Exception: For other unexpected errors during processing loop setup.
        """
        # Input validation
        if not work_db or not parent_chain:
             logger.error(f"Work DB object or Parent Chain is None. Aborting scholarly processing.")
             # Return empty results indicating failure to process
             return [], [], None

        self.logger.info(f"Starting scholarly processing for Work ID: {work_db.id} (OA: {work_db.openalex_id}) under Chain: {parent_chain.id}")
        # Initialize return values
        referenced_oa_ids: List[str] = []
        related_oa_ids: List[str] = []
        cited_by_api_url: Optional[str] = None
        # Instantiate DiscoveryChainService here to use the passed 'db' session
        discovery_chain_service = DiscoveryChainService()

        # Instantiate Repositories for database interactions using the provided session
        domain_repo = DomainRepository(db)
        field_repo = FieldRepository(db)
        subfield_repo = SubfieldRepository(db)
        topic_repo = TopicRepository(db)
        person_repo = PersonRepository(db)
        institution_repo = InstitutionRepository(db)

        # --- 1. Process Authorships and Affiliations ---
        try:
            # Retrieve authorship list from the API data
            authorships_data = work_api_data.get('authorships', [])
            self.logger.debug(f"Processing {len(authorships_data)} authorships for Work ID: {work_db.id}")

            # Iterate through each authorship entry for the work
            for authorship_item in authorships_data:
                # --- 1a. Process Author (Person) ---
                author_data = authorship_item.get('author', {})
                person_oa_id = self._get_id_from_oa_url(author_data.get('id'))
                person_name = author_data.get('display_name')
                # Basic validation for essential author data
                if not person_oa_id or not person_name:
                    logger.warning(f"Skipping authorship due to missing person ID or name: {author_data}")
                    continue # Skip this authorship entry

                person_db: Optional[Person] = None
                person_chain: Optional[DiscoveryChain] = None
                try:
                    # Prepare data for creating/updating the Person record
                    person_input_data = {
                        "openalex_id": person_oa_id,
                        "orcid": self._get_id_from_oa_url(author_data.get('orcid')), # Extract ORCID if available
                        "display_name": person_name,
                        "display_name_alternatives": author_data.get('display_name_alternatives', []) # Store alternative names
                    }
                    person_input_data = {k: v for k, v in person_input_data.items() if v is not None} # Clean None values

                    # Retrieve existing Person by OpenAlex ID or create a new one
                    person_db = person_repo.get_or_create_by_openalex_id(openalex_id=person_oa_id, obj_in_data=person_input_data)
                    db.flush() # Persist changes and ensure Person gets an ID if new
                    if person_db.id is None:
                        # If ID is still None after flush, something went wrong
                        raise RuntimeError(f"Person ID is None after flush for OA ID {person_oa_id}")

                    # Create a discovery chain record for this Person entity
                    person_chain = discovery_chain_service.create_child_chain(
                        db=db, parent_chain=parent_chain, discovery_type='REL_PERSON_FROM_AUTHORSHIP',
                        parameters={'work_id': work_db.id, 'person_oa_id': person_oa_id}
                    )
                    # Link the Person DB record to its discovery chain
                    discovery_chain_service.associate_entity(db=db, chain=person_chain, entity=person_db)
                    # Mark the discovery chain for this person as complete
                    discovery_chain_service.complete_chain(db=db, chain=person_chain)

                except (SQLAlchemyError, ValueError, RuntimeError) as e_person:
                    # Handle errors specifically during Person processing
                    logger.error(f"Error processing Person OA ID {person_oa_id} for Work ID {work_db.id}: {e_person}", exc_info=False)
                    if person_chain:
                        # Attempt to mark the associated discovery chain as FAILED (best-effort)
                        try: discovery_chain_service.fail_chain(db=db, chain=person_chain, error_message=str(e_person))
                        except Exception as fail_err: logger.error(f"Failed attempt to mark person_chain {person_chain.id} as FAILED: {fail_err}")
                    raise e_person # Re-raise critical database or validation errors for transaction rollback by caller

                # If Person processing failed, skip the rest of the steps for this authorship
                if not person_db: continue

                # --- 1b. Process Authorship Link ---
                # Create the link between the Work and the Person
                authorship_db: Optional[Authorship] = None
                authorship_chain: Optional[DiscoveryChain] = None
                try:
                    # Ensure the person discovery chain exists before linking from it
                    if not person_chain:
                        # This state indicates an unexpected issue after successful person processing
                        raise RuntimeError(f"Person chain is None for Person {person_db.id}, cannot proceed with authorship link.")

                    # Create a discovery chain specifically for the Authorship link itself
                    authorship_chain = discovery_chain_service.create_child_chain(
                        db=db, parent_chain=person_chain, discovery_type='LINK_AUTHORSHIP',
                        parameters={'work_id': work_db.id, 'person_id': person_db.id}
                    )

                    # Check if this specific Work-Person authorship link already exists
                    existing_authorship = db.query(Authorship).filter_by(work_id=work_db.id, person_id=person_db.id).first()
                    if existing_authorship:
                        authorship_db = existing_authorship
                        logger.debug(f"Authorship link W:{work_db.id}/P:{person_db.id} already exists.")
                    else:
                        # Prepare data for the new Authorship link record
                        authorship_input_data = {
                            "work_id": work_db.id,
                            "person_id": person_db.id,
                            "author_position": authorship_item.get('author_position'), # e.g., 'first', 'middle', 'last'
                            "is_corresponding": authorship_item.get('is_corresponding') # Boolean flag
                        }
                        authorship_db = Authorship(**authorship_input_data)
                        db.add(authorship_db)
                        db.flush() # Persist the new Authorship link
                        self.logger.info(f"Created Authorship W:{work_db.id}/P:{person_db.id}")

                    # Associate the Authorship link record with its discovery chain
                    # Note: Authorship uses a composite primary key; associate_entity handles this.
                    discovery_chain_service.associate_entity(db=db, chain=authorship_chain, entity=authorship_db, is_direct=True)
                    # Mark the authorship link discovery chain as complete
                    discovery_chain_service.complete_chain(db=db, chain=authorship_chain)

                except (SQLAlchemyError, ValueError, RuntimeError) as e_author:
                    # Handle errors during Authorship link creation or flush
                    logger.error(f"Error creating/flushing Authorship W:{work_db.id}/P:{person_db.id}: {e_author}", exc_info=False)
                    if authorship_chain:
                        # Attempt to mark the chain as failed
                        try: discovery_chain_service.fail_chain(db=db, chain=authorship_chain, error_message=str(e_author))
                        except Exception as fail_err: logger.error(f"Failed attempt to mark authorship_chain {authorship_chain.id} as FAILED: {fail_err}")
                    raise e_author # Re-raise critical errors

                # If Authorship link creation failed, skip processing affiliations for this author
                if not authorship_db: continue

                # --- 1c. Process Affiliations (Institutions) ---
                # Iterate through the institutions listed for this specific authorship
                institutions_data = authorship_item.get('institutions', [])
                for institution_item in institutions_data:
                    # Extract institution identifiers and name
                    inst_oa_id = self._get_id_from_oa_url(institution_item.get('id'))
                    inst_name = institution_item.get('display_name')
                    # Basic validation for institution data
                    if not inst_oa_id or not inst_name:
                        logger.warning(f"Skipping affiliation due to missing institution ID or name: {institution_item}")
                        continue # Skip this institution entry

                    institution_db: Optional[Institution] = None
                    institution_chain: Optional[DiscoveryChain] = None
                    try:
                        # Ensure the authorship chain exists before linking institution discovery to it
                        if not authorship_chain:
                             # This indicates an unexpected state after successful authorship processing
                             raise RuntimeError(f"Authorship chain is None for Auth W:{authorship_db.work_id}/P:{authorship_db.person_id}, cannot process institution.")

                        # Prepare data for creating/updating the Institution record
                        inst_input_data = {
                            "openalex_id": inst_oa_id,
                            "ror": self._get_id_from_oa_url(institution_item.get('ror')), # Extract ROR if present
                            "display_name": inst_name,
                            "country_code": institution_item.get('country_code'),
                            "type": institution_item.get('type') # e.g., 'education', 'company', 'government'
                        }
                        inst_input_data = {k: v for k, v in inst_input_data.items() if v is not None} # Clean None values

                        # Retrieve existing Institution by OpenAlex ID or create a new one
                        institution_db = institution_repo.get_or_create_by_openalex_id(openalex_id=inst_oa_id, obj_in_data=inst_input_data)
                        db.flush() # Persist changes and ensure Institution gets an ID if new
                        if institution_db.id is None:
                             # If ID is still None after flush, something went wrong
                             raise RuntimeError(f"Institution ID is None after flush for OA ID {inst_oa_id}")

                        # Create a discovery chain record for this Institution entity
                        institution_chain = discovery_chain_service.create_child_chain(
                            db=db, parent_chain=authorship_chain, discovery_type='REL_INST_FROM_AFFILIATION',
                            parameters={'authorship': f"W:{work_db.id}/P:{person_db.id}", 'inst_oa_id': inst_oa_id}
                        )
                        # Link the Institution DB record to its discovery chain
                        discovery_chain_service.associate_entity(db=db, chain=institution_chain, entity=institution_db)
                        # Mark the discovery chain for this institution as complete
                        discovery_chain_service.complete_chain(db=db, chain=institution_chain)

                    except (SQLAlchemyError, ValueError, RuntimeError) as e_inst:
                        # Handle errors specifically during Institution processing
                        logger.error(f"Error processing Inst OA ID {inst_oa_id} for Auth W:{work_db.id}/P:{person_db.id}: {e_inst}", exc_info=False)
                        if institution_chain:
                            # Attempt to mark the chain as failed
                            try: discovery_chain_service.fail_chain(db=db, chain=institution_chain, error_message=str(e_inst))
                            except Exception as fail_err: logger.error(f"Failed attempt to mark institution_chain {institution_chain.id} as FAILED: {fail_err}")
                        raise e_inst # Re-raise critical errors

                    # If Institution processing failed, skip creating the affiliation link
                    if not institution_db: continue

                    # --- 1d. Process Affiliation Link ---
                    # Create the link between the Authorship (Work-Person) and the Institution
                    affiliation_db: Optional[Affiliation] = None
                    affiliation_chain: Optional[DiscoveryChain] = None
                    try:
                         # Ensure the institution discovery chain exists before linking from it
                         if not institution_chain:
                             # Indicates an unexpected state after successful institution processing
                             raise RuntimeError(f"Institution chain is None for Inst {institution_db.id}, cannot process affiliation link.")

                         # Create a discovery chain specifically for the Affiliation link itself
                         affiliation_chain = discovery_chain_service.create_child_chain(
                             db=db, parent_chain=institution_chain, discovery_type='LINK_AFFILIATION',
                             parameters={'institution_id': institution_db.id} # Link refers back to institution
                         )

                         # Check if this specific Authorship-Institution affiliation link already exists
                         existing_affiliation = db.query(Affiliation).filter_by(
                             authorship_work_id=authorship_db.work_id,
                             authorship_person_id=authorship_db.person_id,
                             institution_id=institution_db.id
                         ).first()

                         if existing_affiliation:
                              affiliation_db = existing_affiliation
                              logger.debug(f"Affiliation link Auth W:{authorship_db.work_id}/P:{person_db.id}, Inst {institution_db.id} already exists.")
                         else:
                              # Prepare data for the new Affiliation link record (uses composite FK)
                              affiliation_input_data = {
                                  "authorship_work_id": authorship_db.work_id, # Part of composite FK to Authorship
                                  "authorship_person_id": authorship_db.person_id, # Part of composite FK to Authorship
                                  "institution_id": institution_db.id # FK to Institution
                              }
                              affiliation_db = Affiliation(**affiliation_input_data)
                              db.add(affiliation_db)
                              db.flush() # Persist the new Affiliation link
                              self.logger.info(f"Created Affiliation Auth W:{authorship_db.work_id}/P:{person_db.id}, Inst {institution_db.id}")

                         # Associate the Affiliation link record with its discovery chain
                         # Note: Affiliation uses a composite primary key; associate_entity handles this.
                         discovery_chain_service.associate_entity(db=db, chain=affiliation_chain, entity=affiliation_db, is_direct=True)
                         # Mark the affiliation link discovery chain as complete
                         discovery_chain_service.complete_chain(db=db, chain=affiliation_chain)

                    except (SQLAlchemyError, ValueError, RuntimeError) as e_affil:
                         # Handle errors during Affiliation link creation or flush
                         logger.error(f"Error creating/flushing Affiliation Auth W:{authorship_db.work_id}/P:{person_db.id}, Inst {institution_db.id}: {e_affil}", exc_info=False);
                         if affiliation_chain:
                              # Attempt to mark the chain as failed
                              try: discovery_chain_service.fail_chain(db=db, chain=affiliation_chain, error_message=str(e_affil))
                              except Exception as fail_err: logger.error(f"Failed attempt to mark affiliation_chain {affiliation_chain.id} as FAILED: {fail_err}")
                         raise e_affil # Re-raise critical errors

        # Catch potential errors in the setup or iteration of the main authorships loop itself
        except Exception as e_auth_outer:
            logger.error(f"Critical error during authorship/affiliation processing loop for Work ID {work_db.id}: {e_auth_outer}", exc_info=True)
            # Re-raise to indicate a failure in this major processing block, likely requiring transaction rollback
            raise e_auth_outer

        # --- 2. Process Topics and Hierarchy ---
        try:
            # Retrieve primary topic and list of other topics from the API data
            primary_topic_data = work_api_data.get('primary_topic')
            topics_data = work_api_data.get('topics', [])
            all_topic_entries = [] # Combined list to process, ensuring uniqueness
            processed_topic_oa_ids: Set[str] = set() # Track OpenAlex IDs to avoid duplicates

            # Add the primary topic if it's valid and provided as a dictionary
            if primary_topic_data and isinstance(primary_topic_data, dict):
                primary_topic_data['is_primary'] = True # Mark this entry as the primary topic
                all_topic_entries.append(primary_topic_data)
                primary_topic_oa_id = self._get_id_from_oa_url(primary_topic_data.get('id'))
                if primary_topic_oa_id:
                    processed_topic_oa_ids.add(primary_topic_oa_id) # Track its ID
            elif primary_topic_data:
                 # Log if primary topic data is present but not in the expected dictionary format
                 logger.warning(f"Primary topic data for work {work_db.id} is not a dictionary: {type(primary_topic_data)}")


            # Add other topics from the list if valid and not already added as the primary topic
            if isinstance(topics_data, list):
                 for topic_item in topics_data:
                     # Ensure each item in the list is a dictionary
                     if not isinstance(topic_item, dict):
                          logger.warning(f"Skipping non-dictionary item in topics list for work {work_db.id}: {topic_item}")
                          continue
                     topic_oa_id = self._get_id_from_oa_url(topic_item.get('id'))
                     # Add only if it has a valid ID and wasn't the primary topic already processed
                     if topic_oa_id and topic_oa_id not in processed_topic_oa_ids:
                         topic_item['is_primary'] = False # Mark as not the primary topic
                         all_topic_entries.append(topic_item)
                         processed_topic_oa_ids.add(topic_oa_id) # Track its ID
            elif topics_data:
                 # Log if topics data is present but not in the expected list format
                 logger.warning(f"Topics data for work {work_db.id} is not a list: {type(topics_data)}")

            self.logger.debug(f"Processing {len(all_topic_entries)} unique topic entries for Work ID: {work_db.id}")

            # Process each unique topic entry found for the work
            for topic_entry in all_topic_entries:
                topic_oa_id = self._get_id_from_oa_url(topic_entry.get('id'))
                topic_name = topic_entry.get('display_name')
                # Basic validation for the topic entry itself
                if not topic_oa_id or not topic_name:
                    logger.warning(f"Skipping topic entry due to missing ID or name: {topic_entry}")
                    continue # Skip this topic entry

                # Variables to hold the database objects for the topic and its hierarchy
                domain_db: Optional[Domain] = None
                field_db: Optional[Field] = None
                subfield_db: Optional[Subfield] = None
                topic_db: Optional[Topic] = None
                work_topic_db: Optional[WorkTopic] = None # The Work <-> Topic link object
                topic_entry_chain: Optional[DiscoveryChain] = None # Provenance chain for this entry

                try:
                    # Create a discovery chain for processing this specific topic entry and its hierarchy
                    topic_entry_chain = discovery_chain_service.create_child_chain(
                        db=db, parent_chain=parent_chain, discovery_type='REL_TOPIC_ENTRY',
                        parameters={'work_id': work_db.id, 'topic_oa_id': topic_oa_id}
                    )

                    # --- Process Hierarchy (Domain -> Field -> Subfield -> Topic) ---
                    # Traverse the hierarchy provided within the topic entry data

                    # 2a. Domain (Top Level)
                    domain_data = topic_entry.get('domain', {})
                    domain_id_url = domain_data.get('id')
                    domain_oa_id = self._get_id_from_oa_url(domain_id_url) if domain_id_url else None
                    # Domain is essential for the hierarchy; skip if missing
                    if not domain_oa_id:
                         logger.warning(f"Missing Domain ID/URL for Topic {topic_oa_id}, skipping hierarchy processing for this entry.")
                         # Fail the chain for this topic entry if essential hierarchy is missing
                         discovery_chain_service.fail_chain(db, topic_entry_chain, "Missing Domain ID")
                         continue # Move to the next topic entry
                    domain_input = {"openalex_id": domain_oa_id, "display_name": domain_data.get('display_name', 'Unknown Domain')}
                    domain_db = domain_repo.get_or_create_by_openalex_id(openalex_id=domain_oa_id, obj_in_data=domain_input)
                    db.flush(); # Ensure Domain object has an ID
                    if domain_db.id is None: raise RuntimeError(f"Domain ID is None after flush for OA ID {domain_oa_id}")
                    # Associate the Domain with the topic entry chain (indirect discovery)
                    discovery_chain_service.associate_entity(db=db, chain=topic_entry_chain, entity=domain_db, is_direct=False)

                    # 2b. Field (Child of Domain)
                    field_data = topic_entry.get('field', {})
                    field_id_url = field_data.get('id')
                    field_oa_id = self._get_id_from_oa_url(field_id_url) if field_id_url else None
                    # Proceed only if Field ID is present and the parent Domain was processed successfully
                    if not field_oa_id or not (domain_db and domain_db.id):
                         logger.warning(f"Missing Field ID/URL or Domain DB/ID for Topic {topic_oa_id}, skipping Field/Subfield/Topic.")
                         discovery_chain_service.fail_chain(db, topic_entry_chain, "Missing Field ID or Domain")
                         continue # Move to the next topic entry
                    field_input = {"openalex_id": field_oa_id, "display_name": field_data.get('display_name', 'Unknown Field'), "domain_id": domain_db.id}
                    field_db = field_repo.get_or_create_by_openalex_id(openalex_id=field_oa_id, obj_in_data=field_input)
                    db.flush(); # Ensure Field object has an ID
                    if field_db.id is None: raise RuntimeError(f"Field ID is None after flush for OA ID {field_oa_id}")
                    # Associate the Field (indirect discovery)
                    discovery_chain_service.associate_entity(db=db, chain=topic_entry_chain, entity=field_db, is_direct=False)

                    # 2c. Subfield (Child of Field)
                    subfield_data = topic_entry.get('subfield', {})
                    subfield_id_url = subfield_data.get('id')
                    subfield_oa_id = self._get_id_from_oa_url(subfield_id_url) if subfield_id_url else None
                    # Proceed only if Subfield ID is present and the parent Field was processed successfully
                    if not subfield_oa_id or not (field_db and field_db.id):
                         logger.warning(f"Missing Subfield ID/URL or Field DB/ID for Topic {topic_oa_id}, skipping Subfield/Topic.")
                         discovery_chain_service.fail_chain(db, topic_entry_chain, "Missing Subfield ID or Field")
                         continue # Move to the next topic entry
                    subfield_input = {"openalex_id": subfield_oa_id, "display_name": subfield_data.get('display_name', 'Unknown Subfield'), "field_id": field_db.id}
                    subfield_db = subfield_repo.get_or_create_by_openalex_id(openalex_id=subfield_oa_id, obj_in_data=subfield_input)
                    db.flush(); # Ensure Subfield object has an ID
                    if subfield_db.id is None: raise RuntimeError(f"Subfield ID is None after flush for OA ID {subfield_oa_id}")
                    # Associate the Subfield (indirect discovery)
                    discovery_chain_service.associate_entity(db=db, chain=topic_entry_chain, entity=subfield_db, is_direct=False)

                    # 2d. Topic (Child of Subfield - Leaf Level)
                    # Proceed only if the Topic ID itself is valid and the parent Subfield was processed successfully
                    if not topic_oa_id or not (subfield_db and subfield_db.id):
                        logger.warning(f"Missing Topic ID or Subfield DB/ID for Topic OA ID {topic_oa_id}.")
                        discovery_chain_service.fail_chain(db, topic_entry_chain, "Missing Topic ID or Subfield")
                        continue # Move to the next topic entry
                    topic_input = {
                        "openalex_id": topic_oa_id,
                        "display_name": topic_name,
                        "description": topic_entry.get('description'), # Optional description from OpenAlex
                        "subfield_id": subfield_db.id # Link to parent Subfield
                    }
                    topic_input = {k: v for k, v in topic_input.items() if v is not None} # Clean None values
                    topic_db = topic_repo.get_or_create_by_openalex_id(openalex_id=topic_oa_id, obj_in_data=topic_input)
                    db.flush(); # Ensure Topic object has an ID
                    if topic_db.id is None: raise RuntimeError(f"Topic ID is None after flush for OA ID {topic_oa_id}")
                    # Associate the Topic (direct discovery for this topic entry)
                    discovery_chain_service.associate_entity(db=db, chain=topic_entry_chain, entity=topic_db, is_direct=True)

                    # 2e. WorkTopic Association (Link the Work to the processed Topic)
                    # Proceed only if the Topic object was successfully processed
                    if not (topic_db and topic_db.id):
                         logger.warning(f"Missing Topic DB/ID for Topic {topic_oa_id}, cannot create WorkTopic link.")
                         discovery_chain_service.fail_chain(db, topic_entry_chain, "Missing Topic DB/ID for association")
                         continue # Move to the next topic entry

                    # Check if the specific Work-Topic link already exists in the database
                    existing_work_topic = db.query(WorkTopic).filter_by(work_id=work_db.id, topic_id=topic_db.id).first()
                    if not existing_work_topic:
                        # Create the association record linking the Work and Topic
                        work_topic_input = {
                            "work_id": work_db.id,
                            "topic_id": topic_db.id,
                            "score": topic_entry.get('score'), # Store the relevance score from OpenAlex
                            "is_primary": topic_entry.get('is_primary', False) # Store whether this was the primary topic
                        }
                        work_topic_db = WorkTopic(**work_topic_input)
                        db.add(work_topic_db)
                        db.flush() # Persist the link
                        self.logger.info(f"Created WorkTopic link W:{work_db.id} <-> T:{topic_db.id}")
                        # Associate the WorkTopic link record itself with the discovery chain
                        # Note: WorkTopic uses a composite primary key; associate_entity handles this.
                        discovery_chain_service.associate_entity(db=db, chain=topic_entry_chain, entity=work_topic_db, is_direct=True)
                    else:
                        # Link already exists, no action needed for creation
                        self.logger.debug(f"WorkTopic link W:{work_db.id} <-> T:{topic_db.id} already exists.")
                        work_topic_db = existing_work_topic # Assign if needed for potential future use

                    # Mark the discovery chain for this entire topic entry (including hierarchy) as complete
                    discovery_chain_service.complete_chain(db=db, chain=topic_entry_chain)

                except (SQLAlchemyError, ValueError, RuntimeError) as e_topic_hierarchy:
                    # Catch errors occurring during the processing of a SINGLE topic entry's hierarchy or link
                    logger.error(f"Error processing hierarchy/link for Topic OA ID {topic_oa_id} for Work ID {work_db.id}: {e_topic_hierarchy}", exc_info=False) # Keep log concise for production
                    if topic_entry_chain:
                        # Attempt to mark the specific topic entry chain as failed
                        try:
                            discovery_chain_service.fail_chain(db=db, chain=topic_entry_chain, error_message=str(e_topic_hierarchy))
                        except Exception as fail_err:
                            # Log error during failure handling itself
                            logger.error(f"Failed attempt to mark topic_entry_chain {topic_entry_chain.id} as FAILED: {fail_err}")
                    # Re-raise critical database or validation errors to allow transaction rollback by caller
                    raise e_topic_hierarchy

        # Catch potential errors in the setup or iteration of the main topics loop itself
        except Exception as e_topic_outer:
            logger.error(f"Critical error during topic processing setup/loop for Work ID {work_db.id}: {e_topic_outer}", exc_info=True)
            # Re-raise to indicate a failure in this major processing block
            raise e_topic_outer

        # --- 3. Extract Referenced Works, Related Works, and Cited-By URL ---
        # Retrieve lists of related work IDs and the API URL for citing works.
        # These are passed back to the caller (e.g., DOIProcessingService)
        # primarily for enqueueing further background processing tasks.
        try:
            # Get relevant fields from the OpenAlex API data dictionary
            referenced_work_urls = work_api_data.get('referenced_works', []) # Works cited BY this work
            related_work_urls = work_api_data.get('related_works', []) # Semantically related works
            cited_by_api_url = work_api_data.get('cited_by_api_url') # API endpoint to get works CITING this work

            # Extract the OpenAlex IDs from the provided URLs using the helper function
            # Use list comprehensions for concise extraction and filtering
            referenced_oa_ids = [oa_id for url in referenced_work_urls if isinstance(url, str) and (oa_id := self._get_id_from_oa_url(url))]
            related_oa_ids = [oa_id for url in related_work_urls if isinstance(url, str) and (oa_id := self._get_id_from_oa_url(url))]

            # Filter out any None values that might result from failed ID parsing
            referenced_oa_ids = [id for id in referenced_oa_ids if id is not None]
            related_oa_ids = [id for id in related_oa_ids if id is not None]


            self.logger.debug(f"Extracted {len(referenced_oa_ids)} referenced work IDs for Work ID: {work_db.id}")
            self.logger.debug(f"Extracted {len(related_oa_ids)} related work IDs for Work ID: {work_db.id}")
            self.logger.debug(f"Extracted cited_by_api_url: {'Present' if cited_by_api_url else 'Absent'}")

        except Exception as e_ref_extract:
             # Handle potential errors during the extraction of these lists/URL
             logger.error(f"Error extracting referenced/related works lists or cited_by_url for Work ID {work_db.id}: {e_ref_extract}", exc_info=True)
             # Reset lists/URL to safe defaults if extraction fails
             referenced_oa_ids = []
             related_oa_ids = []
             cited_by_api_url = None

        self.logger.info(f"Finished scholarly processing for Work ID: {work_db.id} (OA: {work_db.openalex_id})")
        # Return the extracted IDs and URL needed by the caller
        return referenced_oa_ids, related_oa_ids, cited_by_api_url