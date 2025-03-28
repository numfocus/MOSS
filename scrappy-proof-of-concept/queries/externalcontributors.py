from sqlalchemy import func
from models.models import User, Issue, IssueComment, PRReviewComment, PullRequest, Repository
from db.database import get_db_session
from sqlalchemy.orm import Session

def get_engaged_non_pr_users(session: Session, repo_id: int):
    repo = session.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        print(f"Repository with id {repo_id} not found.")
        return []
    engaged_users_subq = (
        session.query(User.id)
        .join(Issue, Issue.user_id == User.id)
        .filter(Issue.repository_id == repo_id)
        .union(
            session.query(User.id)
            .join(IssueComment, IssueComment.user_id == User.id)
            .join(Issue, IssueComment.issue_id == Issue.id)
            .filter(Issue.repository_id == repo_id)
        )
        .union(
            session.query(User.id)
            .join(PRReviewComment, PRReviewComment.user_id == User.id)
            .join(PullRequest, PRReviewComment.pr_id == PullRequest.id)
            .filter(PullRequest.repository_id == repo_id)
        )
    ).subquery()
    pr_authors_subq = (
        session.query(User.id)
        .join(PullRequest, PullRequest.user_id == User.id)
        .filter(PullRequest.repository_id == repo_id)
    ).subquery()
    users_never_pr = (
        session.query(User)
        .filter(User.id.in_(engaged_users_subq.select()))
        .filter(~User.id.in_(pr_authors_subq.select()))
        .all()
    )
    return users_never_pr

def main(repo_id):
    with get_db_session() as session:
        repo_obj = session.query(Repository).filter_by(id=repo_id).first()
        repo_name = repo_obj.full_name if repo_obj else str(repo_id)
        engaged_bystanders = get_engaged_non_pr_users(session, repo_id)
        print(f"Users who engaged but never opened a PR for repository: {repo_name}")
        for user in engaged_bystanders:
            issue_count = session.query(func.count(Issue.id)).filter(
                Issue.user_id == user.id,
                Issue.repository_id == repo_id
            ).scalar()
            issue_comment_count = (
                session.query(func.count(IssueComment.id))
                .join(Issue, IssueComment.issue_id == Issue.id)
                .filter(
                    IssueComment.user_id == user.id,
                    Issue.repository_id == repo_id
                )
                .scalar()
            )
            pr_review_count = (
                session.query(func.count(func.distinct(PRReviewComment.id)))
                .join(PullRequest, PRReviewComment.pr_id == PullRequest.id)
                .filter(
                    PRReviewComment.user_id == user.id,
                    PullRequest.repository_id == repo_id
                )
                .scalar()
            )
            org_info = user.company if user.company else user.type
            print(
                f"- {user.login} (User ID={user.id}), Issues={issue_count}, "
                f"Comments={issue_comment_count}, PRReviews={pr_review_count}, Org={org_info}"
            )

if __name__ == "__main__":
    print("This module is intended to be run from run_queries.py")
