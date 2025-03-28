# services/openalex_ingestion.py
import json
import time
import logging
from datetime import datetime, timezone

from clients.openalex_client import OpenAlexClient
from utils.common import clean_doi, get_current_time, parse_datetime
from models.models import (
    OpenAlexWork, OpenAlexAuthor, OpenAlexVenue, 
    OpenAlexTopic, OpenAlexInstitution
)
from services.discovery import record_discovery

logger = logging.getLogger(__name__)

def process_authors(session, work, work_data, discovery_method, discovery_details, trigger_input, keyword, chain_id, branch_id, step):
    """
    Process authors from work data and link them to the work.
    """
    authorships = work_data.get('authorships', [])
    for authorship in authorships:
        author_data = authorship.get('author', {})
        if not author_data or not author_data.get('id'):
            continue
            
        author_id = author_data.get('id')
        # If the ID is a URL, extract just the ID part
        if author_id.startswith('https://'):
            author_id = author_id.split('/')[-1]
            
        author = session.query(OpenAlexAuthor).filter_by(openalex_id=author_id).first()
        
        if not author:
            author = OpenAlexAuthor(
                openalex_id=author_id,
                display_name=author_data.get('display_name'),
                orcid=author_data.get('orcid'),
                works_count=author_data.get('works_count'),
                raw_data=json.dumps(author_data)
            )
            author.ingested_at = get_current_time()
            session.add(author)
            session.flush()  # Get the ID without committing
            
            record_discovery(
                author,
                discovery_method,
                f"{discovery_details}; Author discovered from work {work.openalex_id}",
                trigger_input=trigger_input,
                keyword=keyword,
                chain_id=chain_id,
                branch_id=branch_id,
                step=step+1
            )
            
        # Process institutions for this author
        institutions = authorship.get('institutions', [])
        for inst_data in institutions:
            if not inst_data or not inst_data.get('id'):
                continue
                
            inst_id = inst_data.get('id')
            # If the ID is a URL, extract just the ID part
            if inst_id.startswith('https://'):
                inst_id = inst_id.split('/')[-1]
                
            institution = session.query(OpenAlexInstitution).filter_by(openalex_id=inst_id).first()
            
            if not institution:
                institution = OpenAlexInstitution(
                    openalex_id=inst_id,
                    display_name=inst_data.get('display_name'),
                    country_code=inst_data.get('country_code'),
                    url=inst_data.get('url'),
                    raw_data=json.dumps(inst_data)
                )
                institution.ingested_at = get_current_time()
                session.add(institution)
                session.flush()  # Get the ID without committing
                
                record_discovery(
                    institution,
                    discovery_method,
                    f"{discovery_details}; Institution discovered from author {author.openalex_id}",
                    trigger_input=trigger_input,
                    keyword=keyword,
                    chain_id=chain_id,
                    branch_id=branch_id,
                    step=step+2
                )
            
            if institution not in author.institutions:
                author.institutions.append(institution)
        
        if author not in work.authors:
            work.authors.append(author)

def process_topics(session, work, work_data, discovery_method, discovery_details, trigger_input, keyword, chain_id, branch_id, step):
    """
    Process topics from work data and link them to the work.
    """
    topics_data = work_data.get('topics', [])
    for topic_data in topics_data:
        if not topic_data or not topic_data.get('id'):
            continue
            
        topic_id = topic_data.get('id')
        # If the ID is a URL, extract just the ID part
        if topic_id.startswith('https://'):
            topic_id = topic_id.split('/')[-1]
            
        topic = session.query(OpenAlexTopic).filter_by(openalex_id=topic_id).first()
        
        if not topic:
            domain_data = topic_data.get('domain', {})
            field_data = topic_data.get('field', {})
            subfield_data = topic_data.get('subfield', {})
            
            topic = OpenAlexTopic(
                openalex_id=topic_id,
                display_name=topic_data.get('display_name'),
                description=topic_data.get('description'),
                domain_id=domain_data.get('id'),
                domain_display_name=domain_data.get('display_name'),
                field_id=field_data.get('id'),
                field_display_name=field_data.get('display_name'),
                subfield_id=subfield_data.get('id'),
                subfield_display_name=subfield_data.get('display_name'),
                works_count=topic_data.get('works_count'),
                raw_data=json.dumps(topic_data)
            )
            topic.ingested_at = get_current_time()
            session.add(topic)
            session.flush()  # Get the ID without committing
            
            record_discovery(
                topic,
                discovery_method,
                f"{discovery_details}; Topic discovered from work {work.openalex_id}",
                trigger_input=trigger_input,
                keyword=keyword,
                chain_id=chain_id,
                branch_id=branch_id,
                step=step+1
            )
        
        if topic not in work.topics:
            work.topics.append(topic)

def process_venue(session, work, work_data, discovery_method, discovery_details, trigger_input, keyword, chain_id, branch_id, step):
    """
    Process venue from work data and link it to the work.
    """
    primary_location = work_data.get('primary_location', {})
    venue_data = primary_location.get('source', {})
    if not venue_data or not venue_data.get('id'):
        return
        
    venue_id = venue_data.get('id')
    # If the ID is a URL, extract just the ID part
    if venue_id.startswith('https://'):
        venue_id = venue_id.split('/')[-1]
        
    venue = session.query(OpenAlexVenue).filter_by(openalex_id=venue_id).first()
    
    if not venue:
        venue = OpenAlexVenue(
            openalex_id=venue_id,
            display_name=venue_data.get('display_name'),
            publisher=venue_data.get('publisher'),
            url=venue_data.get('url'),
            raw_data=json.dumps(venue_data)
        )
        venue.ingested_at = get_current_time()
        session.add(venue)
        session.flush()  # Get the ID without committing
        
        record_discovery(
            venue,
            discovery_method,
            f"{discovery_details}; Venue discovered from work {work.openalex_id}",
            trigger_input=trigger_input,
            keyword=keyword,
            chain_id=chain_id,
            branch_id=branch_id,
            step=step+1
        )
    
    work.venue_id = venue.id

def update_or_create_openalex_work(session, work_data, fully_fetched=True,
                                   discovery_method="direct_ingestion",
                                   discovery_details="Work discovered during repository ingestion",
                                   trigger_input=None, keyword=None, chain_id=None, branch_id=None, step=1):
    """
    Create or update an OpenAlexWork record based on work_data.
    """
    openalex_id = work_data.get('id')
    doi = work_data.get('doi')
    if doi:
        doi = doi.replace("https://doi.org/", "").strip()
    existing = session.query(OpenAlexWork).filter_by(openalex_id=openalex_id).first()
    if existing:
        existing.ingested_at = get_current_time()
        
        # If we're fully fetching an existing work that wasn't fully fetched before,
        # update its data and process relations
        if fully_fetched and not existing.fully_fetched:
            existing.doi = doi
            existing.title = work_data.get('title')
            existing.publication_year = work_data.get('publication_year')
            existing.abstract = work_data.get('abstract') or None
            existing.type = work_data.get('type')
            existing.url = work_data.get('url')
            existing.fully_fetched = True
            existing.raw_data = json.dumps(work_data)
            
            # Process relations
            process_authors(session, existing, work_data, discovery_method, discovery_details, 
                           trigger_input, keyword, chain_id, branch_id, step)
            process_topics(session, existing, work_data, discovery_method, discovery_details, 
                          trigger_input, keyword, chain_id, branch_id, step)
            process_venue(session, existing, work_data, discovery_method, discovery_details, 
                         trigger_input, keyword, chain_id, branch_id, step)
        
        record_discovery(
            existing, discovery_method, discovery_details, 
            trigger_input=trigger_input, keyword=keyword,
            chain_id=chain_id, branch_id=branch_id, step=step
        )
        return existing
    
    work = OpenAlexWork(
        openalex_id=openalex_id,
        doi=doi,
        title=work_data.get('title'),
        publication_year=work_data.get('publication_year'),
        abstract=work_data.get('abstract') or None,
        type=work_data.get('type'),
        url=work_data.get('url'),
        fully_fetched=fully_fetched,
        raw_data=json.dumps(work_data)
    )
    work.ingested_at = get_current_time()
    session.add(work)
    session.commit()  # Commit to ensure work has an ID
    
    # Process relations for fully fetched works
    if fully_fetched:
        process_authors(session, work, work_data, discovery_method, discovery_details, 
                       trigger_input, keyword, chain_id, branch_id, step)
        process_topics(session, work, work_data, discovery_method, discovery_details, 
                      trigger_input, keyword, chain_id, branch_id, step)
        process_venue(session, work, work_data, discovery_method, discovery_details, 
                     trigger_input, keyword, chain_id, branch_id, step)
    
    record_discovery(
        work, discovery_method, discovery_details, 
        trigger_input=trigger_input, keyword=keyword,
        chain_id=chain_id, branch_id=branch_id, step=step
    )
    return work

def ingest_openalex_data(session, repository, discovery_method, discovery_details, 
                        trigger_input=None, keyword=None, chain_id=None, branch_id=None, step=1):
    """
    Ingest OpenAlex works using all DOIs associated with a repository.
    For each DOI:
      - Fetch the work data using OpenAlexClient.
      - If data is fetched, create or update the OpenAlexWork record.
      - Process referenced works and record discovery events.
      - Process citing works and record discovery events.
      - For each author in the work, fetch additional works and ingest them.
    """
    client_oa = OpenAlexClient()
    for doi_obj in repository.dois:
        doi_str = doi_obj.doi
        cleaned = clean_doi(doi_str)
        logger.info(f"Processing DOI: {doi_str} (cleaned: {cleaned})")
        start_time = time.time()
        work_data = client_oa.get_work_by_doi(doi_str)
        elapsed = time.time() - start_time
        logger.info(f"Query for OpenAlex work took {elapsed:.2f} seconds.")
        
        if work_data:
            work = update_or_create_openalex_work(
                session,
                work_data,
                fully_fetched=True,
                discovery_method=discovery_method,
                discovery_details=f"{discovery_details}; Work discovered from DOI '{doi_str}' in repository '{repository.full_name}'",
                trigger_input=trigger_input,
                keyword=keyword,
                chain_id=chain_id,
                branch_id=branch_id,
                step=step+1  # Increment step for work creation
            )
            
            try:
                work_data_dict = json.loads(work.raw_data)
            except Exception:
                work_data_dict = {}
                
            # Process referenced works
            references = work_data_dict.get("referenced_works", [])
            for ref_id in references:
                cited_work = session.query(OpenAlexWork).filter_by(openalex_id=ref_id).first()
                if not cited_work:
                    # Create a stub record for the cited work
                    cited_work = OpenAlexWork(
                        openalex_id=ref_id,
                        fully_fetched=False,
                        raw_data="{}"
                    )
                    cited_work.ingested_at = get_current_time()
                    session.add(cited_work)
                    session.commit()
                
                # Fetch full data for works that haven't been fully fetched yet
                if not cited_work.fully_fetched:
                    # Fetch full data for the referenced work
                    full_work_data = client_oa.get_work_by_id(ref_id)
                    if full_work_data:
                        # Update the stub record with full data
                        cited_work.doi = full_work_data.get('doi')
                        if cited_work.doi and cited_work.doi.startswith('https://doi.org/'):
                            cited_work.doi = cited_work.doi.replace('https://doi.org/', '')
                        cited_work.title = full_work_data.get('title')
                        cited_work.publication_year = full_work_data.get('publication_year')
                        cited_work.abstract = full_work_data.get('abstract') or None
                        cited_work.type = full_work_data.get('type')
                        cited_work.url = full_work_data.get('url')
                        cited_work.fully_fetched = True
                        cited_work.raw_data = json.dumps(full_work_data)
                        
                        # Process relations for the newly fetched work - using current step + 2
                        current_step = step + 2  # Increment for references
                        process_authors(session, cited_work, full_work_data, discovery_method, discovery_details, 
                                      trigger_input, keyword, chain_id, branch_id, current_step)
                        process_topics(session, cited_work, full_work_data, discovery_method, discovery_details, 
                                     trigger_input, keyword, chain_id, branch_id, current_step)
                        process_venue(session, cited_work, full_work_data, discovery_method, discovery_details, 
                                    trigger_input, keyword, chain_id, branch_id, current_step)
                        
                        # Add a delay to avoid hitting rate limits
                        time.sleep(0.5)
                
                if cited_work not in work.cited_works:
                    record_discovery(
                        cited_work,
                        discovery_method,
                        f"{discovery_details}; Work cited by work discovered from DOI '{doi_str}' in repository '{repository.full_name}'",
                        trigger_input=trigger_input,
                        keyword=keyword,
                        chain_id=chain_id,
                        branch_id=branch_id,
                        step=step+2  # Increment step for citations
                    )
                    work.cited_works.append(cited_work)
            
            # Process citing works (NEW)
            logger.info(f"Fetching works citing {work.openalex_id}...")
            citing_works_data = client_oa.get_citing_works(work.openalex_id)
            logger.info(f"Found {len(citing_works_data)} works citing {work.openalex_id}")
            
            for citing_work_data in citing_works_data:
                if not citing_work_data.get('id'):
                    continue
                    
                citing_work = update_or_create_openalex_work(
                    session,
                    citing_work_data,
                    fully_fetched=True,
                    discovery_method=discovery_method,
                    discovery_details=f"{discovery_details}; Work discovered as citing work for DOI '{doi_str}' from repository '{repository.full_name}'",
                    trigger_input=trigger_input,
                    keyword=keyword,
                    chain_id=chain_id,
                    branch_id=branch_id,
                    step=step+2  # Same level as references
                )
                
                # Establish the citation relationship - this citing work cites our work
                if work not in citing_work.cited_works:
                    citing_work.cited_works.append(work)
                    record_discovery(
                        citing_work,
                        discovery_method,
                        f"{discovery_details}; Work cites work with DOI '{doi_str}' from repository '{repository.full_name}'",
                        trigger_input=trigger_input,
                        keyword=keyword,
                        chain_id=chain_id,
                        branch_id=branch_id,
                        step=step+2
                    )
                
                # Add a delay to avoid hitting rate limits
                time.sleep(0.2)
                    
            session.commit()
            
            for author in work.authors:
                additional_works = client_oa.get_additional_works_for_author(author.openalex_id, per_page=5)
                for add_work_data in additional_works:
                    if not session.query(OpenAlexWork).filter_by(openalex_id=add_work_data.get('id')).first():
                        update_or_create_openalex_work(
                            session,
                            add_work_data,
                            fully_fetched=True,  # Set to True to process relations
                            discovery_method=discovery_method,
                            discovery_details=f"{discovery_details}; Work discovered via citation linked to DOI '{doi_str}' from repository '{repository.full_name}'",
                            trigger_input=trigger_input,
                            keyword=keyword,
                            chain_id=chain_id,
                            branch_id=branch_id,
                            step=step+3  # Increment step for author's works
                        )
        else:
            logger.error(f"Failed to fetch work for DOI {doi_str} from OpenAlex.")