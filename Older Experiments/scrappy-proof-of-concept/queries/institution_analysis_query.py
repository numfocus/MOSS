# queries/institution_analysis_query.py
"""
Interactive interface for institution analysis.
Replaces the current acf_query.py implementation with a more comprehensive workflow.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

from services.institution_analysis import InstitutionAnalysisManager
from services.institution_analysis_impl.surfacing import (
    KeywordRepositorySurfacing, DomainRepositorySurfacing, NameRepositorySurfacing,
    DomainPeopleSurfacing, ProfilePeopleSurfacing, OpenAlexPeopleSurfacing
)
from services.institution_analysis_impl.person_acf import (
    EmailDomainPersonFilter, ProfilePersonFilter, OpenAlexPersonFilter,
    CombinedPersonFilter
)
from services.acf_framework import (
    get_available_filters, get_filter_by_name, apply_filter
)
from db.database import get_db_session
from models.models import (
    Repository, User, OpenAlexAuthor, AnalysisSession, SurfacingResult,
    SurfacedRepository, SurfacedPerson, ACFResult, ACFRepositoryResult,
    ACFPersonResult
)

logger = logging.getLogger(__name__)

def get_available_surfacing_algorithms(analysis_type: str = "repository") -> Dict[str, Any]:
    """
    Get available surfacing algorithms for the given analysis type.
    
    Args:
        analysis_type: Either "repository" or "people"
    
    Returns:
        Dictionary mapping algorithm keys to objects
    """
    if analysis_type == "repository":
        return {
            "1": KeywordRepositorySurfacing(),
            "2": DomainRepositorySurfacing(),
            "3": NameRepositorySurfacing()
        }
    else:  # people
        return {
            "1": DomainPeopleSurfacing(),
            "2": ProfilePeopleSurfacing(),
            "3": OpenAlexPeopleSurfacing()
        }

def get_available_person_filters() -> Dict[str, Any]:
    """
    Get available person ACF filters.
    
    Returns:
        Dictionary mapping filter keys to objects
    """
    return {
        "1": EmailDomainPersonFilter(),
        "2": ProfilePersonFilter(),
        "3": OpenAlexPersonFilter(),
        "4": CombinedPersonFilter()
    }

def print_institution_analysis_menu():
    """Print the main institution analysis menu."""
    print("\n=== Institution Analysis Menu ===")
    print("1) Repository Analysis")
    print("2) People Analysis")
    print("3) Return to Main Menu")

def collect_institution_info() -> Dict[str, Any]:
    """
    Collect institution information from the user.
    
    Returns:
        Dictionary with institution data
    """
    print("\n=== Institution Information ===")
    institution_name = input("Institution name (e.g., 'Stanford University'): ").strip()
    if not institution_name:
        print("Institution name cannot be empty.")
        return {}
    
    institution_domains = input("Email domains (comma-separated, e.g., 'stanford.edu,cs.stanford.edu'): ").strip()
    domains = [d.strip() for d in institution_domains.split(",") if d.strip()]
    
    github_orgs = input("GitHub organization names (comma-separated, e.g., 'stanford,StanfordVL'): ").strip()
    org_list = [org.strip() for org in github_orgs.split(",") if org.strip()]
    
    return {
        "name": institution_name,
        "domains": domains,
        "github_orgs": org_list
    }

def check_past_sessions(manager: InstitutionAnalysisManager) -> Optional[str]:
    """
    Check for past analysis sessions and allow the user to choose one.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        Session ID if a past session was chosen, None otherwise
    """
    past_sessions = manager.get_past_sessions()
    
    if not past_sessions:
        print("No past analyses found for this institution and analysis type.")
        return None
    
    print("\n=== Past Analyses ===")
    print(f"Found {len(past_sessions)} past analyses for {manager.institution_name}:")
    
    for i, session in enumerate(past_sessions, 1):
        status = session["status"].capitalize()
        date = session["last_updated"].strftime("%Y-%m-%d %H:%M")
        print(f"{i}) {date}: {status} (Surfacing: {session['surfacing_count']}, ACF: {session['acf_count']})")
    
    print("\nDo you want to:")
    print("1) Continue with a past analysis")
    print("2) Start a new analysis")
    
    choice = input("Enter your choice (1-2): ").strip()
    
    if choice == "1":
        session_idx = input("Select a past analysis (number): ").strip()
        try:
            idx = int(session_idx) - 1
            if 0 <= idx < len(past_sessions):
                return past_sessions[idx]["session_id"]
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")
    
    return None

def repository_surfacing_phase(manager: InstitutionAnalysisManager) -> bool:
    """
    Run the repository surfacing phase.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        True if surfacing was successful, False otherwise
    """
    print("\n=== Repository Surfacing Phase ===")
    manager.set_phase("surfacing")
    
    # Check for past surfacing runs
    with get_db_session() as session:
        past_runs = session.query(SurfacingResult).filter(
            SurfacingResult.session_id == manager.db_session_id
        ).order_by(
            SurfacingResult.run_at.desc()
        ).all()
    
    if past_runs:
        print("\nPast surfacing runs for this session:")
        for i, run in enumerate(past_runs, 1):
            algorithm = run.algorithm
            date = run.run_at.strftime("%Y-%m-%d %H:%M")
            count = run.result_count
            print(f"{i}) {algorithm} ({date}): {count} repositories found")
        
        print("\nDo you want to:")
        print("1) Use a past surfacing run")
        print("2) Run a new surfacing algorithm")
        
        choice = input("Enter your choice (1-2): ").strip()
        
        if choice == "1":
            run_idx = input("Select a surfacing run (number): ").strip()
            try:
                idx = int(run_idx) - 1
                if 0 <= idx < len(past_runs):
                    manager.surfacing_id = past_runs[idx].id
                    print(f"Using past surfacing run: {past_runs[idx].algorithm}")
                    return True
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
    
    # Get available surfacing algorithms
    algorithms = get_available_surfacing_algorithms("repository")
    
    print("\n=== Available Surfacing Algorithms ===")
    for key, algorithm in algorithms.items():
        print(f"{key}) {algorithm.name}: {algorithm.description}")
    
    choice = input("\nSelect a surfacing algorithm (number): ").strip()
    
    if choice in algorithms:
        algorithm = algorithms[choice]
        print(f"\nRunning {algorithm.name}...")
        
        # Collect algorithm-specific parameters
        parameters = {}
        
        if isinstance(algorithm, KeywordRepositorySurfacing):
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
                return False
            
            parameters["keywords"] = keywords
            
            github_token = input("\nEnter GitHub token for searching (optional): ").strip()
            if github_token:
                parameters["github_token"] = github_token
        
        # Run the algorithm
        try:
            surfacing_id = algorithm.run(
                manager.db_session_id,
                manager.institution_info,
                parameters
            )
            
            manager.surfacing_id = surfacing_id
            
            # Show results
            with get_db_session() as session:
                result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
                if result:
                    print(f"\nSurfacing complete. Found {result.result_count} repositories.")
                    return True
        except Exception as e:
            logger.error(f"Error during surfacing: {e}")
            print(f"Error during surfacing: {e}")
    else:
        print("Invalid selection.")
    
    return False

def repository_acf_phase(manager: InstitutionAnalysisManager) -> bool:
    """
    Run the repository ACF phase.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        True if ACF was successful, False otherwise
    """
    if not manager.surfacing_id:
        print("No surfacing results available. Please complete the surfacing phase first.")
        return False
    
    print("\n=== Repository ACF Phase ===")
    manager.set_phase("acf")
    
    # Check for past ACF runs
    with get_db_session() as session:
        past_runs = session.query(ACFResult).filter(
            ACFResult.session_id == manager.db_session_id
        ).order_by(
            ACFResult.run_at.desc()
        ).all()
    
    if past_runs:
        print("\nPast ACF runs for this session:")
        for i, run in enumerate(past_runs, 1):
            filter_name = run.filter_name
            date = run.run_at.strftime("%Y-%m-%d %H:%M")
            print(f"{i}) {filter_name} ({date})")
        
        print("\nDo you want to:")
        print("1) Use a past ACF run")
        print("2) Run a new ACF")
        
        choice = input("Enter your choice (1-2): ").strip()
        
        if choice == "1":
            run_idx = input("Select an ACF run (number): ").strip()
            try:
                idx = int(run_idx) - 1
                if 0 <= idx < len(past_runs):
                    manager.acf_id = past_runs[idx].id
                    print(f"Using past ACF run: {past_runs[idx].filter_name}")
                    return True
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
    
    # Get available ACF filters
    filters = get_available_filters()
    
    print("\n=== Available Association Confidence Filters ===")
    filter_names = list(filters.keys())
    for i, name in enumerate(filter_names, 1):
        filter_obj = filters[name]
        print(f"{i}) {name}")
        print(f"   {filter_obj.description}")
    
    try:
        selection = int(input("\nSelect a filter to apply (number): ").strip())
        if selection < 1 or selection > len(filter_names):
            print("Invalid selection.")
            return False
        
        selected_filter = filter_names[selection - 1]
    except ValueError:
        print("Please enter a valid number.")
        return False
    
    # Get repositories from surfacing
    with get_db_session() as session:
        surfaced_repos = session.query(SurfacedRepository).filter(
            SurfacedRepository.surfacing_id == manager.surfacing_id
        ).all()
        
        if not surfaced_repos:
            print("No repositories found from surfacing. Cannot apply ACF.")
            return False
        
        repo_ids = [sr.repository_id for sr in surfaced_repos]
        repositories = session.query(Repository).filter(
            Repository.id.in_(repo_ids)
        ).all()
    
    # Apply the selected filter
    print(f"\nApplying {selected_filter} to {len(repositories)} repositories...")
    try:
        # Create a new ACF result record
        with get_db_session() as session:
            acf_result = ACFResult(
                session_id=manager.db_session_id,
                surfacing_id=manager.surfacing_id,
                filter_name=selected_filter,
                run_at=datetime.now(),
                parameters=json.dumps(manager.institution_info)
            )
            session.add(acf_result)
            session.commit()
            acf_id = acf_result.id
        
        # Apply the filter
        filtered_results = apply_filter(
            selected_filter,
            repositories,
            manager.institution_info,
            store_results=False  # We'll store our own results
        )
        
        # Store the results
        with get_db_session() as session:
            for repo, confidence, evidence in filtered_results:
                result = ACFRepositoryResult(
                    acf_id=acf_id,
                    repository_id=repo.id,
                    confidence_score=confidence,
                    evidence=json.dumps(evidence)
                )
                session.add(result)
            
            # Update the ACF result summary
            acf_result = session.query(ACFResult).filter_by(id=acf_id).first()
            if acf_result:
                result_count = len(filtered_results)
                acf_result.result_summary = json.dumps({
                    "count": result_count,
                    "high_confidence": len([r for r, c, _ in filtered_results if c >= 0.7]),
                    "medium_confidence": len([r for r, c, _ in filtered_results if 0.4 <= c < 0.7]),
                    "low_confidence": len([r for r, c, _ in filtered_results if c < 0.4])
                })
        
        manager.acf_id = acf_id
        print(f"\nACF complete. Found {len(filtered_results)} repositories with confidence scores.")
        return True
    except Exception as e:
        logger.error(f"Error during ACF: {e}")
        print(f"Error during ACF: {e}")
    
    return False

def repository_analysis_phase(manager: InstitutionAnalysisManager) -> bool:
    """
    Run the repository analysis phase.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        True if analysis was successful, False otherwise
    """
    if not manager.acf_id:
        print("No ACF results available. Please complete the ACF phase first.")
        return False
    
    print("\n=== Repository Analysis Phase ===")
    manager.set_phase("analysis")
    
    # Get ACF results
    with get_db_session() as session:
        acf_results = session.query(ACFRepositoryResult).filter(
            ACFRepositoryResult.acf_id == manager.acf_id
        ).order_by(
            ACFRepositoryResult.confidence_score.desc()
        ).all()
        
        if not acf_results:
            print("No repository ACF results found. Cannot perform analysis.")
            return False
    
    # Ask for confidence threshold
    min_confidence = input("\nMinimum confidence threshold (0.0-1.0, default=0.5): ").strip() or "0.5"
    try:
        min_confidence = float(min_confidence)
        min_confidence = max(0.0, min(1.0, min_confidence))
    except ValueError:
        print("Invalid threshold, using default 0.5")
        min_confidence = 0.5
    
    # Filter by confidence threshold
    with get_db_session() as session:
        filtered_results = session.query(ACFRepositoryResult, Repository).join(
            Repository, Repository.id == ACFRepositoryResult.repository_id
        ).filter(
            ACFRepositoryResult.acf_id == manager.acf_id,
            ACFRepositoryResult.confidence_score >= min_confidence
        ).order_by(
            ACFRepositoryResult.confidence_score.desc()
        ).all()
        
        if not filtered_results:
            print(f"No repositories meet the confidence threshold of {min_confidence}.")
            return False
        
        # Display the results
        print(f"\n=== Repositories Associated with {manager.institution_name} ===")
        print(f"Found {len(filtered_results)} repositories with confidence ≥ {min_confidence}")
        
        for i, (result, repo) in enumerate(filtered_results, 1):
            confidence_level = "HIGH" if result.confidence_score >= 0.7 else "MEDIUM" if result.confidence_score >= 0.4 else "LOW"
            print(f"\n{i}) {repo.full_name}")
            print(f"   Confidence: {result.confidence_score:.2f} ({confidence_level})")
            print(f"   URL: {repo.html_url}")
            print(f"   Description: {repo.description or 'None'}")
            
            # Display evidence highlights
            if result.evidence:
                try:
                    evidence = json.loads(result.evidence)
                    print("   Evidence Highlights:")
                    display_evidence(evidence)
                except json.JSONDecodeError:
                    pass
    
    # Ask if the user wants to analyze specific repositories
    print("\nWould you like to analyze specific repositories?")
    analyze = input("Enter 'y' to select repositories for analysis: ").strip().lower()
    
    if analyze == 'y':
        selected_indices = input("Enter repository numbers to analyze (comma-separated): ").strip()
        try:
            indices = [int(idx.strip()) for idx in selected_indices.split(",") if idx.strip()]
            selected_repos = []
            
            for idx in indices:
                if 1 <= idx <= len(filtered_results):
                    selected_repos.append(filtered_results[idx-1][1])  # Get the Repository object
                else:
                    print(f"Invalid repository number: {idx}")
            
            if selected_repos:
                analyze_repositories(selected_repos)
                manager.set_phase("completed")
                return True
        except ValueError:
            print("Invalid input. Please enter comma-separated numbers.")
    
    manager.set_phase("completed")
    return True

def display_evidence(evidence: Dict):
    """
    Format and display evidence from ACF results.
    
    Args:
        evidence: Evidence dictionary from ACF
    """
    # Display direct ownership (highest confidence)
    if 'direct_ownership' in evidence:
        ownership = evidence['direct_ownership']
        print(f"     ✓ DIRECT OWNERSHIP: Repository is owned by {ownership.get('owner', 'Unknown')}")
        return
    
    # Display email domain matches
    if 'email_domains' in evidence and 'matching_count' in evidence['email_domains']:
        email_ev = evidence['email_domains']
        print(f"     ✓ Email domains: {email_ev['matching_count']}/{email_ev['total_contributors']} contributors")
        if 'matching_examples' in email_ev and email_ev['matching_examples']:
            print(f"       Examples: {', '.join(email_ev['matching_examples'][:3])}")
    
    # Display OpenAlex affiliations
    if 'openalex_affiliations' in evidence and 'matching_works' in evidence['openalex_affiliations']:
        oa_ev = evidence['openalex_affiliations']
        print(f"     ✓ OpenAlex: {oa_ev['matching_works']}/{oa_ev['total_works']} works")
        if 'matching_authors' in oa_ev and oa_ev['matching_authors']:
            print(f"       Authors: {', '.join(oa_ev['matching_authors'][:3])}")
    
    # Display name matches
    if 'naming_references' in evidence:
        naming_ev = evidence['naming_references']
        if 'name_match' in naming_ev:
            print(f"     ✓ Name match: {naming_ev['name_match']['text']}")
        elif 'fullname_match' in naming_ev:
            print(f"     ✓ Full name match: {naming_ev['fullname_match']['text']}")
        if 'description_match' in naming_ev:
            print("     ✓ Description mentions institution")
    
    # Display combined scores
    if 'component_scores' in evidence:
        print("     ✓ Combined from multiple factors:")
        for filter_name, score in evidence['component_scores'].items():
            print(f"       • {filter_name}: {score:.2f}")

def analyze_repositories(repositories: List[Repository]):
    """
    Run analysis queries on selected repositories.
    
    Args:
        repositories: List of Repository objects to analyze
    """
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

def people_surfacing_phase(manager: InstitutionAnalysisManager) -> bool:
    """
    Run the people surfacing phase.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        True if surfacing was successful, False otherwise
    """
    print("\n=== People Surfacing Phase ===")
    manager.set_phase("surfacing")
    
    # Check for past surfacing runs
    with get_db_session() as session:
        past_runs = session.query(SurfacingResult).filter(
            SurfacingResult.session_id == manager.db_session_id
        ).order_by(
            SurfacingResult.run_at.desc()
        ).all()
    
    if past_runs:
        print("\nPast surfacing runs for this session:")
        for i, run in enumerate(past_runs, 1):
            algorithm = run.algorithm
            date = run.run_at.strftime("%Y-%m-%d %H:%M")
            count = run.result_count
            print(f"{i}) {algorithm} ({date}): {count} people found")
        
        print("\nDo you want to:")
        print("1) Use a past surfacing run")
        print("2) Run a new surfacing algorithm")
        
        choice = input("Enter your choice (1-2): ").strip()
        
        if choice == "1":
            run_idx = input("Select a surfacing run (number): ").strip()
            try:
                idx = int(run_idx) - 1
                if 0 <= idx < len(past_runs):
                    manager.surfacing_id = past_runs[idx].id
                    print(f"Using past surfacing run: {past_runs[idx].algorithm}")
                    return True
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
    
    # Get available surfacing algorithms
    algorithms = get_available_surfacing_algorithms("people")
    
    print("\n=== Available Surfacing Algorithms ===")
    for key, algorithm in algorithms.items():
        print(f"{key}) {algorithm.name}: {algorithm.description}")
    
    choice = input("\nSelect a surfacing algorithm (number): ").strip()
    
    if choice in algorithms:
        algorithm = algorithms[choice]
        print(f"\nRunning {algorithm.name}...")
        
        # Collect algorithm-specific parameters
        parameters = {}
        
        # Run the algorithm
        try:
            surfacing_id = algorithm.run(
                manager.db_session_id,
                manager.institution_info,
                parameters
            )
            
            manager.surfacing_id = surfacing_id
            
            # Show results
            with get_db_session() as session:
                result = session.query(SurfacingResult).filter_by(id=surfacing_id).first()
                if result:
                    print(f"\nSurfacing complete. Found {result.result_count} people.")
                    return True
        except Exception as e:
            logger.error(f"Error during surfacing: {e}")
            print(f"Error during surfacing: {e}")
    else:
        print("Invalid selection.")
    
    return False

def people_acf_phase(manager: InstitutionAnalysisManager) -> bool:
    """
    Run the people ACF phase.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        True if ACF was successful, False otherwise
    """
    if not manager.surfacing_id:
        print("No surfacing results available. Please complete the surfacing phase first.")
        return False
    
    print("\n=== People ACF Phase ===")
    manager.set_phase("acf")
    
    # Check for past ACF runs
    with get_db_session() as session:
        past_runs = session.query(ACFResult).filter(
            ACFResult.session_id == manager.db_session_id
        ).order_by(
            ACFResult.run_at.desc()
        ).all()
    
    if past_runs:
        print("\nPast ACF runs for this session:")
        for i, run in enumerate(past_runs, 1):
            filter_name = run.filter_name
            date = run.run_at.strftime("%Y-%m-%d %H:%M")
            print(f"{i}) {filter_name} ({date})")
        
        print("\nDo you want to:")
        print("1) Use a past ACF run")
        print("2) Run a new ACF")
        
        choice = input("Enter your choice (1-2): ").strip()
        
        if choice == "1":
            run_idx = input("Select an ACF run (number): ").strip()
            try:
                idx = int(run_idx) - 1
                if 0 <= idx < len(past_runs):
                    manager.acf_id = past_runs[idx].id
                    print(f"Using past ACF run: {past_runs[idx].filter_name}")
                    return True
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
    
    # Get available person ACF filters
    filters = get_available_person_filters()
    
    print("\n=== Available Person Confidence Filters ===")
    for key, filter_obj in filters.items():
        print(f"{key}) {filter_obj.name}")
        print(f"   {filter_obj.description}")
    
    choice = input("\nSelect a filter to apply (number): ").strip()
    
    if choice in filters:
        filter_obj = filters[choice]
        print(f"\nApplying {filter_obj.name}...")
        
        # Get people from surfacing
        with get_db_session() as session:
            surfaced_people = session.query(SurfacedPerson).filter(
                SurfacedPerson.surfacing_id == manager.surfacing_id
            ).all()
            
            if not surfaced_people:
                print("No people found from surfacing. Cannot apply ACF.")
                return False
        
        # Create a new ACF result record
        with get_db_session() as session:
            acf_result = ACFResult(
                session_id=manager.db_session_id,
                surfacing_id=manager.surfacing_id,
                filter_name=filter_obj.name,
                run_at=datetime.now(),
                parameters=json.dumps(manager.institution_info)
            )
            session.add(acf_result)
            session.commit()
            acf_id = acf_result.id
        
        # Apply the filter to each person
        with get_db_session() as session:
            high_confidence = 0
            medium_confidence = 0
            low_confidence = 0
            
            for person in surfaced_people:
                confidence, evidence = filter_obj.calculate_confidence(person, manager.institution_info)
                
                if confidence > 0:
                    # Store the result
                    result = ACFPersonResult(
                        acf_id=acf_id,
                        surfaced_person_id=person.id,
                        confidence_score=confidence,
                        evidence=json.dumps(evidence)
                    )
                    session.add(result)
                    
                    # Count by confidence level
                    if confidence >= 0.7:
                        high_confidence += 1
                    elif confidence >= 0.4:
                        medium_confidence += 1
                    else:
                        low_confidence += 1
            
            # Update the ACF result summary
            acf_result = session.query(ACFResult).filter_by(id=acf_id).first()
            if acf_result:
                result_count = high_confidence + medium_confidence + low_confidence
                acf_result.result_summary = json.dumps({
                    "count": result_count,
                    "high_confidence": high_confidence,
                    "medium_confidence": medium_confidence,
                    "low_confidence": low_confidence
                })
        
        manager.acf_id = acf_id
        total_results = high_confidence + medium_confidence + low_confidence
        print(f"\nACF complete. Found {total_results} people with confidence scores.")
        print(f"  High confidence (≥0.7): {high_confidence}")
        print(f"  Medium confidence (≥0.4): {medium_confidence}")
        print(f"  Low confidence (>0.0): {low_confidence}")
        
        return True
    else:
        print("Invalid selection.")
    
    return False

def people_analysis_phase(manager: InstitutionAnalysisManager) -> bool:
    """
    Run the people analysis phase.
    
    Args:
        manager: The InstitutionAnalysisManager instance
        
    Returns:
        True if analysis was successful, False otherwise
    """
    if not manager.acf_id:
        print("No ACF results available. Please complete the ACF phase first.")
        return False
    
    print("\n=== People Analysis Phase ===")
    manager.set_phase("analysis")
    
    # Get ACF results
    with get_db_session() as session:
        acf_results = session.query(ACFPersonResult).filter(
            ACFPersonResult.acf_id == manager.acf_id
        ).order_by(
            ACFPersonResult.confidence_score.desc()
        ).all()
        
        if not acf_results:
            print("No person ACF results found. Cannot perform analysis.")
            return False
    
    # Ask for confidence threshold
    min_confidence = input("\nMinimum confidence threshold (0.0-1.0, default=0.5): ").strip() or "0.5"
    try:
        min_confidence = float(min_confidence)
        min_confidence = max(0.0, min(1.0, min_confidence))
    except ValueError:
        print("Invalid threshold, using default 0.5")
        min_confidence = 0.5
    
    # Filter by confidence threshold and collect person details
    with get_db_session() as session:
        filtered_results = session.query(
            ACFPersonResult, SurfacedPerson
        ).join(
            SurfacedPerson, SurfacedPerson.id == ACFPersonResult.surfaced_person_id
        ).filter(
            ACFPersonResult.acf_id == manager.acf_id,
            ACFPersonResult.confidence_score >= min_confidence
        ).order_by(
            ACFPersonResult.confidence_score.desc()
        ).all()
        
        if not filtered_results:
            print(f"No people meet the confidence threshold of {min_confidence}.")
            return False
        
        # Display the results
        print(f"\n=== People Associated with {manager.institution_name} ===")
        print(f"Found {len(filtered_results)} people with confidence ≥ {min_confidence}")
        
        for i, (result, person) in enumerate(filtered_results, 1):
            confidence_level = "HIGH" if result.confidence_score >= 0.7 else "MEDIUM" if result.confidence_score >= 0.4 else "LOW"
            
            # Get person details
            details = []
            if person.name:
                details.append(f"Name: {person.name}")
            if person.email:
                details.append(f"Email: {person.email}")
            
            # Get user or author details if available
            user = None
            author = None
            
            if person.user_id:
                user = session.query(User).filter_by(id=person.user_id).first()
                if user:
                    details.append(f"GitHub: {user.login}")
                    if user.company:
                        details.append(f"Company: {user.company}")
            
            if person.openalex_author_id:
                author = session.query(OpenAlexAuthor).filter_by(id=person.openalex_author_id).first()
                if author:
                    details.append(f"OpenAlex ID: {author.openalex_id}")
                    details.append(f"Works: {author.works_count or 'Unknown'}")
            
            print(f"\n{i}) {person.name or 'Unknown'}")
            print(f"   Confidence: {result.confidence_score:.2f} ({confidence_level})")
            for detail in details:
                print(f"   {detail}")
            
            # Display evidence highlights
            if result.evidence:
                try:
                    evidence = json.loads(result.evidence)
                    print("   Evidence Highlights:")
                    display_person_evidence(evidence)
                except json.JSONDecodeError:
                    pass
    
    # Future expansion: Add person-specific analysis options here
    
    manager.set_phase("completed")
    return True

def display_person_evidence(evidence: Dict):
    """
    Format and display evidence from Person ACF results.
    
    Args:
        evidence: Evidence dictionary from ACF
    """
    if 'email_match' in evidence:
        email_info = evidence['email_match']
        print(f"     ✓ Email domain match: {email_info['email']}")
    
    if 'subdomain_match' in evidence:
        subdomain_info = evidence['subdomain_match']
        print(f"     ✓ Subdomain match: {subdomain_info['user_domain']} (institution: {subdomain_info['institution_domain']})")
    
    if 'company_match' in evidence:
        company_info = evidence['company_match']
        print(f"     ✓ Company/organization match: {company_info.get('company', 'Institution mentioned')}")
    
    if 'bio_match' in evidence:
        bio_info = evidence['bio_match']
        print(f"     ✓ Bio mentions institution: {bio_info.get('bio_excerpt', '')}")
    
    if 'location_match' in evidence:
        location_info = evidence['location_match']
        print(f"     ✓ Location match: {location_info.get('location', '')}")
    
    if 'institution_affiliation' in evidence:
        affiliation = evidence['institution_affiliation']
        print(f"     ✓ OpenAlex institutional affiliation: {affiliation['institution']}")
    
    if 'coauthor_affiliations' in evidence:
        coauthor_info = evidence['coauthor_affiliations']
        if 'matching_works' in coauthor_info:
            print(f"     ✓ Co-authored with institution affiliates:")
            for i, work in enumerate(coauthor_info['matching_works'][:2], 1):
                print(f"       {i}. {work.get('title', 'Unknown')} ({work.get('year', 'Unknown')})")
    
    if 'component_scores' in evidence:
        print("     ✓ Combined from multiple factors:")
        for filter_name, score in evidence['component_scores'].items():
            print(f"       • {filter_name}: {score:.2f}")

def repository_analysis_workflow(manager: InstitutionAnalysisManager) -> None:
    """
    Run the complete repository analysis workflow.
    
    Args:
        manager: The InstitutionAnalysisManager instance
    """
    # Phase 1: Surfacing
    if manager.current_phase in ["initiated", "surfacing"]:
        if not repository_surfacing_phase(manager):
            print("Repository surfacing failed. Cannot continue.")
            return
    
    # Phase 2: ACF
    if manager.current_phase in ["surfacing", "acf"]:
        if not repository_acf_phase(manager):
            print("Repository ACF failed. Cannot continue.")
            return
    
    # Phase 3: Analysis
    if manager.current_phase in ["acf", "analysis"]:
        if not repository_analysis_phase(manager):
            print("Repository analysis failed.")
            return

def people_analysis_workflow(manager: InstitutionAnalysisManager) -> None:
    """
    Run the complete people analysis workflow.
    
    Args:
        manager: The InstitutionAnalysisManager instance
    """
    # Phase 1: Surfacing
    if manager.current_phase in ["initiated", "surfacing"]:
        if not people_surfacing_phase(manager):
            print("People surfacing failed. Cannot continue.")
            return
    
    # Phase 2: ACF
    if manager.current_phase in ["surfacing", "acf"]:
        if not people_acf_phase(manager):
            print("People ACF failed. Cannot continue.")
            return
    
    # Phase 3: Analysis
    if manager.current_phase in ["acf", "analysis"]:
        if not people_analysis_phase(manager):
            print("People analysis failed.")
            return

def institutional_repository_discovery():
    """Main entry point for the institution analysis interactive mode."""
    while True:
        print_institution_analysis_menu()
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "3":
            print("Returning to main menu.")
            return
        
        if choice not in ["1", "2"]:
            print("Invalid choice. Please try again.")
            continue
        
        analysis_type = "repository" if choice == "1" else "people"
        
        # Collect institution information
        institution_info = collect_institution_info()
        if not institution_info:
            continue
        
        # Initialize the analysis manager
        manager = InstitutionAnalysisManager(
            institution_name=institution_info["name"],
            analysis_type=analysis_type
        )
        
        # Set additional institution information
        manager.set_institution_info(
            domains=institution_info["domains"],
            github_orgs=institution_info["github_orgs"]
        )
        
        # Check for past sessions
        past_session_id = check_past_sessions(manager)
        if past_session_id:
            manager.load_session(past_session_id)
        
        # Run the appropriate workflow
        if analysis_type == "repository":
            repository_analysis_workflow(manager)
        else:  # people
            people_analysis_workflow(manager)

def main():
    institutional_repository_discovery()

if __name__ == "__main__":
    main()