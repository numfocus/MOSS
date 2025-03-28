# services/institution_analysis.py
"""
Core framework for institution analysis.
Manages the three phases: Surfacing, ACF, and Analysis.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

from sqlalchemy.orm import joinedload
from db.database import get_db_session
from models.models import (
    Repository, User, OpenAlexAuthor, AnalysisSession, SurfacingResult,
    SurfacedRepository, SurfacedPerson, ACFResult, ACFRepositoryResult,
    ACFPersonResult
)

logger = logging.getLogger(__name__)

class InstitutionAnalysisManager:
    """
    Manages the workflow for institutional analysis.
    
    This class handles the state transitions between the three phases:
    1. Surfacing phase - discovering repositories/people potentially associated with the institution
    2. ACF phase - applying confidence filters to rank the discoveries
    3. Analysis phase - analyzing the high-confidence matches
    """
    
    def __init__(self, institution_name: str, analysis_type: str = "repository"):
        """
        Initialize a new institution analysis session.
        
        Args:
            institution_name: Name of the institution
            analysis_type: Either "repository" or "people"
        """
        self.institution_name = institution_name
        self.analysis_type = analysis_type
        self.session_id = str(uuid.uuid4())
        self.current_phase = "initiated"
        self.institution_info = {
            "name": institution_name,
            "domains": [],
            "github_orgs": []
        }
        self.surfacing_id = None
        self.acf_id = None
        
        # Create a database record for this session
        with get_db_session() as session:
            new_session = AnalysisSession(
                session_id=self.session_id,
                institution_name=institution_name,
                analysis_type=analysis_type,
                status="initiated",
                parameters=json.dumps(self.institution_info)
            )
            session.add(new_session)
            session.commit()
            self.db_session_id = new_session.id
    
    def set_institution_info(self, domains: List[str] = None, github_orgs: List[str] = None):
        """
        Set additional institution information.
        
        Args:
            domains: List of email domains associated with the institution
            github_orgs: List of GitHub organizations associated with the institution
        """
        if domains:
            self.institution_info["domains"] = domains
        if github_orgs:
            self.institution_info["github_orgs"] = github_orgs
        
        # Update the session record
        with get_db_session() as session:
            db_session = session.query(AnalysisSession).filter_by(id=self.db_session_id).first()
            if db_session:
                db_session.parameters = json.dumps(self.institution_info)
                db_session.last_updated = datetime.now()
    
    def get_past_sessions(self) -> List[Dict]:
        """
        Get past analysis sessions for this institution.
        
        Returns:
            List of session records with summary information
        """
        with get_db_session() as session:
            past_sessions = session.query(AnalysisSession).filter(
                AnalysisSession.institution_name == self.institution_name,
                AnalysisSession.analysis_type == self.analysis_type
            ).order_by(
                AnalysisSession.last_updated.desc()
            ).all()
            
            results = []
            for session_record in past_sessions:
                surfacing_count = session.query(SurfacingResult).filter_by(
                    session_id=session_record.id
                ).count()
                
                acf_count = session.query(ACFResult).filter_by(
                    session_id=session_record.id
                ).count()
                
                results.append({
                    "id": session_record.id,
                    "session_id": session_record.session_id,
                    "created_at": session_record.created_at,
                    "last_updated": session_record.last_updated,
                    "status": session_record.status,
                    "surfacing_count": surfacing_count,
                    "acf_count": acf_count
                })
            
            return results
    
    def load_session(self, session_id: str) -> bool:
        """
        Load an existing session.
        
        Args:
            session_id: UUID of the session to load
            
        Returns:
            True if session was loaded successfully, False otherwise
        """
        with get_db_session() as session:
            existing = session.query(AnalysisSession).filter_by(
                session_id=session_id
            ).first()
            
            if not existing:
                logger.error(f"Session {session_id} not found")
                return False
            
            self.session_id = existing.session_id
            self.db_session_id = existing.id
            self.institution_name = existing.institution_name
            self.analysis_type = existing.analysis_type
            self.current_phase = existing.status
            
            try:
                self.institution_info = json.loads(existing.parameters)
            except (json.JSONDecodeError, TypeError):
                self.institution_info = {
                    "name": existing.institution_name,
                    "domains": [],
                    "github_orgs": []
                }
            
            # Find the most recent surfacing and ACF IDs
            latest_surfacing = session.query(SurfacingResult).filter_by(
                session_id=existing.id
            ).order_by(
                SurfacingResult.run_at.desc()
            ).first()
            
            if latest_surfacing:
                self.surfacing_id = latest_surfacing.id
            
            latest_acf = session.query(ACFResult).filter_by(
                session_id=existing.id
            ).order_by(
                ACFResult.run_at.desc()
            ).first()
            
            if latest_acf:
                self.acf_id = latest_acf.id
            
            return True
    
    def set_phase(self, phase: str):
        """
        Update the current phase of analysis.
        
        Args:
            phase: One of "initiated", "surfacing", "acf", "analysis", "completed"
        """
        valid_phases = ["initiated", "surfacing", "acf", "analysis", "completed"]
        if phase not in valid_phases:
            logger.error(f"Invalid phase: {phase}")
            return
        
        self.current_phase = phase
        
        with get_db_session() as session:
            db_session = session.query(AnalysisSession).filter_by(id=self.db_session_id).first()
            if db_session:
                db_session.status = phase
                db_session.last_updated = datetime.now()
    
    # More methods will be implemented in the next steps