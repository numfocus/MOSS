from sqlalchemy import func, select
from db.database import get_db_session
from models.models import DOI, OpenAlexWork, OpenAlexInstitution, OpenAlexAuthor, Repository
from models.models import openalex_author_institutions, openalex_work_authors

def main(repo_id, doi_filter=None):
    with get_db_session() as session:
        repository = session.query(Repository).filter_by(id=repo_id).first()
        if not repository:
            print(f"Repository with id {repo_id} not found in the database.")
            return
        repository_id = repository.id
        doi_subquery = session.query(DOI.doi).filter(DOI.repository_id == repository_id).subquery()
        institutions_query_with_doi = (
            session.query(
                OpenAlexInstitution.display_name,
                func.count(func.distinct(OpenAlexAuthor.id)).label("author_count")
            )
            .join(openalex_author_institutions, OpenAlexInstitution.id == openalex_author_institutions.c.institution_id)
            .join(OpenAlexAuthor, OpenAlexAuthor.id == openalex_author_institutions.c.author_id)
            .join(openalex_work_authors, OpenAlexAuthor.id == openalex_work_authors.c.author_id)
            .join(OpenAlexWork, OpenAlexWork.id == openalex_work_authors.c.work_id)
            .filter(
                func.replace(OpenAlexWork.doi, 'https://doi.org/', '').in_(select(doi_subquery.c.doi))
            )
            .group_by(OpenAlexInstitution.id)
            .all()
        )
        print("\n=== Institutions with Works Matching the Repository's DOIs ===")
        for institution_name, author_count in institutions_query_with_doi:
            print(f"Institution: {institution_name} — {author_count} distinct authors")

if __name__ == "__main__":
    print("This module is intended to be run from run_queries.py")
