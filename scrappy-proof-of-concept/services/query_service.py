# services/query_service.py
from db.database import get_db_session
from models.models import User, PullRequest, Repository, OpenAlexWork, OpenAlexInstitution, OpenAlexAuthor
from sqlalchemy import desc, func, select

def get_top_contributors(repo_id: int, limit: int = 10):
    with get_db_session() as session:
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

def get_institutions_with_doi(repo_id: int):
    with get_db_session() as session:
        repository = session.query(Repository).filter_by(id=repo_id).first()
        if not repository:
            raise ValueError(f"Repository with ID {repo_id} not found.")
        doi_list = [doi_obj.doi for doi_obj in repository.dois]
        institutions = (
            session.query(
                OpenAlexInstitution.display_name,
                func.count(func.distinct(OpenAlexAuthor.id)).label("author_count")
            )
            .join(OpenAlexAuthor, OpenAlexInstitution.authors)
            .join(OpenAlexWork, OpenAlexAuthor.works)
            .filter(OpenAlexWork.doi.in_(doi_list))
            .group_by(OpenAlexInstitution.id)
            .all()
        )
        return institutions
