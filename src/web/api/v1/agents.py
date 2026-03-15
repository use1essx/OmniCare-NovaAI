"""
Agent System API Endpoints

This module provides endpoints for the multi-agent AI system including:
- Agent information and capabilities
- Chat interaction endpoints
- Agent performance metrics
- Agent routing information
- Conversation history management

NOTE: This is the structure/interface layer. The actual agent implementations
will be added in Phase 3 (Day 3) of development.
"""

from typing import List, Optional, Dict, Any
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from src.core.config import settings
from src.core.exceptions import NotFoundError, ValidationError
from src.core.logging import get_logger, log_api_request, log_agent_interaction
from src.security.auth import InputSanitizer
from src.database.connection import get_async_db
from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_current_user, get_optional_user, require_role
from src.knowledge_base import get_hybrid_retriever
from src.agents.category_navigator import get_category_navigator


logger = get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AgentInfo(BaseModel):
    """Agent information model"""
    type: str = Field(..., description="Agent type identifier")
    name: str = Field(..., description="Agent display name")
    description: str = Field(..., description="Agent description and capabilities")
    specializations: List[str] = Field(..., description="Agent specialization areas")
    supported_languages: List[str] = Field(..., description="Supported languages")
    urgency_levels: List[str] = Field(..., description="Urgency levels this agent handles")
    average_response_time_ms: int = Field(..., description="Average response time in milliseconds")
    confidence_threshold: float = Field(..., description="Minimum confidence threshold")
    is_available: bool = Field(..., description="Whether agent is currently available")


class EmotionContext(BaseModel):
    """Emotion context from real-time tracking"""
    current_emotion: Optional[str] = Field(None, description="Current detected emotion")
    confidence: Optional[float] = Field(None, description="Emotion detection confidence (0-100)")
    dominant_recent: Optional[str] = Field(None, description="Dominant emotion from recent history")
    tracking_active: bool = Field(False, description="Whether emotion tracking is active")


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    language: Optional[str] = Field("auto", pattern="^(en|zh-HK|auto)$", description="Preferred language (en, zh-HK, or auto)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context information")
    agent_type: Optional[str] = Field(None, description="Preferred agent type")
    emotion_context: Optional[EmotionContext] = Field(None, description="Real-time emotion tracking data")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(None, description="Past conversation messages for AI memory")
    user_context: Optional[Dict[str, Any]] = Field(None, description="User profile context (age, name, etc.)")


class ChatResponse(BaseModel):
    """Chat response model"""
    message: str = Field(..., description="Agent response message")
    agent_type: str = Field(..., description="Agent that handled the request")
    agent_name: str = Field(..., description="Agent display name")
    confidence: float = Field(..., description="Agent confidence score")
    urgency_level: str = Field(..., description="Detected urgency level")
    language: str = Field(..., description="Response language")
    session_id: str = Field(..., description="Conversation session ID")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    hk_data_used: List[Dict[str, Any]] = Field(..., description="HK data references used")
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="RAG citations")
    rag_trace: Optional[Dict[str, Any]] = Field(default=None, description="RAG retrieval trace (debug)")
    routing_info: Dict[str, Any] = Field(..., description="Agent routing decision information")
    conversation_id: int = Field(..., description="Database conversation ID")


class ConversationHistoryItem(BaseModel):
    """Conversation history item model"""
    id: int
    timestamp: datetime
    user_message: str
    agent_response: str
    agent_type: str
    agent_name: str
    confidence: float
    urgency_level: str
    language: str
    user_satisfaction: Optional[int] = None
    processing_time_ms: int
    hk_data_used: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    """Conversation history response model"""
    conversations: List[ConversationHistoryItem]
    total: int
    session_id: str
    page: int
    page_size: int


class AgentPerformanceMetrics(BaseModel):
    """Agent performance metrics model"""
    agent_type: str
    period_start: datetime
    period_end: datetime
    total_conversations: int
    average_confidence: float
    average_satisfaction: float
    average_response_time_ms: int
    success_rate: float
    urgency_accuracy_rate: float
    domain_performance: Dict[str, Any]
    language_performance: Dict[str, Any]


class RoutingDecisionInfo(BaseModel):
    """Agent routing decision information"""
    selected_agent: str
    confidence: float
    agent_scores: Dict[str, float]
    routing_factors: Dict[str, Any]
    alternative_agents: List[str]
    routing_time_ms: int


class AgentCapabilitiesResponse(BaseModel):
    """Agent capabilities and status response"""
    available_agents: List[AgentInfo]
    system_status: str
    routing_enabled: bool
    cultural_adaptation: bool
    supported_languages: List[str]
    emergency_detection: bool


# ============================================================================
# AGENT INFORMATION ENDPOINTS
# ============================================================================

@router.get(
    "/info",
    response_model=AgentCapabilitiesResponse,
    summary="Get agent system information",
    description="Get information about available agents and system capabilities",
    responses={
        200: {"description": "Agent information retrieved successfully"},
        500: {"description": "System error"}
    }
)
  # 60 calls per minute
async def get_agent_info(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
) -> AgentCapabilitiesResponse:
    """Get information about available agents and capabilities"""
    start_time = datetime.now()
    
    try:
        # TODO: This will be implemented in Phase 3 with actual agent system
        # For now, return static information about planned agents
        
        available_agents = [
            AgentInfo(
                type="illness_monitor",
                name="Health Monitor",
                description="Physical health expert specializing in symptoms, chronic disease management, and HK hospital routing",
                specializations=["physical_health", "symptoms", "chronic_disease", "medication", "hospital_routing"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["low", "medium", "high", "emergency"],
                average_response_time_ms=2500,
                confidence_threshold=0.7,
                is_available=False  # Disabled for teen/kid focus
            ),
            AgentInfo(
                type="mental_health",
                name="Mental Health Expert",
                description="Mental health expert providing emotional support, counseling, and crisis intervention",
                specializations=["mental_health", "emotional_support", "counseling", "crisis_intervention"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["low", "medium", "high", "emergency"],
                average_response_time_ms=3000,
                confidence_threshold=0.6,
                is_available=True
            ),
            AgentInfo(
                type="safety_guardian",
                name="Emergency Expert",
                description="Emergency response specialist for critical situations and first aid guidance",
                specializations=["emergency_response", "first_aid", "crisis_management", "emergency_routing"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["high", "emergency"],
                average_response_time_ms=1500,
                confidence_threshold=0.9,
                is_available=True
            ),
            AgentInfo(
                type="wellness_coach",
                name="Preventive Care Expert",
                description="Health promotion specialist focusing on preventive care and lifestyle guidance",
                specializations=["preventive_care", "lifestyle", "wellness", "health_promotion"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["low", "medium"],
                average_response_time_ms=2000,
                confidence_threshold=0.6,
                is_available=True
            )
        ]
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            ip_address=request.client.host if request.client else None
        )
        
        return AgentCapabilitiesResponse(
            available_agents=available_agents,
            system_status="operational",
            routing_enabled=True,
            cultural_adaptation=True,
            supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
            emergency_detection=True
        )
        
    except Exception as e:
        logger.error(f"Error retrieving agent information: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving agent information"
        )


@router.get(
    "/{agent_type}/info",
    response_model=AgentInfo,
    summary="Get specific agent information",
    description="Get detailed information about a specific agent",
    responses={
        200: {"description": "Agent information retrieved successfully"},
        404: {"description": "Agent not found"},
        500: {"description": "System error"}
    }
)

async def get_specific_agent_info(
    request: Request,
    agent_type: str,
    db: AsyncSession = Depends(get_async_db)
) -> AgentInfo:
    """Get information about a specific agent"""
    start_time = datetime.now()
    
    try:
        # TODO: This will be implemented in Phase 3 with actual agent system
        # For now, return static information based on agent type
        
        agent_info_map = {
            "illness_monitor": AgentInfo(
                type="illness_monitor",
                name="Health Monitor",
                description="Physical health expert specializing in symptoms, chronic disease management, and HK hospital routing",
                specializations=["physical_health", "symptoms", "chronic_disease", "medication", "hospital_routing"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["low", "medium", "high", "emergency"],
                average_response_time_ms=2500,
                confidence_threshold=0.7,
                is_available=True
            ),
            "mental_health": AgentInfo(
                type="mental_health",
                name="Mental Health Expert",
                description="Mental health expert providing emotional support, counseling, and crisis intervention",
                specializations=["mental_health", "emotional_support", "counseling", "crisis_intervention"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["low", "medium", "high", "emergency"],
                average_response_time_ms=3000,
                confidence_threshold=0.6,
                is_available=True
            ),
            "safety_guardian": AgentInfo(
                type="safety_guardian",
                name="Emergency Expert",
                description="Emergency response specialist for critical situations and first aid guidance",
                specializations=["emergency_response", "first_aid", "crisis_management", "emergency_routing"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["high", "emergency"],
                average_response_time_ms=1500,
                confidence_threshold=0.9,
                is_available=True
            ),
            "wellness_coach": AgentInfo(
                type="wellness_coach",
                name="Preventive Care Expert",
                description="Health promotion specialist focusing on preventive care and lifestyle guidance",
                specializations=["preventive_care", "lifestyle", "wellness", "health_promotion"],
                supported_languages=["en", "zh-HK"],  # Only English and Cantonese (Hong Kong)
                urgency_levels=["low", "medium"],
                average_response_time_ms=2000,
                confidence_threshold=0.6,
                is_available=True
            )
        }
        
        if agent_type not in agent_info_map:
            raise NotFoundError(f"Agent type '{agent_type}' not found")
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            ip_address=request.client.host if request.client else None
        )
        
        return agent_info_map[agent_type]
        
    except Exception as e:
        logger.error(f"Error retrieving agent {agent_type} information: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=404 if isinstance(e, NotFoundError) else 500,
            response_time_ms=processing_time,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, NotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving agent information"
        )


# ============================================================================
# CHAT INTERACTION ENDPOINTS
# ============================================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with AI agents",
    description="Send a message to the AI agent system for processing and response",
    responses={
        200: {"description": "Chat response generated successfully"},
        400: {"description": "Invalid input data"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "System error"}
    }
)
  # 20 chat messages per minute
async def chat_with_agents(
    request: Request,
    chat_request: ChatRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_db)
) -> ChatResponse:
    """Send a message to the AI agent system"""
    start_time = datetime.now()
    response_citations = []
    response_content = ""
    rag_trace = None
    rag_context = None
    async def _translate_response(ai_service, text: str, target_language: str) -> str:
        if not text:
            return text
        if target_language == "zh-HK":
            instruction = "Translate the following into Traditional Chinese (Hong Kong). Use natural Cantonese phrasing. Return only the translated text."
        else:
            instruction = "Translate the following into clear English. Return only the translated text."
        prompt = f"{instruction}\n\n{text}"
        try:
            res = await ai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2,
            )
            translated = res.get("content", "") if isinstance(res, dict) else ""
            return translated.strip() or text
        except Exception:
            return text
    try:
        # Sanitize user input
        sanitizer = InputSanitizer()
        safe_message = sanitizer.sanitize_string(chat_request.message, max_length=4000)
        
        if len(safe_message.strip()) == 0:
            raise ValidationError("Message cannot be empty")
        
        # ?? UNIFIED AGENT SYSTEM (with form delivery support)
        
        # Generate session ID if not provided
        session_id = chat_request.session_id or f"kb_sandbox_{int(datetime.now().timestamp())}"
        
        # Get request language early (needed for fallback)
        request_language = chat_request.language or "auto"
        resolved_language = request_language
        
        # Resolve language: request > user profile > auto-detect
        user_language_pref = None
        if current_user:
            user_language_pref = getattr(current_user, 'language_preference', None)
        
        if user_language_pref and user_language_pref in ["en", "zh-HK"]:
            resolved_language = user_language_pref
        elif request_language != "auto":
            resolved_language = request_language
        else:
            # Auto-detect from message
            resolved_language = "zh-HK" if any('\u4e00' <= c <= '\u9fff' for c in safe_message) else "en"
        
        # BUGFIX: Create conversation record BEFORE calling UnifiedAgent
        # This ensures the conversation_id exists for form delivery foreign key constraint
        conversation_id = None
        try:
            from src.database.models_comprehensive import Conversation
            
            # Create placeholder conversation record
            conversation = Conversation(
                session_id=session_id,
                user_id=current_user.id if current_user else None,
                user_input=safe_message,
                agent_response="",  # Will be updated after AI response
                agent_type="wellness_coach",  # Default, will be updated
                agent_name="Little Star (小星星)",
                agent_confidence=0.0,  # Will be updated
                urgency_level="low",  # Will be updated
                language=resolved_language,
                processing_time_ms=0,  # Will be updated
            )
            db.add(conversation)
            await db.flush()  # Get the ID without committing
            conversation_id = conversation.id
            logger.info(f"📝 Created conversation record {conversation_id} for session {session_id}")
        except Exception as db_error:
            logger.error(f"Failed to create conversation record: {db_error}", exc_info=True)
            # Continue without conversation_id - form delivery will be skipped
        
        # Initialize AI services and UnifiedAgent
        from src.ai.ai_service import get_ai_service
        from src.agents.unified_agent import UnifiedAgent
        
        try:
            ai_service = await get_ai_service()
            
            # SECURITY: Initialize UnifiedAgent with database session for form delivery
            # This enables form_delivery_tracker and form_download_service
            unified_agent = UnifiedAgent(
                ai_service=ai_service,
                db_session=db  # Enable form delivery services
            )
            
            # Process message with UnifiedAgent (includes RAG, form delivery, skill activation)
            # BUGFIX: Pass conversation_id to enable form delivery with proper foreign key
            user_id_int = current_user.id if current_user else None
            
            unified_response = await unified_agent.process_message(
                message=safe_message,
                session_id=session_id,
                user_id=user_id_int,
                conversation_id=conversation_id,  # Pass the real conversation_id
                multimodal_context=None,  # KB Sandbox doesn't have multimodal input
                language=resolved_language
            )
            
            # Extract response data from UnifiedAgent
            response_content = unified_response.message
            response_citations = unified_response.citations
            selected_agent_type = unified_response.active_skills[0] if unified_response.active_skills else "wellness_coach"
            agent_name = "Little Star (小星星)"
            confidence = 0.85  # UnifiedAgent doesn't expose confidence, use default
            urgency = "emergency" if unified_response.crisis_detected else "low"
            
            # Map skill to agent type for compatibility
            skill_to_agent_map = {
                "safety_crisis": "safety_guardian",
                "mental_health": "mental_health",
                "physical_health": "wellness_coach",
                "wellness_coaching": "wellness_coach",
                "sleep_support": "mental_health",
                "social_support": "mental_health",
                "motor_screening": "smartkidpath_screener",
            }
            if unified_response.active_skills:
                selected_agent_type = skill_to_agent_map.get(
                    unified_response.active_skills[0],
                    "wellness_coach"
                )
            
            # Note: UnifiedAgent handles conversation history internally
            # No need to manually update conversation memory here
            
        except Exception as ai_error:
            # Fallback response if UnifiedAgent fails
            logger.error(f"UnifiedAgent error: {ai_error}", exc_info=True)
            selected_agent_type = "wellness_coach"
            agent_name = "Little Star (小星星)"
            confidence = 0.70
            urgency = "low"
            response_citations = []
            # Language-aware fallback response
            if resolved_language == "zh-HK":
                response_content = "歡迎使用 OmniCare！我可以幫你解答健康相關問題。有咩想問我？（注意：系統暫時使用備用模式）"
            else:
                response_content = "Welcome to OmniCare! I'm here to help with your health questions. How can I assist you today? (Note: Our AI system is temporarily using fallback mode)"
        
        # 📝 QUESTIONNAIRE INTEGRATION - Check for active questionnaire assignments
        # This runs AFTER the AI response is generated (whether successful or fallback)
        if current_user:
            try:
                from src.web.live2d.backend.questionnaire_integration import get_questionnaire_integration
                from src.web.live2d.backend.answer_extraction_service import get_answer_extraction_service
                from src.database.models_questionnaire import ConversationAnswer, QuestionnaireQuestion
                from src.database.models_comprehensive import Conversation
                from sqlalchemy import and_, func, select as sql_select
                from datetime import timedelta
                
                questionnaire_service = get_questionnaire_integration()
                answer_extraction_service = get_answer_extraction_service()
                
                # Check if user has active questionnaire assignment
                assignment_info = await questionnaire_service.check_active_assignment(current_user.id)
                
                if assignment_info:
                    logger.info(f"📋 User {current_user.id} has active questionnaire assignment {assignment_info['assignment_id']}")
                    
                    # STEP 1: Try to extract answer from user's message (if they're responding to a question)
                    # Check if there's a recently asked question waiting for answer
                    recent_question_query = sql_select(ConversationAnswer).where(
                        and_(
                            ConversationAnswer.assignment_id == assignment_info['assignment_id'],
                            ConversationAnswer.extracted_answer_value.is_(None),  # Not yet answered (check for NULL)
                            ConversationAnswer.asked_at >= datetime.now() - timedelta(hours=1)
                        )
                    ).order_by(ConversationAnswer.asked_at.desc()).limit(1)
                    
                    recent_result = await db.execute(recent_question_query)
                    pending_answer = recent_result.scalar_one_or_none()
                    
                    if pending_answer:
                        logger.info(f"🔍 Attempting to extract answer from user message for question {pending_answer.question_id}")
                        logger.info(f"📝 User message: {safe_message[:100]}...")
                        
                        # Get question details for AI extraction
                        question_query = sql_select(QuestionnaireQuestion).where(
                            QuestionnaireQuestion.id == pending_answer.question_id
                        )
                        question_result = await db.execute(question_query)
                        question = question_result.scalar_one_or_none()
                        
                        if question:
                            # Extract answer using AI-powered service
                            extracted_data = await answer_extraction_service.extract_answer_from_response(
                                user_response=safe_message,
                                question_text=pending_answer.question_asked or question.question_text,
                                question_type=question.question_type or 'scale',
                                conversation_context=None
                            )
                            
                            logger.info(f"📊 AI Extraction result: {extracted_data}")
                            
                            # Check if extraction was successful
                            if extracted_data.get('success', True) and extracted_data.get('extracted_value') is not None:
                                # Save the extracted answer WITH EMOTION ANALYSIS
                                logger.info(f"💾 Saving extracted answer with emotion analysis: value={extracted_data.get('extracted_value')}, confidence={extracted_data.get('confidence')}")
                                
                                # Get conversation history for emotion analysis context
                                conversation_history = []
                                
                                saved = await answer_extraction_service.save_extracted_answer(
                                    answer_record_id=pending_answer.id,
                                    user_response_text=safe_message,
                                    extracted_text=extracted_data.get('extracted_text'),
                                    extracted_value=extracted_data.get('extracted_value'),
                                    confidence=extracted_data.get('confidence', 0.5),
                                    extraction_method='ai_extraction',
                                    question_context=pending_answer.question_asked or question.question_text,
                                    conversation_history=conversation_history
                                )
                                
                                if saved:
                                    logger.info(f"✅ Answer extracted and saved with emotion analysis: value={extracted_data.get('extracted_value')}, confidence={extracted_data.get('confidence')}")
                                    # Refresh assignment info after saving answer
                                    assignment_info = await questionnaire_service.check_active_assignment(current_user.id)
                                else:
                                    logger.warning(f"❌ Failed to save extracted answer")
                            else:
                                logger.warning(f"⚠️ Could not extract clear answer from message: {safe_message[:50]}...")
                        else:
                            logger.error(f"❌ Question {pending_answer.question_id} not found")
                    else:
                        logger.info(f"ℹ️ No pending question found for answer extraction")
                    
                    # STEP 2: Check if we should ask a new question
                    # Count REAL messages in this session from database
                    message_count_result = await db.execute(
                        sql_select(func.count(Conversation.id))
                        .where(Conversation.session_id == session_id)
                    )
                    message_count = message_count_result.scalar() or 1
                    logger.info(f"📊 Real message count for session {session_id}: {message_count}")
                    
                    # Check if we should ask a question now
                    should_ask = await questionnaire_service.should_ask_question(message_count, assignment_info)
                    
                    if should_ask:
                        # Get next unanswered question
                        question_info = await questionnaire_service.get_next_question(
                            assignment_info['assignment_id'],
                            assignment_info['questionnaire_id']
                        )
                        
                        if question_info:
                            # Format question naturally
                            formatted_question = await questionnaire_service.format_question_naturally(
                                question_info['question_text'],
                                language=chat_request.language or "en",
                                question_text_zh=question_info.get('question_text_zh')
                            )
                            
                            # Record that we asked this question
                            await questionnaire_service.record_question_asked(
                                assignment_id=assignment_info['assignment_id'],
                                question_id=question_info['question_id'],
                                user_id=current_user.id,
                                question_text=formatted_question
                            )
                            
                            # Inject question into response with natural transition
                            # Add a natural transition before the question
                            if chat_request.language and chat_request.language.startswith("zh"):
                                transition = "\n\n另外，我想了解一下："
                            else:
                                transition = "\n\nAlso, I'd like to understand:"
                            
                            response_content = f"{response_content}{transition}\n{formatted_question}"
                            logger.info(f"✅ Injected questionnaire question {question_info['question_id']} into response")
                        else:
                            logger.info(f"✅ No more questions to ask - questionnaire completed")
                    else:
                        logger.info(f"⏸️ Not asking question yet (message_count={message_count})")
                else:
                    logger.info(f"No active questionnaire assignment for user {current_user.id}")
                    
            except Exception as questionnaire_error:
                # Don't fail the entire request if questionnaire integration fails
                logger.error(f"Questionnaire integration error: {questionnaire_error}", exc_info=True)
        
        # Calculate processing time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # BUGFIX: Update the conversation record created earlier with AI response
        # This replaces the old duplicate conversation creation code
        if conversation_id:
            try:
                from src.database.models_comprehensive import Conversation
                
                # Update the existing conversation record with AI response
                result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()
                
                if conversation:
                    conversation.agent_response = response_content
                    conversation.agent_type = selected_agent_type
                    conversation.agent_name = agent_name
                    conversation.agent_confidence = round(confidence, 2)
                    conversation.urgency_level = urgency
                    conversation.processing_time_ms = processing_time
                    await db.commit()
                    logger.info(f"✅ Updated conversation {conversation_id} with AI response")
                else:
                    logger.error(f"❌ Conversation {conversation_id} not found for update")
            except Exception as db_error:
                logger.error(f"Failed to update conversation record: {db_error}", exc_info=True)
        else:
            logger.warning("⚠️  No conversation_id available - skipping conversation update")

        
        # Log agent interaction
        log_agent_interaction(
            agent_type=selected_agent_type,
            user_input=safe_message,
            agent_response=response_content,
            confidence=confidence,
            urgency_level=urgency,
            processing_time_ms=processing_time,
            user_id=current_user.id if current_user else None,
            session_id=session_id
        )
        
        # ? Crisis Alert Detection and Creation
        try:
            await _check_and_create_crisis_alert(
                message=safe_message,
                urgency=urgency,
                session_id=session_id,
                user_id=current_user.id if current_user else None,
                agent_type=selected_agent_type,
                db=db
            )
        except Exception as alert_error:
            logger.warning(f"Failed to process crisis alert: {alert_error}")
        
        # Log successful request
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id if current_user else None,
            ip_address=request.client.host if request.client else None
        )
        
        # Return successful response
        return ChatResponse(
            message=response_content,
            agent_type=selected_agent_type,
            agent_name=agent_name,
            confidence=confidence,
            urgency_level=urgency,
            language=resolved_language,
            session_id=session_id,
            processing_time_ms=processing_time,
            hk_data_used=[],
            citations=response_citations,
            rag_trace=rag_trace,
            routing_info={
                "selected_agent": selected_agent_type,
                "confidence": confidence,
                "routing_factors": getattr(routing_result, 'reasons', ["ai_agent_routing"]) if 'routing_result' in locals() else ["fallback_mode"],
                "alternative_agents": getattr(routing_result, 'alternative_agents', ["illness_monitor", "mental_health", "safety_guardian", "wellness_coach"]) if 'routing_result' in locals() else ["illness_monitor", "mental_health", "safety_guardian", "wellness_coach"]
            },
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id if current_user else None,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing chat request"
        )


# ============================================================================
# CONVERSATION HISTORY ENDPOINTS
# ============================================================================

@router.get(
    "/conversations",
    response_model=ConversationHistoryResponse,
    summary="Get conversation history",
    description="Get conversation history for authenticated user",
    responses={
        200: {"description": "Conversation history retrieved successfully"},
        401: {"description": "Authentication required"},
        500: {"description": "System error"}
    }
)

async def get_conversation_history(
    request: Request,
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> ConversationHistoryResponse:
    """Get conversation history for authenticated user"""
    start_time = datetime.now()
    
    try:
        # TODO: This will be implemented with actual conversation repository
        # For now, return empty history
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return ConversationHistoryResponse(
            conversations=[],
            total=0,
            session_id=session_id or "all",
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving conversation history"
        )


# ============================================================================
# PERFORMANCE METRICS ENDPOINTS
# ============================================================================

@router.get(
    "/performance",
    response_model=List[AgentPerformanceMetrics],
    dependencies=[Depends(require_role("admin"))],
    summary="Get agent performance metrics (Admin)",
    description="Get performance metrics for all agents",
    responses={
        200: {"description": "Performance metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        500: {"description": "System error"}
    }
)

async def get_agent_performance(
    request: Request,
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> List[AgentPerformanceMetrics]:
    """Get agent performance metrics (admin only)"""
    start_time = datetime.now()
    
    try:
        # TODO: This will be implemented with actual performance tracking
        # For now, return placeholder metrics
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        placeholder_metrics = [
            AgentPerformanceMetrics(
                agent_type="illness_monitor",
                period_start=start_date,
                period_end=end_date,
                total_conversations=0,
                average_confidence=0.0,
                average_satisfaction=0.0,
                average_response_time_ms=0,
                success_rate=0.0,
                urgency_accuracy_rate=0.0,
                domain_performance={},
                language_performance={}
            ),
            AgentPerformanceMetrics(
                agent_type="mental_health",
                period_start=start_date,
                period_end=end_date,
                total_conversations=0,
                average_confidence=0.0,
                average_satisfaction=0.0,
                average_response_time_ms=0,
                success_rate=0.0,
                urgency_accuracy_rate=0.0,
                domain_performance={},
                language_performance={}
            )
        ]
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return placeholder_metrics
        
    except Exception as e:
        logger.error(f"Error retrieving agent performance metrics: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving agent performance metrics"
        )


# ============================================================================
# ? REAL-TIME WEBSOCKET CHAT ENDPOINT
# ============================================================================

@router.websocket("/chat/ws")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    ?? Real-time WebSocket chat with Healthcare AI agents
    
    Features:
    - Real-time bidirectional communication
    - Live agent responses
    - Typing indicators
    - Emergency escalation alerts
    - Session persistence
    - Anonymous and authenticated chat support
    """
    await websocket.accept()
    
    # Initialize session data
    session_data = {
        "session_id": f"ws_{int(datetime.now().timestamp())}_{hash(str(websocket.client)) % 10000:04d}",
        "user_id": None,
        "connection_time": datetime.now(),
        "message_count": 0,
        "last_agent": None
    }
    
    logger.info(f"WebSocket connection established: {session_data['session_id']}")
    
    try:
        # Send welcome message
        welcome_message = {
            "type": "system",
            "message": "? Welcome to Healthcare AI V2! I'm here to help with your health questions.",
            "session_id": session_data["session_id"],
            "timestamp": datetime.now().isoformat(),
            "agents_available": ["illness_monitor", "mental_health", "safety_guardian", "wellness_coach"]
        }
        await websocket.send_json(welcome_message)
        
        # Initialize AI services
        from src.ai.ai_service import get_ai_service
        from src.agents.orchestrator import AgentOrchestrator
        from src.agents.context_manager import ConversationContextManager
        
        ai_service = await get_ai_service()
        orchestrator = AgentOrchestrator(ai_service)
        context_manager = ConversationContextManager()
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            session_data["message_count"] += 1
            
            if data.get("type") == "chat":
                user_message = data.get("message", "").strip()
                
                if not user_message:
                    await websocket.send_json({
                        "type": "error", 
                        "message": "Empty message received",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue
                
                # Send typing indicator
                await websocket.send_json({
                    "type": "typing",
                    "agent": "AI is thinking...",
                    "timestamp": datetime.now().isoformat()
                })
                
                try:
                    # Process with agent system
                    user_id = session_data["user_id"] or f"ws_anonymous_{hash(str(websocket.client)) % 10000:04d}"
                    
                    # Create context
                    context = context_manager.create_context(
                        user_id=user_id,
                        session_id=session_data["session_id"],
                        user_input=user_message,
                        additional_context={
                            "connection_type": "websocket",
                            "message_count": session_data["message_count"],
                            "last_agent": session_data["last_agent"]
                        }
                    )
                    
                    # Route to agent
                    selected_agent, routing_result = await orchestrator.route_request(
                        user_input=user_message,
                        context=context
                    )
                    
                    # Generate response
                    agent_response = await selected_agent.generate_response(user_message, context)
                    
                    # Update session data
                    session_data["last_agent"] = routing_result.selected_agent
                    
                    # Send response
                    response_data = {
                        "type": "agent_response",
                        "message": agent_response.content,
                        "agent_type": routing_result.selected_agent,
                        "agent_name": selected_agent.agent_id,
                        "confidence": routing_result.confidence,
                        "urgency_level": routing_result.urgency_level,
                        "session_id": session_data["session_id"],
                        "timestamp": datetime.now().isoformat(),
                        "suggested_actions": agent_response.suggested_actions if hasattr(agent_response, 'suggested_actions') else [],
                        "professional_alert": agent_response.professional_alert_needed if hasattr(agent_response, 'professional_alert_needed') else False
                    }
                    
                    await websocket.send_json(response_data)
                    
                    # Send emergency alert if needed
                    if hasattr(agent_response, 'professional_alert_needed') and agent_response.professional_alert_needed:
                        await websocket.send_json({
                            "type": "emergency_alert",
                            "message": "?? This situation may require immediate professional attention. Please consider contacting emergency services (999) or a healthcare provider.",
                            "alert_details": agent_response.alert_details if hasattr(agent_response, 'alert_details') else {},
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Log interaction
                    log_agent_interaction(
                        agent_type=routing_result.selected_agent,
                        user_input=user_message,
                        agent_response=agent_response.content,
                        confidence=routing_result.confidence,
                        urgency_level=routing_result.urgency_level,
                        processing_time_ms=0,  # WebSocket doesn't track this easily
                        session_id=session_data["session_id"]
                    )
                    
                except Exception as e:
                    logger.error(f"WebSocket agent processing error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "I'm experiencing technical difficulties. Please try again or contact support if this persists.",
                        "error_code": "AGENT_ERROR",
                        "timestamp": datetime.now().isoformat()
                    })
            
            elif data.get("type") == "ping":
                # Respond to keepalive pings
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            elif data.get("type") == "auth":
                # Handle authentication (optional)
                auth_token = data.get("token")
                if auth_token:
                    try:
                        # Validate token and get user
                        from src.web.auth.handlers import token_validator
                        from src.database.repositories.user_repository import UserRepository
                        
                        payload = token_validator.decode_token(auth_token)
                        user_repo = UserRepository()
                        user = await user_repo.get_by_id(int(payload.get("sub")))
                        
                        if user and user.is_active:
                            session_data["user_id"] = str(user.id)
                            await websocket.send_json({
                                "type": "auth_success",
                                "user_id": user.id,
                                "username": user.username,
                                "timestamp": datetime.now().isoformat()
                            })
                        else:
                            await websocket.send_json({
                                "type": "auth_failed",
                                "message": "Invalid authentication",
                                "timestamp": datetime.now().isoformat()
                            })
                    except Exception as e:
                        logger.error(f"WebSocket auth error: {e}")
                        await websocket.send_json({
                            "type": "auth_failed",
                            "message": "Authentication failed",
                            "timestamp": datetime.now().isoformat()
                        })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_data['session_id']}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Connection error occurred",
                "error_code": "CONNECTION_ERROR",
                "timestamp": datetime.now().isoformat()
            })
        except Exception:
            pass  # Connection might already be closed


# ============================================================================
# CRISIS ALERT DETECTION HELPER
# ============================================================================

# Crisis keywords for detection
CRISIS_KEYWORDS_EN = [
    "suicide", "kill myself", "want to die", "end my life", "hurt myself",
    "self-harm", "cutting", "overdose", "jump off", "hang myself",
    "don't want to live", "not want to live", "live anymore", "no point living",
    "end it all", "wish i was dead", "better off dead", "hopeless"
]

CRISIS_KEYWORDS_ZH = [
    "??", "??", "?????", "????", "??",
    "??", "??", "????", "??", "??",
    "???", "????", "???", "???", "????"
]


async def _check_and_create_crisis_alert(
    message: str,
    urgency: str,
    session_id: str,
    user_id: Optional[int],
    agent_type: str,
    db: AsyncSession
) -> None:
    """
    Check for crisis indicators and create alert if needed.
    
    Args:
        message: User message text
        urgency: Detected urgency level
        session_id: Session identifier
        user_id: User ID if authenticated
        agent_type: Agent that handled the message
        db: Database session
    """
    # Check for crisis keywords
    message_lower = message.lower()
    is_crisis = False
    detected_keywords = []
    
    for keyword in CRISIS_KEYWORDS_EN:
        if keyword in message_lower:
            is_crisis = True
            detected_keywords.append(keyword)
    
    for keyword in CRISIS_KEYWORDS_ZH:
        if keyword in message:
            is_crisis = True
            detected_keywords.append(keyword)
    
    # Also check if urgency is emergency or high
    if urgency in ["emergency", "high"]:
        is_crisis = True
    
    if not is_crisis:
        return
    
    logger.warning(f"? Crisis detected! Keywords: {detected_keywords}, Urgency: {urgency}")
    
    try:
        from src.social_worker.alert_manager import get_alert_manager
        
        alert_manager = get_alert_manager()
        
        # Determine severity (1-5, 5 being most severe)
        severity = 5 if any(kw in message_lower for kw in ["suicide", "kill myself", "?芣捏"]) else 4
        
        # Create alert
        alert = await alert_manager.create_alert(
            session_id=session_id,
            child_id=user_id,
            alert_type="emergency" if severity == 5 else "risk_detected",
            severity=severity,
            message=f"Crisis indicators detected in conversation: {message[:200]}...",
            detected_by="ai_agent",
            skill_involved=agent_type,
            trigger_reason=f"Keywords detected: {', '.join(detected_keywords[:3])}",
            recommended_action="Immediate review required. Contact child/family as soon as possible.",
            force_create=True  # Bypass debouncing for critical alerts
        )
        
        if alert:
            logger.warning(f"??Crisis alert created: ID={alert.id}, Severity={severity}")
        else:
            logger.info("Alert debounced or skipped")
            
    except Exception as e:
        logger.error(f"Failed to create crisis alert: {e}")
# ============================================================================
# INTERNAL HELPERS
# ============================================================================

async def _resolve_doc_by_title(
    query: str,
    organization_id: Optional[int] = None,
    visibility: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Resolve a knowledge document by title mention in the query."""
    # Extract simple tokens (English/number + CJK sequences)
    tokens = re.findall(r"[A-Za-z0-9_]{2,}", query)
    cjk_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    
    # For CJK text, also extract shorter substrings (2-10 chars) to handle compound words
    for seq in cjk_sequences:
        tokens.append(seq)  # Add full sequence
        # Also add shorter substrings from the beginning (likely to be meaningful terms)
        for length in range(min(10, len(seq)), 1, -1):
            tokens.append(seq[:length])
    
    if not tokens:
        return None
    # Drop common filler words
    stop = {"about", "know", "tell", "want", "need", "please"}
    terms = [t for t in tokens if t.lower() not in stop]
    if not terms:
        return None
    # Prefer longer tokens first, but deduplicate
    terms = sorted(set(terms), key=len, reverse=True)

    visibility_clause = ""
    if visibility:
        visibility_clause = "AND kd.visibility = :visibility"
    org_clause = ""
    if organization_id:
        org_clause = "AND (kd.organization_id = :org_id OR kd.visibility = 'public')"

    sql = text(f"""
        SELECT kd.id, kd.title
        FROM knowledge_documents kd
        WHERE kd.status = 'indexed'
        {visibility_clause}
        {org_clause}
        AND kd.title ILIKE :pattern
        ORDER BY kd.indexed_at DESC NULLS LAST, kd.created_at DESC
        LIMIT 1
    """)

    async for session in get_async_db():
        for term in terms[:10]:  # Try more terms to handle variations
            result = await session.execute(
                sql,
                {
                    "pattern": f"%{term}%",
                    "visibility": visibility,
                    "org_id": organization_id,
                }
            )
            row = result.fetchone()
            if row:
                return {"id": row.id, "title": row.title}
    return None
