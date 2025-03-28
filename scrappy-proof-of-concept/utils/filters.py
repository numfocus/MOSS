# filters.py
from models.models import Repository

def filter_has_doi(query):
    """
    Return repositories that have at least one associated DOI.
    Assumes the Repository model has a relationship named 'dois'.
    """
    return query.join(Repository.dois).distinct()

def filter_has_stars(query):
    """
    Return repositories that have at least one star.
    Assumes Repository.stargazers_count is populated.
    """
    return query.filter(Repository.stargazers_count > 0)

def filter_has_contributors(query):
    """
    Return repositories that have at least one contributor.
    Here we assume that having at least one pull request indicates contribution.
    (You might change this logic later.)
    """
    return query.join(Repository.pull_requests).distinct()

def filter_has_forks(query):
    """
    Return repositories that have at least one fork.
    """
    return query.filter(Repository.forks_count > 0)
