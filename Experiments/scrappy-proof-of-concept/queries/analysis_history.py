# queries/analysis_history.py
"""
Module for querying and displaying historical repository-institution analysis results.
"""

import json
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from db.database import get_db_session
from models.models import RepositoryInstitutionAnalysis, Repository

def format_datetime(dt):
    """Format a datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M")

def view_analysis_history(institution_name=None, days=30, min_score=0.0, limit=50):
    """
    Display historical analysis results for a specific institution or all institutions.
    
    Args:
        institution_name: Filter by institution name (None for all)
        days: Number of days to look back
        min_score: Minimum confidence score to include
        limit: Maximum number of results to show
    """
    with get_db_session() as session:
        # Build query
        query = session.query(
            RepositoryInstitutionAnalysis,
            Repository
        ).join(
            Repository,
            Repository.id == RepositoryInstitutionAnalysis.repository_id
        ).filter(
            RepositoryInstitutionAnalysis.confidence_score >= min_score
        )
        
        # Apply date filter
        if days > 0:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(RepositoryInstitutionAnalysis.created_at >= cutoff_date)
        
        # Apply institution filter if provided
        if institution_name:
            query = query.filter(RepositoryInstitutionAnalysis.institution_name == institution_name)
        
        # Get results ordered by most recent first
        results = query.order_by(
            desc(RepositoryInstitutionAnalysis.created_at)
        ).limit(limit).all()
        
        # Display results
        print(f"\n=== Repository-Institution Analysis History ===")
        if institution_name:
            print(f"Institution: {institution_name}")
        else:
            print("All Institutions")
        
        print(f"Time range: Past {days} days (minimum score: {min_score})")
        print(f"Found {len(results)} analysis results\n")
        
        for analysis, repo in results:
            score_color = "\033[92m" if analysis.confidence_score >= 0.7 else \
                         "\033[93m" if analysis.confidence_score >= 0.4 else "\033[0m"
            
            print(f"Date: {format_datetime(analysis.created_at)}")
            print(f"Repository: {repo.full_name}")
            print(f"Institution: {analysis.institution_name}")
            print(f"Filter: {analysis.filter_name}")
            print(f"Confidence: {score_color}{analysis.confidence_score:.2f}\033[0m")
            
            if analysis.keywords_used:
                print(f"Keywords: {analysis.keywords_used}")
            
            # Display comprehensive evidence summary
            if analysis.evidence:
                try:
                    evidence = json.loads(analysis.evidence)
                    print("Evidence Summary:")
                    
                    # Direct ownership (highest confidence)
                    if 'direct_ownership' in evidence:
                        owner_info = evidence['direct_ownership']
                        print(f"  - Direct ownership match (100% confidence): {owner_info.get('owner', 'Unknown')}")
                    
                    # Core contributors (high confidence)
                    if 'core_contributors' in evidence:
                        core_ev = evidence['core_contributors']
                        if 'matching_core_contributors' in core_ev and 'total_core_contributors' in core_ev:
                            print(f"  - Core contributors: {core_ev['matching_core_contributors']}/{core_ev['total_core_contributors']} repository maintainers")
                            if 'contributors' in core_ev and core_ev['contributors']:
                                print(f"    Top contributor: {core_ev['contributors'][0]['login']}")
                    
                    # Combined high confidence factors
                    if 'combined_high_confidence' in evidence:
                        combined = evidence['combined_high_confidence']
                        print("  - Multiple high-confidence factors combined:")
                        if 'core_contributor_score' in combined:
                            print(f"    • Core Contributors: {combined['core_contributor_score']:.2f}")
                        if 'email_score' in combined:
                            print(f"    • Email Domains: {combined['email_score']:.2f}")
                        if 'openalex_score' in combined:
                            print(f"    • OpenAlex Affiliations: {combined['openalex_score']:.2f}")
                    
                    # Email domains
                    if 'email_domains' in evidence:
                        email_ev = evidence['email_domains']
                        if 'matching_count' in email_ev and 'total_contributors' in email_ev:
                            print(f"  - Email domains: {email_ev['matching_count']}/{email_ev['total_contributors']} contributors")
                            if 'matching_examples' in email_ev and email_ev['matching_examples']:
                                examples = ', '.join(email_ev['matching_examples'][:2])
                                print(f"    Examples: {examples}")
                    
                    # OpenAlex affiliations
                    if 'openalex_affiliations' in evidence:
                        oa_ev = evidence['openalex_affiliations']
                        if 'matching_works' in oa_ev and 'total_works' in oa_ev:
                            print(f"  - OpenAlex affiliations: {oa_ev['matching_works']}/{oa_ev['total_works']} works")
                            if 'matching_authors' in oa_ev and oa_ev['matching_authors']:
                                authors = ', '.join(oa_ev['matching_authors'][:2])
                                print(f"    Authors: {authors}")
                    
                    # Name/description matches
                    if 'naming_references' in evidence:
                        naming_ev = evidence['naming_references']
                        print("  - Name/description matches:")
                        if 'name_match' in naming_ev:
                            print(f"    • Repository name: {naming_ev['name_match']['text']}")
                        elif 'fullname_match' in naming_ev:
                            print(f"    • Repository full name: {naming_ev['fullname_match']['text']}")
                        if 'description_match' in naming_ev:
                            print("    • Repository description contains institution name")
                    
                    # Topic matches
                    if 'topic_matches' in evidence:
                        topic_ev = evidence['topic_matches']
                        if 'matching_topics' in topic_ev:
                            topics = ', '.join(topic_ev['matching_topics'][:3])
                            print(f"  - Topic matches: {topics}")
                    
                    # Multi-factor bonus
                    if 'multi_factor_bonus' in evidence and evidence['multi_factor_bonus']:
                        print("  - Multiple confidence factors (score bonus applied)")
                        
                    # Check if no specific evidence was printed but we have a score
                    evidence_types = ['direct_ownership', 'core_contributors', 'combined_high_confidence', 
                                     'email_domains', 'openalex_affiliations', 'naming_references', 
                                     'topic_matches', 'multi_factor_bonus']
                    if not any(k in evidence for k in evidence_types):
                        print("  - Confidence score based on combination of repository attributes")
                        
                except json.JSONDecodeError:
                    print("  - Evidence data could not be parsed")
            
            print("-" * 60)

def view_institution_score_trends(institution_name, days=90, chart=False):
    """
    View trends in confidence scores for a specific institution over time.
    
    Args:
        institution_name: Name of the institution to analyze
        days: Number of days to look back
        chart: Whether to display a chart of trends (requires visualization libraries)
    """
    with get_db_session() as session:
        # Filter date range
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get average score per day
        daily_scores = session.query(
            func.date(RepositoryInstitutionAnalysis.created_at).label('date'),
            func.avg(RepositoryInstitutionAnalysis.confidence_score).label('avg_score'),
            func.count(RepositoryInstitutionAnalysis.id).label('count')
        ).filter(
            RepositoryInstitutionAnalysis.institution_name == institution_name,
            RepositoryInstitutionAnalysis.created_at >= cutoff_date
        ).group_by(
            func.date(RepositoryInstitutionAnalysis.created_at)
        ).order_by(
            'date'
        ).all()
        
        # Display results
        print(f"\n=== Confidence Score Trends for {institution_name} ===")
        print(f"Time range: Past {days} days")
        
        if not daily_scores:
            print("No analysis data found for this time period.")
            return
        
        print("\nDaily Average Confidence Scores:")
        for date, avg_score, count in daily_scores:
            print(f"{date}: {avg_score:.2f} (from {count} repositories)")
        
        # Calculate overall statistics
        avg_scores = [score for _, score, _ in daily_scores]
        if avg_scores:
            overall_avg = sum(avg_scores) / len(avg_scores)
            print(f"\nOverall average score: {overall_avg:.2f}")
            
            # Trend analysis
            if len(avg_scores) >= 2:
                first_week = avg_scores[:min(7, len(avg_scores))]
                last_week = avg_scores[-min(7, len(avg_scores)):]
                
                first_week_avg = sum(first_week) / len(first_week)
                last_week_avg = sum(last_week) / len(last_week)
                
                if last_week_avg > first_week_avg:
                    print(f"Trend: Improving (+{(last_week_avg - first_week_avg):.2f})")
                elif last_week_avg < first_week_avg:
                    print(f"Trend: Declining ({(last_week_avg - first_week_avg):.2f})")
                else:
                    print("Trend: Stable")

def main():
    """Interactive menu for analysis history queries."""
    print("\n=== Analysis History Queries ===")
    print("1) View recent analysis results")
    print("2) View analysis history for a specific institution")
    print("3) View institution confidence score trends")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == "1":
        days = input("Number of days to look back (default: 30): ").strip()
        days = int(days) if days.isdigit() else 30
        
        min_score = input("Minimum confidence score (0.0-1.0, default: 0.3): ").strip()
        try:
            min_score = float(min_score) if min_score else 0.3
            min_score = max(0.0, min(1.0, min_score))
        except ValueError:
            min_score = 0.3
        
        view_analysis_history(days=days, min_score=min_score)
    
    elif choice == "2":
        institution = input("Institution name: ").strip()
        if not institution:
            print("Institution name cannot be empty.")
            return
        
        days = input("Number of days to look back (default: 30): ").strip()
        days = int(days) if days.isdigit() else 30
        
        min_score = input("Minimum confidence score (0.0-1.0, default: 0.3): ").strip()
        try:
            min_score = float(min_score) if min_score else 0.3
            min_score = max(0.0, min(1.0, min_score))
        except ValueError:
            min_score = 0.3
        
        view_analysis_history(institution_name=institution, days=days, min_score=min_score)
    
    elif choice == "3":
        institution = input("Institution name: ").strip()
        if not institution:
            print("Institution name cannot be empty.")
            return
        
        days = input("Number of days to look back (default: 90): ").strip()
        days = int(days) if days.isdigit() else 90
        
        view_institution_score_trends(institution, days=days)
    
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()