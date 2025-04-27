from typing import Dict, Any
from github.NamedUser import NamedUser as GithubUser

def get_user_metadata(user: GithubUser) -> Dict[str, Any]:
    """
    Extracts metadata from a GitHub user object.

    Args:
        user: The GitHub user object.

    Returns:
        A dictionary containing the user's metadata.
    """
    return {
        "login": user.login,
        "id": user.id,
        "node_id": user.node_id,
        "avatar_url": user.avatar_url,
        "gravatar_id": user.gravatar_id,
        "url": user.url,
        "html_url": user.html_url,
        "followers_url": user.followers_url,
        "following_url": user.following_url,
        "gists_url": user.gists_url,
        "starred_url": user.starred_url,
        "subscriptions_url": user.subscriptions_url,
        "organizations_url": user.organizations_url,
        "repos_url": user.repos_url,
        "events_url": user.events_url,
        "received_events_url": user.received_events_url,
        "type": user.type,
        "site_admin": user.site_admin,
        "name": user.name,
        "company": user.company,
        "blog": user.blog,
        "location": user.location,
        "email": user.email,
        "hireable": user.hireable,
        "bio": user.bio,
        "twitter_username": user.twitter_username,
        "public_repos": user.public_repos,
        "public_gists": user.public_gists,
        "followers": user.followers,
        "following": user.following,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }
