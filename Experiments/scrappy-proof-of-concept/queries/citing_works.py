from sqlalchemy.orm import joinedload
from db.database import get_db_session
from models.models import Repository, OpenAlexWork

def main(repo_id, doi_filter=None):
    with get_db_session() as session:
        repo = session.query(Repository).options(joinedload(Repository.dois)).filter_by(id=repo_id).first()
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
        print(f"\nInitiating Work: {work.title} (DB ID: {work.id})")
        print(f"It is cited by {len(work.citing_works)} work(s).\n")
        topics_count = {}
        subfields_count = {}
        fields_count = {}
        domains_count = {}
        for citing_work in work.citing_works:
            print(f"Citing Work: {citing_work.title} (DB ID: {citing_work.id})")
            if citing_work.topics:
                for topic in citing_work.topics:
                    topic_name = topic.display_name if topic.display_name else "N/A"
                    subfield_name = topic.subfield_display_name if topic.subfield_display_name else "N/A"
                    field_name = topic.field_display_name if topic.field_display_name else "N/A"
                    domain_name = topic.domain_display_name if topic.domain_display_name else "N/A"
                    print(f"  Topic: {topic_name}")
                    print(f"    Domain: {domain_name}")
                    print(f"    Field: {field_name}")
                    print(f"    Subfield: {subfield_name}")
                    topics_count[topic_name] = topics_count.get(topic_name, 0) + 1
                    subfields_count[subfield_name] = subfields_count.get(subfield_name, 0) + 1
                    fields_count[field_name] = fields_count.get(field_name, 0) + 1
                    domains_count[domain_name] = domains_count.get(domain_name, 0) + 1
            else:
                print("  Topics: None")
            print("-" * 40)
        print("\nAggregate Counts for Citing Works:")
        if topics_count:
            print("\nTopics:")
            for topic, count in sorted(topics_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {topic}: {count}")
        else:
            print("\nNo topics found.")
        if subfields_count:
            print("\nSubfields:")
            for subfield, count in sorted(subfields_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {subfield}: {count}")
        else:
            print("\nNo subfields found.")
        if fields_count:
            print("\nFields:")
            for field, count in sorted(fields_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {field}: {count}")
        else:
            print("\nNo fields found.")
        if domains_count:
            print("\nDomains:")
            for domain, count in sorted(domains_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {domain}: {count}")
        else:
            print("\nNo domains found.")
        print(f"It is cited by {len(work.citing_works)} work(s).\n")

if __name__ == '__main__':
    main()
