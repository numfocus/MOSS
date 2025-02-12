#!/usr/bin/env python3
"""
Repo Cite Script

This script collects metadata and citation information from a GitHub repository and related scholarly works.
It retrieves repository details from GitHub and then uses the OpenAlex API to fetch paper details,
authors, citations, and related metadata. The output (in JSON format) can be used, for example,
to generate a network graph of papers, people, institutions, topics, and projects.

Note:
    - Currently, the DOI extraction is tailored to GitHub by looking for a 'CITATION.cff' file
      (or, as a fallback, scanning the README). Future versions may generalize to other hosting platforms.
    - RECORD_LIMIT and MAX_DEPTH are now read as integers (with 0 meaning “all”) to keep their type consistent.
"""

import requests
import json
import re
import time
import logging
from urllib.parse import quote
from collections import deque
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed output
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('repo_cite.log'),  # More descriptive log file name
        logging.StreamHandler()             # Also log to console
    ]
)

# Load environment variables from .env file
load_dotenv()

# Global dictionaries to store unique entities (capitalized to denote globals)
PAPERS_DICT: Dict[str, Any] = {}
AUTHORS_DICT: Dict[str, Any] = {}
INSTITUTIONS_DICT: Dict[str, Any] = {}
TOPICS_DICT: Dict[str, Any] = {}
PROJECTS_LIST: list = []

# Visited papers set to prevent duplicates
VISITED_PAPERS: set = set()

# Set your email for OpenAlex API rate limit increase, sourced from the .env file if available
OPENALEX_EMAIL: str = os.getenv('OPENALEX_EMAIL', 'your.email@example.com')  # Replace in your .env file

# GitHub personal access token (read from .env file)
GITHUB_TOKEN: Optional[str] = os.getenv('GITHUB_TOKEN')  # Ensure your .env file has GITHUB_TOKEN=<your_token>

# Set the number of records to retrieve per API call (0 means all)
try:
    RECORD_LIMIT: int = int(os.getenv('RECORD_LIMIT', '0'))
except ValueError:
    RECORD_LIMIT = 0  # default to 0 (all records)

# Maximum depth for citation traversal, sourced from .env if available
try:
    MAX_DEPTH: int = int(os.getenv('MAX_DEPTH', '2'))
except ValueError:
    MAX_DEPTH = 2

# Maximum number of retries for API calls
MAX_RETRIES: int = 3

# Delay between retries (in seconds)
RETRY_DELAY: int = 5

def get_doi_from_github_repo(repo_owner: str, repo_name: str) -> Optional[str]:
    """
    Fetch the DOI from a GitHub repository.

    Parameters:
        repo_owner (str): GitHub username or organization name (e.g., "jring-o").
        repo_name (str): Repository name (e.g., "repo_cite").

    Returns:
        Optional[str]: The DOI if found; otherwise, None.

    This function searches for a 'CITATION.cff' file in the repository first.
    If not found, it then searches the 'README.md' for DOI patterns.
    
    TODO:
        - Extend this function to search for a '.zenodo.json' file, which may also contain metadata.
    
    Note:
        Scanning 'README.md' may sometimes capture DOIs unrelated to the software’s own citation.
    """
    logging.info(f"Fetching DOI from GitHub repository '{repo_owner}/{repo_name}'")
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents"
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logging.error(f"Error fetching repository contents: {response.status_code}")
        return None
    contents = response.json()
    # Search for CITATION.cff
    for item in contents:
        if item['name'].lower() == 'citation.cff':
            logging.info("Found 'CITATION.cff' in repository")
            # Fetch the content of CITATION.cff
            citation_url = item.get('download_url')
            if citation_url:
                citation_response = requests.get(citation_url, headers=headers)
                if citation_response.status_code == 200:
                    citation_content = citation_response.text
                    # Parse the CITATION.cff content to get the DOI
                    for line in citation_content.splitlines():
                        if 'doi:' in line.lower():
                            doi = line.split(':', 1)[1].strip().strip('"')
                            logging.info(f"DOI found in 'CITATION.cff': {doi}")
                            return doi
                else:
                    # Not treating inability to fetch CITATION.cff as an error
                    logging.info("Unable to fetch 'CITATION.cff' content; continuing search in README.md")
            else:
                logging.info("'CITATION.cff' does not have a download URL; continuing search")
    # If CITATION.cff not found or DOI not found, try README.md
    for item in contents:
        if item['name'].lower() == 'readme.md':
            logging.info("Searching for DOI in 'README.md'")
            readme_url = item.get('download_url')
            if readme_url:
                readme_response = requests.get(readme_url, headers=headers)
                if readme_response.status_code == 200:
                    readme_content = readme_response.text
                    doi_matches = re.findall(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', readme_content, re.IGNORECASE)
                    if doi_matches:
                        doi = doi_matches[0]
                        logging.info(f"DOI found in 'README.md': {doi}")
                        return doi
                else:
                    logging.error("Error fetching 'README.md'")
                    return None
    logging.warning("DOI not found in the repository")
    # Implicitly returns None

def get_paper_details(doi: str) -> Optional[dict]:
    """
    Fetch paper details from OpenAlex using the DOI.

    Parameters:
        doi (str): Digital Object Identifier of the paper.

    Returns:
        Optional[dict]: Paper data as a dictionary if retrieval is successful; otherwise, None.
    """
    logging.info(f"Fetching paper details for DOI: {doi}")
    url = f"https://api.openalex.org/works/doi:{quote(doi)}?mailto={OPENALEX_EMAIL}"
    response = make_api_request(url)
    if response is None:
        return None
    paper_data = response.json()
    logging.debug(f"Paper data retrieved: {paper_data}")
    return paper_data

def make_api_request(url: str, headers: Optional[dict] = None, params: Optional[dict] = None) -> Optional[requests.Response]:
    """
    Make an API request with retry logic and exponential backoff.

    Parameters:
        url (str): The API endpoint.
        headers (Optional[dict]): HTTP headers to include in the request.
        params (Optional[dict]): Query parameters for the GET request.

    Returns:
        Optional[requests.Response]: The HTTP response if successful; otherwise, None.
    """
    if headers is None:
        headers = {}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response
            elif response.status_code in [429, 500, 502, 503, 504]:
                retries += 1
                sleep_time = RETRY_DELAY * (2 ** (retries - 1))
                logging.warning(f"API request failed with status {response.status_code}. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error(f"API request failed with status {response.status_code}. URL: {url}")
                return None
        except requests.exceptions.RequestException as e:
            retries += 1
            sleep_time = RETRY_DELAY * (2 ** (retries - 1))
            logging.warning(f"Request exception: {e}. Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
    logging.error(f"Failed to retrieve data after {MAX_RETRIES} attempts.")
    return None

def process_paper_data(paper_data: dict) -> None:
    """
    Process and store paper data from OpenAlex.

    Parameters:
        paper_data (dict): The paper data dictionary obtained from OpenAlex.

    Side Effects:
        Updates the global PAPERS_DICT, AUTHORS_DICT, INSTITUTIONS_DICT, and TOPICS_DICT.
    """
    openalex_id = paper_data.get('id')
    if openalex_id in PAPERS_DICT:
        logging.debug(f"Paper {openalex_id} already processed")
        return
    logging.info(f"Processing paper {openalex_id}")
    title = paper_data.get('title')
    doi = paper_data.get('doi')
    publication_date = paper_data.get('publication_date')
    abstract_inverted_index = paper_data.get('abstract_inverted_index')

    # Convert abstract_inverted_index to a readable abstract
    if abstract_inverted_index:
        word_positions = {}
        for word, positions in abstract_inverted_index.items():
            for position in positions:
                word_positions[position] = word
        abstract_words = [word_positions[i] for i in sorted(word_positions.keys())]
        abstract_text = ' '.join(abstract_words)
    else:
        abstract_text = None
        # TODO: Consider fetching open access objects for a more detailed abstract if available.

    # Get topics (concepts)
    concepts = paper_data.get('concepts', [])
    topics = []
    for concept in concepts:
        topic_id = concept.get('id')
        if topic_id and topic_id not in TOPICS_DICT:
            logging.info(f"Adding topic {topic_id}")
            topic_node = {
                'id': topic_id,
                'name': concept.get('display_name'),
                'type': 'topic'
            }
            TOPICS_DICT[topic_id] = topic_node
        if topic_id:
            topics.append(topic_id)

    # Process authors
    authors = []
    authors_data = paper_data.get('authorships', [])
    for author_entry in authors_data:
        author_data = author_entry.get('author', {})
        author_id = author_data.get('id')
        if author_id and author_id not in AUTHORS_DICT:
            logging.info(f"Adding author {author_id}")
            author_node = {
                'id': author_id,
                'name': author_data.get('display_name'),
                'orcid': author_data.get('orcid'),
                'affiliations': [],
                'type': 'person',
                'papers_authored': []
            }
            # Process affiliations
            affiliations_data = author_entry.get('institutions', [])
            for inst_data in affiliations_data:
                inst_id = inst_data.get('id')
                if inst_id and inst_id not in INSTITUTIONS_DICT:
                    logging.info(f"Adding institution {inst_id}")
                    institution_node = {
                        'id': inst_id,
                        'name': inst_data.get('display_name'),
                        'type': 'institution'
                    }
                    INSTITUTIONS_DICT[inst_id] = institution_node
                if inst_id:
                    author_node['affiliations'].append(inst_id)
            AUTHORS_DICT[author_id] = author_node
        if author_id:
            authors.append(author_id)
            if openalex_id not in AUTHORS_DICT[author_id]['papers_authored']:
                AUTHORS_DICT[author_id]['papers_authored'].append(openalex_id)

    # Create paper node
    paper_node = {
        'id': openalex_id,
        'title': title,
        'doi': doi,
        'publication_date': publication_date,
        'abstract': abstract_text,
        'type': 'paper',
        'authors': authors,
        'topics': topics,
        'cited_by': [],
        'references': []
    }

    # Process references
    references = paper_data.get('referenced_works', [])
    for ref_id in references:
        paper_node['references'].append(ref_id)
        # TODO: Consider retaining additional metadata from referenced_works if needed.

    PAPERS_DICT[openalex_id] = paper_node
    logging.debug(f"Paper node created: {paper_node}")

def get_papers_by_author(author_id: str) -> None:
    """
    Fetch papers authored by a given author from OpenAlex.

    Parameters:
        author_id (str): The OpenAlex identifier for the author.
    """
    logging.info(f"Fetching papers authored by {author_id}")
    page = 1
    per_page = 200  # Maximum allowed per-page value
    records_retrieved = 0

    while True:
        params = {
            "filter": f"authorships.author.id:{author_id}",
            "page": page,
            "per-page": per_page,
            "mailto": OPENALEX_EMAIL
        }
        url = "https://api.openalex.org/works"
        response = make_api_request(url, params=params)
        if response is None:
            break
        data = response.json()
        works = data.get('results', [])
        if not works:
            logging.info(f"No more papers found for author {author_id}")
            break
        for work in works:
            process_paper_data(work)
            records_retrieved += 1
            if RECORD_LIMIT != 0 and records_retrieved >= RECORD_LIMIT:
                logging.info(f"Reached record limit ({RECORD_LIMIT}) for author {author_id}")
                return
        if data.get('meta', {}).get('next_page') and (RECORD_LIMIT == 0 or records_retrieved < RECORD_LIMIT):
            page += 1
            logging.debug(f"Moving to page {page} for author {author_id}")
            time.sleep(1)  # Respect rate limits
        else:
            break

def iterative_citation_gathering(start_paper_id: str) -> None:
    """
    Perform iterative citation gathering up to MAX_DEPTH starting from a given paper.

    Parameters:
        start_paper_id (str): The OpenAlex identifier for the starting paper.
    """
    logging.info(f"Starting iterative citation gathering from paper {start_paper_id}")
    queue = deque()
    queue.append((start_paper_id, 1))
    while queue:
        try:
            current_paper_id, current_depth = queue.popleft()
            if current_depth > MAX_DEPTH:
                continue
            if current_paper_id in VISITED_PAPERS:
                continue
            VISITED_PAPERS.add(current_paper_id)
            logging.info(f"Processing paper {current_paper_id} at depth {current_depth}")
            # Fetch and process the paper details if not already done
            if current_paper_id not in PAPERS_DICT:
                url = f"https://api.openalex.org/works/{current_paper_id}"
                params = {"mailto": OPENALEX_EMAIL}
                response = make_api_request(url, params=params)
                if response is None:
                    continue
                paper_data = response.json()
                process_paper_data(paper_data)
            else:
                paper_data = PAPERS_DICT[current_paper_id]
            # Get authors of the current paper and fetch their papers
            authors = paper_data.get('authors', [])
            for author_id in authors:
                get_papers_by_author(author_id)
            # Get citing papers
            page = 1
            per_page = 200
            records_retrieved = 0
            while True:
                params = {
                    "filter": f"cites:{current_paper_id}",
                    "page": page,
                    "per-page": per_page,
                    "mailto": OPENALEX_EMAIL
                }
                url = "https://api.openalex.org/works"
                response = make_api_request(url, params=params)
                if response is None:
                    break
                data = response.json()
                works = data.get('results', [])
                if not works:
                    logging.info(f"No more citing papers found for paper {current_paper_id} at depth {current_depth}")
                    break
                for work in works:
                    citing_paper_id = work.get('id')
                    if citing_paper_id in VISITED_PAPERS:
                        continue
                    process_paper_data(work)
                    # Update cited_by attribute
                    if current_paper_id in PAPERS_DICT:
                        if citing_paper_id not in PAPERS_DICT[current_paper_id]['cited_by']:
                            PAPERS_DICT[current_paper_id]['cited_by'].append(citing_paper_id)
                    records_retrieved += 1
                    queue.append((citing_paper_id, current_depth + 1))
                    if RECORD_LIMIT != 0 and records_retrieved >= RECORD_LIMIT:
                        logging.info(f"Reached record limit ({RECORD_LIMIT}) for citing papers of {current_paper_id}")
                        break
                if data.get('meta', {}).get('next_page') and (RECORD_LIMIT == 0 or records_retrieved < RECORD_LIMIT):
                    page += 1
                    logging.debug(f"Moving to page {page} for citing papers of {current_paper_id}")
                    time.sleep(1)
                else:
                    break
        except KeyboardInterrupt:
            logging.warning("Process interrupted by user. Saving collected data.")
            break

def collect_github_data(repo_owner: str, repo_name: str) -> Optional[dict]:
    """
    Collect data from the GitHub repository, including repository details, contributors,
    issues, pull requests, languages, releases, and recent activity.

    Parameters:
        repo_owner (str): GitHub username or organization name.
        repo_name (str): Repository name.

    Returns:
        Optional[dict]: A dictionary containing the repository data if successful; otherwise, None.
    """
    logging.info(f"Collecting data for GitHub repository '{repo_owner}/{repo_name}'")
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    repo_data: dict = {}
    # Get repository details
    response = make_api_request(base_url, headers=headers)
    if response is None:
        logging.error("Failed to fetch repository data.")
        return None
    repo_info = response.json()
    repo_data['name'] = repo_info.get('name')
    repo_data['description'] = repo_info.get('description')
    repo_data['license'] = repo_info.get('license', {}).get('name')
    repo_data['stars'] = repo_info.get('stargazers_count')
    repo_data['forks'] = repo_info.get('forks_count')
    repo_data['watchers'] = repo_info.get('subscribers_count')
    repo_data['main_language'] = repo_info.get('language')
    repo_data['created_at'] = repo_info.get('created_at')
    repo_data['updated_at'] = repo_info.get('updated_at')
    repo_data['pushed_at'] = repo_info.get('pushed_at')
    repo_data['has_readme'] = False
    repo_data['has_code_of_conduct'] = False
    repo_data['documentation_files'] = {
        'CITATION.cff': False,
        'CONTRIBUTING.md': False,
        'GOVERNANCE.md': False,
        'FUNDING.yml': False,
        'funding.json': False
    }
    # Check for README and other files
    contents_url = f"{base_url}/contents"
    response = make_api_request(contents_url, headers=headers)
    if response is None:
        logging.error("Failed to fetch repository contents.")
        return None
    contents = response.json()
    for item in contents:
        name = item.get('name', '').lower()
        if name == 'readme.md':
            repo_data['has_readme'] = True
        elif name == 'code_of_conduct.md':
            repo_data['has_code_of_conduct'] = True
        elif name in [key.lower() for key in repo_data['documentation_files'].keys()]:
            # Match the original key casing
            for key in repo_data['documentation_files']:
                if key.lower() == name:
                    repo_data['documentation_files'][key] = True
                    break
    # Get contributors
    contributors_url = f"{base_url}/contributors"
    contributors_set = set()
    page = 1
    while True:
        params = {"per_page": 100, "page": page}
        response = make_api_request(contributors_url, headers=headers, params=params)
        if response is None:
            break
        page_contributors = response.json()
        if not page_contributors:
            break
        for contributor in page_contributors:
            login = contributor.get('login')
            if login:
                contributors_set.add(login)
        if 'next' in response.links:
            page += 1
            logging.debug(f"Fetching page {page} of contributors")
        else:
            break
    repo_data['num_contributors'] = len(contributors_set)
    logging.info(f"Total contributors: {repo_data['num_contributors']}")
    # Get issues
    issues_url = f"{base_url}/issues"
    issues = []
    page = 1
    while True:
        params = {"state": "all", "per_page": 100, "page": page}
        response = make_api_request(issues_url, headers=headers, params=params)
        if response is None:
            break
        page_issues = response.json()
        if not page_issues:
            break
        issues.extend(page_issues)
        page += 1
    open_issues = [issue for issue in issues if issue.get('state') == 'open' and 'pull_request' not in issue]
    closed_issues = [issue for issue in issues if issue.get('state') == 'closed' and 'pull_request' not in issue]
    repo_data['total_issues'] = len(issues)
    repo_data['open_issues'] = len(open_issues)
    repo_data['closed_issues'] = len(closed_issues)
    # Calculate average time to close issues
    total_close_time = 0
    total_first_response_time = 0
    num_closed_issues_with_close_time = 0
    num_issues_with_first_response = 0
    for issue in closed_issues:
        try:
            created_at = datetime.strptime(issue['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            closed_at = datetime.strptime(issue['closed_at'], "%Y-%m-%dT%H:%M:%SZ")
            close_time = (closed_at - created_at).total_seconds() / 3600  # in hours
            total_close_time += close_time
            num_closed_issues_with_close_time += 1
            # First response time
            comments_url = issue.get('comments_url')
            if comments_url:
                comments_response = make_api_request(comments_url, headers=headers)
                if comments_response and comments_response.status_code == 200:
                    comments = comments_response.json()
                    if comments:
                        first_comment = comments[0]
                        first_response_at = datetime.strptime(first_comment['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                        first_response_time = (first_response_at - created_at).total_seconds() / 3600  # in hours
                        total_first_response_time += first_response_time
                        num_issues_with_first_response += 1
        except Exception as e:
            logging.error(f"Error processing issue dates: {e}")
    repo_data['avg_time_to_close_issues'] = (total_close_time / num_closed_issues_with_close_time) if num_closed_issues_with_close_time > 0 else None
    repo_data['avg_time_to_first_response_issue'] = (total_first_response_time / num_issues_with_first_response) if num_issues_with_first_response > 0 else None
    # Get pull requests
    pulls_url = f"{base_url}/pulls"
    pulls = []
    page = 1
    while True:
        params = {"state": "all", "per_page": 100, "page": page}
        response = make_api_request(pulls_url, headers=headers, params=params)
        if response is None:
            break
        page_pulls = response.json()
        if not page_pulls:
            break
        pulls.extend(page_pulls)
        page += 1
    open_pulls = [pr for pr in pulls if pr.get('state') == 'open']
    closed_pulls = [pr for pr in pulls if pr.get('state') == 'closed']
    merged_pulls = []
    total_merge_time = 0
    total_first_review_time = 0
    num_merged_pulls_with_time = 0
    num_pulls_with_first_review = 0
    for pr in closed_pulls:
        pr_details_response = make_api_request(pr.get('url'), headers=headers)
        if pr_details_response and pr_details_response.status_code == 200:
            pr_details = pr_details_response.json()
            if pr_details.get('merged_at'):
                merged_pulls.append(pr)
                try:
                    created_at = datetime.strptime(pr_details['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                    merged_at = datetime.strptime(pr_details['merged_at'], "%Y-%m-%dT%H:%M:%SZ")
                    merge_time = (merged_at - created_at).total_seconds() / 3600  # in hours
                    total_merge_time += merge_time
                    num_merged_pulls_with_time += 1
                    # First review time
                    reviews_url = pr_details['url'] + '/reviews'
                    reviews_response = make_api_request(reviews_url, headers=headers)
                    if reviews_response and reviews_response.status_code == 200:
                        reviews = reviews_response.json()
                        if reviews:
                            first_review = reviews[0]
                            review_submitted_at = datetime.strptime(first_review['submitted_at'], "%Y-%m-%dT%H:%M:%SZ")
                            first_review_time = (review_submitted_at - created_at).total_seconds() / 3600  # in hours
                            total_first_review_time += first_review_time
                            num_pulls_with_first_review += 1
                except Exception as e:
                    logging.error(f"Error processing pull request dates: {e}")
    repo_data['total_pull_requests'] = len(pulls)
    repo_data['open_pull_requests'] = len(open_pulls)
    repo_data['closed_pull_requests'] = len(closed_pulls)
    repo_data['merged_pull_requests'] = len(merged_pulls)
    repo_data['avg_time_to_merge_pr'] = (total_merge_time / num_merged_pulls_with_time) if num_merged_pulls_with_time > 0 else None
    repo_data['avg_time_to_first_review_pr'] = (total_first_review_time / num_pulls_with_first_review) if num_pulls_with_first_review > 0 else None
    repo_data['pr_merge_percentage'] = ((len(merged_pulls) / repo_data['total_pull_requests']) * 100) if repo_data['total_pull_requests'] > 0 else None
    # Calculate pull request update frequency
    pr_dates = []
    for pr in pulls:
        try:
            pr_dates.append(datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ"))
        except Exception as e:
            logging.error(f"Error parsing pull request date: {e}")
    if len(pr_dates) > 1:
        pr_dates.sort()
        time_differences = [(pr_dates[i+1] - pr_dates[i]).total_seconds() / 3600 for i in range(len(pr_dates)-1)]
        repo_data['pr_update_frequency'] = sum(time_differences) / len(time_differences)
    else:
        repo_data['pr_update_frequency'] = None
    # Average time for first response on pull requests
    total_first_response_time_pr = 0
    num_pulls_with_first_response = 0
    for pr in pulls:
        try:
            created_at = datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            comments_url = pr.get('comments_url')
            if comments_url:
                comments_response = make_api_request(comments_url, headers=headers)
                if comments_response and comments_response.status_code == 200:
                    comments = comments_response.json()
                    if comments:
                        first_comment = comments[0]
                        first_response_at = datetime.strptime(first_comment['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                        first_response_time = (first_response_at - created_at).total_seconds() / 3600  # in hours
                        total_first_response_time_pr += first_response_time
                        num_pulls_with_first_response += 1
        except Exception as e:
            logging.error(f"Error processing pull request response time: {e}")
    repo_data['avg_time_to_first_response_pr'] = (total_first_response_time_pr / num_pulls_with_first_response) if num_pulls_with_first_response > 0 else None
    # Get languages
    languages_url = f"{base_url}/languages"
    response = make_api_request(languages_url, headers=headers)
    if response is None:
        logging.error("Failed to fetch languages.")
        repo_data['languages'] = {}
        repo_data['language_percentages'] = {}
    else:
        languages = response.json()
        total_bytes = sum(languages.values())
        repo_data['languages'] = languages
        if total_bytes > 0:
            repo_data['language_percentages'] = {lang: (bytes_ / total_bytes) * 100 for lang, bytes_ in languages.items()}
        else:
            repo_data['language_percentages'] = {}
    # Get total downloads from releases
    releases_url = f"{base_url}/releases"
    response = make_api_request(releases_url, headers=headers)
    if response is None:
        logging.error("Failed to fetch releases.")
        repo_data['total_downloads'] = 0
    else:
        releases = response.json()
        total_downloads = 0
        for release in releases:
            assets = release.get('assets', [])
            for asset in assets:
                total_downloads += asset.get('download_count', 0)
        repo_data['total_downloads'] = total_downloads
    # Recent activity (past 60 days)
    since_date = (datetime.utcnow() - timedelta(days=60)).isoformat() + 'Z'
    # Recent commits
    commits_url = f"{base_url}/commits"
    commits = []
    page = 1
    while True:
        params = {"since": since_date, "per_page": 100, "page": page}
        response = make_api_request(commits_url, headers=headers, params=params)
        if response is None or response.status_code != 200:
            break
        page_commits = response.json()
        if not page_commits:
            break
        commits.extend(page_commits)
        page += 1
    repo_data['recent_commits'] = len(commits)
    # Active contributors (past 60 days)
    contributors_set_recent = set()
    for commit in commits:
        author = commit.get('author')
        if author:
            contributors_set_recent.add(author.get('login'))
    repo_data['recent_active_contributors'] = len(contributors_set_recent)
    # Recent issues opened and closed
    recent_issues_url = f"{base_url}/issues"
    recent_issues = []
    page = 1
    while True:
        params = {"since": since_date, "state": "all", "per_page": 100, "page": page}
        response = make_api_request(recent_issues_url, headers=headers, params=params)
        if response is None or response.status_code != 200:
            break
        page_issues = response.json()
        if not page_issues:
            break
        recent_issues.extend(page_issues)
        page += 1
    recent_issues_opened = [issue for issue in recent_issues if 'pull_request' not in issue and issue.get('created_at', '') >= since_date]
    recent_issues_closed = [issue for issue in recent_issues_opened if issue.get('closed_at', '') >= since_date]
    repo_data['recent_issues_opened'] = len(recent_issues_opened)
    repo_data['recent_issues_closed'] = len(recent_issues_closed)
    # Recent pull requests opened and merged
    recent_pulls_url = f"{base_url}/pulls"
    recent_pulls = []
    page = 1
    while True:
        params = {"state": "all", "per_page": 100, "page": page}
        response = make_api_request(recent_pulls_url, headers=headers, params=params)
        if response is None or response.status_code != 200:
            break
        page_pulls = response.json()
        if not page_pulls:
            break
        recent_pulls.extend(page_pulls)
        page += 1
    recent_pulls_opened = [pr for pr in recent_pulls if pr.get('created_at', '') >= since_date]
    recent_pulls_merged = []
    for pr in recent_pulls_opened:
        pr_details_response = make_api_request(pr.get('url'), headers=headers)
        if pr_details_response and pr_details_response.status_code == 200:
            pr_details = pr_details_response.json()
            if pr_details.get('merged_at', '') >= since_date:
                recent_pulls_merged.append(pr)
    repo_data['recent_pulls_opened'] = len(recent_pulls_opened)
    repo_data['recent_pulls_merged'] = len(recent_pulls_merged)
    # Add the repository URL
    repo_data['url'] = f"https://github.com/{repo_owner}/{repo_name}"
    # Add to projects list
    PROJECTS_LIST.append(repo_data)
    logging.info(f"GitHub data collected for '{repo_owner}/{repo_name}'")
    return repo_data

def run_repo_cite() -> None:
    """
    Main function to run the repository citation data collection process.
    """
    global OPENALEX_EMAIL, RECORD_LIMIT, MAX_DEPTH, GITHUB_TOKEN

    logging.info("Script started")
    try:
        repo_url = input("Enter GitHub repository URL: ").strip()
        # Parse the GitHub URL to get the owner and repo name
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', repo_url)
        if not match:
            logging.error("Invalid GitHub URL format. Exiting.")
            return
        repo_owner, repo_name = match.groups()

        # Optional: Prompt for email and record limit
        email_input = input("Enter your email for OpenAlex API (optional): ").strip()
        if email_input:
            OPENALEX_EMAIL = email_input
        record_limit_input = input("Enter number of records to retrieve per API call (integer, 0 for all) [default is 0]: ").strip()
        if record_limit_input:
            if record_limit_input.isdigit():
                RECORD_LIMIT = int(record_limit_input)
            else:
                logging.warning("Invalid record limit input. Using default (0 for all).")
                RECORD_LIMIT = 0
        max_depth_input = input("Enter maximum depth for citation traversal (integer) [default is 2]: ").strip()
        if max_depth_input:
            if max_depth_input.isdigit():
                MAX_DEPTH = int(max_depth_input)
            else:
                logging.warning("Invalid max depth input. Using default (2).")
                MAX_DEPTH = 2

        # Ensure GitHub token is available
        if not GITHUB_TOKEN:
            logging.error("GitHub personal access token not found in .env file. Exiting.")
            return

        # Collect GitHub data
        github_data = collect_github_data(repo_owner, repo_name)
        if github_data is None:
            logging.error("Failed to collect GitHub data. Exiting.")
            return

        doi = get_doi_from_github_repo(repo_owner, repo_name)
        if not doi:
            logging.error("DOI not found. Exiting.")
            return
        logging.info(f"DOI found: {doi}")
        paper_data = get_paper_details(doi)
        if not paper_data:
            logging.error("Paper details not found. Exiting.")
            return
        process_paper_data(paper_data)

        original_paper_id = paper_data.get('id')

        # Get authors from the original paper and fetch their papers
        authors_data = paper_data.get('authorships', [])
        for author_entry in authors_data:
            author_data = author_entry.get('author', {})
            author_id = author_data.get('id')
            if author_id:
                get_papers_by_author(author_id)

        # Start iterative citation gathering
        iterative_citation_gathering(original_paper_id)

        # Prepare the output data
        output_data = {
            'people': list(AUTHORS_DICT.values()),
            'papers': list(PAPERS_DICT.values()),
            'institutions': list(INSTITUTIONS_DICT.values()),
            'topics': list(TOPICS_DICT.values()),
            'projects': PROJECTS_LIST
        }

        # Save to JSON file
        with open('output_data.json', 'w') as f:
            json.dump(output_data, f, indent=2)
        logging.info("Data collection complete. Output saved to 'output_data.json'.")

        # Log the total number of nodes
        logging.info(f"Total number of papers: {len(output_data['papers'])}")
        logging.info(f"Total number of people: {len(output_data['people'])}")
        logging.info(f"Total number of institutions: {len(output_data['institutions'])}")
        logging.info(f"Total number of topics: {len(output_data['topics'])}")
        logging.info(f"Total number of projects: {len(output_data['projects'])}")

    except KeyboardInterrupt:
        logging.warning("Process interrupted by user. Saving collected data.")
        output_data = {
            'people': list(AUTHORS_DICT.values()),
            'papers': list(PAPERS_DICT.values()),
            'institutions': list(INSTITUTIONS_DICT.values()),
            'topics': list(TOPICS_DICT.values()),
            'projects': PROJECTS_LIST
        }
        with open('output_data_partial.json', 'w') as f:
            json.dump(output_data, f, indent=2)
        logging.info("Partial data saved to 'output_data_partial.json'.")
        logging.info(f"Total number of papers collected: {len(output_data['papers'])}")
        logging.info(f"Total number of people collected: {len(output_data['people'])}")
        logging.info(f"Total number of institutions collected: {len(output_data['institutions'])}")
        logging.info(f"Total number of topics collected: {len(output_data['topics'])}")
        logging.info(f"Total number of projects collected: {len(output_data['projects'])}")

if __name__ == "__main__":
    run_repo_cite()
