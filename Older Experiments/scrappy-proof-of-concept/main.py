import sys
from config import GITHUB_TOKEN
from utils.logging_config import setup_logging
from db.database import init_db
from utils.common import parse_github_url
from services import ingestion_service, query_service
from datetime import datetime

setup_logging()

def main_menu():
    print("Welcome to the Unified GitHub & OpenAlex Data Application")
    while True:
        print("\nMain Menu:")
        print("1) Ingest a single repository")
        print("2) Search and ingest repositories by keyword")
        print("3) Run interactive query mode")
        print("4) Find repositories associated with your institution")
        print("5) View analysis history and trends")  # New option
        print("0) Exit")
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            # Capture pre-ingestion counts.
            pre_counts = ingestion_service.get_ingestion_counts()
            
            repo_url = input("Enter repository URL: ").strip()
            owner, repo_name = parse_github_url(repo_url)
            if not owner or not repo_name:
                print("Invalid repository URL provided.")
                continue
            
            # NEW: Check if repository already exists
            existing_repo = ingestion_service.check_repository_exists(owner, repo_name)
            if existing_repo:
                print(f"\nRepository '{existing_repo.full_name}' is already in the database.")
                print(f"Last ingested: {existing_repo.ingested_at}")
                
                # Show associated data counts
                doi_count = ingestion_service.get_repository_doi_counts(existing_repo.id)
                print(f"DOIs associated: {doi_count}")
                
                # Show discovery events
                events = ingestion_service.get_discovery_events(existing_repo.id)
                if events:
                    print(f"Discovery chain: {events[0].chain_id}")
                    print(f"Discovery method: {events[0].discovery_method}")
                    print(f"Original trigger: {events[0].url or events[0].keyword or 'Direct'}")
                
                # Ask if user wants to re-ingest
                reingest = input("\nDo you want to re-ingest this repository? (y/n): ").strip().lower()
                if reingest != 'y':
                    continue
            
            token = input("Enter GitHub token (or press Enter to use the default token): ").strip() or GITHUB_TOKEN
            try:
                # Pass the repository URL as trigger_input.
                repo = ingestion_service.ingest_repository(owner, repo_name, token, trigger_input=repo_url)
                print(f"Repository '{repo.full_name}' ingested successfully.")
            except Exception as e:
                print(f"Error ingesting repository: {e}")
                continue
            
            # Capture post-ingestion counts and output the summary.
            post_counts = ingestion_service.get_ingestion_counts()
            print(ingestion_service.print_ingestion_summary(pre_counts, post_counts))
        
        elif choice == "2":
            # Capture pre-ingestion counts.
            pre_counts = ingestion_service.get_ingestion_counts()
            
            keywords_input = input("Enter search keywords (comma-separated): ").strip()
            if not keywords_input:
                print("No keywords provided.")
                continue
            
            # NEW: Convert the input to a list of keywords
            keyword_list = [k.strip() for k in keywords_input.split(',') if k.strip()]
            
            # NEW: Check which keywords have been used before
            from services.acf_framework import find_keyword_matches
            keyword_matches = find_keyword_matches(keyword_list)
            
            # NEW: Display keyword status
            print("\n=== Keyword Status ===")
            
            used_keywords = []
            new_keywords = []
            
            for keyword in keyword_list:
                if keyword in keyword_matches:
                    used_keywords.append(keyword)
                else:
                    new_keywords.append(keyword)
            
            if new_keywords:
                print("New keywords:")
                for kw in new_keywords:
                    print(f"  - {kw}")
            
            if used_keywords:
                print("\nPreviously used keywords:")
                for kw in used_keywords:
                    stats = keyword_matches[kw]
                    last_run = stats['last_run'].strftime("%Y-%m-%d %H:%M")
                    repo_count = stats['repository_count']
                    print(f"  - {kw} (Last run: {last_run}, Repositories found: {repo_count})")
            
            # NEW: Option to remove already used keywords
            if used_keywords:
                remove_used = input("\nDo you want to remove already used keywords? (y/n): ").strip().lower()
                if remove_used == 'y':
                    keyword_list = new_keywords
                    print(f"Kept {len(keyword_list)} new keywords.")
            
            # NEW: Option to modify the keyword list
            modify = input("\nDo you want to modify the keyword list? (y/n): ").strip().lower()
            if modify == 'y':
                print("Enter keywords one per line. Empty line to finish.")
                modified_keywords = []
                while True:
                    keyword = input("> ").strip()
                    if not keyword:
                        break
                    modified_keywords.append(keyword)
                
                if modified_keywords:
                    keyword_list = modified_keywords
            
            # NEW: Confirm keyword list
            if not keyword_list:
                print("Keyword list is empty. Returning to main menu.")
                continue
            
            print("\n=== Final Keyword List ===")
            for i, kw in enumerate(keyword_list, 1):
                print(f"{i}. {kw}")
            
            confirm = input("\nProceed with these keywords? (y/n): ").strip().lower()
            if confirm != 'y':
                continue
            
            # Convert back to comma-separated string for existing function
            keywords = ','.join(keyword_list)
            
            token = input("Enter GitHub token (or press Enter to use the default token): ").strip() or GITHUB_TOKEN
            # Pass keywords as trigger_input.
            repos = ingestion_service.search_and_ingest_repositories(token, keywords, trigger_input=keywords)
            print(f"Ingested {len(repos)} repositories matching '{keywords}'.")
            
            # Capture post-ingestion counts and output the summary.
            post_counts = ingestion_service.get_ingestion_counts()
            print(ingestion_service.print_ingestion_summary(pre_counts, post_counts))
        
        elif choice == "3":
            # Launch the interactive query experience
            try:
                import queries.interactive_query as interactive_query 
                interactive_query.interactive_query()
            except Exception as e:
                print(f"Error running interactive query mode: {e}")
        
        elif choice == "4":
            # Launch the institutional repository discovery
            try:
                # Updated import to use the new implementation
                from queries.institution_analysis_query import institutional_repository_discovery
                institutional_repository_discovery()
            except Exception as e:
                print(f"Error running institutional repository discovery: {e}")
        
        elif choice == "5":
            # Launch the analysis history view
            try:
                from queries.analysis_history import main as analysis_history_main
                analysis_history_main()
            except Exception as e:
                print(f"Error viewing analysis history: {e}")
        
        elif choice == "0":
            print("Exiting.")
            sys.exit(0)
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    init_db()
    main_menu()