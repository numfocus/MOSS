import requests
import json
import csv
import time
import re
import base64
import logging
import os
import argparse
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from tqdm import tqdm

# Initialize the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Handler for logging with tqdm
class TqdmLoggingHandler(logging.Handler):
    """
    Custom logging handler compatible with tqdm progress bars.
    """
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        
    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

# Configure the logger to use the custom handler
handler = TqdmLoggingHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Constants
GITHUB_API_URL = "https://api.github.com"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def github_api_request(url, headers, params=None):
    """
    Sends a GET request to the GitHub API with rate limit handling.

    Args:
        url (str): The API endpoint URL.
        headers (dict): HTTP headers for the request.
        params (dict, optional): Query parameters for the request.

    Returns:
        tuple: A tuple containing the JSON response and response headers.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        logger.debug(f"Attempt {attempt} for URL: {url}")
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred for URL: {url}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY)
            continue
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY)
            continue

        logger.debug(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logger.debug("Successful response.")
            return response.json(), response.headers
        elif response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
            if response.headers['X-RateLimit-Remaining'] == '0':
                reset_time = int(response.headers['X-RateLimit-Reset'])
                sleep_time = max(reset_time - int(time.time()), 0) + 1
                logger.warning(f"Rate limit exceeded. Sleeping for {sleep_time} seconds.")
                time.sleep(sleep_time)
                continue
        else:
            logger.error(f"Error: {response.status_code} - {response.reason}")
            if attempt == MAX_RETRIES:
                response.raise_for_status()
            time.sleep(RETRY_DELAY)
            continue
    raise Exception(f"Failed to get a successful response after {MAX_RETRIES} attempts.")

def get_next_link(headers):
    """
    Parses the 'Link' header from GitHub API response to find the next page URL.

    Args:
        headers (dict): Response headers from the GitHub API.

    Returns:
        str or None: The URL for the next page, or None if there isn't one.
    """
    link_header = headers.get('Link', '')
    if not link_header:
        return None
    links = link_header.split(',')
    for link in links:
        parts = link.split(';')
        if len(parts) < 2:
            continue
        url_part = parts[0].strip()
        rel_part = parts[1].strip()
        if rel_part == 'rel="next"':
            next_url = url_part.lstrip('<').rstrip('>')
            return next_url
    return None

def search_repositories_with_queries(query_terms, headers):
    """
    Searches GitHub repositories based on query terms and records matching queries.

    Args:
        query_terms (list): List of query strings.
        headers (dict): HTTP headers for the request.

    Returns:
        dict: A dictionary of repositories with their matching queries.
    """
    repositories = {}
    for query_term in query_terms:
        params = {'q': query_term, 'per_page': 100}
        url = f"{GITHUB_API_URL}/search/repositories"
        while url:
            logger.debug(f"Searching repositories with URL: {url} and params: {params}")
            try:
                data, headers_response = github_api_request(url, headers, params)
            except Exception as e:
                logger.error(f"Error searching repositories: {e}")
                break
            if data:
                items = data.get('items', [])
                logger.info(f"Found {len(items)} repositories in this page for query '{query_term}'.")
                for repo in items:
                    repo_id = repo.get('id')
                    if repo_id in repositories:
                        repositories[repo_id]['queries'].add(query_term)
                    else:
                        repositories[repo_id] = {
                            'repo_data': repo,
                            'queries': set([query_term])
                        }
                next_url = get_next_link(headers_response)
                url = next_url
                params = None  # Parameters are only needed for the initial request
            else:
                break
    return repositories

def load_keywords(filename):
    """
    Loads keywords from a CSV file and preprocesses them.

    Args:
        filename (str): Path to the CSV file containing keywords.

    Returns:
        set: A set of keywords.
    """
    keywords = set()
    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                for keyword in row:
                    keywords.add(keyword.strip().lower())
        logger.info(f"Loaded {len(keywords)} keywords.")
        if not keywords:
            logger.warning("No keywords found in the file.")
    except FileNotFoundError:
        logger.error(f"Keyword file {filename} not found.")
    return keywords

def load_hierarchical_keywords(filename):
    """
    Loads the hierarchical keyword dataset from a JSON file.

    Args:
        filename (str): Path to the JSON file containing hierarchical keywords.

    Returns:
        list: A list of hierarchical keyword entries.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as jsonfile:
            data = json.load(jsonfile)
            logger.info(f"Loaded hierarchical dataset with {len(data)} entries.")
            return data
    except FileNotFoundError:
        logger.error(f"Dataset file {filename} not found.")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        return []

def contains_keywords(text, keywords):
    """
    Checks if the text contains any of the keywords.

    Args:
        text (str): The text to search within.
        keywords (set): A set of keywords to search for.

    Returns:
        bool: True if any keyword is found, False otherwise.
    """
    text = text.lower()
    for keyword in keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text):
            logger.debug(f"Keyword '{keyword}' found in text.")
            return True
    return False

def count_keyword_matches(text, keywords):
    """
    Counts the number of keyword matches in the text and collects matched keywords.

    Args:
        text (str): The text to search within.
        keywords (set): A set of keywords to search for.

    Returns:
        tuple: A tuple containing the count of matches and a list of matched keywords.
    """
    text = text.lower()
    matched_keywords = []
    for keyword in keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text):
            matched_keywords.append(keyword)
    count = len(matched_keywords)
    return count, matched_keywords

def match_repository_keywords(repo_text, hierarchical_keywords):
    """
    Matches repository text against the hierarchical keywords and calculates scores.

    Args:
        repo_text (str): Combined text from the repository.
        hierarchical_keywords (list): List of hierarchical keyword entries.

    Returns:
        tuple: A dictionary of scores and a list of matched keywords.
    """
    scores = {
        'domains': {},
        'fields': {},
        'subfields': {},
        'topics': {}
    }
    matched_keywords = set()
    
    # Tokenize the repository text for efficient matching
    repo_words = set(re.findall(r'\b\w+\b', repo_text.lower()))
    
    for entry in hierarchical_keywords:
        domain = entry['Domain']
        field = entry['Field']
        subfield = entry['Subfield']
        topic = entry['Topic']
        keywords = set(map(str.lower, entry['Keywords']))  # Ensure keywords are lowercase
        
        # Check for keyword matches
        common_keywords = repo_words.intersection(keywords)
        if common_keywords:
            matched_keywords.update(common_keywords)
            # Increment scores
            scores['domains'][domain] = scores['domains'].get(domain, 0) + 1
            scores['fields'][field] = scores['fields'].get(field, 0) + 1
            scores['subfields'][subfield] = scores['subfields'].get(subfield, 0) + 1
            scores['topics'][topic] = scores['topics'].get(topic, 0) + 1
        
    return scores, list(matched_keywords)

def get_contributors(owner, repo_name, headers):
    """
    Retrieves the list of contributors for a given repository.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.

    Returns:
        list: A list of contributors.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contributors"
    params = {'per_page': 100}
    contributors = []
    while url:
        logger.debug(f"Getting contributors for repository: {owner}/{repo_name}")
        try:
            contributors_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching contributors: {e}")
            break
        if contributors_data:
            contributors.extend(contributors_data)
            next_url = get_next_link(headers_response)
            url = next_url
            params = None
        else:
            break
    logger.debug(f"Total contributors fetched: {len(contributors)}")
    return contributors if contributors else []

def get_user_repositories(username, headers):
    """
    Retrieves the list of repositories for a given user.

    Args:
        username (str): GitHub username.
        headers (dict): HTTP headers for the request.

    Returns:
        list: A list of repositories.
    """
    repos = []
    url = f"{GITHUB_API_URL}/users/{username}/repos"
    params = {'per_page': 100, 'type': 'owner'}
    page = 1  # Track the current page
    while url:
        logger.debug(f"Fetching repositories for user: {username}, page {page}")
        try:
            repo_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching user repositories: {e}")
            break
        if repo_data:
            repos.extend(repo_data)
            next_url = get_next_link(headers_response)
            url = next_url
            params = None  # Parameters are only needed for the initial request
            page += 1
        else:
            break
    logger.debug(f"Total repositories fetched for user {username}: {len(repos)}")
    return repos

def analyze_user_repositories(repos, keywords, university_name):
    """
    Analyzes a user's repositories for affiliation indicators.

    Args:
        repos (list): List of repositories.
        keywords (set): Set of keywords to look for.
        university_name (str): Name of the university.

    Returns:
        dict: A dictionary containing affiliation indicators.
    """
    affiliation_indicators = []
    for repo in repos:
        repo_name = repo.get('name', '')
        description = repo.get('description') or ''
        topics = repo.get('topics', [])
        created_at = repo.get('created_at')
        updated_at = repo.get('updated_at')
        repo_url = repo.get('html_url')
        # Check for affiliation indicators
        text_to_check = ' '.join([repo_name, description, ' '.join(topics)])
        if contains_keywords(text_to_check, {university_name.lower()}):
            affiliation_indicators.append({
                'name': repo_name,
                'description': description,
                'created_at': created_at,
                'updated_at': updated_at,
                'topics': topics,
                'url': repo_url
            })
    return {'affiliation_indicators': affiliation_indicators}

def get_pull_request_reviews(owner, repo_name, pr_number, headers):
    """
    Retrieves reviews for a specific pull request.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        pr_number (int): Pull request number.
        headers (dict): HTTP headers for the request.

    Returns:
        list: A list of reviews.
    """
    reviews = []
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews"
    params = {'per_page': 100}
    while url:
        logger.debug(f"Fetching reviews for PR #{pr_number} in {owner}/{repo_name}")
        try:
            reviews_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching PR reviews: {e}")
            break
        if reviews_data:
            reviews.extend(reviews_data)
            next_url = get_next_link(headers_response)
            url = next_url
            params = None
        else:
            break
    return reviews

def analyze_pull_requests(pull_requests, owner, repo_name, headers):
    """
    Analyzes pull requests for various metrics.

    Args:
        pull_requests (list): List of pull requests.
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.

    Returns:
        dict: A dictionary containing pull request analysis.
    """
    pr_analysis = {
        'total_prs': 0,
        'open_prs': 0,
        'closed_prs': 0,
        'average_time_to_merge': None,  # In days
        'pr_update_frequency': None,    # Average number of days between PRs
        'average_time_to_first_review': None,  # In days
        'review_to_merge_percentage': None     # Percentage
    }

    if not pull_requests:
        return pr_analysis

    pr_analysis['total_prs'] = len(pull_requests)
    merged_durations = []
    pr_dates = []
    total_reviewed_prs = 0
    reviewed_and_merged_prs = 0
    time_to_first_review_list = []

    # Initialize a progress bar for analyzing pull requests
    with tqdm(total=len(pull_requests), desc='Analyzing PRs', unit='PR', position=2, leave=False) as pbar:
        for pr in pull_requests:
            pr_number = pr.get('number')
            state = pr.get('state')
            created_at = pr.get('created_at')
            pr_dates.append(created_at)

            if state == 'open':
                pr_analysis['open_prs'] += 1
            elif state == 'closed':
                pr_analysis['closed_prs'] += 1

                if pr.get('merged_at'):
                    created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    merged_date = datetime.strptime(pr['merged_at'], "%Y-%m-%dT%H:%M:%SZ")
                    duration = (merged_date - created_date).total_seconds() / (3600 * 24)
                    merged_durations.append(duration)

            # Fetch reviews for the PR
            reviews = get_pull_request_reviews(owner, repo_name, pr_number, headers)
            if reviews:
                total_reviewed_prs += 1
                # Sort reviews by 'submitted_at' date
                reviews.sort(key=lambda x: x.get('submitted_at'))
                first_review_date = reviews[0].get('submitted_at')
                if first_review_date:
                    created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    first_review_datetime = datetime.strptime(first_review_date, "%Y-%m-%dT%H:%M:%SZ")
                    time_to_first_review = (first_review_datetime - created_date).total_seconds() / (3600 * 24)
                    time_to_first_review_list.append(time_to_first_review)

                if pr.get('merged_at'):
                    reviewed_and_merged_prs += 1

            pbar.update(1)  # Update the PRs progress bar

    # Calculate average time to merge pull requests
    if merged_durations:
        pr_analysis['average_time_to_merge'] = sum(merged_durations) / len(merged_durations)

    # Calculate PR update frequency
    pr_dates.sort()
    if len(pr_dates) > 1:
        date_differences = []
        for i in range(1, len(pr_dates)):
            date1 = datetime.strptime(pr_dates[i - 1], "%Y-%m-%dT%H:%M:%SZ")
            date2 = datetime.strptime(pr_dates[i], "%Y-%m-%dT%H:%M:%SZ")
            difference = (date2 - date1).total_seconds() / (3600 * 24)
            date_differences.append(difference)
        pr_analysis['pr_update_frequency'] = sum(date_differences) / len(date_differences)

    # Calculate average time to first review
    if time_to_first_review_list:
        pr_analysis['average_time_to_first_review'] = sum(time_to_first_review_list) / len(time_to_first_review_list)

    # Calculate review-to-merge percentage
    if total_reviewed_prs > 0:
        pr_analysis['review_to_merge_percentage'] = (reviewed_and_merged_prs / total_reviewed_prs) * 100

    return pr_analysis

def analyze_contributors(contributors, university_email_domain, university_name, keywords, headers):
    """
    Analyzes contributor profiles for affiliation and status.

    Args:
        contributors (list): List of contributors.
        university_email_domain (str): University's email domain.
        university_name (str): Name of the university.
        keywords (set): Set of keywords to look for.
        headers (dict): HTTP headers for the request.

    Returns:
        list: A list of contributor details with analysis.
    """
    contributor_details = []
    total_contributors = len(contributors)

    with tqdm(total=total_contributors, desc='Analyzing Contributors', unit='contributor', position=3, leave=False) as pbar:
        for index, contributor in enumerate(contributors, start=1):
            username = contributor.get('login')
            user_url = contributor.get('url')
            logger.debug(f"Analyzing contributor [{index}/{total_contributors}]: {username}")
            try:
                user_data, _ = github_api_request(user_url, headers)
            except Exception as e:
                logger.warning(f"Could not retrieve data for user: {username} - {e}")
                pbar.update(1)
                continue
            if user_data:
                logger.debug(f"Retrieved data for user: {username}")
                # Extract profile information
                email = user_data.get('email', '')
                bio = user_data.get('bio', '')
                company = user_data.get('company', '')
                name = user_data.get('name', '')
                location = user_data.get('location', '')
                blog = user_data.get('blog', '')
                twitter = user_data.get('twitter_username', '')
                public_repos_count = user_data.get('public_repos', 0)
                followers = user_data.get('followers', 0)
                created_at = user_data.get('created_at', '')
                updated_at = user_data.get('updated_at', '')
                # Determine status
                if contains_keywords(bio or '', {'student', 'faculty', 'professor', 'researcher'}):
                    status = 'Faculty/Student/Researcher'
                else:
                    status = 'Unknown'
                # Determine affiliation
                if (university_email_domain.lower() in (email or '').lower() or
                    contains_keywords(company or '', {university_name.lower()})):
                    affiliation = university_name
                else:
                    affiliation = company or 'Unknown'
                # Analyze user's repositories
                repos = get_user_repositories(username, headers)
                repo_analysis = analyze_user_repositories(repos, keywords, university_name)
                # Compile contributor details
                contributor_info = {
                    'username': username,
                    'name': name,
                    'status': status,
                    'affiliation': affiliation,
                    'current_company': company,
                    'location': location,
                    'email': email,
                    'bio': bio,
                    'blog': blog,
                    'twitter': twitter,
                    'public_repos': public_repos_count,
                    'followers': followers,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'repositories': repo_analysis['affiliation_indicators']
                }
                contributor_details.append(contributor_info)
                logger.info(f"Contributor analyzed: {username}")
            else:
                logger.warning(f"Could not retrieve data for user: {username}")
            pbar.update(1)
    return contributor_details

def determine_project_type(repo_name, description, topics, readme_content, files):
    """
    Determines the project type based on content analysis.

    Args:
        repo_name (str): Name of the repository.
        description (str): Description of the repository.
        topics (list): List of topics/tags.
        readme_content (str): Content of the README file.
        files (list): List of file names in the repository.

    Returns:
        tuple: Project type, scores, and matched keywords.
    """
    classproject_keywords = {'assignment', 'homework', 'hw', 'coursework'}
    research_keywords = {'research', 'thesis', 'dissertation', 'paper', 'publication', 'study', 'experiment', 'analysis', 'used in'}
    syllabus_keywords = {'syllabus', 'curriculum', 'outline', 'schedule', 'taught', 'students', 'course', 'class', 'lecture', 'tutorial', 'exam', 'quiz'}

    text_to_check = ' '.join([repo_name, description, ' '.join(topics), readme_content])
    file_names = ' '.join(files)

    # Combine text and file names
    total_text = text_to_check + ' ' + file_names

    # Count keyword matches and collect matched keywords for each category
    classproject_score, classproject_matches = count_keyword_matches(total_text, classproject_keywords)
    research_score, research_matches = count_keyword_matches(total_text, research_keywords)
    syllabus_score, syllabus_matches = count_keyword_matches(total_text, syllabus_keywords)

    # Determine the category with the highest score
    scores = {
        'Class Project': classproject_score,
        'Research Project': research_score,
        'Syllabus': syllabus_score
    }

    matched_keywords = {
        'Class Project': classproject_matches,
        'Research Project': research_matches,
        'Syllabus': syllabus_matches
    }

    max_score = max(scores.values())
    if max_score == 0:
        project_type = 'Other'
    else:
        # Handle ties
        max_categories = [category for category, score in scores.items() if score == max_score]
        if len(max_categories) == 1:
            project_type = max_categories[0]
        else:
            project_type = 'Tie: ' + ', '.join(max_categories)

    return project_type, scores, matched_keywords

def get_repository_issues(owner, repo_name, headers, since=None):
    """
    Retrieves issues for a repository.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.
        since (str, optional): Only issues updated at or after this time are returned.

    Returns:
        list: A list of issues.
    """
    issues = []
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues"
    params = {'state': 'all', 'per_page': 100}
    if since:
        params['since'] = since
    while url:
        logger.debug(f"Fetching issues for repository: {owner}/{repo_name}")
        try:
            issues_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching issues: {e}")
            break
        if issues_data is not None:
            # Filter out pull requests
            issues_only = [issue for issue in issues_data if 'pull_request' not in issue]
            issues.extend(issues_only)
            next_url = get_next_link(headers_response)
            url = next_url
            params = None
        else:
            break
    return issues

def get_issue_comments(owner, repo_name, issue_number, headers):
    """
    Retrieves comments for a specific issue.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        issue_number (int): Issue number.
        headers (dict): HTTP headers for the request.

    Returns:
        list: A list of comments.
    """
    comments = []
    page = 1
    per_page = 100
    while True:
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues/{issue_number}/comments"
        params = {'page': page, 'per_page': per_page}
        logger.debug(f"Fetching comments for issue #{issue_number} in {owner}/{repo_name}, page {page}")
        try:
            comments_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching issue comments: {e}")
            break
        if comments_data is not None:
            comments.extend(comments_data)
            if len(comments_data) < per_page:
                break
            page += 1
        else:
            break
    return comments

def get_pull_request_comments(owner, repo_name, pr_number, headers):
    """
    Retrieves comments for a specific pull request.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        pr_number (int): Pull request number.
        headers (dict): HTTP headers for the request.

    Returns:
        list: A list of comments.
    """
    comments = []
    page = 1
    per_page = 100
    while True:
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls/{pr_number}/comments"
        params = {'page': page, 'per_page': per_page}
        logger.debug(f"Fetching comments for PR #{pr_number} in {owner}/{repo_name}, page {page}")
        try:
            comments_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching PR comments: {e}")
            break
        if comments_data:
            comments.extend(comments_data)
            if len(comments_data) < per_page:
                break
            page += 1
        else:
            break
    return comments

def analyze_issues(issues, owner, repo_name, headers, university_email_domain, university_name):
    """
    Analyzes issues for collaboration and external participation.

    Args:
        issues (list): List of issues.
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.
        university_email_domain (str): University's email domain.
        university_name (str): Name of the university.

    Returns:
        dict: A dictionary containing issue analysis.
    """
    issue_analysis = {
        'total_issues': 0,
        'open_issues': 0,
        'closed_issues': 0,
        'average_time_to_close': None,  # In days
        'issue_update_frequency': None,  # Average number of days between issues
        'external_participants': set(),
        'collaboration_opportunities': []  # List of issue numbers or titles
    }

    if not issues:
        return issue_analysis

    issue_analysis['total_issues'] = len(issues)
    closed_issue_durations = []
    issue_dates = []

    # Initialize a progress bar for analyzing issues
    with tqdm(total=len(issues), desc='Analyzing Issues', unit='issue', position=1, leave=False) as pbar:
        for issue in issues:
            issue_number = issue.get('number')
            state = issue.get('state')
            created_at = issue.get('created_at')
            issue_dates.append(created_at)

            if state == 'open':
                issue_analysis['open_issues'] += 1
            elif state == 'closed':
                issue_analysis['closed_issues'] += 1
                closed_at = issue.get('closed_at')
                if closed_at:
                    # Calculate duration in days
                    created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    closed_date = datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
                    duration = (closed_date - created_date).total_seconds() / (3600 * 24)
                    closed_issue_durations.append(duration)

            # Fetch comments for the issue
            comments = get_issue_comments(owner, repo_name, issue_number, headers)

            # Analyze participants
            for comment in comments:
                commenter = comment.get('user', {})
                commenter_login = commenter.get('login')

                if commenter_login and commenter_login != owner:
                    # Fetch commenter details
                    user_url = commenter.get('url')
                    try:
                        user_data, _ = github_api_request(user_url, headers)
                    except Exception as e:
                        logger.warning(f"Could not retrieve data for commenter: {commenter_login} - {e}")
                        continue
                    if user_data:
                        email = user_data.get('email', '')
                        company = user_data.get('company', '')

                        # Check if external
                        if (university_email_domain.lower() not in (email or '').lower() and
                            not contains_keywords(company or '', {university_name.lower()})):
                            issue_analysis['external_participants'].add(commenter_login)

            # Analyze issue content for collaboration opportunities
            if comments and len(comments) > 5:
                issue_analysis['collaboration_opportunities'].append({
                    'issue_number': issue_number,
                    'title': issue.get('title'),
                    'comments_count': len(comments)
                })

            pbar.update(1)  # Update the issues progress bar

    # Calculate average time to close issues
    if closed_issue_durations:
        issue_analysis['average_time_to_close'] = sum(closed_issue_durations) / len(closed_issue_durations)

    # Calculate issue update frequency
    issue_dates.sort()
    if len(issue_dates) > 1:
        date_differences = []
        for i in range(1, len(issue_dates)):
            date1 = datetime.strptime(issue_dates[i - 1], "%Y-%m-%dT%H:%M:%SZ")
            date2 = datetime.strptime(issue_dates[i], "%Y-%m-%dT%H:%M:%SZ")
            difference = (date2 - date1).total_seconds() / (3600 * 24)
            date_differences.append(difference)
        issue_analysis['issue_update_frequency'] = sum(date_differences) / len(date_differences)

    # Convert set to list for serialization
    issue_analysis['external_participants'] = list(issue_analysis['external_participants'])

    return issue_analysis

def get_release_downloads(owner, repo_name, headers):
    """
    Retrieves total download counts for all releases of a repository.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.

    Returns:
        int: Total number of downloads.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/releases"
    releases = []
    while url:
        logger.debug(f"Fetching releases for repository: {owner}/{repo_name}")
        try:
            releases_data, headers_response = github_api_request(url, headers)
        except Exception as e:
            logger.error(f"Error fetching release downloads: {e}")
            break
        if releases_data:
            releases.extend(releases_data)
            next_url = get_next_link(headers_response)
            url = next_url
        else:
            break
    total_downloads = 0
    if releases:
        for release in releases:
            assets = release.get('assets', [])
            for asset in assets:
                download_count = asset.get('download_count', 0)
                total_downloads += download_count
    return total_downloads

def get_repository_releases(owner, repo_name, headers, since=None):
    """
    Retrieves the list of releases for a repository.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.
        since (str, optional): Only releases published at or after this time are returned.

    Returns:
        list: A list of releases.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/releases"
    releases = []
    while url:
        logger.debug(f"Fetching releases for repository: {owner}/{repo_name}")
        try:
            releases_data, headers_response = github_api_request(url, headers)
        except Exception as e:
            logger.error(f"Error fetching releases: {e}")
            break
        if releases_data:
            if since:
                releases_data = [
                    release for release in releases_data
                    if release.get('published_at') and release['published_at'] >= since
                ]
            releases.extend(releases_data)
            next_url = get_next_link(headers_response)
            url = next_url
        else:
            break
    return releases

def get_commits(owner, repo_name, headers, since=None):
    """
    Retrieves commits for a repository.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.
        since (str, optional): Only commits after this date will be returned.

    Returns:
        list: A list of commits.
    """
    commits = []
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits"
    params = {'per_page': 100}
    if since:
        params['since'] = since
    while url:
        logger.debug(f"Fetching commits for repository: {owner}/{repo_name}")
        try:
            commits_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching commits: {e}")
            break
        if commits_data:
            commits.extend(commits_data)
            next_url = get_next_link(headers_response)
            url = next_url
            params = None
        else:
            break
    return commits

def get_repository_pull_requests(owner, repo_name, headers, since=None):
    """
    Retrieves pull requests for a repository.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.
        since (str, optional): Only pull requests updated at or after this time are returned.

    Returns:
        list: A list of pull requests.
    """
    pull_requests = []
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls"
    params = {'state': 'all', 'per_page': 100}
    if since:
        params['since'] = since
    while url:
        logger.debug(f"Fetching pull requests for repository: {owner}/{repo_name}")
        try:
            pr_data, headers_response = github_api_request(url, headers, params)
        except Exception as e:
            logger.error(f"Error fetching pull requests: {e}")
            break
        if pr_data:
            pull_requests.extend(pr_data)
            next_url = get_next_link(headers_response)
            url = next_url
            params = None
        else:
            break
    return pull_requests

def get_active_contributors(commits):
    """
    Retrieves active contributors from the list of commits.

    Args:
        commits (list): List of commits.

    Returns:
        set: A set of contributor usernames.
    """
    contributors = set()
    for commit in commits:
        author = commit.get('author')
        if author and author.get('login'):
            contributors.add(author['login'])
    return contributors

def calculate_average_time_to_close_issues(issues):
    """
    Calculates the average time to close issues.

    Args:
        issues (list): List of issues.

    Returns:
        float or None: Average time to close issues in hours, or None if not applicable.
    """
    closed_durations = []
    for issue in issues:
        if issue['state'] == 'closed':
            created_at = datetime.strptime(issue['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            closed_at = datetime.strptime(issue['closed_at'], "%Y-%m-%dT%H:%M:%SZ")
            duration = (closed_at - created_at).total_seconds() / 3600  # Duration in hours
            closed_durations.append(duration)
    if closed_durations:
        return sum(closed_durations) / len(closed_durations)
    else:
        return None

def calculate_average_time_to_merge_prs(pull_requests):
    """
    Calculates the average time to merge pull requests.

    Args:
        pull_requests (list): List of pull requests.

    Returns:
        float or None: Average time to merge pull requests in hours, or None if not applicable.
    """
    merged_durations = []
    for pr in pull_requests:
        if pr.get('merged_at'):
            created_at = datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            merged_at = datetime.strptime(pr['merged_at'], "%Y-%m-%dT%H:%M:%SZ")
            duration = (merged_at - created_at).total_seconds() / 3600  # Duration in hours
            merged_durations.append(duration)
    if merged_durations:
        return sum(merged_durations) / len(merged_durations)
    else:
        return None

def get_discussion_activity_count(owner, repo_name, headers, since_date):
    """
    Counts comments on issues and pull requests within the time window.

    Args:
        owner (str): Owner of the repository.
        repo_name (str): Name of the repository.
        headers (dict): HTTP headers for the request.
        since_date (str): Start date for counting activity.

    Returns:
        int: Total number of comments.
    """
    # Count comments on issues
    issues_comments_count = 0
    issues = get_repository_issues(owner, repo_name, headers, since=since_date)
    for issue in issues:
        comments = get_issue_comments(owner, repo_name, issue['number'], headers)
        issues_comments_count += len([comment for comment in comments if comment.get('created_at') >= since_date])

    # Count comments on pull requests
    prs_comments_count = 0
    pull_requests = get_repository_pull_requests(owner, repo_name, headers, since=since_date)
    for pr in pull_requests:
        comments = get_pull_request_comments(owner, repo_name, pr['number'], headers)
        prs_comments_count += len([comment for comment in comments if comment.get('created_at') >= since_date])

    total_comments = issues_comments_count + prs_comments_count
    return total_comments

def calculate_activity_score(metrics, weights):
    """
    Calculates the activity score based on metrics and weights.

    Args:
        metrics (dict): Dictionary of activity metrics.
        weights (dict): Dictionary of weights for each metric.

    Returns:
        float: The calculated activity score.
    """
    # Define max values for normalization (adjust these based on realistic expectations)
    max_values = {
        'recent_commits_count': 500,
        'active_contributors_count': 50,
        'recent_issues_opened_count': 100,
        'recent_issues_closed_count': 100,
        'avg_issue_close_time': 24,  # In hours, lower is better
        'recent_prs_opened_count': 100,
        'recent_prs_merged_count': 100,
        'avg_pr_merge_time': 24,     # In hours, lower is better
        'stars_growth': 1000,
        'forks_growth': 500,
        'recent_releases_count': 20,
        'total_downloads_recent': 10000,
        'discussion_activity_count': 500
    }

    # Normalize metrics
    normalized_scores = {}
    for metric, value in metrics.items():
        max_value = max_values.get(metric, 1)
        if value is None:
            normalized_score = 0
        else:
            if 'avg_' in metric:
                # For average times, lower is better
                normalized_score = max(0, (max_value - value) / max_value) * 100
            else:
                normalized_score = min(value / max_value, 1) * 100
        normalized_scores[metric] = normalized_score

    # Calculate weighted score
    activity_score = 0
    for metric, weight in weights.items():
        activity_score += normalized_scores.get(metric, 0) * weight

    # Ensure score is between 1 and 100
    activity_score = min(max(activity_score, 1), 100)
    return activity_score

def contains_university_identifier(text, university_identifiers):
    """
    Checks if the text contains any of the university identifiers.

    Args:
        text (str): Text to search within.
        university_identifiers (set): Set of university identifiers.

    Returns:
        bool: True if any identifier is found, False otherwise.
    """
    text = text.lower()
    for identifier in university_identifiers:
        if identifier.lower() in text:
            return True
    return False

def count_university_identifier_occurrences(text, university_identifiers, points_per_occurrence):
    """
    Counts the occurrences of university identifiers in the text and calculates points.

    Args:
        text (str): Text to search within.
        university_identifiers (set): Set of university identifiers.
        points_per_occurrence (dict): Points assigned per occurrence of each identifier.

    Returns:
        tuple: Total points and a dictionary of matches.
    """
    text = text.lower()
    points = 0
    matches = {}
    for identifier, points_value in points_per_occurrence.items():
        count = text.count(identifier.lower())
        if count > 0:
            matches[identifier] = count
            points += count * points_value
    return points, matches

def analyze_contributors_for_affiliation(contributors, university_details):
    """
    Analyzes contributors for affiliation with the university.

    Args:
        contributors (list): List of contributor details.
        university_details (dict): University details and identifiers.

    Returns:
        tuple: Total points and a dictionary of matches.
    """
    email_points = 0
    profile_points = 0
    other_repos_points = 0
    matches = {
        'email': {'contributors': [], 'points': 0},
        'profile': {'contributors': [], 'points': 0},
        'other_repos': {'contributors': [], 'points': 0}
    }
    for contributor in contributors:
        email = contributor.get('email') or ''
        bio = contributor.get('bio') or ''
        username = contributor.get('username')
        # Check email
        if university_details['email_domain'].lower() in email.lower():
            matches['email']['contributors'].append(username)
            email_points += 15
        # Check profile
        if contains_university_identifier(bio, university_details['identifiers']):
            matches['profile']['contributors'].append(username)
            profile_points += 10
        # Check other repositories
        associated_repos = contributor.get('repositories', [])
        if associated_repos:
            points = 5 * len(associated_repos)
            other_repos_points += points
            matches['other_repos']['contributors'].append({
                'username': username,
                'repo_count': len(associated_repos),
                'points': points
            })
    # Record points
    matches['email']['points'] = email_points
    matches['profile']['points'] = profile_points
    matches['other_repos']['points'] = other_repos_points
    total_points = email_points + profile_points + other_repos_points
    return total_points, matches

def analyze_owner_for_affiliation(owner_data, university_details):
    """
    Analyzes the repository owner (organization) for affiliation with the university.

    Args:
        owner_data (dict): Data about the repository owner.
        university_details (dict): University details and identifiers.

    Returns:
        tuple: Points, matches, and a boolean indicating if the owner is an organization.
    """
    points = 0
    matches = {}
    owner_type = owner_data.get('type', 'User')
    if owner_type == 'Organization':
        # Analyze organization details
        org_name = owner_data.get('name', '')
        org_description = owner_data.get('description', '')
        org_blog = owner_data.get('blog', '')
        org_email = owner_data.get('email', '')
        org_location = owner_data.get('location', '')
        # Ensure all items are strings
        text_to_check = ' '.join([
            org_name or '',
            org_description or '',
            org_blog or '',
            org_email or '',
            org_location or ''
        ]).lower()
        points_per_occurrence = {k: 30 for k in university_details['identifiers']}
        points, owner_matches = count_university_identifier_occurrences(
            text_to_check, university_details['identifiers'], points_per_occurrence
        )
        matches = owner_matches
    return points, matches, owner_type == 'Organization'

def analyze_repository(repo_info, university_details, keywords, university_email_domain, idx, headers, time_window, weights, hierarchical_keywords):
    """
    Analyzes a repository for various metrics and information.

    Args:
        repo_info (dict): Repository information.
        university_details (dict): University details and identifiers.
        keywords (set): Set of keywords to look for.
        university_email_domain (str): University's email domain.
        idx (int): Index number of the repository.
        headers (dict): HTTP headers for the request.
        time_window (int): Time window in months for activity metrics.
        weights (dict): Weights for activity score calculation.

    Returns:
        dict: A dictionary containing analyzed repository data.
    """
    repo = repo_info['repo_data']
    queries = repo_info['queries']
    repo_full_name = repo.get('full_name')
    owner = repo.get('owner', {}).get('login')
    repo_name = repo.get('name')
    description = repo.get('description') or ''
    topics = repo.get('topics', [])
    readme_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/readme"
    logger.info(f"Analyzing repository [{idx}]: {repo_full_name}")

    # Fetch README content
    try:
        readme_data, _ = github_api_request(readme_url, headers)
    except Exception as e:
        logger.warning(f"Could not retrieve README for {repo_full_name}: {e}")
        readme_data = None
    readme_content = ''
    if readme_data and readme_data.get('content'):
        readme_content = base64.b64decode(
            readme_data.get('content')
        ).decode('utf-8', errors='ignore')

    # Get list of files in the repository
    contents_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contents"
    try:
        contents, _ = github_api_request(contents_url, headers)
    except Exception as e:
        logger.warning(f"Could not retrieve contents for {repo_full_name}: {e}")
        contents = None
    files = []
    if contents and isinstance(contents, list):
        for content in contents:
            files.append(content.get('name', ''))

    # Determine project type
    project_type, project_type_scores, project_type_matches = determine_project_type(
        repo_name, description, topics, readme_content, files
    )

    # Check for scientific research usage
    is_scientific = contains_keywords(description + ' ' + readme_content, keywords)

    # Collect repository text for keyword matching
    repo_text = ' '.join([
        repo_name or '',
        description or '',
        ' '.join(topics) or '',
        readme_content or ''
    ])

    # Match repository text against hierarchical keywords
    hierarchical_scores, matched_keywords = match_repository_keywords(repo_text, hierarchical_keywords)

    # Determine the highest scores
    def get_highest_score(scores_dict):
        if scores_dict:
            return max(scores_dict.items(), key=lambda item: item[1])[0]
        else:
            return None

    domain = get_highest_score(hierarchical_scores['domains'])
    field = get_highest_score(hierarchical_scores['fields'])
    subfield = get_highest_score(hierarchical_scores['subfields'])
    topic = get_highest_score(hierarchical_scores['topics'])

    # Initialize total points and matches for confidence score
    total_points = 0
    matches = {
        'total_points': 0,
        'details': {}
    }

    # Define university identifiers
    university_identifiers = {
        university_details['name'].lower(),
        university_details['acronym'].lower(),
        university_details['email_domain'].lower(),
        university_details['website_url'].lower(),
    }

    # Points per occurrence
    points_per_occurrence = {
        identifier: value['points']
        for identifier, value in university_details['identifiers'].items()
    }

    # Check repository name and description
    repo_text_lower = (repo_name + ' ' + description).lower()
    points, repo_matches = count_university_identifier_occurrences(
        repo_text_lower, university_identifiers, points_per_occurrence
    )
    total_points += points
    matches['details']['repo_identifiers'] = {
        'matches': repo_matches,
        'points': points
    }

    # Check repository topics
    topics_text = ' '.join(topics).lower()
    points, topics_matches = count_university_identifier_occurrences(
        topics_text, university_identifiers, points_per_occurrence
    )
    total_points += points
    matches['details']['repo_topics'] = {
        'matches': topics_matches,
        'points': points
    }

    # Check README content
    readme_text = readme_content.lower()
    points, readme_matches = count_university_identifier_occurrences(
        readme_text, university_identifiers, points_per_occurrence
    )
    total_points += points
    matches['details']['readme'] = {
        'matches': readme_matches,
        'points': points
    }

    # Fetch repository owner data
    owner_url = repo['owner']['url']
    try:
        owner_data, _ = github_api_request(owner_url, headers)
    except Exception as e:
        logger.warning(f"Could not retrieve owner data for {repo_full_name}: {e}")
        owner_data = {}
    owner_type = owner_data.get('type', 'User')

    # Check if owner is affiliated organization
    owner_points = 0
    owner_affiliation_matches = {}
    is_owner_org = owner_type == 'Organization'
    if is_owner_org:
        points, owner_matches, _ = analyze_owner_for_affiliation(owner_data, university_details)
        owner_points += points
        total_points += owner_points
        matches['details']['owner_organization'] = {
            'matches': owner_matches,
            'points': points
        }
        # If owner is affiliated organization, assign high confidence
        if owner_points > 0:
            total_points += 500  # Assign high confidence
            matches['details']['repo_under_university_org'] = {
                'matched': True,
                'points': 500
            }
        else:
            matches['details']['repo_under_university_org'] = {
                'matched': False,
                'points': 0
            }
    else:
        # Owner is a user; check owner's profile
        owner_bio = (owner_data.get('bio') or '').lower()
        points, owner_matches = count_university_identifier_occurrences(
            owner_bio, university_identifiers, points_per_occurrence
        )
        total_points += points
        matches['details']['owner_profile'] = {
            'matches': owner_matches,
            'points': points
        }
        matches['details']['repo_under_university_org'] = {
            'matched': False,
            'points': 0
        }

    # Analyze contributors for affiliation
    contributors = get_contributors(owner, repo_name, headers)
    contributors_count = len(contributors)
    logger.debug(f"Number of contributors found: {contributors_count}")
    logger.debug(f"Analyzing contributors for repository: {repo_full_name}")
    contributor_details = analyze_contributors(contributors, university_email_domain, university_details['name'], keywords, headers)

    # Analyze contributors for confidence score
    contributor_points, contributor_matches = analyze_contributors_for_affiliation(contributor_details, university_details)
    total_points += contributor_points
    matches['details']['contributors'] = contributor_matches

    # Record total points
    matches['total_points'] = total_points

    # Normalize confidence score (using practical maximum of 500)
    confidence_score = min((total_points / 500) * 100, 100)

    # Get license
    license_info = repo.get('license') or {}
    license_name = license_info.get('name', 'No license')

    # Calculate 'since_date' based on the provided 'time_window'
    since_date = (datetime.now(timezone.utc) - timedelta(days=time_window * 30)).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Fetch all issues for total counts
    all_issues = get_repository_issues(owner, repo_name, headers)

    # Issue analysis using all issues
    issues_analysis = analyze_issues(all_issues, owner, repo_name, headers, university_email_domain, university_details['name'])

    # Exclude 'collaboration_opportunities' from output
    issues_analysis_output = issues_analysis.copy()
    issues_analysis_output.pop('collaboration_opportunities', None)

    # Fetch all pull requests for total counts
    all_pull_requests = get_repository_pull_requests(owner, repo_name, headers)

    # Pull Request analysis using all pull requests
    pr_analysis = analyze_pull_requests(all_pull_requests, owner, repo_name, headers)

    # Fetch recent issues for activity metrics
    recent_issues = get_repository_issues(owner, repo_name, headers, since=since_date)
    recent_issues_opened_count = len([issue for issue in recent_issues if issue.get('created_at') >= since_date])
    recent_issues_closed_count = len([issue for issue in recent_issues if issue.get('closed_at') and issue['closed_at'] >= since_date])
    avg_issue_close_time = calculate_average_time_to_close_issues(recent_issues)

    # Fetch recent commits
    recent_commits = get_commits(owner, repo_name, headers, since=since_date)
    recent_commits_count = len(recent_commits)

    # Fetch recent pull requests
    recent_pull_requests = get_repository_pull_requests(owner, repo_name, headers, since=since_date)
    recent_prs_opened_count = len([pr for pr in recent_pull_requests if pr.get('created_at') >= since_date])
    recent_prs_merged_count = len([pr for pr in recent_pull_requests if pr.get('merged_at') and pr['merged_at'] >= since_date])
    avg_pr_merge_time = calculate_average_time_to_merge_prs(recent_pull_requests)

    # Fetch active contributors
    active_contributors = get_active_contributors(recent_commits)
    active_contributors_count = len(active_contributors)

    # Fetch recent releases
    recent_releases = get_repository_releases(owner, repo_name, headers, since=since_date)
    recent_releases_count = len(recent_releases)
    total_downloads_recent = get_release_downloads(owner, repo_name, headers)

    # Collect discussion activity
    discussion_activity_count = get_discussion_activity_count(owner, repo_name, headers, since_date)

    # For stars and forks growth, GitHub API doesn't provide historical data
    stars_count = repo.get('stargazers_count', 0)
    forks_count = repo.get('forks_count', 0)
    # In absence of historical data, we'll set growth to current counts as a proxy
    stars_growth = stars_count
    forks_growth = forks_count

    # Prepare data for activity score calculation
    activity_metrics = {
        'recent_commits_count': recent_commits_count,
        'active_contributors_count': active_contributors_count,
        'recent_issues_opened_count': recent_issues_opened_count,
        'recent_issues_closed_count': recent_issues_closed_count,
        'avg_issue_close_time': avg_issue_close_time,
        'recent_prs_opened_count': recent_prs_opened_count,
        'recent_prs_merged_count': recent_prs_merged_count,
        'avg_pr_merge_time': avg_pr_merge_time,
        'stars_growth': stars_growth,
        'forks_growth': forks_growth,
        'recent_releases_count': recent_releases_count,
        'total_downloads_recent': total_downloads_recent,
        'discussion_activity_count': discussion_activity_count
    }

    # Calculate activity score
    activity_score = calculate_activity_score(activity_metrics, weights)

    # Last commit date
    last_commit_date = recent_commits[0]['commit']['committer']['date'] if recent_commits else 'No recent commits'

    # Check for documentation files
    has_readme = bool(readme_data)
    code_of_conduct_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/community/code_of_conduct"
    try:
        code_of_conduct, _ = github_api_request(code_of_conduct_url, headers)
    except Exception as e:
        logger.warning(f"Could not retrieve code of conduct for {repo_full_name}: {e}")
        code_of_conduct = None
    has_code_of_conduct = code_of_conduct is not None and 'url' in code_of_conduct
    files_to_check = ['citation.cff', 'CONTRIBUTING.md', 'GOVERNANCE.md', 'FUNDING.yml', 'funding.json']
    documentation = {file: False for file in files_to_check}
    if contents and isinstance(contents, list):
        for content in contents:
            if content['name'] in files_to_check:
                documentation[content['name']] = True

    # Lead institution
    affiliations = [c['affiliation'] for c in contributor_details if c['affiliation']]
    lead_institution = max(set(affiliations), key=affiliations.count) if affiliations else 'Unknown'

    # External impact
    external_contributors = [c for c in contributor_details if c['affiliation'] != university_details['name']]
    external_impact = len(external_contributors)

    # Calculate association score
    association_score = len(queries)

    # Fetch stars, forks, watchers
    watchers_count = repo.get('watchers_count', 0)
    open_issues_count = repo.get('open_issues_count', 0)

    # Fetch Languages
    languages_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/languages"
    try:
        languages_data, _ = github_api_request(languages_url, headers)
    except Exception as e:
        logger.warning(f"Could not retrieve languages for {repo_full_name}: {e}")
        languages_data = None
    if languages_data:
        total_bytes = sum(languages_data.values())
        languages_percentages = {
            language: (bytes_count / total_bytes * 100)
            for language, bytes_count in languages_data.items()
        }
        sorted_languages = sorted(
            languages_percentages.items(),
            key=lambda item: item[1],
            reverse=True
        )
        main_language = sorted_languages[0][0] if sorted_languages else 'Unknown'
    else:
        languages_data = {}
        languages_percentages = {}
        main_language = 'Unknown'

    # Collect data
    repo_data = {
        'repo_number': idx,
        'full_name': repo_full_name,
        'description': description,
        'project_type': project_type,
        'project_type_scores': project_type_scores,
        'project_type_matches': project_type_matches,
        'is_scientific': is_scientific,
        'license': license_name,
        'last_commit_date': last_commit_date,
        'has_readme': has_readme,
        'has_code_of_conduct': has_code_of_conduct,
        'documentation': documentation,
        'lead_institution': lead_institution,
        'external_impact': external_impact,
        'contributors': contributor_details,
        'queries': list(queries),
        'association_score': association_score,
        'confidence_score': confidence_score,
        'confidence_matches': matches,
        'issues_analysis': issues_analysis_output,
        'pr_analysis': pr_analysis,  # PR analysis data with its own progress bar
        'languages': languages_data,
        'main_language': main_language,
        'languages_percentages': languages_percentages,
        'stars_count': stars_count,
        'forks_count': forks_count,
        'watchers_count': watchers_count,
        'open_issues_count': open_issues_count,
        'total_downloads': total_downloads_recent,
        'contributors_count': contributors_count,
        'activity_metrics': activity_metrics,
        'activity_score': activity_score,
        'domain': domain,
        'field': field,
        'subfield': subfield,
        'topic': topic,
        'matched_keywords': matched_keywords,
        'hierarchical_scores': hierarchical_scores
    }
    logger.info(f"Repository analyzed: {repo_full_name} with confidence score {confidence_score:.2f} and activity score {activity_score:.2f}")
    return repo_data

def write_to_csv(all_repo_data, output_filename_csv):
    """
    Writes repository data to a CSV file with separate columns for documentation files.

    Args:
        all_repo_data (list): List of analyzed repository data.
        output_filename_csv (str): Output CSV file path.
    """
    # Define the headers for the CSV file
    headers = [
        'repo_number',
        'full_name',
        'description',
        'domain',
        'field',
        'subfield',
        'topic',
        'matched_keywords',
        'hierarchical_scores',
        'project_type',
        'project_type_scores',
        'project_type_matches',
        'is_scientific',
        'license',
        'last_commit_date',
        'has_readme',
        'has_code_of_conduct',
        'citation.cff',
        'CONTRIBUTING.md',
        'GOVERNANCE.md',
        'FUNDING.yml',
        'funding.json',
        'lead_institution',
        'external_impact',
        'contributors_count',
        'association_score',
        'confidence_score',
        'confidence_matches',
        'queries',
        'total_issues',
        'open_issues',
        'closed_issues',
        'average_time_to_close',
        'issue_update_frequency',
        'external_participants_count',
        'external_participants',
        'total_prs',
        'open_prs',
        'closed_prs',
        'average_time_to_merge',
        'pr_update_frequency',
        'average_time_to_first_review',
        'review_to_merge_percentage',
        'main_language',
        'languages_percentages',
        'stars_count',
        'forks_count',
        'watchers_count',
        'open_issues_count',
        'total_downloads',
        'activity_score',
        'recent_commits_count',
        'active_contributors_count',
        'recent_issues_opened_count',
        'recent_issues_closed_count',
        'avg_issue_close_time',
        'recent_prs_opened_count',
        'recent_prs_merged_count',
        'avg_pr_merge_time',
        'stars_growth',
        'forks_growth',
        'recent_releases_count',
        'total_downloads_recent',
        'discussion_activity_count'
    ]
    # Open the CSV file for writing
    with open(output_filename_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for repo_data in all_repo_data:
            # Prepare project type scores as a string
            project_type_scores_str = '; '.join(
                [f"{key}: {value}" for key, value in repo_data['project_type_scores'].items()]
            )
            # Prepare project type matches as a string
            project_type_matches_str = '; '.join(
                [f"{key}: {', '.join(value)}" for key, value in repo_data['project_type_matches'].items() if value]
            )
            # Extract issues analysis
            issues_analysis = repo_data['issues_analysis']
            # Extract pull request analysis
            pr_analysis = repo_data['pr_analysis']
            # Prepare languages_percentages as a string
            languages_percentages_str = '; '.join(
                [f"{language}: {percentage:.2f}%" for language, percentage in repo_data['languages_percentages'].items()]
            )
            # Prepare confidence matches as a string
            confidence_matches_str = json.dumps(repo_data['confidence_matches'])
            # Prepare hierarchical_scores as a string
            hierarchical_scores_str = json.dumps(repo_data['hierarchical_scores'])
            # Prepare the row data
            activity_metrics = repo_data.get('activity_metrics', {})
            # Extract documentation flags
            documentation = repo_data['documentation']
            row = {
                'repo_number': repo_data['repo_number'],
                'full_name': repo_data['full_name'],
                'description': repo_data['description'],
                'domain': repo_data.get('domain'),
                'field': repo_data.get('field'),
                'subfield': repo_data.get('subfield'),
                'topic': repo_data.get('topic'),
                'matched_keywords': '; '.join(repo_data.get('matched_keywords', [])),
                'hierarchical_scores': hierarchical_scores_str,
                'project_type': repo_data['project_type'],
                'project_type_scores': project_type_scores_str,
                'project_type_matches': project_type_matches_str,
                'is_scientific': repo_data['is_scientific'],
                'license': repo_data['license'],
                'last_commit_date': repo_data['last_commit_date'],
                'has_readme': repo_data['has_readme'],
                'has_code_of_conduct': repo_data['has_code_of_conduct'],
                # Include each documentation file as a separate column
                'citation.cff': documentation.get('citation.cff', False),
                'CONTRIBUTING.md': documentation.get('CONTRIBUTING.md', False),
                'GOVERNANCE.md': documentation.get('GOVERNANCE.md', False),
                'FUNDING.yml': documentation.get('FUNDING.yml', False),
                'funding.json': documentation.get('funding.json', False),
                'lead_institution': repo_data['lead_institution'],
                'external_impact': repo_data['external_impact'],
                'contributors_count': repo_data['contributors_count'],
                'association_score': repo_data['association_score'],
                'confidence_score': repo_data['confidence_score'],
                'confidence_matches': confidence_matches_str,
                'queries': '; '.join(repo_data['queries']),
                'total_issues': issues_analysis['total_issues'],
                'open_issues': issues_analysis['open_issues'],
                'closed_issues': issues_analysis['closed_issues'],
                'average_time_to_close': issues_analysis['average_time_to_close'],
                'issue_update_frequency': issues_analysis['issue_update_frequency'],
                'external_participants_count': len(issues_analysis['external_participants']),
                'external_participants': '; '.join(issues_analysis['external_participants']),
                'total_prs': pr_analysis['total_prs'],
                'open_prs': pr_analysis['open_prs'],
                'closed_prs': pr_analysis['closed_prs'],
                'average_time_to_merge': pr_analysis['average_time_to_merge'],
                'pr_update_frequency': pr_analysis['pr_update_frequency'],
                'average_time_to_first_review': pr_analysis.get('average_time_to_first_review'),
                'review_to_merge_percentage': pr_analysis.get('review_to_merge_percentage'),
                'main_language': repo_data['main_language'],
                'languages_percentages': languages_percentages_str,
                'stars_count': repo_data['stars_count'],
                'forks_count': repo_data['forks_count'],
                'watchers_count': repo_data['watchers_count'],
                'open_issues_count': repo_data['open_issues_count'],
                'total_downloads': repo_data['total_downloads'],
                'activity_score': repo_data.get('activity_score'),
                'recent_commits_count': activity_metrics.get('recent_commits_count'),
                'active_contributors_count': activity_metrics.get('active_contributors_count'),
                'recent_issues_opened_count': activity_metrics.get('recent_issues_opened_count'),
                'recent_issues_closed_count': activity_metrics.get('recent_issues_closed_count'),
                'avg_issue_close_time': activity_metrics.get('avg_issue_close_time'),
                'recent_prs_opened_count': activity_metrics.get('recent_prs_opened_count'),
                'recent_prs_merged_count': activity_metrics.get('recent_prs_merged_count'),
                'avg_pr_merge_time': activity_metrics.get('avg_pr_merge_time'),
                'stars_growth': activity_metrics.get('stars_growth'),
                'forks_growth': activity_metrics.get('forks_growth'),
                'recent_releases_count': activity_metrics.get('recent_releases_count'),
                'total_downloads_recent': activity_metrics.get('total_downloads_recent'),
                'discussion_activity_count': activity_metrics.get('discussion_activity_count')
            }
            writer.writerow(row)
    logger.info(f"CSV data written to {output_filename_csv}")

def convert_sets_to_lists(obj):
    """
    Recursively converts sets to lists in a data structure.

    Args:
        obj: The data structure to convert.

    Returns:
        The data structure with sets converted to lists.
    """
    if isinstance(obj, dict):
        return {k: convert_sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_sets_to_lists(element) for element in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj

def get_user_input(prompt):
    """
    Prompts the user for input and ensures it's not empty.

    Args:
        prompt (str): The prompt message.

    Returns:
        str: The user's input.
    """
    while True:
        user_input = input(prompt).strip()
        if user_input:
            return user_input
        else:
            print("Input cannot be empty. Please try again.")

def main():
    """
    Main function to execute the script logic.
    """
    start_time = time.time()

    # Parse command-line arguments (excluding --activity-metric)
    parser = argparse.ArgumentParser(description='University Repository Analysis Script')
    parser.add_argument('--limit', '-l', type=int, help='Limit processing to the first N repositories')
    args, unknown = parser.parse_known_args()

    # User input
    university_name = get_user_input("Enter the university name (e.g., 'University of California, Santa Cruz'): ")
    university_acronym = get_user_input("Enter the university acronym (e.g., 'UCSC'): ")
    university_email_domain = get_user_input("Enter the university email domain (e.g., 'ucsc.edu'): ")
    university_website_url = get_user_input("Enter the university website URL (e.g., 'ucsc.edu'): ")
    additional_queries = []
    while True:
        query = input("Enter an additional query (or 'n' to stop): ").strip()
        if query.lower() == 'n':
            break
        additional_queries.append(query)

    # Prompt for activity metric choice
    activity_metric_options = {
        '1': {'name': 'OSSci Activity Metric', 'key': 'default'},
        '2': {'name': 'Set your own', 'key': 'custom'},
    }

    print("\nChoose the activity metric:")
    for number, option in activity_metric_options.items():
        print(f"{number}. {option['name']}")

    while True:
        activity_metric_choice = get_user_input("Enter the number of your choice: ").strip()
        if activity_metric_choice in activity_metric_options:
            args.activity_metric = activity_metric_options[activity_metric_choice]['key']
            break
        else:
            print("Please enter a valid number from the options above.")

    # Assign to args.activity_metric
    args.activity_metric = activity_metric_choice

    # GitHub authentication
    load_dotenv()
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN not found in .env file. Please create a .env file with your GitHub token.")
        exit(1)
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Load keywords
    keywords = load_keywords('oaont.csv')

    # Load the hierarchical keyword dataset
    hierarchical_keywords = load_hierarchical_keywords('oaont.json')

    # Build query terms
    query_terms = [
        f'"{university_name}" in:name,description,readme',
        f'"{university_acronym}" in:name,description,readme',
        f'"{university_email_domain}" in:email'
    ] + additional_queries

    # Define the available metrics and their default weights
    available_metrics = {
        'recent_commits_count': {'name': 'Recent Commits Count', 'default_weight': 20},
        'active_contributors_count': {'name': 'Active Contributors Count', 'default_weight': 15},
        'recent_issues_opened_count': {'name': 'Recent Issues Opened Count', 'default_weight': 10},
        'recent_issues_closed_count': {'name': 'Recent Issues Closed Count', 'default_weight': 10},
        'avg_issue_close_time': {'name': 'Average Time to Close Issues', 'default_weight': 5},
        'recent_prs_opened_count': {'name': 'Recent PRs Opened Count', 'default_weight': 10},
        'recent_prs_merged_count': {'name': 'Recent PRs Merged Count', 'default_weight': 10},
        'avg_pr_merge_time': {'name': 'Average Time to Merge PRs', 'default_weight': 5},
        'stars_growth': {'name': 'Growth in Stars', 'default_weight': 5},
        'forks_growth': {'name': 'Growth in Forks', 'default_weight': 5},
        'recent_releases_count': {'name': 'Recent Releases Count', 'default_weight': 5},
        'total_downloads_recent': {'name': 'Total Downloads in Time Window', 'default_weight': 5},
        'discussion_activity_count': {'name': 'Discussion Activity Count (Comments on Issues and PRs)', 'default_weight': 0}
    }

    if args.activity_metric == '2':
        # Get custom time window
        while True:
            try:
                time_window = int(get_user_input("Enter the number of months to look back: "))
                if time_window > 0:
                    break
                else:
                    print("Time window must be a positive integer.")
            except ValueError:
                print("Please enter a valid integer.")

        # Initialize weights
        weights = {}
        total_percentage = 0

        # Display the list of metrics before assigning weights
        print("\nYou will be assigning weights to the following metrics:")
        for metric_key, metric_info in available_metrics.items():
            print(f"- {metric_info['name']}")

        print("\nPlease assign percentages to the following metrics. The total must sum up to 100%.")

        for metric_key, metric_info in available_metrics.items():
            remaining_percentage = 100 - total_percentage
            while True:
                try:
                    prompt_message = f"Enter percentage for {metric_info['name']} (remaining {remaining_percentage}%): "
                    percentage = float(get_user_input(prompt_message))
                    if 0 <= percentage <= remaining_percentage:
                        weights[metric_key] = percentage / 100  # Convert to decimal
                        total_percentage += percentage
                        break
                    else:
                        print(f"Please enter a value between 0 and {remaining_percentage}.")
                except ValueError:
                    print("Please enter a valid number.")

        if total_percentage != 100:
            print("Percentages do not sum up to 100%. Please run the script again and ensure the total sums to 100%.")
            exit(1)
    else:
        # Use default OSSci Activity Metric
        time_window = 6  # Default time window in months
        # Extract default weights and convert to decimals
        weights = {key: info['default_weight'] / 100 for key, info in available_metrics.items()}

    # Search repositories
    repositories = search_repositories_with_queries(query_terms, headers)
    logger.info(f"Total repositories found: {len(repositories)}")

    # Limit processing if --limit flag is set
    if args.limit:
        limit_count = args.limit
        logger.info(f"Limiting processing to the first {limit_count} repositories due to --limit flag.")
        # Convert repositories dictionary to a list of items and take the first N
        repositories_items = list(repositories.items())[:limit_count]
    else:
        repositories_items = list(repositories.items())

    # Define university details
    university_details = {
        'name': university_name,
        'acronym': university_acronym,
        'email_domain': university_email_domain,
        'website_url': university_website_url,
        'identifiers': {
            university_name.lower(): {'points': 20},
            university_acronym.lower(): {'points': 20},
            university_email_domain.lower(): {'points': 30},
            university_website_url.lower(): {'points': 20},
        }
    }

    # Analyze repositories with a progress bar
    all_repo_data = []
    total_repos = len(repositories_items)

    with tqdm(total=total_repos, desc='Analyzing Repositories', unit='repo', position=0) as pbar:
        for idx, (repo_id, repo_info) in enumerate(repositories_items, start=1):
            logger.info(f"Processing repository {idx}/{total_repos}: {repo_info['repo_data'].get('full_name', '')}")
            repo_data = analyze_repository(
                repo_info,
                university_details,
                keywords,
                university_email_domain,
                idx,
                headers,
                time_window,
                weights,
                hierarchical_keywords
            )
            all_repo_data.append(repo_data)
            pbar.update(1)

    # Convert all sets in all_repo_data to lists
    all_repo_data_serializable = convert_sets_to_lists(all_repo_data)

    # Output results
    output_filename_json = f"repository_data_{university_details['acronym']}.json"
    with open(output_filename_json, 'w', encoding='utf-8') as f:
        json.dump(all_repo_data_serializable, f, ensure_ascii=False, indent=4)
    logger.info(f"JSON data written to {output_filename_json}")

    # Write to CSV
    output_filename_csv = f"repository_data_{university_details['acronym']}.csv"
    write_to_csv(all_repo_data_serializable, output_filename_csv)

    # Print the output if limited
    if args.limit:
        print(json.dumps(all_repo_data_serializable, indent=4))

    end_time = time.time()
    total_runtime = end_time - start_time
    logger.info(f"Total runtime: {total_runtime:.2f} seconds")

if __name__ == "__main__":
    main()
