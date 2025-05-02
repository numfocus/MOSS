# queries/acf_query.py (Improved version)
"""
User interface for applying Association Confidence Filters (ACFs) to 
discover repositories associated with an institution.
"""

import logging
import json
from datetime import datetime
from typing import List, Dict, Any

from db.database import get_db_session
from models.models import Repository, DiscoveryEvent, RepositoryInstitutionAnalysis
from services.acf_framework import (
    find_keyword_matches,
    get_repositories_from_keywords,
    get_available_filters,
    apply_filter
)

logger = logging.getLogger(__name__)

def check_existing_analysis_for_repos(repositories, institution_name):
    """
    Check if analysis results already exist for these repositories and this institution.
    Returns a summary of existing results.
    """
    results = {}
    repo_ids = [repo.id for repo in repositories]
    
    with get_db_session() as session:
        # Find analysis records for these repositories and this institution
        analyses = session.query(RepositoryInstitutionAnalysis).filter(
            RepositoryInstitutionAnalysis.repository_id.in_(repo_ids),
            RepositoryInstitutionAnalysis.institution_name == institution_name
        ).all()
        
        if not analyses:
            return None
        
        # Group by filter
        for analysis in analyses:
            filter_name = analysis.filter_name
            if filter_name not in results:
                results[filter_name] = {
                    "total": 0,
                    "high_confidence": 0,
                    "medium_confidence": 0,
                    "low_confidence": 0,
                    "last_run": analysis.created_at
                }
            
            # Update counts based on confidence score
            results[filter_name]["total"] += 1
            
            if analysis.confidence_score >= 0.7:
                results[filter_name]["high_confidence"] += 1
            elif analysis.confidence_score >= 0.4:
                results[filter_name]["medium_confidence"] += 1
            elif analysis.confidence_score > 0:
                results[filter_name]["low_confidence"] += 1
            
            # Update last run date if more recent
            if analysis.created_at > results[filter_name]["last_run"]:
                results[filter_name]["last_run"] = analysis.created_at
    
    return results

def display_evidence(evidence, filter_name):
    """Display evidence highlights based on filter type."""
    if filter_name == "Comprehensive Filter":
        display_comprehensive_evidence(evidence)
    elif filter_name == "Name Match Filter":
        if 'owner_name_match' in evidence:
            print(f"     - Owner name contains institution name: {evidence['owner_name_match']['match']}")
        if 'repo_name_match' in evidence:
            print(f"     - Repository name contains institution name: {evidence['repo_name_match']['match']}")
        if 'description_match' in evidence:
            print("     - Repository description mentions institution name")
        if 'topic_match' in evidence:
            print(f"     - Repository topic contains institution name: {evidence['topic_match']['match']}")
    elif filter_name == "Email Domain Filter":
        if 'matching_contributors' in evidence:
            print(f"     - {evidence['matching_contributors']} of {evidence['total_contributors']} contributors have institution email domains")
            if 'matching_logins' in evidence:
                print(f"     - Matching contributors include: {', '.join(evidence['matching_logins'])}")
    elif filter_name == "OpenAlex Affiliation Filter":
        if 'matching_works' in evidence:
            print(f"     - {evidence['matching_works']} of {evidence['total_works']} works linked to this repository have authors affiliated with the institution")
            if 'work_details' in evidence:
                for i, work in enumerate(evidence['work_details'], 1):
                    print(f"     - Paper {i}: {work['title']}")
                    print(f"       Authors: {', '.join(work['authors'])}")
    elif filter_name == "Combined Filter":
        if 'component_scores' in evidence:
            print("     - Combined from multiple filters:")
            for filter_name, score in evidence['component_scores'].items():
                print(f"       • {filter_name}: {score:.2f}")

def view_detailed_results_for_repos(repositories, institution_name):
    """
    Show detailed analysis results for specific repositories and institution.
    """
    repo_ids = [repo.id for repo in repositories]
    
    # Get available filters that have been used
    available_filters = {}
    
    with get_db_session() as session:
        filters = session.query(RepositoryInstitutionAnalysis.filter_name).filter(
            RepositoryInstitutionAnalysis.repository_id.in_(repo_ids),
            RepositoryInstitutionAnalysis.institution_name == institution_name
        ).distinct().all()
        
        for i, (filter_name,) in enumerate(filters, 1):
            available_filters[str(i)] = filter_name
    
    if not available_filters:
        print("No filters have been applied to these repositories for this institution.")
        return
    
    # Select filter
    print("\n=== Available Filters ===")
    for num, name in available_filters.items():
        print(f"{num}) {name}")
    
    selection = input("\nSelect a filter to view results (number): ").strip()
    if selection not in available_filters:
        print("Invalid selection.")
        return
    
    selected_filter = available_filters[selection]
    
    # Get minimum confidence threshold
    min_confidence = input("\nMinimum confidence threshold (0.0-1.0, default=0.3): ").strip() or "0.3"
    try:
        min_confidence = float(min_confidence)
        min_confidence = max(0.0, min(1.0, min_confidence))
    except ValueError:
        print("Invalid threshold, using default 0.3")
        min_confidence = 0.3
    
    # Query database for results
    with get_db_session() as session:
        analysis_results = session.query(
            RepositoryInstitutionAnalysis, 
            Repository
        ).join(
            Repository, 
            Repository.id == RepositoryInstitutionAnalysis.repository_id
        ).filter(
            RepositoryInstitutionAnalysis.repository_id.in_(repo_ids),
            RepositoryInstitutionAnalysis.institution_name == institution_name,
            RepositoryInstitutionAnalysis.filter_name == selected_filter,
            RepositoryInstitutionAnalysis.confidence_score >= min_confidence
        ).order_by(
            RepositoryInstitutionAnalysis.confidence_score.desc()
        ).all()
    
    # Display results
    if not analysis_results:
        print(f"\nNo repositories met the confidence threshold of {min_confidence}.")
        return
    
    print(f"\n=== Repositories Associated with {institution_name} ===")
    print(f"Found {len(analysis_results)} repositories with confidence ≥ {min_confidence}")
    print(f"Filter: {selected_filter}")
    
    # Display the results
    for i, (analysis, repo) in enumerate(analysis_results, 1):
        confidence_level = "HIGH" if analysis.confidence_score >= 0.7 else "MEDIUM" if analysis.confidence_score >= 0.4 else "LOW"
        
        print(f"\n{i}) {repo.full_name}")
        print(f"   Confidence: {analysis.confidence_score:.2f} ({confidence_level})")
        print(f"   URL: {repo.html_url}")
        print(f"   Description: {repo.description or 'None'}")
        
        # Display evidence highlights
        if analysis.evidence:
            try:
                evidence = json.loads(analysis.evidence)
                print("   Evidence:")
                display_evidence(evidence, selected_filter)
            except json.JSONDecodeError:
                print("   Evidence: Unable to parse evidence data")
    
    # Allow the user to select repositories for further analysis
    print("\nWould you like to analyze specific repositories?")
    analyze = input("Enter 'y' to select repositories for analysis: ").strip().lower()
    
    if analyze == 'y':
        selected_indices = input("Enter repository numbers to analyze (comma-separated): ").strip()
        try:
            indices = [int(idx.strip()) for idx in selected_indices.split(",") if idx.strip()]
            selected_repos = []
            
            for idx in indices:
                if 1 <= idx <= len(analysis_results):
                    selected_repos.append(analysis_results[idx-1][1])  # Get the Repository object
                else:
                    print(f"Invalid repository number: {idx}")
            
            if selected_repos:
                analyze_repositories(selected_repos)
        except ValueError:
            print("Invalid input. Please enter comma-separated numbers.")

def print_keyword_status(keywords: List[str]):
    """Print which keywords have been used before and when."""
    matches = find_keyword_matches(keywords)
    
    print("\n=== Keyword Status ===")
    print(f"You provided {len(keywords)} keywords.")
    
    if not matches:
        print("None of these keywords have been used for repository discovery yet.")
        return False
    
    print(f"{len(matches)} of these keywords have been used for repository discovery:")
    
    for keyword, stats in matches.items():
        last_run = stats['last_run'].strftime("%Y-%m-%d %H:%M:%S")
        repo_count = stats['repository_count']
        print(f"- '{keyword}': Last run on {last_run}, discovered {repo_count} repositories")
    
    return True

def display_comprehensive_evidence(evidence: Dict):
    """Format and display evidence from the Comprehensive Filter."""
    # Check for direct ownership (100% confidence)
    if 'direct_ownership' in evidence:
        ownership = evidence['direct_ownership']
        print(f"     ✓ DIRECT OWNERSHIP (100% confidence):")
        print(f"       Repository is owned by institutional GitHub organization: {ownership['owner']}")
        print(f"       This is a verified {ownership['owner_type']} of your institution")
        return
    
    # Check for core contributors (high confidence)
    if 'core_contributors' in evidence and evidence['core_contributors'].get('score', 0) >= 0.7:
        core_ev = evidence['core_contributors']
        print(f"     ✓ HIGH CONFIDENCE: Core Contributor Analysis ({core_ev['score']:.2f})")
        print(f"       {core_ev['matching_core_contributors']} of {core_ev['total_core_contributors']} core contributors are affiliated with your institution")
        
        if 'contributors' in core_ev and core_ev['contributors']:
            print("       Key contributors:")
            for contrib in core_ev['contributors'][:3]:
                matches = []
                if 'evidence' in contrib:
                    ev = contrib['evidence']
                    if ev.get('company_match'): matches.append("company")
                    if ev.get('location_match'): matches.append("location")
                    if ev.get('email_domain_match'): matches.append("email domain")
                
                print(f"         - {contrib['login']} (matches: {', '.join(matches)})")
            
            if len(core_ev['contributors']) > 3:
                print(f"         ...and {len(core_ev['contributors'])-3} more")
        return
        
    # Check for high confidence factors
    high_confidence_found = False
    
    if 'email_domains' in evidence and evidence['email_domains'].get('score', 0) >= 0.7:
        high_confidence_found = True
        email_ev = evidence['email_domains']
        print(f"     ✓ HIGH CONFIDENCE: Institutional Email Domains ({email_ev['score']:.2f})")
        print(f"       {email_ev['matching_count']} of {email_ev['total_contributors']} contributors have institutional email domains")
        if 'matching_examples' in email_ev and email_ev['matching_examples']:
            print(f"       Contributors include: {', '.join(email_ev['matching_examples'][:3])}")
            if len(email_ev['matching_examples']) > 3:
                print(f"       ...and {len(email_ev['matching_examples'])-3} more")
    
    if 'openalex_affiliations' in evidence and evidence['openalex_affiliations'].get('score', 0) >= 0.7:
        high_confidence_found = True
        openalex_ev = evidence['openalex_affiliations']
        print(f"     ✓ HIGH CONFIDENCE: OpenAlex Affiliations ({openalex_ev['score']:.2f})")
        print(f"       {openalex_ev['matching_works']} of {openalex_ev['total_works']} papers have authors affiliated with your institution")
        if 'matching_authors' in openalex_ev and openalex_ev['matching_authors']:
            print(f"       Authors include: {', '.join(openalex_ev['matching_authors'][:3])}")
            if len(openalex_ev['matching_authors']) > 3:
                print(f"       ...and {len(openalex_ev['matching_authors'])-3} more")
    
    if 'combined_high_confidence' in evidence:
        high_confidence_found = True
        combined = evidence['combined_high_confidence']
        print(f"     ✓ HIGH CONFIDENCE: Combined Factors ({combined['combined_score']:.2f})")
        
        if 'core_contributor_score' in combined:
            print(f"       Core Contributors: {combined['core_contributor_score']:.2f}")
            
        if 'email_score' in combined:
            print(f"       Email Domains: {combined['email_score']:.2f}")
            
        if 'openalex_score' in combined:
            print(f"       OpenAlex Affiliations: {combined['openalex_score']:.2f}")
    
    # Medium confidence factors
    if not high_confidence_found and 'naming_references' in evidence:
        naming_ev = evidence['naming_references']
        print(f"     ✓ MEDIUM CONFIDENCE: Name References ({naming_ev['score']:.2f})")
        
        if 'name_match' in naming_ev:
            print(f"       Repository name contains institution name: {naming_ev['name_match']['text']}")
        elif 'fullname_match' in naming_ev:
            print(f"       Repository full name contains institution name: {naming_ev['fullname_match']['text']}")
        if 'description_match' in naming_ev:
            print("       Repository description mentions institution name")
    
    # Lower confidence factors
    if 'topic_matches' in evidence:
        topics_ev = evidence['topic_matches']
        print(f"     ✓ LOWER CONFIDENCE: Topic Matches ({topics_ev['score']:.2f})")
        if 'matching_topics' in topics_ev:
            print(f"       Matching topics: {', '.join(topics_ev['matching_topics'])}")
    
    # Show other factors if they weren't already shown as high confidence
    if not high_confidence_found:
        if 'core_contributors' in evidence:
            core_ev = evidence['core_contributors']
            print(f"     ✓ Core Contributor Matches ({core_ev['score']:.2f})")
            print(f"       {core_ev['matching_core_contributors']} of {core_ev['total_core_contributors']} core contributors")
            
        if 'email_domains' in evidence:
            email_ev = evidence['email_domains']
            print(f"     ✓ Email Domain Matches ({email_ev['score']:.2f})")
            print(f"       {email_ev['matching_count']} of {email_ev['total_contributors']} contributors")
        
        if 'openalex_affiliations' in evidence:
            openalex_ev = evidence['openalex_affiliations']
            print(f"     ✓ OpenAlex Affiliations ({openalex_ev['score']:.2f})")
            print(f"       {openalex_ev['matching_works']} of {openalex_ev['total_works']} papers")
    
    # Multi-factor bonus
    if 'multi_factor_bonus' in evidence and evidence['multi_factor_bonus']:
        print("     ✓ Multiple confidence factors found (score bonus applied)")

def institutional_repository_discovery():
    """
    Interactive interface for discovering repositories associated with an institution
    using Association Confidence Filters.
    """
    print("\n=== Institutional Repository Discovery ===")
    print("This tool helps you find repositories associated with your institution.")
    
    # Step 1: Collect institution information
    institution_name = input("Institution name (e.g., 'Stanford University'): ").strip()
    if not institution_name:
        print("Institution name cannot be empty.")
        return
    
    institution_domains = input("Email domains (comma-separated, e.g., 'stanford.edu,cs.stanford.edu'): ").strip()
    domains = [d.strip() for d in institution_domains.split(",") if d.strip()]
    
    github_orgs = input("GitHub organization names (comma-separated, e.g., 'stanford,StanfordVL'): ").strip()
    org_list = [org.strip() for org in github_orgs.split(",") if org.strip()]
    
    # Step 2: Collect keywords associated with the institution
    print("\nEnter keywords associated with your institution (one per line).")
    print("These could include research areas, lab names, project identifiers, etc.")
    print("Press Enter on an empty line when finished.")
    
    keywords = []
    while True:
        keyword = input("> ").strip()
        if not keyword:
            break
        keywords.append(keyword)
    
    if not keywords:
        print("You must provide at least one keyword.")
        return
    
    # Step 3: Check which keywords have been used before
    keywords_exist = print_keyword_status(keywords)
    if not keywords_exist:
        print("\nYou need to first ingest repositories using these keywords.")
        print("Please use option 2 from the main menu to search for repositories.")
        return
    
    # Step 4: Get repositories discovered with these keywords
    repositories = get_repositories_from_keywords(keywords)
    if not repositories:
        print("\nNo repositories were found using these keywords.")
        return
    
    print(f"\nFound {len(repositories)} repositories discovered using these keywords.")
    
    # NEW: Check if these repositories have been analyzed for this institution
    existing_analysis = check_existing_analysis_for_repos(repositories, institution_name)
    
    if existing_analysis:
        print("\n=== Existing Analysis Results ===")
        print(f"Found existing analysis results for {institution_name} and these repositories:")
        
        for filter_name, stats in existing_analysis.items():
            last_run = stats["last_run"].strftime("%Y-%m-%d %H:%M:%S")
            print(f"\nFilter: {filter_name} (last run: {last_run})")
            print(f"  Total repositories analyzed: {stats['total']}")
            print(f"  High confidence (≥0.7): {stats['high_confidence']}")
            print(f"  Medium confidence (≥0.4): {stats['medium_confidence']}")
            print(f"  Low confidence (>0.0): {stats['low_confidence']}")
        
        # Ask if they want to view detailed results or run a new analysis
        choice = input("\nDo you want to [v]iew detailed results or [r]un a new analysis? (v/r) ").strip().lower()
        
        if choice == 'v':
            # View detailed results for a specific filter
            view_detailed_results_for_repos(repositories, institution_name)
            return
        # If 'r' or any other input, continue with new analysis
    
    # Step 5: Select and apply an Association Confidence Filter
    available_filters = get_available_filters()
    
    print("\n=== Available Association Confidence Filters ===")
    filter_names = list(available_filters.keys())
    for i, name in enumerate(filter_names, 1):
        filter_obj = available_filters[name]
        print(f"{i}) {name}")
        print(f"   {filter_obj.description}")
    
    try:
        selection = int(input("\nSelect a filter to apply (number): ").strip())
        if selection < 1 or selection > len(filter_names):
            print("Invalid selection.")
            return
        
        selected_filter = filter_names[selection - 1]
    except ValueError:
        print("Please enter a valid number.")
        return
    
    # Step 6: Apply the selected filter
    institution_info = {
        'name': institution_name,
        'domains': domains,
        'github_orgs': org_list
    }
    
    print(f"\nApplying {selected_filter} to {len(repositories)} repositories...")
    filtered_results = apply_filter(
        selected_filter, 
        repositories, 
        institution_info,
        store_results=True,
        keywords=keywords
    )
    
    if not filtered_results:
        print("\nNo repositories met the confidence threshold for association with your institution.")
        return
    
    # Step 7: Display the results
    min_confidence = input("\nMinimum confidence threshold (0.0-1.0, default=0.3): ").strip() or "0.3"
    try:
        min_confidence = float(min_confidence)
        min_confidence = max(0.0, min(1.0, min_confidence))
    except ValueError:
        print("Invalid threshold, using default 0.3")
        min_confidence = 0.3
    
    # Filter by confidence threshold
    high_confidence_results = [r for r in filtered_results if r[1] >= min_confidence]
    
    if not high_confidence_results:
        print(f"\nNo repositories met the confidence threshold of {min_confidence}.")
        return
    
    print(f"\n=== Repositories Associated with {institution_name} ===")
    print(f"Found {len(high_confidence_results)} repositories with confidence ≥ {min_confidence}")
    print(f"Analysis results have been stored in the database for historical tracking.")
    
    # Display the high confidence results
    for i, (repo, confidence, evidence) in enumerate(high_confidence_results, 1):
        confidence_level = "HIGH" if confidence >= 0.7 else "MEDIUM" if confidence >= 0.4 else "LOW"
        
        print(f"\n{i}) {repo.full_name}")
        print(f"   Confidence: {confidence:.2f} ({confidence_level})")
        print(f"   URL: {repo.html_url}")
        print(f"   Description: {repo.description or 'None'}")
        
        # Display evidence highlights based on filter type
        print("   Evidence:")
        display_evidence(evidence, selected_filter)
    
    # Step 8: Allow the user to select repositories for further analysis
    print("\nWould you like to analyze specific repositories?")
    analyze = input("Enter 'y' to select repositories for analysis: ").strip().lower()
    
    if analyze == 'y':
        selected_indices = input("Enter repository numbers to analyze (comma-separated): ").strip()
        try:
            indices = [int(idx.strip()) for idx in selected_indices.split(",") if idx.strip()]
            selected_repos = []
            
            for idx in indices:
                if 1 <= idx <= len(high_confidence_results):
                    selected_repos.append(high_confidence_results[idx-1][0])
                else:
                    print(f"Invalid repository number: {idx}")
            
            if selected_repos:
                analyze_repositories(selected_repos)
        except ValueError:
            print("Invalid input. Please enter comma-separated numbers.")

def analyze_repositories(repositories: List[Repository]):
    """Allow the user to run analysis queries on selected repositories."""
    if not repositories:
        return
    
    print(f"\n=== Repository Analysis ===")
    print(f"Selected {len(repositories)} repositories for analysis:")
    
    for i, repo in enumerate(repositories, 1):
        print(f"{i}) {repo.full_name}")
    
    print("\nWhat type of analysis would you like to perform?")
    print("1) Top contributors")
    print("2) External contributors analysis")
    print("3) Citation analysis (requires DOIs)")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == "1":
        for repo in repositories:
            print(f"\nAnalyzing top contributors for {repo.full_name}:")
            from queries import top10
            top10.main(repo.id)
    
    elif choice == "2":
        for repo in repositories:
            print(f"\nAnalyzing external contributors for {repo.full_name}:")
            from queries import externalcontributors
            externalcontributors.main(repo.id)
    
    elif choice == "3":
        for repo in repositories:
            if not repo.dois:
                print(f"\n{repo.full_name} has no associated DOIs, skipping citation analysis.")
                continue
                
            print(f"\nAnalyzing citations for {repo.full_name}:")
            from queries import top_topics
            top_topics.main(repo.id)

def main():
    institutional_repository_discovery()

if __name__ == "__main__":
    main()