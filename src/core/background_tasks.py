# src/core/background_tasks.py
"""
Background task processing system for file uploads and document processing
"""

import asyncio
import hashlib
import json
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import redis.asyncio as redis

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.exceptions import FileProcessingError
from src.database.connection import get_async_session
from src.database.models_comprehensive import UploadedDocument
from src.data.processors.file_processor import FileProcessor
from src.data.processors.quality_scorer import QualityScorer
from src.data.processors.approval_workflow import ApprovalWorkflow

logger = get_logger(__name__)
settings = get_settings()

class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class TaskDefinition:
    """Task definition structure"""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: int = 300  # seconds
    created_at: datetime = None
    scheduled_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['priority'] = self.priority.value
        data['created_at'] = self.created_at.isoformat()
        if self.scheduled_at:
            data['scheduled_at'] = self.scheduled_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskDefinition':
        """Create from dictionary"""
        data['priority'] = TaskPriority(data['priority'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('scheduled_at'):
            data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'])
        return cls(**data)

@dataclass
class TaskResult:
    """Task execution result"""
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['status'] = self.status.value
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

class BackgroundTaskManager:
    """Background task management system"""
    
    def __init__(self):
        self.redis_client = None
        self.workers = {}
        self.task_handlers = {}
        self.running = False
        self.worker_pool_size = settings.worker_concurrency or 4
        
        # Register built-in task handlers
        self._register_default_handlers()
    
    async def initialize(self):
        """Initialize the task manager"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(
                settings.redis_url_str,
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Background task manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize background task manager: {e}")
            raise
    
    async def start_workers(self):
        """Start background worker processes"""
        if self.running:
            logger.warning("Workers already running")
            return
        
        self.running = True
        logger.info(f"Starting {self.worker_pool_size} background workers")
        
        # Start worker coroutines
        for worker_id in range(self.worker_pool_size):
            worker_task = asyncio.create_task(
                self._worker_loop(f"worker-{worker_id}")
            )
            self.workers[f"worker-{worker_id}"] = worker_task
        
        logger.info("Background workers started successfully")
    
    async def stop_workers(self):
        """Stop background worker processes"""
        if not self.running:
            return
        
        logger.info("Stopping background workers")
        self.running = False
        
        # Cancel all worker tasks
        for worker_id, worker_task in self.workers.items():
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Worker {worker_id} stopped")
        
        self.workers.clear()
        logger.info("Background workers stopped")
    
    async def enqueue_task(
        self, 
        task_type: str, 
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Enqueue a background task
        
        Args:
            task_type: Type of task to execute
            payload: Task payload data
            priority: Task priority
            delay: Delay before execution (seconds)
            **kwargs: Additional task options
            
        Returns:
            Task ID
        """
        # Generate task ID
        task_id = self._generate_task_id(task_type, payload)
        
        # Create task definition
        scheduled_at = None
        if delay:
            scheduled_at = datetime.utcnow() + timedelta(seconds=delay)
        
        task = TaskDefinition(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            scheduled_at=scheduled_at,
            **kwargs
        )
        
        # Store task in Redis
        await self._store_task(task)
        
        # Add to appropriate queue
        if scheduled_at:
            # Scheduled task
            await self.redis_client.zadd(
                "healthcare_ai:scheduled_tasks",
                {task_id: scheduled_at.timestamp()}
            )
        else:
            # Immediate task - add to priority queue
            queue_name = f"healthcare_ai:tasks:priority_{priority.value}"
            await self.redis_client.lpush(queue_name, task_id)
        
        logger.info(f"Enqueued task {task_id} of type {task_type}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get task execution status"""
        try:
            result_data = await self.redis_client.hget(
                "healthcare_ai:task_results", 
                task_id
            )
            
            if result_data:
                data = json.loads(result_data)
                data['status'] = TaskStatus(data['status'])
                if data.get('started_at'):
                    data['started_at'] = datetime.fromisoformat(data['started_at'])
                if data.get('completed_at'):
                    data['completed_at'] = datetime.fromisoformat(data['completed_at'])
                return TaskResult(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        try:
            # Remove from all queues
            for priority in TaskPriority:
                queue_name = f"healthcare_ai:tasks:priority_{priority.value}"
                await self.redis_client.lrem(queue_name, 0, task_id)
            
            # Remove from scheduled tasks
            await self.redis_client.zrem("healthcare_ai:scheduled_tasks", task_id)
            
            # Mark as cancelled
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED,
                completed_at=datetime.utcnow()
            )
            
            await self._store_result(result)
            
            logger.info(f"Task {task_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            stats = {
                "queues": {},
                "scheduled_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "active_workers": len([w for w in self.workers.values() if not w.done()])
            }
            
            # Queue lengths
            for priority in TaskPriority:
                queue_name = f"healthcare_ai:tasks:priority_{priority.value}"
                length = await self.redis_client.llen(queue_name)
                stats["queues"][priority.name.lower()] = length
            
            # Scheduled tasks
            stats["scheduled_tasks"] = await self.redis_client.zcard(
                "healthcare_ai:scheduled_tasks"
            )
            
            # Task results summary
            all_results = await self.redis_client.hgetall("healthcare_ai:task_results")
            for result_data in all_results.values():
                try:
                    result = json.loads(result_data)
                    status = result.get('status')
                    if status == TaskStatus.COMPLETED.value:
                        stats["completed_tasks"] += 1
                    elif status == TaskStatus.FAILED.value:
                        stats["failed_tasks"] += 1
                except Exception:
                    continue
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a task handler function"""
        self.task_handlers[task_type] = handler
        logger.info(f"Registered task handler for {task_type}")
    
    async def _worker_loop(self, worker_id: str):
        """Main worker loop"""
        logger.info(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Check for scheduled tasks first
                await self._process_scheduled_tasks()
                
                # Get next task from priority queues
                task_id = await self._get_next_task()
                
                if task_id:
                    await self._execute_task(worker_id, task_id)
                else:
                    # No tasks available, wait a bit
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(5)  # Brief pause on error
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_scheduled_tasks(self):
        """Move scheduled tasks to execution queues when ready"""
        try:
            current_time = datetime.utcnow().timestamp()
            
            # Get tasks ready for execution
            ready_tasks = await self.redis_client.zrangebyscore(
                "healthcare_ai:scheduled_tasks",
                0,
                current_time,
                withscores=False
            )
            
            for task_id in ready_tasks:
                # Get task definition
                task_data = await self.redis_client.hget(
                    "healthcare_ai:tasks", 
                    task_id
                )
                
                if task_data:
                    task = TaskDefinition.from_dict(json.loads(task_data))
                    
                    # Move to priority queue
                    queue_name = f"healthcare_ai:tasks:priority_{task.priority.value}"
                    await self.redis_client.lpush(queue_name, task_id)
                    
                    # Remove from scheduled tasks
                    await self.redis_client.zrem("healthcare_ai:scheduled_tasks", task_id)
                    
        except Exception as e:
            logger.error(f"Error processing scheduled tasks: {e}")
    
    async def _get_next_task(self) -> Optional[str]:
        """Get next task from priority queues"""
        try:
            # Check queues in priority order (highest first)
            for priority in sorted(TaskPriority, key=lambda p: p.value, reverse=True):
                queue_name = f"healthcare_ai:tasks:priority_{priority.value}"
                task_id = await self.redis_client.rpop(queue_name)
                if task_id:
                    return task_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next task: {e}")
            return None
    
    async def _execute_task(self, worker_id: str, task_id: str):
        """Execute a task"""
        start_time = time.time()
        
        try:
            # Get task definition
            task_data = await self.redis_client.hget("healthcare_ai:tasks", task_id)
            if not task_data:
                logger.error(f"Task {task_id} not found")
                return
            
            task = TaskDefinition.from_dict(json.loads(task_data))
            
            # Create initial result
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                started_at=datetime.utcnow()
            )
            await self._store_result(result)
            
            logger.info(f"Worker {worker_id} executing task {task_id} of type {task.task_type}")
            
            # Get task handler
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise Exception(f"No handler registered for task type: {task.task_type}")
            
            # Execute task with timeout
            task_result = await asyncio.wait_for(
                handler(task.payload),
                timeout=task.timeout
            )
            
            # Task completed successfully
            duration_ms = int((time.time() - start_time) * 1000)
            result.status = TaskStatus.COMPLETED
            result.result = task_result
            result.completed_at = datetime.utcnow()
            result.duration_ms = duration_ms
            
            await self._store_result(result)
            logger.info(f"Task {task_id} completed successfully in {duration_ms}ms")
            
        except asyncio.TimeoutError:
            # Task timed out
            duration_ms = int((time.time() - start_time) * 1000)
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error="Task timed out",
                started_at=result.started_at if 'result' in locals() else datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_ms=duration_ms
            )
            await self._store_result(result)
            logger.error(f"Task {task_id} timed out after {task.timeout} seconds")
            
        except Exception as e:
            # Task failed
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=error_msg,
                started_at=result.started_at if 'result' in locals() else datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_ms=duration_ms
            )
            
            # Check if we should retry
            if hasattr(task, 'max_retries') and result.retry_count < task.max_retries:
                result.status = TaskStatus.RETRYING
                result.retry_count += 1
                
                # Re-enqueue with delay
                await self.enqueue_task(
                    task.task_type,
                    task.payload,
                    task.priority,
                    delay=task.retry_delay
                )
                
                logger.warning(f"Task {task_id} failed, retrying ({result.retry_count}/{task.max_retries}): {error_msg}")
            else:
                logger.error(f"Task {task_id} failed permanently: {error_msg}")
                logger.debug(f"Task {task_id} traceback: {traceback.format_exc()}")
            
            await self._store_result(result)
    
    async def _store_task(self, task: TaskDefinition):
        """Store task definition in Redis"""
        await self.redis_client.hset(
            "healthcare_ai:tasks",
            task.task_id,
            json.dumps(task.to_dict())
        )
        
        # Set expiration for task data (7 days)
        await self.redis_client.expire("healthcare_ai:tasks", 7 * 24 * 3600)
    
    async def _store_result(self, result: TaskResult):
        """Store task result in Redis"""
        await self.redis_client.hset(
            "healthcare_ai:task_results",
            result.task_id,
            json.dumps(result.to_dict())
        )
        
        # Set expiration for results (7 days)
        await self.redis_client.expire("healthcare_ai:task_results", 7 * 24 * 3600)
    
    def _generate_task_id(self, task_type: str, payload: Dict[str, Any]) -> str:
        """Generate unique task ID"""
        timestamp = str(int(time.time() * 1000000))  # microseconds
        payload_hash = hashlib.md5(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()[:8]
        
        return f"{task_type}_{timestamp}_{payload_hash}"
    
    def _register_default_handlers(self):
        """Register default task handlers"""
        self.register_task_handler("process_document", self._handle_document_processing)
        self.register_task_handler("ocr_processing", self._handle_ocr_processing)
        self.register_task_handler("quality_scoring", self._handle_quality_scoring)
        self.register_task_handler("workflow_processing", self._handle_workflow_processing)
    
    async def _handle_document_processing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle document processing task"""
        document_id = payload.get('document_id')
        file_path = payload.get('file_path')
        
        if not document_id or not file_path:
            raise ValueError("Missing required parameters: document_id, file_path")
        
        try:
            async with get_async_session() as db:
                # Get document
                document = await db.get(UploadedDocument, document_id)
                if not document:
                    raise ValueError(f"Document {document_id} not found")
                
                # Process file
                file_processor = FileProcessor()
                processing_result = await file_processor.process_file(
                    Path(file_path), 
                    document.file_type
                )
                
                # Update document with extracted content
                document.extracted_content = processing_result.get("content", "")
                document.content_summary = processing_result.get("summary", "")
                
                # Update keywords
                keywords = document.keywords or {}
                keywords.update(processing_result.get("keywords", {}))
                document.keywords = keywords
                
                # Calculate quality score
                quality_scorer = QualityScorer()
                quality_score = await quality_scorer.score_medical_content(
                    document.extracted_content,
                    document.category
                )
                document.quality_score = quality_score
                
                # Update status
                document.status = "pending_approval"
                
                # Update metadata
                metadata = document.metadata or {}
                metadata.update({
                    "processing_completed_at": datetime.utcnow().isoformat(),
                    "processing_time_ms": processing_result.get("processing_time_ms", 0),
                    "extraction_method": processing_result.get("extraction_method", "unknown")
                })
                document.metadata = metadata
                
                await db.commit()
                
                # Trigger workflow processing
                workflow = ApprovalWorkflow()
                await workflow.process_document_upload(document_id, auto_review=True)
                
                return {
                    "document_id": document_id,
                    "content_length": len(document.extracted_content),
                    "quality_score": quality_score,
                    "processing_time_ms": processing_result.get("processing_time_ms", 0)
                }
                
        except Exception as e:
            # Update document status to error
            try:
                async with get_async_session() as db:
                    document = await db.get(UploadedDocument, document_id)
                    if document:
                        document.status = "processing_error"
                        metadata = document.metadata or {}
                        metadata.update({
                            "error_message": str(e),
                            "error_timestamp": datetime.utcnow().isoformat()
                        })
                        document.metadata = metadata
                        await db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update document error status: {update_error}")
            
            raise FileProcessingError(f"Document processing failed: {str(e)}")
    
    async def _handle_ocr_processing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OCR processing task"""
        # Placeholder for specialized OCR processing
        return await self._handle_document_processing(payload)
    
    async def _handle_quality_scoring(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle quality scoring task"""
        document_id = payload.get('document_id')
        
        if not document_id:
            raise ValueError("Missing required parameter: document_id")
        
        try:
            async with get_async_session() as db:
                document = await db.get(UploadedDocument, document_id)
                if not document:
                    raise ValueError(f"Document {document_id} not found")
                
                if not document.extracted_content:
                    raise ValueError("No content available for quality scoring")
                
                # Calculate quality score
                quality_scorer = QualityScorer()
                quality_score = await quality_scorer.score_medical_content(
                    document.extracted_content,
                    document.category
                )
                
                # Get detailed metrics
                metrics = await quality_scorer.get_detailed_quality_metrics(
                    document.extracted_content,
                    document.category
                )
                
                # Update document
                document.quality_score = quality_score
                
                metadata = document.metadata or {}
                metadata["quality_metrics"] = metrics.to_dict()
                document.metadata = metadata
                
                await db.commit()
                
                return {
                    "document_id": document_id,
                    "quality_score": quality_score,
                    "metrics": metrics.to_dict()
                }
                
        except Exception as e:
            raise Exception(f"Quality scoring failed: {str(e)}")
    
    async def _handle_workflow_processing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow processing task"""
        document_id = payload.get('document_id')
        
        if not document_id:
            raise ValueError("Missing required parameter: document_id")
        
        try:
            workflow = ApprovalWorkflow()
            result = await workflow.process_document_upload(document_id, auto_review=True)
            
            return result
            
        except Exception as e:
            raise Exception(f"Workflow processing failed: {str(e)}")

# Global task manager instance
task_manager = BackgroundTaskManager()

async def initialize_background_tasks():
    """Initialize background task system"""
    await task_manager.initialize()
    await task_manager.start_workers()

async def shutdown_background_tasks():
    """Shutdown background task system"""
    await task_manager.stop_workers()

def enqueue_document_processing(
    document_id: int, 
    file_path: str, 
    priority: TaskPriority = TaskPriority.NORMAL
) -> str:
    """
    Convenience function to enqueue document processing
    
    Args:
        document_id: ID of document to process
        file_path: Path to uploaded file
        priority: Task priority
        
    Returns:
        Task ID
    """
    return asyncio.create_task(task_manager.enqueue_task(
        "process_document",
        {"document_id": document_id, "file_path": file_path},
        priority=priority,
        timeout=600  # 10 minutes for large files
    ))

async def get_processing_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get processing status for a task"""
    result = await task_manager.get_task_status(task_id)
    if result:
        return {
            "task_id": task_id,
            "status": result.status.value,
            "progress": _calculate_progress(result),
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "result": result.result
        }
    return None

def _calculate_progress(result: TaskResult) -> int:
    """Calculate progress percentage based on task status"""
    if result.status == TaskStatus.PENDING:
        return 0
    elif result.status == TaskStatus.RUNNING:
        # Estimate progress based on elapsed time
        if result.started_at:
            elapsed = (datetime.utcnow() - result.started_at).total_seconds()
            # Assume average processing time of 60 seconds
            estimated_progress = min(90, int((elapsed / 60) * 90))
            return estimated_progress
        return 10
    elif result.status == TaskStatus.COMPLETED:
        return 100
    elif result.status in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
        return 0
    elif result.status == TaskStatus.RETRYING:
        return 5
    return 0

