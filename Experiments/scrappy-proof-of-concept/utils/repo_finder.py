# utils/repo_finder.py
import logging
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

def search_repositories(client, keywords):
    """
    Search GitHub repositories using the GitHub API.
    Returns a list of repository JSON objects.
    """
    search_url = f"{client.BASE_URL}/search/repositories"
    all_repositories = []
    per_page = 100
    page = 1
    while True:
        params = {"q": keywords, "per_page": per_page, "page": page}
        logger.info(f"Searching repositories: page {page}")
        results = client.get(search_url, params=params)
        if not results or "items" not in results:
            break
        items = results["items"]
        all_repositories.extend(items)
        if len(items) < per_page:
            break
        page += 1
        time.sleep(1)
    return all_repositories

def search_repositories_in_range(client, keywords, start_date, end_date, threshold=1000):
    """
    Search GitHub repositories with the given keywords created between start_date and end_date.
    If the total_count is >= threshold, subdivide the range recursively.
    Logs the count for each date range and returns the repository JSON objects.
    """
    query = f"\"{keywords}\" created:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
    search_url = f"{client.BASE_URL}/search/repositories"
    params = {"q": query, "per_page": 1, "page": 1}
    response = client.get(search_url, params=params)
    if not response:
        return []
    total_count = response.get("total_count", 0)
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} -> {total_count} repos found")
    if total_count >= threshold:
        mid_timedelta = (end_date - start_date) / 2
        mid_date = start_date + mid_timedelta
        left_repos = search_repositories_in_range(client, keywords, start_date, mid_date, threshold)
        right_start = mid_date + timedelta(days=1)
        right_repos = search_repositories_in_range(client, keywords, right_start, end_date, threshold)
        return left_repos + right_repos
    else:
        all_repositories = []
        per_page = 100
        page = 1
        while True:
            params = {"q": query, "per_page": per_page, "page": page}
            results = client.get(search_url, params=params)
            if not results or "items" not in results:
                break
            items = results["items"]
            all_repositories.extend(items)
            if len(items) < per_page:
                break
            page += 1
            time.sleep(1)
        return all_repositories

def search_repositories_by_date_ranges(client, keywords):
    """
    Generate date-range chunks starting from the current time back to January 1st of the current year at 00:01
    (first chunk), and then subsequent chunks as 12-month lookbacks. Search each chunk using dynamic subdivision.
    Returns the aggregated list of repository JSON objects.
    """
    chunks_results = []
    now = datetime.now()
    current_year_boundary = datetime(now.year, 1, 1, 0, 1)
    first_chunk_start = current_year_boundary
    first_chunk_end = now
    repos = search_repositories_in_range(client, keywords, first_chunk_start, first_chunk_end)
    chunks_results.extend(repos)
    logger.info(f"First chunk (current year): {first_chunk_start.strftime('%Y-%m-%d')} to {first_chunk_end.strftime('%Y-%m-%d')} -> {len(repos)} repos found")
    
    next_end = current_year_boundary - timedelta(seconds=1)
    while True:
        next_start = next_end - relativedelta(years=1) + timedelta(seconds=1)
        if next_start.year < 2008:
            break
        repos_chunk = search_repositories_in_range(client, keywords, next_start, next_end)
        logger.info(f"12-month chunk: {next_start.strftime('%Y-%m-%d')} to {next_end.strftime('%Y-%m-%d')} -> {len(repos_chunk)} repos found")
        chunks_results.extend(repos_chunk)
        next_end = next_start - timedelta(seconds=1)
    return chunks_results