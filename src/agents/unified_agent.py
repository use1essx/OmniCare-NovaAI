"""
Unified Agent (小星星)

Single AI personality with dynamic skill activation.
Replaces the multi-agent system with one cohesive agent that can
activate different skills based on conversation context.

Key Features:
- Single personality: 小星星 (Little Star)
- Dynamic skill activation based on keywords, emotions, movement
- Shared conversation memory across all skills
- Function calling with circuit breaker
- RAG knowledge retrieval per skill
- Live2D emotion and gesture mapping
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .skills import SkillActivator, SkillContext, get_skill_activator
from .context_manager import ConversationContextManager
from .emotion_mapper import EmotionMapper
from .gesture_library import GestureLibrary
from ..knowledge_base import HybridRetriever, get_hybrid_retriever
from ..knowledge_base.form_delivery_tracker import FormDeliveryTracker
from ..knowledge_base.form_download_service import FormDownloadService
from ..core.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


@dataclass
class UnifiedAgentResponse:
    """Response from the unified agent"""
    
    # Core response
    message: str
    session_id: str
    
    # Live2D integration
    emotion: str = "neutral"
    gesture: str = "idle"
    
    # Skills used
    active_skills: List[str] = field(default_factory=list)
    skill_contexts: List[Dict] = field(default_factory=list)
    
    # Function calls made
    function_calls: List[Dict] = field(default_factory=list)
    function_results: List[Dict] = field(default_factory=list)
    
    # Knowledge used
    citations: List[Dict] = field(default_factory=list)
    
    # Metadata
    processing_time_ms: int = 0
    model_used: str = ""
    tokens_used: int = 0
    
    # Flags
    requires_follow_up: bool = False
    alert_triggered: bool = False
    crisis_detected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            'message': self.message,
            'session_id': self.session_id,
            'emotion': self.emotion,
            'gesture': self.gesture,
            'active_skills': self.active_skills,
            'function_calls': self.function_calls,
            'citations': self.citations,
            'processing_time_ms': self.processing_time_ms,
            'requires_follow_up': self.requires_follow_up,
            'crisis_detected': self.crisis_detected
        }


class UnifiedAgent:
    """
    小星星 (Little Star) - Unified AI Companion
    
    A single AI personality that dynamically activates specialized skills
    based on conversation context, emotion detection, and movement analysis.
    
    Architecture:
    1. Message arrives with optional multimodal context
    2. SkillActivator detects relevant skills
    3. RAG retrieves knowledge for active skill categories
    4. Unified prompt combines base personality + active skill prompts
    5. AI generates response with optional function calls
    6. FunctionDispatcher executes calls (with circuit breaker)
    7. EmotionMapper and GestureLibrary prepare Live2D output
    8. Response stored in shared conversation memory
    """
    
    # Agent identity
    AGENT_NAME = "小星星"
    AGENT_NAME_EN = "Little Star"
    
    # Base personality prompt - loaded from file
    BASE_PERSONALITY = load_prompt("system/unified_agent_base", default="""你是小星星，一個溫暖、關懷、理解的AI朋友。""")
    
    def __init__(
        self,
        ai_service,
        context_manager: Optional[ConversationContextManager] = None,
        skill_activator: Optional[SkillActivator] = None,
        rag_service: Optional[HybridRetriever] = None,
        function_dispatcher = None,
        db_session = None
    ):
        """
        Initialize Unified Agent.
        
        Args:
            ai_service: AI service for generating responses
            context_manager: Conversation context manager
            skill_activator: Skill detection service
            rag_service: RAG retrieval service
            function_dispatcher: Function execution service
            db_session: Database session for form delivery tracking
        """
        self.ai_service = ai_service
        self.context_manager = context_manager or ConversationContextManager()
        self.skill_activator = skill_activator or get_skill_activator()
        self.rag_service = rag_service or get_hybrid_retriever()
        self.function_dispatcher = function_dispatcher
        self.db_session = db_session
        
        # Live2D mapping
        self.emotion_mapper = EmotionMapper()
        self.gesture_library = GestureLibrary()
        
        # Form delivery services (initialized only if db_session provided)
        self.form_delivery_tracker = None
        self.form_download_service = None
        if db_session:
            self.form_delivery_tracker = FormDeliveryTracker(db_session)
            self.form_download_service = FormDownloadService(db_session)
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        multimodal_context: Optional[Dict] = None,
        language: str = "auto"
    ) -> UnifiedAgentResponse:
        """
        Process a user message and generate response.
        
        Args:
            message: User's message text
            session_id: Session identifier
            user_id: Optional user ID
            conversation_id: Optional conversation ID (for form delivery tracking)
            multimodal_context: Optional emotion/movement data
            language: Preferred language (auto, en, zh-HK)
            
        Returns:
            UnifiedAgentResponse with message, emotion, gesture, etc.
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Get conversation context
            context = await self._get_conversation_context(session_id)
            previous_skills = context.get('previous_skills', [])
            
            # Step 2: Detect active skills
            active_skills = await self.skill_activator.detect_skills(
                message=message,
                context=context,
                multimodal=multimodal_context,
                previous_skills=previous_skills
            )
            
            # Check for crisis
            crisis_detected = any(
                s.skill_name == 'safety_crisis' for s in active_skills
            )
            
            # Step 3: Retrieve relevant knowledge
            knowledge_context = await self._retrieve_knowledge(
                query=message,
                active_skills=active_skills
            )
            
            # Step 3.5: Handle form delivery if forms detected in knowledge results
            # Requirements: 3.2, 3.4, 3.5
            # SECURITY: Anonymous users can access public forms with guest user ID
            form_delivery_messages = []
            if knowledge_context.get('results'):
                logger.info(f"🔍 Checking {len(knowledge_context['results'])} search results for forms")
                
                # BUGFIX: Deduplicate forms by document_id to avoid multiple delivery messages
                # Multiple chunks from the same form document should only trigger one delivery
                seen_form_ids = set()
                
                for idx, result in enumerate(knowledge_context['results']):
                    metadata = result.get('metadata', {})
                    logger.info(f"  Result {idx+1}: is_form={metadata.get('is_form')}, document_id={result.get('document_id')}, title={metadata.get('title', 'N/A')}")
                    if metadata.get('is_form'):
                        # BUGFIX: Form detected - handle delivery
                        logger.info(f"✅ Form detected in search results: {metadata.get('title', 'Unknown')}")
                        
                        # BUGFIX: Extract document_id from result level, not metadata level
                        document_id = result.get('document_id')
                        
                        if document_id is None:
                            logger.warning(f"⚠️  Form detected but document_id is missing in result: {result}")
                            continue  # Skip this form if document_id is missing
                        
                        # BUGFIX: Skip if we've already processed this form document
                        if document_id in seen_form_ids:
                            logger.info(f"⏭️  Skipping duplicate form document_id={document_id}")
                            continue
                        
                        seen_form_ids.add(document_id)
                        
                        # BUGFIX: Allow form delivery for anonymous users (user_id=None)
                        # Use guest user ID (-1) for anonymous users
                        # SECURITY: Guest users can access public forms with appropriate restrictions
                        if session_id:
                            # BUGFIX: Use effective_user_id to handle both authenticated and anonymous users
                            # SECURITY: Guest user ID (-1) for anonymous users, actual user_id for authenticated users
                            effective_user_id = user_id if user_id is not None else -1
                            
                            # PRIVACY: Log only IDs, not user details
                            if user_id is None:
                                logger.info(f"📋 Anonymous user (guest ID: -1) requesting form delivery")
                            else:
                                logger.info(f"📋 Authenticated user (ID: {user_id}) requesting form delivery")
                            
                            # BUGFIX: Use actual conversation_id if provided, otherwise generate fallback
                            # The conversation_id should be passed from the endpoint after creating the conversation record
                            if conversation_id is None:
                                # Fallback for backward compatibility (e.g., Live2D WebSocket)
                                conversation_id = hash(session_id) % (10 ** 8)
                                logger.warning(f"⚠️  No conversation_id provided, using fallback hash: {conversation_id}")
                            
                            # SECURITY: Use default organization_id (1) for anonymous users, actual org_id for authenticated users
                            organization_id = context.get('organization_id', 1)  # Default to 1 if not set
                            
                            # BUGFIX: Use document_id from result level
                            form_document = {
                                'id': document_id,
                                'title': metadata.get('title', 'Form'),
                                'doc_metadata': metadata
                            }
                            
                            logger.info(f"📋 Calling _handle_form_delivery for document_id={document_id}")
                            
                            # BUGFIX: Pass effective_user_id instead of user_id
                            form_message = await self._handle_form_delivery(
                                form_document=form_document,
                                user_id=effective_user_id,  # Use guest ID (-1) for anonymous users
                                conversation_id=conversation_id,
                                organization_id=organization_id,
                                user_message=message,
                                language=language
                            )
                            
                            form_delivery_messages.append(form_message)
                    else:
                        logger.debug(f"  Result {idx+1} is not a form")
                
                if not form_delivery_messages:
                    logger.info("ℹ️  No forms detected in search results")
            
            # Step 4: Build unified prompt
            prompt = self._build_unified_prompt(
                active_skills=active_skills,
                knowledge_context=knowledge_context,
                multimodal_context=multimodal_context,
                language=language
            )
            
            # Step 5: Get AI response
            available_functions = self.skill_activator.get_available_functions(active_skills)
            
            ai_response = await self._generate_response(
                user_message=message,
                system_prompt=prompt,
                context=context,
                available_functions=available_functions
            )
            
            # Step 6: Execute function calls if any
            function_results = []
            if ai_response.get('function_calls') and self.function_dispatcher:
                function_results = await self.function_dispatcher.execute_batch(
                    calls=ai_response['function_calls'],
                    session_id=session_id,
                    user_id=user_id
                )
            
            # Step 7: Map emotion and gesture for Live2D
            emotion = self._map_emotion(
                response_text=ai_response['message'],
                active_skills=active_skills,
                multimodal=multimodal_context
            )
            
            gesture = self._select_gesture(
                response_text=ai_response['message'],
                emotion=emotion,
                active_skills=active_skills
            )
            
            # Step 8: Store in conversation memory
            await self._store_turn(
                session_id=session_id,
                user_message=message,
                assistant_message=ai_response['message'],
                active_skills=[s.skill_name for s in active_skills],
                multimodal=multimodal_context
            )
            
            # Calculate processing time
            processing_time_ms = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            # Combine AI response with form delivery messages
            final_message = ai_response['message']
            if form_delivery_messages:
                # BUGFIX: Filter out empty strings (failed form deliveries)
                # Only append non-empty form delivery messages
                non_empty_messages = [msg for msg in form_delivery_messages if msg.strip()]
                if non_empty_messages:
                    final_message = final_message + "\n\n" + "\n\n".join(non_empty_messages)
            
            # Build response
            return UnifiedAgentResponse(
                message=final_message,
                session_id=session_id,
                emotion=emotion,
                gesture=gesture,
                active_skills=[s.skill_name for s in active_skills],
                skill_contexts=[s.to_dict() for s in active_skills],
                function_calls=ai_response.get('function_calls', []),
                function_results=function_results,
                citations=knowledge_context.get('citations', []),
                processing_time_ms=processing_time_ms,
                model_used=ai_response.get('model', ''),
                tokens_used=ai_response.get('tokens', 0),
                requires_follow_up=crisis_detected,
                alert_triggered=any(
                    fr.get('function') == 'alert_social_worker' 
                    for fr in function_results
                ),
                crisis_detected=crisis_detected
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            
            # Return safe error response
            return UnifiedAgentResponse(
                message="對不起，我遇到了一些問題。如果你有緊急情況，請致電999或撒瑪利亞熱線 2389 2222。",
                session_id=session_id,
                emotion="concerned",
                gesture="apologetic",
                crisis_detected=False
            )
    
    async def _get_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get conversation history and context"""
        try:
            # Use create_context which returns AgentContext
            # Extract user_id from session_id if it follows pattern "user_{id}_persistent"
            user_id = "guest"
            if session_id.startswith("user_") and "_persistent" in session_id:
                try:
                    user_id = session_id.split("_")[1]
                except:
                    pass
            
            agent_context = self.context_manager.create_context(
                user_id=user_id,
                session_id=session_id,
                user_input=""
            )
            
            # Get conversation memory
            memory = self.context_manager.get_or_create_conversation_memory(
                user_id=user_id,
                session_id=session_id
            )
            
            # Convert to dict format expected by UnifiedAgent
            return {
                'history': [
                    {'user': turn.get('user', ''), 'assistant': turn.get('assistant', '')}
                    for turn in memory.conversation_history[-10:]  # Last 10 turns
                ],
                'previous_skills': [],
                'organization_id': agent_context.user_profile.get('organization_id', 1)
            }
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return {'history': [], 'previous_skills': [], 'organization_id': 1}
    
    async def _retrieve_knowledge(
        self,
        query: str,
        active_skills: List[SkillContext]
    ) -> Dict[str, Any]:
        """Retrieve relevant knowledge for active skills"""
        try:
            from src.core.config import settings
            if not settings.rag_enabled:
                logger.info("RAG is disabled in settings")
                return {'results': [], 'citations': []}

            # Get categories for filtering (optional)
            # BUGFIX: Don't use category filtering - it excludes forms with category=None
            # Forms need to be searchable regardless of skill categories
            categories = self.skill_activator.get_knowledge_categories(active_skills)
            if categories:
                logger.info(f"Note: Skill has categories {categories}, but not filtering by them to allow form discovery")
            else:
                logger.info("No category filter - searching all documents")

            # Per-skill flag check - if RAG_PER_SKILL is empty, allow all skills
            if settings.rag_per_skill:
                skill_names = [s.skill_name for s in active_skills]
                if not any(s in settings.rag_per_skill for s in skill_names):
                    logger.info(f"Skills {skill_names} not in RAG_PER_SKILL list")
                    return {'results': [], 'citations': []}
            
            # Search knowledge base
            org_id = getattr(active_skills[0], "organization_id", None) if active_skills else None
            visibility = getattr(active_skills[0], "visibility", None) if active_skills else None

            # BUGFIX: Don't pass categories to hybrid_search - let it search all documents
            # This allows forms (which have category=None or different categories) to be found
            logger.info(f"🔎 Searching knowledge base for: {query[:50]}...")
            results = await self.rag_service.hybrid_search(
                query=query,
                skills=None,  # Don't filter by skills to allow form discovery
                top_k=7,  # BUGFIX: Increased from 3 to 7 for better form discovery (hybrid approach)
                organization_id=org_id,
                visibility=visibility
                # NOTE: Not passing skills/categories to allow form discovery
            )
            
            logger.info(f"📚 Knowledge search returned {len(results.get('results', []))} results")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {e}")
            return {'results': [], 'citations': []}
    
    def _build_unified_prompt(
        self,
        active_skills: List[SkillContext],
        knowledge_context: Dict[str, Any],
        multimodal_context: Optional[Dict],
        language: str
    ) -> str:
        """Build the unified system prompt"""
        
        prompt_parts = []
        
        # BUGFIX: Add language instruction at the TOP with strong emphasis
        # This overrides the base personality's language preferences
        if language == "en":
            prompt_parts.append("🌍 CRITICAL LANGUAGE OVERRIDE: You MUST respond in English for this conversation.")
            prompt_parts.append("The user has explicitly requested English. Ignore any other language instructions below.")
            prompt_parts.append("All your responses in this conversation must be in English.\n")
        elif language == "zh-HK":
            prompt_parts.append("🌍 語言設定：請用繁體中文（廣東話）回應。\n")
        else:
            prompt_parts.append("🌍 語言設定：根據用戶的語言自動選擇回應語言。\n")
        
        # Add base personality
        prompt_parts.append(self.BASE_PERSONALITY)
        
        # Add skill-specific prompts
        skill_additions = self.skill_activator.get_combined_prompt_addition(active_skills)
        if skill_additions:
            prompt_parts.append("\n=== 當前啟動的技能 ===")
            prompt_parts.append(skill_additions)
        
        # Add multimodal context if available
        if multimodal_context:
            emotion_data = multimodal_context.get('emotion')
            movement_data = multimodal_context.get('movement')
            
            multimodal_info = "\n=== 多模態觀察 ==="
            
            if emotion_data:
                emotion = emotion_data.get('emotion', 'neutral')
                intensity = emotion_data.get('intensity', 0)
                multimodal_info += f"\n用戶表情：{emotion}（強度 {intensity}/5）"
            
            if movement_data:
                energy = movement_data.get('energy_level', 'medium')
                posture = movement_data.get('posture', 'neutral')
                multimodal_info += f"\n用戶姿態：{posture}，能量水平：{energy}"
            
            prompt_parts.append(multimodal_info)
        
        # Add relevant knowledge
        if knowledge_context.get('results'):
            knowledge_info = "\n=== 相關知識參考 ==="
            for i, result in enumerate(knowledge_context['results'][:3], 1):
                content = result.get('content', '')[:300]
                knowledge_info += f"\n[{i}] {content}..."
            
            prompt_parts.append(knowledge_info)
            prompt_parts.append("\n請在回應中自然地融入上述知識，但不要直接引用編號。")
        
        # BUGFIX: Reinforce language instruction at the end
        if language == "en":
            prompt_parts.append("\n⚠️ REMINDER: Respond in English only. The user requested English language.")
        
        return "\n".join(prompt_parts)
    
    async def _generate_response(
        self,
        user_message: str,
        system_prompt: str,
        context: Dict[str, Any],
        available_functions: List[str]
    ) -> Dict[str, Any]:
        """Generate AI response"""
        try:
            # Build messages list
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            history = context.get('history', [])
            for turn in history[-10:]:  # Last 10 turns
                messages.append({"role": "user", "content": turn.get('user', '')})
                messages.append({"role": "assistant", "content": turn.get('assistant', '')})
            
            # Add current message
            messages.append({"role": "user", "content": user_message})
            
            # Generate response (don't pass functions parameter - not supported)
            response = await self.ai_service.chat_completion(
                messages=messages
            )
            
            return {
                'message': response.get('content', ''),
                'function_calls': [],  # Function calling not used in this flow
                'model': response.get('model', ''),
                'tokens': response.get('usage', {}).get('total_tokens', 0)
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                'message': "我現在有些問題，請稍後再試。",
                'function_calls': []
            }
    
    def _map_emotion(
        self,
        response_text: str,
        active_skills: List[SkillContext],
        multimodal: Optional[Dict]
    ) -> str:
        """Map response to Live2D emotion"""
        try:
            # Get primary skill for emotion hints
            primary_skill = active_skills[0] if active_skills else None
            
            # Use emotion mapper
            emotion = self.emotion_mapper.map_to_emotion(
                text=response_text,
                skill_name=primary_skill.skill_name if primary_skill else None
            )
            
            return emotion
            
        except Exception:
            return "neutral"
    
    def _select_gesture(
        self,
        response_text: str,
        emotion: str,
        active_skills: List[SkillContext]
    ) -> str:
        """Select appropriate Live2D gesture"""
        try:
            gesture = self.gesture_library.select_gesture(
                emotion=emotion,
                response_length=len(response_text)
            )
            
            return gesture
            
        except Exception:
            return "idle"
    
    async def _store_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        active_skills: List[str],
        multimodal: Optional[Dict]
    ) -> None:
        """Store conversation turn in memory"""
        try:
            # Extract user_id from session_id
            user_id = "guest"
            if session_id.startswith("user_") and "_persistent" in session_id:
                try:
                    user_id = session_id.split("_")[1]
                except:
                    pass
            
            # Get or create conversation memory
            memory = self.context_manager.get_or_create_conversation_memory(
                user_id=user_id,
                session_id=session_id
            )
            
            # Store user message
            self.context_manager.update_conversation_history(
                memory=memory,
                content=user_message,
                role="user",
                agent_id=None,
                metadata={
                    'active_skills': active_skills,
                    'multimodal': multimodal,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            # Store assistant message
            self.context_manager.update_conversation_history(
                memory=memory,
                content=assistant_message,
                role="assistant",
                agent_id=active_skills[0] if active_skills else "wellness_coach",
                metadata={
                    'active_skills': active_skills,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error storing turn: {e}")
    
    def _detect_re_request(self, message: str) -> bool:
        """
        Detect if user is explicitly requesting a form again.
        
        Args:
            message: User's message text
            
        Returns:
            bool: True if re-request detected, False otherwise
            
        Requirements: 7.1, 7.2
        """
        # Normalize message for matching
        message_lower = message.lower()
        
        # Re-request phrases (English and Chinese)
        re_request_phrases = [
            "send me that form again",
            "send that form again",
            "i need the form again",
            "i need that form again",
            "resend form",
            "resend the form",
            "send again",
            "再發一次",
            "再傳一次",
            "再發送",
            "再給我",
            "重新發送",
            "重新傳送"
        ]
        
        # Check if any re-request phrase is in the message
        return any(phrase in message_lower for phrase in re_request_phrases)
    
    def _is_asking_for_form(self, message: str) -> bool:
        """
        Detect if user is asking for a form document.
        
        This prevents form delivery when user is just greeting or asking unrelated questions.
        
        Args:
            message: User's message text
            
        Returns:
            bool: True if user is asking for a form, False otherwise
        """
        # Normalize message for matching
        message_lower = message.lower()
        
        # Form-related keywords (English and Chinese)
        form_keywords = [
            # English
            "form", "application", "document", "申請", "表格", "文件",
            "download", "下載", "need", "需要", "want", "想要",
            "get", "拿", "取得", "obtain", "索取",
            # Specific form names
            "樂悠咭", "綜援", "cssa", "elder card"
        ]
        
        # Check if any form keyword is in the message
        return any(keyword in message_lower for keyword in form_keywords)
    
    def _select_language_version(
        self,
        form_document: Dict,
        user_language: str
    ) -> tuple[Dict, bool, str]:
        """
        Select the appropriate language version of a form based on user preference.
        
        This method:
        1. Checks if the form has multiple language versions
        2. Selects the version matching user's language preference
        3. Falls back to the current document if preferred language unavailable
        4. Returns whether fallback occurred and available language
        
        Args:
            form_document: Document metadata including language_versions
            user_language: User's preferred language code (e.g., "en", "zh-HK", "zh-CN")
            
        Returns:
            tuple: (selected_document_dict, is_fallback, selected_language)
                - selected_document_dict: Document metadata for selected version
                - is_fallback: True if fallback to different language occurred
                - selected_language: Language code of selected version
                
        Requirements: 11.1, 11.2, 11.3, 11.4
        
        Security:
            - PRIVACY: No PII in logs, only document IDs
        """
        doc_metadata = form_document.get("doc_metadata", {})
        language_versions = doc_metadata.get("language_versions", {})
        
        # If no language versions defined, return current document
        if not language_versions:
            # PRIVACY: Log only document ID, not content
            logger.debug(f"No language versions for document {form_document.get('id')}")
            return form_document, False, user_language
        
        # Normalize user language (handle variations like zh-CN, zh-HK, zh)
        normalized_lang = user_language.lower()
        
        # Check if user's preferred language is available
        # Requirements: 11.2
        if normalized_lang in language_versions:
            target_doc_id = language_versions[normalized_lang]
            # In a full implementation, we would fetch the target document from DB
            # For now, we'll update the current document's ID to indicate version selection
            selected_doc = form_document.copy()
            selected_doc["id"] = target_doc_id
            logger.info(f"Selected language version {normalized_lang} (doc {target_doc_id})")
            return selected_doc, False, normalized_lang
        
        # Fallback: Use first available language version
        # Requirements: 11.4
        if language_versions:
            fallback_lang = next(iter(language_versions.keys()))
            fallback_doc_id = language_versions[fallback_lang]
            selected_doc = form_document.copy()
            selected_doc["id"] = fallback_doc_id
            # PRIVACY: Log only IDs and language codes
            logger.info(
                f"Language {normalized_lang} not available for doc {form_document.get('id')}, "
                f"falling back to {fallback_lang} (doc {fallback_doc_id})"
            )
            return selected_doc, True, fallback_lang
        
        # No versions available, return original
        return form_document, False, user_language
    
    def _filter_forms_by_type(
        self,
        form_documents: list[Dict],
        form_type: str = None
    ) -> list[Dict]:
        """
        Filter form documents by form type.
        
        Args:
            form_documents: List of form document metadata
            form_type: Form type to filter by (e.g., "application", "assessment", "registration", "consent")
                      If None, returns all forms
            
        Returns:
            list[Dict]: Filtered list of form documents
            
        Requirements: 12.4
        
        Security:
            - PRIVACY: No PII in logs, only document IDs and types
        """
        if not form_type:
            return form_documents
        
        # Normalize form type for comparison
        normalized_type = form_type.lower().strip()
        
        filtered_forms = []
        for form_doc in form_documents:
            doc_metadata = form_doc.get("doc_metadata", {})
            doc_form_type = doc_metadata.get("form_type", "").lower().strip()
            
            if doc_form_type == normalized_type:
                filtered_forms.append(form_doc)
        
        # PRIVACY: Log only counts and types, not content
        logger.debug(
            f"Filtered {len(form_documents)} forms by type '{normalized_type}': "
            f"{len(filtered_forms)} matches"
        )
        
        return filtered_forms
    def _select_language_version(
            self,
            form_document: Dict,
            user_language: str
        ) -> tuple[Dict, bool, str]:
            """
            Select the appropriate language version of a form based on user preference.

            This method:
            1. Checks if the form has multiple language versions
            2. Selects the version matching user's language preference
            3. Falls back to the current document if preferred language unavailable
            4. Returns whether fallback occurred and available language

            Args:
                form_document: Document metadata including language_versions
                user_language: User's preferred language code (e.g., "en", "zh-HK", "zh-CN")

            Returns:
                tuple: (selected_document_dict, is_fallback, selected_language)
                    - selected_document_dict: Document metadata for selected version
                    - is_fallback: True if fallback to different language occurred
                    - selected_language: Language code of selected version

            Requirements: 11.1, 11.2, 11.3, 11.4

            Security:
                - PRIVACY: No PII in logs, only document IDs
            """
            doc_metadata = form_document.get("doc_metadata", {})
            language_versions = doc_metadata.get("language_versions", {})

            # If no language versions defined, return current document
            if not language_versions:
                # PRIVACY: Log only document ID, not content
                logger.debug(f"No language versions for document {form_document.get('id')}")
                return form_document, False, user_language

            # Normalize user language (handle variations like zh-CN, zh-HK, zh)
            normalized_lang = user_language.lower()

            # Check if user's preferred language is available
            # Requirements: 11.2
            if normalized_lang in language_versions:
                target_doc_id = language_versions[normalized_lang]
                # In a full implementation, we would fetch the target document from DB
                # For now, we'll update the current document's ID to indicate version selection
                selected_doc = form_document.copy()
                selected_doc["id"] = target_doc_id
                logger.info(f"Selected language version {normalized_lang} (doc {target_doc_id})")
                return selected_doc, False, normalized_lang

            # Fallback: Use first available language version
            # Requirements: 11.4
            if language_versions:
                fallback_lang = next(iter(language_versions.keys()))
                fallback_doc_id = language_versions[fallback_lang]
                selected_doc = form_document.copy()
                selected_doc["id"] = fallback_doc_id
                # PRIVACY: Log only IDs and language codes
                logger.info(
                    f"Language {normalized_lang} not available for doc {form_document.get('id')}, "
                    f"falling back to {fallback_lang} (doc {fallback_doc_id})"
                )
                return selected_doc, True, fallback_lang

            # No versions available, return original
            return form_document, False, user_language

    
    async def _handle_form_delivery(
        self,
        form_document: Dict,
        user_id: int,
        conversation_id: int,
        organization_id: int,
        user_message: str,
        language: str = "auto"
    ) -> str:
        """
        Handle form delivery with tracking and duplicate prevention.
        
        This method:
        1. Checks if form was previously delivered in this conversation
        2. Detects if user is explicitly re-requesting the form
        3. Either delivers the form or references previous delivery
        4. Records delivery events and creates audit logs
        
        Args:
            form_document: Document metadata including id, title, doc_metadata
            user_id: ID of the user receiving the form
            conversation_id: ID of the current conversation
            organization_id: ID of the user's organization
            user_message: The user's original message (for re-request detection)
            language: User's preferred language
            
        Returns:
            str: Formatted response message with form delivery or reference
            
        Requirements: 3.2, 3.4, 3.5, 4.1, 4.2, 4.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.3, 7.4, 7.5, 11.1, 11.2, 11.4
        
        Security:
            - ORGANIZATION: Enforces organization-level isolation
            - AUTHENTICATION: Generates JWT-based download links
            - AUDIT: Records all deliveries for compliance
        """
        # Check if services are available
        if not self.form_delivery_tracker or not self.form_download_service:
            logger.warning("Form delivery services not initialized - skipping download link")
            # BUGFIX: Don't show error message - just skip download link
            # The AI will still answer using RAG content
            return ""  # Return empty string instead of error message
        
        # Step 0: Select appropriate language version
        # Requirements: 11.1, 11.2, 11.4
        selected_form, is_language_fallback, selected_language = self._select_language_version(
            form_document, language
        )
        
        document_id = selected_form.get("id")
        if not document_id:
            logger.error("Form document missing ID - skipping download link")
            # BUGFIX: Don't show error message - just skip download link
            # The AI will still answer using RAG content
            return ""  # Return empty string instead of error message
        
        try:
            # Step 0: Check if user is actually asking for a form
            # This prevents showing form links when user says "hi" or other unrelated messages
            is_asking_for_form = self._is_asking_for_form(user_message)
            
            # Step 1: Check if form was previously delivered
            # Requirements: 6.1
            previous_delivery = await self.form_delivery_tracker.was_delivered(
                user_id=user_id,
                conversation_id=conversation_id,
                document_id=document_id
            )
            
            # Step 2: Detect re-request intent
            # Requirements: 7.1, 7.2
            is_re_request = self._detect_re_request(user_message)
            
            # Step 3: Decide delivery strategy
            # BUGFIX: Only show previous delivery reference if user is actually asking for a form
            if previous_delivery and not is_re_request and is_asking_for_form:
                # Reference previous delivery instead of re-delivering
                # Requirements: 6.2, 6.3, 6.4, 6.5
                return self._format_previous_delivery_reference(
                    form_document=selected_form,
                    previous_delivery=previous_delivery,
                    language=selected_language,
                    is_language_fallback=is_language_fallback
                )
            
            # BUGFIX: If user is not asking for a form and it's not a re-request, skip delivery
            if not is_asking_for_form and not is_re_request:
                logger.info(f"User not asking for form - skipping delivery for document {document_id}")
                return ""  # Return empty string - no form delivery message
            
            # Step 4: Deliver the form (initial or re-request)
            delivery_method = "re-request" if previous_delivery else "initial"
            
            # Generate download link
            # Requirements: 4.1, 4.2
            download_token = self.form_download_service.generate_download_link(
                document_id=document_id,
                user_id=user_id,
                organization_id=organization_id,
                expiration_minutes=60
            )
            
            # Calculate link expiration
            link_expiration = datetime.utcnow() + timedelta(minutes=60)
            
            # Record delivery
            # Requirements: 5.1, 5.2, 5.3, 7.4
            await self.form_delivery_tracker.record_delivery(
                user_id=user_id,
                conversation_id=conversation_id,
                document_id=document_id,
                delivery_method=delivery_method,
                organization_id=organization_id,
                download_link=download_token,
                link_expiration=link_expiration
            )
            
            # Format response
            # Requirements: 4.2, 4.5, 7.5, 11.3, 11.4
            return self._format_form_delivery_response(
                form_document=selected_form,
                download_token=download_token,
                is_re_request=is_re_request,
                language=selected_language,
                is_language_fallback=is_language_fallback
            )
            
        except Exception as e:
            logger.error(f"Error handling form delivery: {e}", exc_info=True)
            # BUGFIX: Don't show error message - just skip download link
            # The AI will still answer using RAG content
            # Requirements: User wants RAG to work even if download fails
            logger.info("Form delivery failed, but RAG content will still be used in AI response")
            return ""  # Return empty string instead of error message
    
    def _format_form_delivery_response(
        self,
        form_document: Dict,
        download_token: str,
        is_re_request: bool,
        language: str,
        is_language_fallback: bool = False
    ) -> str:
        """
        Format the form delivery response message.
        
        Args:
            form_document: Document metadata
            download_token: JWT token for download
            is_re_request: Whether this is a re-delivery
            language: User's preferred language
            is_language_fallback: Whether fallback to different language occurred
            
        Returns:
            str: Formatted response message
            
        Requirements: 4.2, 4.5, 7.5, 11.3, 11.4, 12.2
        """
        doc_metadata = form_document.get("doc_metadata", {})
        title = form_document.get("title", "表格")
        form_type = doc_metadata.get("form_type", "")
        submission_instructions = doc_metadata.get("submission_instructions", "")
        
        # Build download URL
        download_url = f"/api/v1/forms/download/{download_token}"
        
        # Format response based on language
        if language == "en":
            # English response
            response_parts = []
            
            # Re-request acknowledgment (Requirement 7.5)
            if is_re_request:
                response_parts.append("Here is the form again as requested.")
            
            # Form type context (Requirement 12.2)
            if form_type:
                type_text = f"the {form_type} form"
            else:
                type_text = "the form"
            
            response_parts.append(f"I've prepared {type_text} for you: **{title}**")
            
            # Language fallback note (Requirements 11.3, 11.4)
            if is_language_fallback:
                response_parts.append(f"\n*Note: This form is available in {language.upper()}.*")
            
            # Download link (Requirement 4.2)
            response_parts.append(f"\n\n📄 [Download Form]({download_url})")
            
            # Submission instructions (Requirement 4.5)
            if submission_instructions:
                response_parts.append(f"\n\n**Instructions:** {submission_instructions}")
            else:
                response_parts.append("\n\nPlease complete the form and return it to your caregiver.")
            
            return "\n".join(response_parts)
        else:
            # Chinese response (default)
            response_parts = []
            
            # Re-request acknowledgment (Requirement 7.5)
            if is_re_request:
                response_parts.append("好的，我再次為你準備這份表格。")
            
            # Form type context (Requirement 12.2)
            form_type_map = {
                "application": "申請",
                "assessment": "評估",
                "registration": "登記",
                "consent": "同意"
            }
            type_text = form_type_map.get(form_type, "")
            if type_text:
                response_parts.append(f"這是{type_text}表格：**{title}**")
            else:
                response_parts.append(f"這是表格：**{title}**")
            
            # Language fallback note (Requirements 11.3, 11.4)
            if is_language_fallback:
                lang_display = {"en": "英文", "zh-hk": "繁體中文", "zh-cn": "簡體中文"}.get(
                    language.lower(), language.upper()
                )
                response_parts.append(f"\n*注意：此表格提供{lang_display}版本。*")
            
            # Download link (Requirement 4.2)
            response_parts.append(f"\n\n📄 [下載表格]({download_url})")
            
            # Submission instructions (Requirement 4.5)
            if submission_instructions:
                response_parts.append(f"\n\n**提交說明：** {submission_instructions}")
            else:
                response_parts.append("\n\n請填寫完成後交給你的照顧者。")
            
            return "\n".join(response_parts)
    
    def _format_previous_delivery_reference(
        self,
        form_document: Dict,
        previous_delivery: Dict,
        language: str,
        is_language_fallback: bool = False
    ) -> str:
        """
        Format a reference to a previously delivered form.
        
        Args:
            form_document: Document metadata
            previous_delivery: Previous delivery record
            language: User's preferred language
            is_language_fallback: Whether fallback to different language occurred
            
        Returns:
            str: Formatted reference message
            
        Requirements: 6.3, 6.4, 11.3, 11.4
        """
        title = form_document.get("title", "表格")
        delivered_at = previous_delivery.get("delivered_at")
        
        # Format timestamp
        if delivered_at:
            if isinstance(delivered_at, str):
                delivered_at = datetime.fromisoformat(delivered_at)
            time_str = delivered_at.strftime("%H:%M")
        else:
            time_str = "earlier"
        
        if language == "en":
            message = (
                f"I already shared the form **{title}** with you earlier in our conversation "
                f"(at {time_str}). You can scroll up to find the download link. "
                f"If you need me to send it again, just let me know!"
            )
            # Add language note if fallback occurred (Requirements 11.3, 11.4)
            if is_language_fallback:
                message += f"\n\n*Note: This form is available in {language.upper()}.*"
            return message
        else:
            message = (
                f"我已經在我們的對話中分享過這份表格 **{title}** "
                f"（時間：{time_str}）。你可以向上滾動找到下載連結。"
                f"如果你需要我再次發送，請告訴我！"
            )
            # Add language note if fallback occurred (Requirements 11.3, 11.4)
            if is_language_fallback:
                lang_display = {"en": "英文", "zh-hk": "繁體中文", "zh-cn": "簡體中文"}.get(
                    language.lower(), language.upper()
                )
                message += f"\n\n*注意：此表格提供{lang_display}版本。*"
            return message
    
    def _format_fallback_response(
        self,
        form_document: Dict,
        language: str
    ) -> str:
        """
        Format a fallback response when form delivery services are unavailable.
        
        Args:
            form_document: Document metadata
            language: User's preferred language
            
        Returns:
            str: Formatted fallback message
        """
        title = form_document.get("title", "表格")
        
        if language == "en":
            return (
                f"I found the form **{title}** for you, but I'm having trouble "
                f"generating a download link right now. Please contact your caregiver "
                f"to request this form."
            )
        else:
            return (
                f"我找到了表格 **{title}**，但現在無法生成下載連結。"
                f"請聯絡你的照顧者索取這份表格。"
            )


# Factory function
def create_unified_agent(ai_service, **kwargs) -> UnifiedAgent:
    """
    Create a unified agent instance.
    
    Args:
        ai_service: AI service for generating responses
        **kwargs: Additional components (context_manager, skill_activator, etc.)
        
    Returns:
        UnifiedAgent instance
    """
    return UnifiedAgent(ai_service=ai_service, **kwargs)

