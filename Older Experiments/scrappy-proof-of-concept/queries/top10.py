from sqlalchemy import desc, func
from models.models import User, PullRequest, Repository
from db.database import get_db_session

def top_merged_pr_contributors(session, repo_id, limit=10):
    results = (
        session.query(
            User.login.label("user_login"),
            func.count(PullRequest.id).label("merged_count")
        )
        .join(PullRequest, PullRequest.user_id == User.id)
        .filter(PullRequest.merged_at.isnot(None))
        .filter(PullRequest.repository_id == repo_id)
        .group_by(User.login)
        .order_by(desc("merged_count"))
        .limit(limit)
        .all()
    )
    return results

def main(repo_id):
    with get_db_session() as session:
        repo_obj = session.query(Repository).filter_by(id=repo_id).first()
        repo_name = repo_obj.full_name if repo_obj else str(repo_id)
        contributors = top_merged_pr_contributors(session, repo_id, limit=10)
        print(f"Top 10 contributors by merged PRs for repository: {repo_name}")
        for user_login, merged_count in contributors:
            print(f"{user_login}: {merged_count} merged PRs")

if __name__ == "__main__":
    print("This module is intended to be run from run_queries.py")
