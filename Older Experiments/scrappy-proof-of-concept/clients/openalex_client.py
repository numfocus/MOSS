# clients/openalex_client.py
import requests
import logging
from utils.common import clean_doi
from config import OPENALEX_BASE_URL  # Use centralized configuration

logger = logging.getLogger(__name__)

class OpenAlexClient:
    BASE_URL = OPENALEX_BASE_URL

    def __init__(self):
        self.headers = {"User-Agent": "MyGitHubOpenAlexApp/1.0 (your_email@example.com)"}

    def get_work_by_doi(self, doi):
        doi = clean_doi(doi).lower()
        url = f"{self.BASE_URL}/works/doi:{doi}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                logger.debug(f"Fetched work for DOI {doi}.")
                return response.json()
            else:
                logger.error(f"OpenAlex: Failed to fetch work for DOI {doi} (status: {response.status_code}).")
                return None
        except Exception as e:
            logger.error(f"OpenAlex: Exception while fetching work for DOI {doi}: {e}")
            return None
    
    def get_work_by_id(self, openalex_id):
        """
        Fetch a work by its OpenAlex ID.
        """
        # If the ID is the full URL, extract just the ID part
        if openalex_id.startswith('https://'):
            openalex_id = openalex_id.split('/')[-1]
        
        url = f"{self.BASE_URL}/works/{openalex_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                logger.debug(f"Fetched work for ID {openalex_id}.")
                return response.json()
            else:
                logger.error(f"OpenAlex: Failed to fetch work for ID {openalex_id} (status: {response.status_code}).")
                return None
        except Exception as e:
            logger.error(f"OpenAlex: Exception while fetching work for ID {openalex_id}: {e}")
            return None

    def get_additional_works_for_author(self, author_openalex_id, per_page=5):
        url = f"{self.BASE_URL}/works"
        params = {"filter": f"authorships.author.id:{author_openalex_id}", "per_page": per_page}
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Fetched {len(data.get('results', []))} additional works for author {author_openalex_id}.")
                return data.get("results", [])
            else:
                logger.error(f"OpenAlex: Failed to fetch additional works for author {author_openalex_id}.")
                return []
        except Exception as e:
            logger.error(f"OpenAlex: Exception while fetching additional works for author {author_openalex_id}: {e}")
            return []

    def get_citing_works(self, work_openalex_id, per_page=200):
        """
        Retrieve all citing works for a given work using explicit pagination.
        """
        short_id = work_openalex_id.split("/")[-1]
        page = 1
        all_results = []
        while True:
            url = f"{self.BASE_URL}/works"
            params = {"filter": f"cites:{short_id}", "per_page": per_page, "page": page}
            logger.debug(f"Fetching citing works for {work_openalex_id}: page {page} with params {params}")
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    logger.debug(f"Page {page}: Retrieved {len(results)} works.")
                    if not results:
                        logger.info(f"No more citing works found on page {page}. Total works: {len(all_results)}")
                        break
                    all_results.extend(results)
                    page += 1
                else:
                    logger.error(f"OpenAlex: Failed to fetch citing works for {work_openalex_id} on page {page} (status: {response.status_code}).")
                    break
            except Exception as e:
                logger.error(f"OpenAlex: Exception while fetching citing works for {work_openalex_id} on page {page}: {e}")
                break
        logger.info(f"Total citing works fetched for {work_openalex_id}: {len(all_results)}")
        return all_results