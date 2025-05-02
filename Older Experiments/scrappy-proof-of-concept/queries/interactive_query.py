import sys
import logging
from sqlalchemy.orm import joinedload
from db.database import SessionLocal
from models.models import Repository
import re

# Set up logging with both file and stream handlers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("query_results.log"),
        logging.StreamHandler()
    ]
)

# Optional: Redirect stdout to logging so all prints are captured
class LoggerWriter:
    def __init__(self, level):
        self.level = level
    def write(self, message):
        message = message.strip()
        if message:
            self.level(message)
    def flush(self):
        pass

sys.stdout = LoggerWriter(logging.info)

def select_repository_custom():
    """
    Allow the user to iteratively apply filters to the repository list.
    The user may add filters one by one, undo the last filter, or reset all filters.
    """
    session = SessionLocal()
    base_query = session.query(Repository).options(joinedload(Repository.dois))
    current_query = base_query
    filter_stack = []  # Keep track of applied filters

    # Import available filter functions from utils/filters.py
    from utils.filters import filter_has_doi, filter_has_stars, filter_has_contributors, filter_has_forks
    available_filters = {
        "1": ("Has DOI", filter_has_doi),
        "2": ("Has Stars", filter_has_stars),
        "3": ("Has Contributor", filter_has_contributors),
        "4": ("Has Fork", filter_has_forks)
    }

    while True:
        repos = current_query.all()
        print("\nCurrent Repositories:")
        if repos:
            for i, repo in enumerate(repos, start=1):
                print(f"{i}) {repo.full_name}")
        else:
            print("No repositories match the current filters.")

        print("\nOptions:")
        print("A) Add a new filter")
        if filter_stack:
            print("B) Undo last filter")
        print("R) Reset all filters")
        print("S) Select a repository from the list")
        option = input("Enter your choice (A/B/R/S): ").strip().upper()

        if option == "A":
            print("\nAvailable Filters:")
            for key, (desc, _) in available_filters.items():
                print(f"{key}) {desc}")
            chosen = input("Enter the filter number to apply: ").strip()
            if chosen in available_filters:
                _, filter_func = available_filters[chosen]
                filter_stack.append((chosen, filter_func))
                current_query = filter_func(current_query)
            else:
                print("Invalid filter selection. Try again.")
        elif option == "B" and filter_stack:
            removed_filter = filter_stack.pop()
            print(f"Removed filter: {available_filters[removed_filter[0]][0]}")
            # Rebuild the current query from the base query using remaining filters.
            current_query = base_query
            for _, func in filter_stack:
                current_query = func(current_query)
        elif option == "R":
            filter_stack = []
            current_query = base_query
            print("All filters have been reset.")
        elif option == "S":
            if not repos:
                print("No repositories available to select. Please adjust filters.")
                continue
            try:
                selection = int(input("Enter the number of the repository: ").strip())
                if 1 <= selection <= len(repos):
                    selected_repo = repos[selection - 1]
                    print(f"Selected repository: {selected_repo.full_name}")
                    session.close()
                    return selected_repo
                else:
                    print("Invalid repository number. Try again.")
            except ValueError:
                print("Please enter a valid number.")
        else:
            print("Invalid option. Please try again.")

def select_doi(repository):
    """
    Allow the user to select a DOI from the repository's associated DOIs.
    If none are available, default to using all associated DOIs.
    """
    dois = repository.dois
    if not dois:
        print("No DOIs found for this repository. Defaulting to all associated DOIs.")
        return None
    print("\nSelect a DOI to analyze:")
    print("0) All Associated DOIs")
    for i, doi_obj in enumerate(dois, start=1):
        print(f"{i}) {doi_obj.doi} (Source: {doi_obj.source})")
    while True:
        choice = input("Enter the number of your choice: ").strip()
        try:
            idx = int(choice)
            if idx == 0:
                print("Selected: All Associated DOIs")
                return None
            elif 1 <= idx <= len(dois):
                selected_doi = dois[idx - 1].doi
                print(f"Selected DOI: {selected_doi}")
                return selected_doi
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

def print_query_menu():
    print("\nSelect a query to run:")
    print("1) Institutions with Works Matching the DOI (usage query)")
    print("2) Top 10 contributors by merged PRs (top10 query)")
    print("3) Engaged but Non-PR Users (external contributors query)")
    print("4) Top Topics of Works that Cite the DOI")
    print("5) Top Subfields of Works that Cite the DOI")
    print("6) Top Fields of Works that Cite the DOI")
    print("7) Top Domains of Works that Cite the DOI")
    print("8) Citing Works")
    print("0) Exit")

def interactive_query():
    repo = select_repository_custom()
    if not repo:
        sys.exit("No repository selected. Exiting.")
    selected_doi = select_doi(repo)
    repo_id = repo.id
    while True:
        print_query_menu()
        choice = input("Enter your choice: ").strip()
        if choice == "1":
            from queries import usage
            usage.main(repo_id, doi_filter=selected_doi)
        elif choice == "2":
            from queries import top10
            top10.main(repo_id)
        elif choice == "3":
            from queries import externalcontributors
            externalcontributors.main(repo_id)
        elif choice == "4":
            from queries import top_topics
            top_topics.main(repo_id, doi_filter=selected_doi)
        elif choice == "5":
            from queries import top_subfields
            top_subfields.main(repo_id, doi_filter=selected_doi)
        elif choice == "6":
            from queries import top_fields
            top_fields.main(repo_id, doi_filter=selected_doi)
        elif choice == "7":
            from queries import top_domains
            top_domains.main(repo_id, doi_filter=selected_doi)
        elif choice == "8":
            from queries import citing_works
            citing_works.main(repo_id, doi_filter=selected_doi)
        elif choice == "0":
            print("Exiting interactive query mode.")
            sys.exit(0)
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    interactive_query()
