# utils/common.py
import re
import json
from dateutil import parser
from datetime import datetime, timezone

def parse_github_url(url: str) -> tuple:
    """
    Extracts (owner, repo) from a GitHub URL.
    Example:
        "https://github.com/user/repo.git" -> ("user", "repo")
    """
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, url)
    if match:
        owner, repo = match.groups()
        # Remove .git suffix if present
        repo = repo.replace(".git", "")
        return owner, repo
    return None, None

def clean_doi(doi: str) -> str:
    """
    Clean DOI string by stripping whitespace and unwanted trailing characters.
    """
    return doi.strip().rstrip(").,;")

def extract_dois_from_text(text: str):
    """
    Extract all DOI strings from a given text.
    """
    pattern = r"10\.\d{4,9}/[-._;()/:A-Z0-9]+"
    return re.findall(pattern, text, flags=re.IGNORECASE)

def parse_datetime(dt_str: str):
    """
    Parse an ISO formatted datetime string.
    """
    if dt_str:
        try:
            return parser.isoparse(dt_str)
        except Exception:
            return None
    return None

def save_json_field(data):
    """
    Convert data to a JSON string if data is present.
    """
    return json.dumps(data) if data else None

def get_current_time():
    """
    Get current UTC time.
    """
    return datetime.now(timezone.utc)
