"""Service for managing job status persistence."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Job

logger = logging.getLogger(__name__)


class JobService:
    """Service for creating and updating job records."""
    
    @staticmethod
    def create_job(db: Session, user_id: str, document_url: str) -> Job:
        """
        Create a new job record with status 'queued'.
        
        Args:
            db: Database session
            user_id: User ID
            document_url: URL of the document to process
            
        Returns:
            Created Job instance
        """
        job = Job(
            user_id=user_id,
            document_url=document_url,
            status="queued"
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(f"Created job {job.id} for user {user_id}")
        return job
    
    @staticmethod
    def update_status(
        db: Session,
        job_id: str | UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[Job]:
        """
        Update job status.
        
        Args:
            db: Database session
            job_id: Job UUID
            status: New status value
            error_message: Optional error message (for failed status)
            
        Returns:
            Updated Job instance or None if not found
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found for status update")
            return None
        
        job.status = status
        
        # Set started_at on first status change from queued
        if job.started_at is None and status != "queued":
            job.started_at = datetime.now(timezone.utc)
        
        if error_message:
            job.error_message = error_message
        
        db.commit()
        db.refresh(job)
        
        logger.debug(f"Updated job {job_id} status to '{status}'")
        return job
    
    @staticmethod
    def complete_job(
        db: Session,
        job_id: str | UUID,
        document_id: Optional[UUID] = None,
        question_count: int = 0
    ) -> Optional[Job]:
        """
        Mark job as completed with results.
        
        Args:
            db: Database session
            job_id: Job UUID
            document_id: Created document UUID
            question_count: Number of questions extracted
            
        Returns:
            Updated Job instance or None if not found
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found for completion")
            return None
        
        job.status = "completed"
        job.document_id = document_id
        job.question_count = question_count
        job.completed_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(job)
        
        logger.info(f"Job {job_id} completed: document_id={document_id}, questions={question_count}")
        return job
    
    @staticmethod
    def fail_job(
        db: Session,
        job_id: str | UUID,
        error_message: str
    ) -> Optional[Job]:
        """
        Mark job as failed with error message.
        
        Args:
            db: Database session
            job_id: Job UUID
            error_message: Description of the failure
            
        Returns:
            Updated Job instance or None if not found
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found for failure update")
            return None
        
        job.status = "failed"
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(job)
        
        logger.error(f"Job {job_id} failed: {error_message}")
        return job
    
    @staticmethod
    def get_job(db: Session, job_id: str | UUID) -> Optional[Job]:
        """
        Get job by ID.
        
        Args:
            db: Database session
            job_id: Job UUID
            
        Returns:
            Job instance or None if not found
        """
        return db.query(Job).filter(Job.id == job_id).first()
    
    @staticmethod
    def get_jobs_by_user(
        db: Session,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> list[Job]:
        """
        Get jobs for a user, ordered by creation date (newest first).
        
        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            List of Job instances
        """
        return (
            db.query(Job)
            .filter(Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
