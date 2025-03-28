from db.database import get_db_session
from models.models import OpenAlexWork, Repository

def main(repo_id, doi_filter=None):
    with get_db_session() as session:
        repo = session.query(Repository).filter_by(id=repo_id).first()
        if not repo:
            print("Repository not found.")
            return
        if doi_filter:
            selected_doi = doi_filter
        else:
            if repo.dois:
                selected_doi = repo.dois[0].doi
                print(f"No specific DOI selected; defaulting to first DOI: {selected_doi}")
            else:
                print("No DOIs found for this repository.")
                return
        work = session.query(OpenAlexWork).filter(OpenAlexWork.doi == selected_doi).first()
        if not work:
            print(f"No OpenAlex work found with DOI: {selected_doi}")
            return
        topic_counts = {}
        for citing_work in work.citing_works:
            if citing_work.topics:
                for topic in citing_work.topics:
                    topic_name = topic.display_name or "N/A"
                    topic_counts[topic_name] = topic_counts.get(topic_name, 0) + 1
        print(f"\nAggregate Top Topics for works citing the work with DOI: {selected_doi}")
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {topic}: {count}")

if __name__ == "__main__":
    print("This module is intended to be run from run_queries.py")
