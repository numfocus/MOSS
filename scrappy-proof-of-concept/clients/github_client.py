# clients/github_client.py
import requests
import time
import json
import logging
from config import GITHUB_API_BASE_URL  # Use centralized config

logger = logging.getLogger(__name__)

class GitHubClient:
    BASE_URL = GITHUB_API_BASE_URL

    def __init__(self, token=None, default_timeout=30):
        """
        :param token: GitHub Personal Access Token
        :param default_timeout: seconds before timing out a single request
        """
        self.token = token
        self.default_timeout = default_timeout
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def get(self, url, params=None):
        """
        Send a GET request, handling retries and rate-limit errors.
        """
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            logger.debug(f"[GET Attempt {attempt}/{max_retries}] URL={url} Params={params}")
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=self.default_timeout
                )
                if response.status_code == 200:
                    logger.debug(f"[GET {url}] -> 200 OK")
                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        logger.error(f"[GET {url}] JSON parse error: {e}")
                        return None
                elif response.status_code == 403:
                    try:
                        error_json = response.json()
                    except json.JSONDecodeError:
                        error_json = {}
                    message = error_json.get("message", "").lower()
                    if "rate limit exceeded" in message:
                        reset_timestamp = response.headers.get("X-RateLimit-Reset")
                        remaining = response.headers.get("X-RateLimit-Remaining")
                        logger.warning("GitHub rate limit exceeded!")
                        logger.warning(f"X-RateLimit-Remaining: {remaining}")
                        logger.warning(f"X-RateLimit-Reset: {reset_timestamp}")
                        if reset_timestamp:
                            reset_ts = int(reset_timestamp)
                            current_ts = int(time.time())
                            sleep_time = reset_ts - current_ts + 1
                            if sleep_time < 1:
                                sleep_time = 1
                            logger.warning(f"Sleeping for {sleep_time} seconds (rate limit).")
                            time.sleep(sleep_time)
                            continue
                        else:
                            logger.warning("No X-RateLimit-Reset header found. Sleeping 60s.")
                            time.sleep(60)
                            continue
                    else:
                        logger.error(f"[GET {url}] 403 Forbidden: {response.text}")
                        return None
                else:
                    logger.error(f"[GET {url}] -> {response.status_code} {response.reason}")
                    logger.error(f"Response Text: {response.text}")
                    return None
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as e:
                logger.warning(f"[GET {url}] Timeout on attempt {attempt}. Error: {e}")
                if attempt < max_retries:
                    backoff = 5 * attempt
                    logger.warning(f"Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                else:
                    logger.error("Max retries reached. Giving up.")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"[GET {url}] RequestException on attempt {attempt}: {e}")
                if attempt < max_retries:
                    backoff = 5 * attempt
                    logger.warning(f"Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                else:
                    logger.error("Max retries reached. Giving up.")
                    return None
        logger.error(f"[GET {url}] All retries exhausted. Returning None.")
        return None

    def get_all_pages(self, url, params=None):
        """
        Fetch all pages from a paginated endpoint.
        """
        all_items = []
        page = 1
        while True:
            local_params = params.copy() if params else {}
            local_params.update({"page": page, "per_page": 100})
            logger.info(f"Fetching page {page} of {url}")
            items = self.get(url, params=local_params)
            if not items:
                logger.info(f"No more data for {url} on page {page}.")
                break
            if isinstance(items, list):
                all_items.extend(items)
                logger.info(f"Fetched {len(items)} items from page {page}.")
                if len(items) < 100:
                    break
            else:
                logger.info(f"Non-list response encountered. Ending pagination for {url}.")
                break
            page += 1
            time.sleep(1)
        logger.info(f"Finished pagination for {url}, total items fetched: {len(all_items)}")
        return all_items

    def get_repository(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        return self.get(url)

    def get_user(self, username):
        url = f"{self.BASE_URL}/users/{username}"
        return self.get(url)

    def get_organization(self, org_login):
        url = f"{self.BASE_URL}/orgs/{org_login}"
        return self.get(url)

    def get_branches(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/branches"
        return self.get_all_pages(url)

    def get_tags(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/tags"
        return self.get_all_pages(url)

    def get_commits(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits"
        return self.get_all_pages(url)

    def get_labels(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/labels"
        return self.get_all_pages(url)

    def get_milestones(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/milestones"
        return self.get_all_pages(url)

    def get_releases(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/releases"
        return self.get_all_pages(url)

    def get_webhooks(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/hooks"
        return self.get_all_pages(url)

    def get_events(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/events"
        return self.get_all_pages(url)

    def get_collaborators(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/collaborators"
        return self.get_all_pages(url)

    def get_workflows(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows"
        data = self.get(url)
        if data and isinstance(data, dict):
            return data.get("workflows", [])
        return []

    def get_workflow_runs(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs"
        data = self.get(url)
        if data and isinstance(data, dict):
            return data.get("workflow_runs", [])
        return []

    def get_readme(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/readme"
        return self.get(url)

    def get_discussions(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/discussions"
        return self.get_all_pages(url)

    def get_citation_cff(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contents/CITATION.cff"
        return self.get(url)

    def get_traffic_views(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/traffic/views"
        return self.get(url)

    def get_traffic_clones(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/traffic/clones"
        return self.get(url)

    def get_traffic_popular_paths(self, owner, repo):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/traffic/popular/paths"
        return self.get(url)
