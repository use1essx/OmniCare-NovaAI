"""
Background Job Processor for Questionnaire Generation
Handles long-running generation tasks asynchronously
"""
import logging
import asyncio
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from src.database.models_multistage_questionnaire import AIGenerationJob, QuestionnaireAnalysis
from src.services.questionnaire_pipeline import MultiStageQuestionnairePipeline

logger = logging.getLogger(__name__)


class BackgroundJobProcessor:
    """Process questionnaire generation jobs asynchronously"""
    
    def __init__(self, db: Session):
        self.db = db
        self.active_jobs = {}  # job_id -> task
    
    async def start_job(
        self,
        document_text: str,
        target_question_count: int = 10,
        language: str = "en",
        purpose: str = "child-screening",
        generation_mode: str = "auto"
    ) -> UUID:
        """
        Start a new generation job
        Returns job_id for tracking
        """
        job_id = uuid4()
        
        # Create job record
        job = AIGenerationJob(
            job_id=job_id,
            status="queued",
            current_stage="Initializing",
            progress_percentage=0,
            started_at=datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()
        
        logger.info(f"🚀 Started job {job_id}")
        
        # Run pipeline in background
        task = asyncio.create_task(
            self._run_job(job_id, document_text, target_question_count, language, purpose, generation_mode)
        )
        self.active_jobs[job_id] = task
        
        return job_id
    
    async def _log_event(self, job_id: UUID, message: str, level: str = "info", db: Session = None):
        """Log an event to the job record"""
        try:
            timestamp = datetime.utcnow().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "message": message,
                "level": level
            }
            
            # Use provided session or create new one
            if db:
                job = db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
                if job:
                    current_logs = job.logs or []
                    # Ensure current_logs is a list (handle potential None or non-list)
                    if not isinstance(current_logs, list):
                        current_logs = []
                    current_logs.append(log_entry)
                    job.logs = current_logs
                    # Force update for JSONB
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(job, "logs")
                    db.commit()
            else:
                from src.database.connection import get_sync_session
                with get_sync_session() as session:
                    job = session.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
                    if job:
                        current_logs = job.logs or []
                        if not isinstance(current_logs, list):
                            current_logs = []
                        current_logs.append(log_entry)
                        job.logs = current_logs
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(job, "logs")
                        session.commit()
                        
        except Exception as e:
            logger.error(f"Failed to log event for job {job_id}: {e}")

    async def _run_job(
        self,
        job_id: UUID,
        document_text: str,
        target_count: int,
        language: str,
        purpose: str,
        generation_mode: str = "auto"
    ):
        """Execute the complete pipeline"""
        from src.database.connection import get_sync_session
        
        try:
            logger.info(f"▶️  Executing job {job_id}")
            await self._log_event(job_id, "Job execution started", "info")
            
            # Create a new session for the background task
            with get_sync_session() as db:
                # Create pipeline with new session
                pipeline = MultiStageQuestionnairePipeline(db)
                
                # NEW: Stage 0: Extract Document Structure
                logger.info("📄 Starting Stage 0: Document Extraction...")
                await self._log_event(job_id, "Starting Stage 0: Document Extraction", "info", db)
                extracted_data = await pipeline._stage0_extract_document(document_text, job_id)
                
                # Check if extraction found anything and auto-detect mode if needed
                total_items = extracted_data.get('total_items_found', 0)
                
                # Auto-detect mode based on extraction results
                if generation_mode == "auto":
                    if total_items > 0:
                        generation_mode = "extract"
                        logger.info(f"🤖 Auto-detected: EXTRACT mode ({total_items} existing questions found)")
                        await self._log_event(job_id, f"🤖 Auto-detected: EXTRACT mode - Found {total_items} existing questions", "info", db)
                    else:
                        generation_mode = "generate"
                        logger.info("🤖 Auto-detected: GENERATE mode (no existing questions, will create from guidelines)")
                        await self._log_event(job_id, "🤖 Auto-detected: GENERATE mode - Will create questions from document guidelines", "info", db)
                
                # Now check based on the determined mode
                if total_items == 0 and generation_mode == "extract":
                    # Only fail in extract mode - generate mode can work with 0 extracted items
                    error_msg = "Stage 0 extracted 0 items from the document. The file may not contain a questionnaire, assessment, or survey. Please upload a document with questions or assessment items, or switch to 'Generate' mode for guideline documents."
                    logger.error(f"❌ {error_msg}")
                    await self._log_event(job_id, f"❌ {error_msg}", "error", db)
                    
                    # Mark job as failed
                    job = db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
                    if job:
                        job.status = "failed"
                        job.error_message = error_msg
                        db.commit()
                    
                    raise ValueError(error_msg)
                elif total_items == 0 and generation_mode == "generate":
                    # In generate mode, 0 items is OK - we'll generate based on guidelines
                    logger.info("📝 Generate mode: No existing questions found, will generate based on document content")
                    await self._log_event(job_id, "📝 Generate mode: Will create new questions based on document guidelines", "info", db)
                
                await self._log_event(job_id, f"Stage 0 complete. Extracted {len(extracted_data.get('sections', []))} sections.", "success", db)
                
                # Stage 1: Analyze
                logger.info("📖 Starting Stage 1: Document Analysis...")
                await self._log_event(job_id, "Starting Stage 1: Document Analysis", "info", db)
                analysis = await pipeline._stage1_analyze(document_text, job_id)
                await self._log_event(job_id, "Stage 1 complete. Document analysis finished.", "success", db)
                
                # Store analysis_id to avoid session detachment issues
                analysis_id = analysis.id
                
                # Re-fetch managed instance to ensure it's bound to the current session
                analysis = db.query(QuestionnaireAnalysis).filter(QuestionnaireAnalysis.id == analysis_id).first()
                
                # NEW: Stage 1.5: Build Multi-AI Consensus
                logger.info("🤝 Starting Stage 1.5: Multi-AI Consensus...")
                await self._log_event(job_id, "Starting Stage 1.5: Multi-AI Consensus", "info", db)
                consensus_data = await pipeline._stage1_5_build_consensus(
                    document_text, extracted_data, analysis, job_id
                )
                await self._log_event(job_id, "Stage 1.5 complete. Consensus built.", "success", db)
                
                # Re-fetch for Stage 2
                analysis = db.query(QuestionnaireAnalysis).filter(QuestionnaireAnalysis.id == analysis_id).first()
                
                # MODIFIED: Stage 2: Extract Questions (not generate random ones)
                logger.info("✨ Starting Stage 2: Document-Faithful Question Extraction...")
                await self._log_event(job_id, "Starting Stage 2: Question Extraction (5 models parallel)", "info", db)
                candidates = await pipeline._stage2_generate(
                    analysis, extracted_data, consensus_data, document_text,
                    target_count, language, purpose, job_id
                )
                await self._log_event(job_id, f"Stage 2 complete. Generated {len(candidates)} candidates.", "success", db)
                
                # Re-fetch again for Stage 3 to keep a session-bound instance
                analysis = db.query(QuestionnaireAnalysis).filter(QuestionnaireAnalysis.id == analysis_id).first()
                
                # Stage 3: Validate
                logger.info("🔍 Starting Stage 3: Validation...")
                await self._log_event(job_id, "Starting Stage 3: Validation", "info", db)
                validated = await pipeline._stage3_validate(candidates, analysis, job_id)
                await self._log_event(job_id, "Stage 3 complete. Validation finished.", "success", db)
                
                # NEW: Stage 3.5 Fidelity Validation (ensure extracted questions match source)
                logger.info("🔎 Starting Stage 3.5: Fidelity Validation...")
                await self._log_event(job_id, "Starting Stage 3.5: Fidelity Validation", "info", db)
                fidelity_validated = await pipeline._stage3_5_fidelity_validation(
                    validated,
                    extracted_data,
                    job_id
                )
                await self._log_event(job_id, "Stage 3.5 complete. Fidelity check finished.", "success", db)
                
                # Re-fetch for Stage 4 (use fidelity_validated as input)
                analysis = db.query(QuestionnaireAnalysis).filter(QuestionnaireAnalysis.id == analysis_id).first()
                
                # Stage 4: Smart Filter (NEW!)
                logger.info("🎯 Starting Stage 4: Smart Filtering...")
                await self._log_event(job_id, "Starting Stage 4: Smart Filtering", "info", db)
                filtered = await pipeline._stage4_smart_filter(
                    fidelity_validated,
                    target_count,
                    language,
                    purpose,
                    job_id
                )
                await self._log_event(job_id, f"Stage 4 complete. Filtered to {len(filtered)} questions.", "success", db)
                
                # Stage 4.5: Duplicate Detection (NEW!)
                logger.info("🔍 Starting Stage 4.5: Duplicate Detection...")
                await self._log_event(job_id, "Starting Stage 4.5: Duplicate Detection", "info", db)
                await pipeline._stage4_5_detect_duplicates(
                    filtered,
                    purpose,
                    job_id
                )
                await self._log_event(job_id, "Stage 4.5 complete. Deduplication finished.", "success", db)
                
                # Re-fetch for final stage
                analysis = db.query(QuestionnaireAnalysis).filter(QuestionnaireAnalysis.id == analysis_id).first()
                
                # Stage 5: Assemble (final)
                logger.info("📚 Starting Stage 5: Final Assembly...")
                await self._log_event(job_id, "Starting Stage 5: Final Assembly", "info", db)
                await pipeline._stage4_assemble(filtered, analysis, job_id)
                await self._log_event(job_id, "Stage 5 complete. Assembly finished.", "success", db)
                
                # Update job
                job = db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
                if job:
                    usage = pipeline.client.get_usage_summary()
                    job.status = "completed"
                    job.progress_percentage = 100
                    job.total_tokens_used = usage["total_tokens"]
                    job.estimated_cost_usd = usage["total_cost_usd"]
                    job.models_used = usage
                    job.completed_at = datetime.utcnow()
                    db.commit()
                
                await self._log_event(job_id, "Job completed successfully", "success", db)
                logger.info(f"✅ Job {job_id} completed successfully")
                logger.info(f"   Total questions extracted: {len(filtered)}")
                logger.info(f"   Total tokens used: {usage['total_tokens']}")
                logger.info(f"   Estimated cost: ${usage['total_cost_usd']:.4f}")
                
                # Remove from active jobs
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
            
        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)
            await self._log_event(job_id, f"Job failed: {e}", "error")
            
            # Update job with error (need a session for this too if the main block failed)
            try:
                with get_sync_session() as error_db:
                    job = error_db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
                    if job:
                        job.status = "failed"
                        error_msg = str(e)
                        if not error_msg:
                            error_msg = f"Unknown error: {type(e).__name__}"
                        job.error_message = error_msg
                        job.completed_at = datetime.utcnow()
                        error_db.commit()
            except Exception as db_e:
                logger.error(f"Failed to update job status: {db_e}")
            
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    def get_job_status(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get current job status and progress"""
        job = self.db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
        
        if not job:
            return None
        
        # Get additional details if completed
        questions_generated = 0
        questions_validated = 0
        questions_selected = 0
        
        if job.analysis_id:
            
            analysis = self.db.query(QuestionnaireAnalysis).filter(
                QuestionnaireAnalysis.id == job.analysis_id
            ).first()
            
            if analysis:
                questions_generated = len(analysis.candidates)
                questions_validated = len([c for c in analysis.candidates if c.status in ("validated", "selected")])
                questions_selected = len([c for c in analysis.candidates if c.status == "selected"])
        
        # Estimate time remaining based on progress
        estimated_time = self._estimate_time_remaining(job.progress_percentage)
        
        # Map stage names to user-friendly descriptions
        stage_descriptions = {
            "Initializing": "Preparing to process document...",
            "Extracting Document": "Reading and extracting content from document...",
            "Analyzing Structure": "Analyzing document structure and domains...",
            "Building Consensus": "Building consensus across AI models...",
            "Generating Questions": "Generating questionnaire candidates...",
            "Validating Quality": "Validating question quality and relevance...",
            "Checking Fidelity": "Verifying questions match source document...",
            "Smart Filtering": "Selecting best questions...",
            "Detecting Duplicates": "Checking for duplicate questions...",
            "Creating Knowledge Base": "Assembling final questionnaire...",
            "Complete": "Generation complete!",
        }
        
        current_stage = job.current_stage or "Initializing"
        stage_description = stage_descriptions.get(current_stage, current_stage)
        
        return {
            "job_id": str(job.job_id),
            "status": job.status,
            # Old field names (for compatibility)
            "stage": current_stage,
            "progress": job.progress_percentage,
            # New field names (preferred)
            "current_stage": current_stage,
            "progress_percentage": job.progress_percentage,
            "stage_description": stage_description,
            # Additional details
            "estimated_time_remaining": estimated_time,
            "analysis_id": job.analysis_id,
            "questions_generated": questions_generated,
            "questions_validated": questions_validated,
            "questions_selected": questions_selected,
            "total_tokens_used": job.total_tokens_used,
            "estimated_cost_usd": float(job.estimated_cost_usd) if job.estimated_cost_usd else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "logs": job.logs or []  # Return logs
        }
    
    def _estimate_time_remaining(self, progress: int) -> str:
        """Estimate time remaining based on progress"""
        if progress >= 100:
            return "Complete"
        elif progress >= 75:
            return "1-2 minutes"
        elif progress >= 50:
            return "2-4 minutes"
        elif progress >= 25:
            return "4-6 minutes"
        elif progress >= 10:
            return "6-8 minutes"
        else:
            return "8-11 minutes"
    
    async def cancel_job(self, job_id: UUID) -> bool:
        """Cancel a running job"""
        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            task.cancel()
            del self.active_jobs[job_id]
            
            # Update job
            job = self.db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
            if job:
                job.status = "cancelled"
                job.completed_at = datetime.utcnow()
                self.db.commit()
            
            logger.info(f"🛑 Job {job_id} cancelled")
            return True
        
        return False
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get list of active jobs"""
        return [
            self.get_job_status(job_id)
            for job_id in self.active_jobs.keys()
        ]


