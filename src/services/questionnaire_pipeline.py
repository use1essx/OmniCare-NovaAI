"""
Multi-Stage Questionnaire Pipeline Orchestrator
Coordinates the 4-stage AI questionnaire generation process
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
from pathlib import Path
from sqlalchemy.orm import Session

from src.ai.unified_ai_client import AIRequest
from src.ai.providers.nova_bedrock_client import get_nova_client
from src.database.models_multistage_questionnaire import (
    QuestionnaireAnalysis,
    GeneratedQuestionCandidate,
    QuestionnaireKnowledgeBase,
    AIGenerationJob
)

logger = logging.getLogger(__name__)





# Coordinates the 4-stage AI questionnaire generation process
import logging  # noqa: E402


logger = logging.getLogger(__name__)


class MultiStageQuestionnairePipeline:
    """Orchestrate multi-stage AI questionnaire generation"""
    
    def __init__(self, db: Session):
        self.client = get_nova_client()
        self.db = db
        self.prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "questionnaire_generation"
        logger.info(f"📁 Prompt directory: {self.prompt_dir}")
    
    async def _call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "questionnaire",
        temperature: float = 0.5,
        max_tokens: int = 4000
    ) -> str:
        """
        Helper method to call AI with unified client interface.
        Replaces the old call_model method from MultiModelAIClient.
        """
        request = AIRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens
        )
        response = await self.client.make_request(request=request)
        return response.content
    
    def _load_prompt(self, prompt_name: str) -> str:
        """Load structured prompt from file"""
        prompt_file = self.prompt_dir / f"{prompt_name}.txt"
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"✅ Loaded prompt: {prompt_name}")
                return content
        except FileNotFoundError:
            logger.error(f"❌ Prompt file not found: {prompt_file}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading prompt {prompt_name}: {e}")
            raise
    
    def _calculate_document_hash(self, text: str) -> str:
        """Calculate SHA-256 hash of document for caching"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    async def _generate_document_summary(
        self,
        document_text: str,
        analysis_map: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive summary for AI agent's question base
        """
        try:
            # Load summary generation prompt
            summary_prompt_template = self._load_prompt("summary_generation")
            
            # Format prompt with document and analysis
            prompt = f"""{summary_prompt_template}

DOCUMENT TEXT:
{document_text[:50000]}

ANALYSIS RESULTS:
{json.dumps(analysis_map, indent=2)}

IMPORTANT: You MUST generate a 'suggested_title' for this questionnaire based on the document content (e.g., 'Child Development Screening (5-7 Years)' or 'General Anxiety Assessment').

Generate the comprehensive summary JSON now, including 'suggested_title':
"""
            
            # Call AI to generate summary
            response = await self._call_ai(
                system_prompt="You are a healthcare document analysis expert creating knowledge base entries for AI agents.",
                user_prompt=prompt,
                task_type="report_generation",
                temperature=0.5,
                max_tokens=4000
            )
            
            # Parse JSON response
            summary_data = self._safe_json_parse(response)
            
            return summary_data if isinstance(summary_data, dict) else None
            
        except Exception as e:
            logger.error(f"Error generating document summary: {e}")
            return None
    
    def _update_job_progress(self, job_id: UUID, status: str, stage: str, progress: int):
        """Update job progress in database"""
        job = self.db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
        if job:
            job.status = status
            job.current_stage = stage
            job.progress_percentage = progress
            
            # Update usage stats if client available
            if hasattr(self, 'client'):
                usage = self.client.get_usage_summary()
                job.total_tokens_used = usage.get("total_tokens", 0)
                job.estimated_cost_usd = usage.get("total_cost_usd", 0.0)
            
            self.db.commit()
            logger.info(f"📊 Job {job_id}: {stage} - {progress}%")

    def _log_action(self, job_id: UUID, message: str, level: str = "info"):
        """Log detailed AI action to job record for Superadmin Console"""
        try:
            timestamp = datetime.utcnow().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "message": message,
                "level": level
            }
            
            job = self.db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
            if job:
                current_logs = job.logs or []
                if not isinstance(current_logs, list):
                    current_logs = []
                current_logs.append(log_entry)
                job.logs = current_logs
                # Force update for JSONB
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(job, "logs")
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log action for job {job_id}: {e}")
    
    async def _stage0_extract_document(
        self,
        document_text: str,
        job_id: UUID
    ) -> Dict[str, Any]:
        """
        Stage 0: Document Extraction (NEW - 1-2 minutes)
        Extract ALL existing questions/items from the uploaded document
        This is the foundation for document-faithful generation
        """
        self._update_job_progress(job_id, "extracting", "Stage 0: Extracting Document Content", 5)
        
        logger.info("📄 Stage 0: Extracting questions from document...")
        
        # Log document text info for debugging
        doc_length = len(document_text)
        doc_preview = document_text[:500].replace('\n', ' ')[:200]
        logger.info(f"   Document length: {doc_length} characters")
        logger.info(f"   Document preview: {doc_preview}...")
        self._log_action(job_id, f"📄 Document has {doc_length} characters")
        self._log_action(job_id, f"📝 Preview: {doc_preview[:150]}...", "info")
        
        if doc_length < 100:
            logger.warning(f"⚠️ Document is very short ({doc_length} chars) - may not contain enough content")
            self._log_action(job_id, f"⚠️ WARNING: Document is very short ({doc_length} chars)", "error")
        
        # Load extraction prompt
        extraction_prompt_template = self._load_prompt("stage0_document_extraction")
        
        # Format prompt with document
        extraction_prompt = f"{extraction_prompt_template}\n\nDOCUMENT TO EXTRACT FROM:\n{document_text[:150000]}"
        
        # Call AI to extract document structure
        self._log_action(job_id, "🤖 Sending document to Nova for structural extraction...")
        result = await self._call_ai(
            system_prompt="You are a document extraction specialist. Your job is to EXTRACT existing questions from documents, NOT to generate new ones.",
            user_prompt=extraction_prompt,
            task_type="report_generation",
            temperature=0.2,  # Low temperature for accurate extraction
            max_tokens=5000
        )
        
        # Parse extraction result
        raw_response = result
        logger.debug(f"Raw AI response length: {len(raw_response)}")
        logger.debug(f"Raw AI response start: {raw_response[:200]}")
        
        extracted_data = self._safe_json_parse(raw_response)
        
        # Check if parsing succeeded
        if not extracted_data:
            logger.error("❌ JSON parsing failed!")
            logger.error(f"Full raw response ({len(raw_response)} chars):")
            logger.error(raw_response)
            self._log_action(job_id, "❌ Failed to parse AI response as JSON", "error")
            self._log_action(job_id, f"📄 Full response ({len(raw_response)} chars): {raw_response[:500]}...", "error")
        
        total_items = extracted_data.get('total_items_found', 0)
        num_domains = len(extracted_data.get('domains', []))
        
        # Log extraction results
        self._log_action(job_id, f"📥 Received extraction: {total_items} items, {num_domains} domains", "success" if total_items > 0 else "error")
        
        # If 0 items found, log the AI's response for debugging
        if total_items == 0:
            logger.warning("⚠️ Stage 0 extracted 0 items!")
            logger.warning(f"   AI response preview: {raw_response[:500]}")
            self._log_action(job_id, f"🔍 AI Response (0 items): {raw_response[:300]}...", "error")
            
            # Check if the AI provided an explanation
            explanation = extracted_data.get('explanation', '') or extracted_data.get('notes', '')
            if explanation:
                logger.info(f"   AI explanation: {explanation}")
                self._log_action(job_id, f"💬 AI says: {explanation}", "info")
        
        logger.info(f"✅ Stage 0 complete: Extracted {total_items} items from document")
        logger.info(f"   Document type: {extracted_data.get('document_type', 'unknown')}")
        logger.info(f"   Domains found: {num_domains}")
        
        return extracted_data
    

    async def _stage1_analyze(self, document_text: str, job_id: UUID) -> QuestionnaireAnalysis:
        """
        Stage 1: Document Analysis (2-3 minutes)
        Parallel: Gemini (structure) + Grok (domain analysis)
        """
        self._update_job_progress(job_id, "analyzing", "Stage 1: Document Analysis", 10)
        
        logger.info("📖 Stage 1: Analyzing document...")
        
        # Check cache first
        doc_hash = self._calculate_document_hash(document_text)
        existing = self.db.query(QuestionnaireAnalysis).filter(
            QuestionnaireAnalysis.document_hash == doc_hash
        ).first()
        
        if existing:
            # IMPORTANT: Refresh to reattach to current session
            self.db.refresh(existing)
            logger.info(f"✅ Using cached analysis (ID: {existing.id})")
            
            # Update job with analysis_id (Fix for missing analysis_id)
            job = self.db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
            if job:
                logger.info(f"DEBUG: Updating job {job_id} with cached analysis_id {existing.id}")
                job.analysis_id = existing.id
                self.db.commit()
                
            return existing
        
        # Load structured prompts
        structure_prompt_template = self._load_prompt("stage1_structure_analysis")
        domain_prompt_template = self._load_prompt("stage1_domain_analysis")
        
        # Format prompts with document text
        structure_prompt = f"{structure_prompt_template}\n\nDOCUMENT:\n{document_text[:100000]}"
        domain_prompt = f"{domain_prompt_template}\n\nDOCUMENT:\n{document_text[:60000]}"
        
        # Parallel analysis calls
        self._log_action(job_id, "🤖 dispatching parallel analysis: Gemini (Structure) + Grok (Domain)...")
        results = await self.client.call_models_parallel([
            {
                "model_key": "llama-70b",
                "system_prompt": "You are a document structure analyst specializing in medical and psychological documents.",
                "user_prompt": structure_prompt,
                "temperature": 0.3,
                "max_tokens": 4000
            },
            {
                "model_key": "mixtral",
                "system_prompt": "You are a medical/psychological domain expert. Think step-by-step and show your reasoning.",
                "user_prompt": domain_prompt,
                "temperature": 0.5,
                "max_tokens": 4000
            }
        ])
        
        self._log_action(job_id, "📥 Received parallel analysis results", "success")
        
        # Parse results
        structure_data = self._safe_json_parse(results[0]["content"])
        domain_data = self._safe_json_parse(results[1]["content"])
        
        # Combine into analysis_map
        analysis_map = {
            "document_hash": doc_hash,
            "structure": structure_data,
            "domain": domain_data,
            "question_categories": self._extract_categories(structure_data, domain_data),
            "age_bands": self._extract_age_bands(domain_data),
            "assessment_topics": self._extract_topics(structure_data, domain_data)
        }
        
        # Save to database
        analysis = QuestionnaireAnalysis(
            document_hash=doc_hash,
            structure_analysis=structure_data,
            domain_analysis=domain_data,
            analysis_map=analysis_map,
            models_used=["meta-llama/llama-3.1-70b-instruct", "mistralai/mixtral-8x7b-instruct"],
            processing_time_seconds=0  # Will update at end
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        # Update job with analysis_id
        job = self.db.query(AIGenerationJob).filter(AIGenerationJob.job_id == job_id).first()
        if job:
            logger.info(f"DEBUG: Updating job {job_id} with analysis_id {analysis.id}")
            job.analysis_id = analysis.id
            self.db.commit()
        else:
            logger.error(f"DEBUG: Job {job_id} not found for update!")
        
        # Generate comprehensive summary for AI agent
        logger.info("📝 Generating comprehensive document summary...")
        summary_data = await self._generate_document_summary(document_text, analysis_map)
        
        # Update analysis with summary data
        if summary_data:
            analysis.document_summary = summary_data.get('executive_summary', '')
            analysis.key_insights = summary_data.get('key_insights', [])
            
            # Store suggested title in domain_analysis (safe place for extra metadata)
            if 'suggested_title' in summary_data:
                current_domain = dict(analysis.domain_analysis) if analysis.domain_analysis else {}
                current_domain['suggested_title'] = summary_data['suggested_title']
                analysis.domain_analysis = current_domain
                logger.info(f"   Suggested title: {summary_data['suggested_title']}")
                
            self.db.commit()
            logger.info("✅ Document summary generated")
        
        self._update_job_progress(job_id, "analyzing", "Stage 1: Complete", 25)
        logger.info(f"✅ Stage 1 complete: Analysis ID {analysis.id}")
        
        return analysis
    
    async def _stage1_5_build_consensus(
        self,
        document_text: str,
        extracted_data: Dict[str, Any],
        analysis: QuestionnaireAnalysis,
        job_id: UUID
    ) -> Dict[str, Any]:
        """
        Stage 1.5: Multi-AI Consensus (NEW - 2-3 minutes)
        3 AI models independently analyze, then build consensus
        This ensures accurate understanding before question generation
        """
        self._update_job_progress(job_id, "consensus", "Stage 1.5: Building AI Consensus", 20)
        
        logger.info("🤝 Stage 1.5: Building multi-AI consensus...")
        
        # Prepare document summary for AI models
        doc_summary = f"""
EXTRACTED DOCUMENT STRUCTURE:
{json.dumps(extracted_data, indent=2)[:10000]}

DOCUMENT TEXT (first 50k chars):
{document_text[:50000]}
"""
        
        # Call 3 different AI models in parallel for independent analysis
        consensus_calls = [
            {
                "model_key": "llama-70b",
                "system_prompt": "You are analyzing a healthcare document. Focus on structure, domains, and assessment methodology.",
                "user_prompt": f"Analyze this document and identify its key characteristics. Return your analysis as a valid JSON object.\n\n{doc_summary}",
                "temperature": 0.3,
                "max_tokens": 3000
            },
            {
                "model_key": "mixtral",
                "system_prompt": "You are analyzing a healthcare document. Focus on clinical content, scoring systems, and assessment items.",
                "user_prompt": f"Analyze this document and identify its assessment framework. Return your analysis as a valid JSON object.\n\n{doc_summary}",
                "temperature": 0.3,
                "max_tokens": 3000
            },
            {
                "model_key": "llama-8b",
                "system_prompt": "You are analyzing a healthcare document. Focus on question types, target population, and practical administration.",
                "user_prompt": f"Analyze this document and identify its practical characteristics. Return your analysis as a valid JSON object.\n\n{doc_summary}",
                "temperature": 0.3,
                "max_tokens": 3000
            }
        ]
        
        # Execute parallel analysis
        logger.info("   Running 3 AI models in parallel...")
        self._log_action(job_id, "🤖 Stage 1.5: Dispatching 3 independent AI analysts (Gemini, Grok, GPT-4o)...")
        results = await self.client.call_models_parallel(consensus_calls)
        
        # Parse individual analyses
        gemini_analysis = self._safe_json_parse(results[0]["content"]) if results[0]["success"] else {}
        grok_analysis = self._safe_json_parse(results[1]["content"]) if results[1]["success"] else {}
        gpt_analysis = self._safe_json_parse(results[2]["content"]) if results[2]["success"] else {}
        
        self._log_action(job_id, "📥 Received independent analyses from all models. Starting consensus moderation...")
        
        logger.info("   All 3 AI models completed analysis")
        
        # Build consensus using moderator AI
        logger.info("   Building consensus from 3 analyses...")
        consensus_prompt_template = self._load_prompt("stage1_5_consensus_discussion")
        
        consensus_prompt = consensus_prompt_template.replace("{gemini_analysis}", json.dumps(gemini_analysis, indent=2))
        consensus_prompt = consensus_prompt.replace("{grok_analysis}", json.dumps(grok_analysis, indent=2))
        consensus_prompt = consensus_prompt.replace("{gpt_analysis}", json.dumps(gpt_analysis, indent=2))
        consensus_prompt = consensus_prompt.replace("{document_text}", document_text[:30000])
        
        # Moderator AI builds final consensus
        self._log_action(job_id, "⚖️ Moderator AI (Nova Pro) resolving conflicts and building consensus...")
        consensus_result = await self._call_ai(
            system_prompt="You are a moderator building consensus between multiple AI analyses of the same document.",
            user_prompt=consensus_prompt,
            task_type="report_generation",
            temperature=0.2,
            max_tokens=4000
        )
        
        consensus_data = self._safe_json_parse(consensus_result)
        confidence = consensus_data.get('confidence_level', {}).get('overall', 'unknown')
        self._log_action(job_id, f"✅ Consensus reached (Confidence: {confidence})", "success")
        
        logger.info("✅ Stage 1.5 complete: Consensus built")
        logger.info(f"   Confidence level: {consensus_data.get('confidence_level', {}).get('overall', 'unknown')}")
        logger.info(f"   Total items agreed: {consensus_data.get('final_structure', {}).get('total_items', 0)}")
        
        return consensus_data
    

    async def _stage2_generate(
        self,
        analysis: QuestionnaireAnalysis,
        extracted_data: Dict[str, Any],
        consensus_data: Dict[str, Any],
        document_text: str,
        target_count: int,
        language: str,
        purpose: str,
        job_id: UUID
    ) -> List[GeneratedQuestionCandidate]:
        """
        Stage 2: Document-Faithful Question Extraction (MODIFIED - 2-4 minutes)
        Extract questions from document based on consensus understanding
        Focus areas now map to document domains, not random topics
        """
        self._update_job_progress(job_id, "generating", "Stage 2: Extracting Questions from Document", 30)
        
        logger.info(f"✨ Stage 2: Extracting questions from document (Language: {language})...")
        
        # Ensure we operate on a session-bound instance
        analysis_id_local = analysis.id
        analysis = self.db.query(QuestionnaireAnalysis).filter(QuestionnaireAnalysis.id == analysis_id_local).first()
        
        # Get domains from extracted data
        domains = extracted_data.get('domains', [])
        total_items = extracted_data.get('total_items_found', 0)
        
        logger.info(f"   Document has {total_items} items across {len(domains)} domains")
        self._log_action(job_id, f"📊 Stage 0 extracted {total_items} items, {len(domains)} domains")
        
        # Check if we have sufficient data to proceed
        if total_items == 0 and len(domains) == 0:
            self._log_action(job_id, "⚠️ WARNING: Stage 0 extracted 0 items. Document may be empty or unreadable.", "error")
            logger.warning("Stage 0 extracted 0 items - document may be empty or OCR failed")
        
        # Map domains to focus areas for parallel extraction
        # Instead of random topics, we extract from actual document domains
        generation_calls = []
        
        if len(domains) >= 1:
            generation_calls.append({
                "model_key": "llama-70b",
                "instance": "llama-domain-1",
                "focus": domains[0].get('domain_name', 'domain-1'),
                "domain_data": domains[0]
            })
        
        if len(domains) >= 2:
            generation_calls.append({
                "model_key": "mixtral",
                "instance": "mixtral-domain-2",
                "focus": domains[1].get('domain_name', 'domain-2'),
                "domain_data": domains[1]
            })
        
        if len(domains) >= 3:
            generation_calls.append({
                "model_key": "llama-8b",
                "instance": "llama8b-domain-3",
                "focus": domains[2].get('domain_name', 'domain-3'),
                "domain_data": domains[2]
            })
        
        if len(domains) >= 4:
            generation_calls.append({
                "model_key": "llama-70b",
                "instance": "llama-domain-4",
                "focus": domains[3].get('domain_name', 'domain-4'),
                "domain_data": domains[3]
            })
        
        # If fewer than 4 domains, use general extraction
        if len(generation_calls) < 4:
            generation_calls.append({
                "model_key": "llama-8b",
                "instance": "llama8b-general",
                "focus": "all-domains",
                "domain_data": {"all_domains": domains}
            })
        
        # Build prompts using NEW document-faithful approach
        api_calls = []
        self._load_prompt("stage2_question_generation")
        
        for gen_call in generation_calls:
            # Build document-faithful prompt
            prompt = self._build_document_extraction_prompt(
                document_text,
                extracted_data,
                consensus_data,
                gen_call["instance"],
                gen_call["focus"],
                gen_call.get("domain_data", {})
            )
            
            api_calls.append({
                "model_key": gen_call["model_key"],
                "system_prompt": "You are a document extraction specialist. EXTRACT questions from the document, do NOT generate new ones from your knowledge.",
                "user_prompt": prompt,
                "temperature": 0.3,  # Lower temperature for faithful extraction
                "max_tokens": 8000
            })
        
        # Execute in parallel
        logger.info(f"   Running {len(api_calls)} parallel extraction tasks...")
        self._log_action(job_id, f"🚀 Launching {len(api_calls)} parallel AI extraction workers for specific domains...")
        results = await self.client.call_models_parallel(api_calls)
        
        # Parse and store candidates
        candidates = []
        for i, result in enumerate(results):
            gen_info = generation_calls[i]
            model_name = gen_info["model_key"]
            domain_name = gen_info.get("focus", "general")
            
            if not result["success"]:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"❌ Extractor {i} failed: {error_msg}")
                self._log_action(job_id, f"❌ Worker {model_name} failed on domain '{domain_name}': {error_msg}", "error")
                continue
            
            # Log raw response for debugging
            raw_content = result.get("content", "")
            logger.debug(f"Raw response from {model_name}: {raw_content[:500]}")
            
            questions_data = self._safe_json_parse(result["content"])
            logger.debug(f"Parsed data type: {type(questions_data)}, is_list: {isinstance(questions_data, list)}, is_dict: {isinstance(questions_data, dict)}")
            
            # Handle different response formats
            if isinstance(questions_data, list):
                questions_list = questions_data
            elif isinstance(questions_data, dict):
                # Check for common wrapper keys
                if "questions" in questions_data:
                    questions_list = questions_data["questions"]
                elif "items" in questions_data:
                    questions_list = questions_data["items"]
                elif "extracted_items" in questions_data:
                    questions_list = questions_data["extracted_items"]
                else:
                    # If dict has no wrapper key, it might be a single question - wrap it
                    logger.warning(f"⚠️ Dict response without wrapper key from {model_name}. Keys: {list(questions_data.keys())[:5]}")
                    # Check if it looks like a single question object
                    if any(key in questions_data for key in ['question_en', 'question_zh', 'id', 'domain']):
                        questions_list = [questions_data]
                    else:
                        logger.error(f"❌ Invalid format from extractor {i}: dict with keys {list(questions_data.keys())[:5]}")
                        self._log_action(job_id, f"⚠️ Worker {model_name} returned invalid format for '{domain_name}'. Dict keys: {list(questions_data.keys())[:5]}", "error")
                        self._log_action(job_id, f"🔍 Response preview: {raw_content[:200]}...", "info")
                        continue
            else:
                logger.error(f"❌ Invalid format from extractor {i}: {type(questions_data)}")
                self._log_action(job_id, f"⚠️ Worker {model_name} returned invalid format for '{domain_name}'. Response type: {type(questions_data).__name__}", "error")
                if isinstance(raw_content, str) and len(raw_content) > 0:
                    self._log_action(job_id, f"🔍 Response preview: {raw_content[:200]}...", "info")
                continue
            
            # Log extraction result
            if len(questions_list) == 0:
                self._log_action(job_id, f"⚠️ Worker {model_name} extracted 0 items from domain '{domain_name}' - model may have refused or found no questions", "error")
                logger.warning(f"Worker {model_name} returned 0 questions for domain '{domain_name}'")
            else:
                self._log_action(job_id, f"📥 Worker {model_name} extracted {len(questions_list)} items from domain '{domain_name}'")
            
            # Store each question as candidate with fidelity tracking
            for q_data in questions_list:
                # Add fidelity metadata
                if 'extracted_from_document' not in q_data:
                    q_data['extracted_from_document'] = True
                if 'fidelity_score' not in q_data:
                    q_data['fidelity_score'] = 1.0  # Will be validated later
                
                candidate = GeneratedQuestionCandidate(
                    analysis_id=analysis.id,
                    question_data=q_data,
                    generator_instance=gen_info["instance"],
                    model_used=result["model_full_name"],
                    focus_area=gen_info["focus"],
                    status="candidate"
                )
                self.db.add(candidate)
                candidates.append(candidate)
        
        self.db.commit()
        
        self._update_job_progress(job_id, "generating", "Stage 2: Complete", 50)
        logger.info(f"✅ Stage 2 complete: {len(candidates)} questions extracted from document")
        
        return candidates
    

    async def _stage3_5_fidelity_validation(
        self,
        candidates: List[GeneratedQuestionCandidate],
        extracted_data: Dict[str, Any],
        job_id: UUID
    ) -> List[GeneratedQuestionCandidate]:
        """Stage 3.5: Fidelity Validation (NEW)
        Verify that each extracted question actually appears in the original document
        and assign a fidelity_score (1.0 = exact match, 0.0 = not found).
        
        If Stage 0 found no pre-existing questions (e.g., due to PDF parsing limitations),
        we use AI validation scores as a proxy for fidelity.
        """
        self._update_job_progress(job_id, "validating", "Stage 3.5: Fidelity Validation", 65)
        logger.info("🔎 Stage 3.5: Checking fidelity of extracted questions...")
        
        # Build a set of all question texts from extracted_data for quick lookup
        extracted_questions = set()
        for item in extracted_data.get('items', []):
            # Assume each item has 'question_en' and optionally 'question_zh'
            if isinstance(item, dict):
                if 'question_en' in item:
                    extracted_questions.add(item['question_en'].strip())
                if 'question_zh' in item:
                    extracted_questions.add(item['question_zh'].strip())
        
        # Check if we have baseline questions
        has_baseline = len(extracted_questions) > 0
        logger.info(f"   Baseline questions found: {len(extracted_questions)}")
        
        validated = []
        for candidate in candidates:
            q_data = candidate.question_data
            
            if has_baseline:
                # Strict fidelity check against extracted questions
                fidelity = 0.0
                # Check English version
                if q_data.get('question_en') and q_data['question_en'].strip() in extracted_questions:
                    fidelity = 1.0
                # If not found, check Chinese version
                elif q_data.get('question_zh') and q_data['question_zh'].strip() in extracted_questions:
                    fidelity = 1.0
            else:
                # No baseline questions - use AI validation scores as proxy
                # If the question has high validation scores (from Stage 3), consider it high fidelity
                validation_scores = candidate.validation_feedback or {}
                overall_score = validation_scores.get('overall_score', 0) if isinstance(validation_scores, dict) else 0
                
                # Convert validation score (0-100) to fidelity score (0-1)
                # Questions with score >= 80 get high fidelity
                if overall_score >= 80:
                    fidelity = 0.95  # High confidence
                elif overall_score >= 70:
                    fidelity = 0.85  # Medium-high confidence
                elif overall_score >= 60:
                    fidelity = 0.75  # Medium confidence
                else:
                    fidelity = 0.60  # Lower confidence
                
                logger.debug(f"   No baseline - using validation score {overall_score} -> fidelity {fidelity}")
            
            # Update candidate with fidelity score
            q_data['fidelity_score'] = fidelity
            candidate.question_data = q_data
            self.db.add(candidate)
            
            if fidelity >= 0.85:
                # Keep high-fidelity candidates
                validated.append(candidate)
            else:
                # Mark low-fidelity as rejected
                candidate.status = "rejected"
                self.db.add(candidate)
        
        self.db.commit()
        
        logger.info(f"✅ Stage 3.5 complete: {len(validated)} high-fidelity questions kept out of {len(candidates)}")
        self._update_job_progress(job_id, "validating", "Stage 3.5: Complete", 70)
        return validated
    
    async def _stage3_validate(
        self,
        candidates: List[GeneratedQuestionCandidate],
        analysis: QuestionnaireAnalysis,
        job_id: UUID
    ) -> List[GeneratedQuestionCandidate]:
        """Stage 3: Validation & Deduplication (1-2 minutes)
        Grok validates and scores all candidates
        """
        self._update_job_progress(job_id, "validating", "Stage 3: Validating Questions", 60)
        
        logger.info("🔍 Stage 3: Validating and deduplicating...")
        
        # Prepare candidates for validation
        candidates_for_validation = [
            {
                "id": c.id,
                "question_data": c.question_data,
                "generator": c.generator_instance,
                "focus": c.focus_area
            }
            for c in candidates
        ]
        
        validation_prompt = f"""You are a validation expert for psychological assessment tools.

DOCUMENT ANALYSIS SUMMARY:
{json.dumps(analysis.analysis_map, indent=2)[:5000]}

QUESTION CANDIDATES TO VALIDATE ({len(candidates_for_validation)} total):
{json.dumps(candidates_for_validation, indent=2)}

For EACH question, provide validation scores:

1. quality_score (0-100): Grammar, clarity, age-appropriateness, bilingual quality
2. relevance_score (0-100): How relevant to the document's actual content
3. uniqueness_score (0-100): Not duplicate/similar to other questions (check all questions)
4. cultural_appropriateness (0-100): Hong Kong cultural context fit
5. overall_score: Weighted average (relevance 35%, quality 25%, uniqueness 20%, cultural 20%)
6. issues: List any specific problems
7. recommendation: "keep", "revise", or "reject"
8. reasoning: Brief explanation of your scores

Think carefully about duplicates - questions asking essentially the same thing should have LOW uniqueness scores.

Return JSON array with validation for each question:
[
  {{
    "id": candidate_id,
    "quality_score": 85,
    "relevance_score": 90,
    "uniqueness_score": 75,
    "cultural_appropriateness": 88,
    "overall_score": 85.5,
    "issues": ["Minor grammar issue in Chinese"],
    "recommendation": "keep",
    "reasoning": "Strong question, highly relevant..."
  }},
  ...
]
"""
        
        # Call Grok for validation
        self._log_action(job_id, f"🧐 Sending {len(candidates_for_validation)} candidates to Mixtral for deep validation and scoring...")
        result = await self.client.call_model(
            model_key="mixtral",
            system_prompt="You are a meticulous validation expert. Provide detailed, thoughtful scores.",
            user_prompt=validation_prompt,
            temperature=0.3,
            max_tokens=8000
        )
        
        # Parse validation results
        validation_results = self._safe_json_parse(result["content"])
        
        if not isinstance(validation_results, list):
            logger.error("❌ Invalid validation format")
            self._log_action(job_id, "❌ Validation failed: Invalid format returned from AI", "error")
            return candidates[:15]  # Return top 15 unvalidated
            
        self._log_action(job_id, f"✅ Validation complete. Scored {len(validation_results)} items.", "success")
        
        # Update candidates with scores
        validated_candidates = []
        for val in validation_results:
            candidate_id = val.get("id")
            candidate = next((c for c in candidates if c.id == candidate_id), None)
            
            if candidate:
                candidate.quality_score = val.get("quality_score", 0)
                candidate.relevance_score = val.get("relevance_score", 0)
                candidate.uniqueness_score = val.get("uniqueness_score", 0)
                candidate.overall_score = val.get("overall_score", 0)
                candidate.validation_feedback = val
                candidate.status = "validated" if val.get("recommendation") == "keep" else "rejected"
                validated_candidates.append(candidate)
        
        self.db.commit()
        
        # Deduplicate and select top questions
        validated_keep = [c for c in validated_candidates if c.status == "validated"]
        validated_keep.sort(key=lambda c: float(c.overall_score or 0), reverse=True)
        
        # Mark top 15 as selected
        top_15 = validated_keep[:15]
        for candidate in top_15:
            candidate.status = "selected"
        self.db.commit()
        
        self._update_job_progress(job_id, "validating", "Stage 3: Complete", 75)
        logger.info(f"✅ Stage 3 complete: {len(top_15)} questions selected")
        
        return top_15
    
    async def _stage4_smart_filter(
        self,
        candidates: List[GeneratedQuestionCandidate],
        target_count: int,
        target_language: str,
        target_purpose: str,
        job_id: UUID
    ) -> List[GeneratedQuestionCandidate]:
        """
        Stage 4: Smart Filtering (30 seconds)
        Filter and rank questions by user configuration
        """
        self._update_job_progress(job_id, "filtering", "Stage 4: Smart Filtering", 77)
        
        logger.info(f"🎯 Stage 4: Smart filtering {len(candidates)} candidates -> top {target_count}")
        logger.info(f"   Filters: language={target_language}, purpose={target_purpose}")
        
        # Step 1: Filter by language if specified (be lenient)
        if target_language and target_language != "auto":
            lang_candidates = []
            for c in candidates:
                q_lang = c.question_data.get('question_language') or c.question_data.get('language', '')
                # Accept if:
                # 1. Language matches exactly
                # 2. Language is empty/None (bilingual questions)
                # 3. Question has both EN and ZH versions (bilingual)
                has_en = bool(c.question_data.get('question_en'))
                has_zh = bool(c.question_data.get('question_zh'))
                is_bilingual = has_en and has_zh
                
                if q_lang == target_language or not q_lang or is_bilingual:
                    lang_candidates.append(c)
            
            logger.info(f"   After language filter ({target_language}): {len(lang_candidates)}/{len(candidates)} questions")
            if len(lang_candidates) == 0:
                logger.warning("   Language filter removed all questions! Keeping all candidates.")
                lang_candidates = candidates
        else:
            lang_candidates = candidates
        
        # Step 2: Filter by category/purpose if specified (be lenient)
        if target_purpose and target_purpose not in ['general', '', None]:
            category_candidates = [
                c for c in lang_candidates
                if c.question_data.get('category') == target_purpose
                or target_purpose.lower() in str(c.question_data.get('category', '')).lower()
            ]
            logger.info(f"   After category filter ({target_purpose}): {len(category_candidates)}/{len(lang_candidates)} questions")
            if len(category_candidates) == 0:
                logger.warning("   Category filter removed all questions! Keeping all candidates.")
                category_candidates = lang_candidates
        else:
            category_candidates = lang_candidates
        
        # Step 3: Sort by overall_score descending
        sorted_candidates = sorted(
            category_candidates,
            key=lambda x: float(x.overall_score or 0),
            reverse=True
        )
        
        # Step 4: Select top N with diversity
        selected = []
        used_questions = set()
        
        for candidate in sorted_candidates:
            if len(selected) >= target_count:
                break
            
            # Check for diversity (avoid very similar questions)
            question_text = candidate.question_data.get('question_en', '').lower()
            
            # Simple similarity check: if question shares > 60% words with existing, skip
            is_too_similar = False
            question_words = set(question_text.split())
            
            for used_q in used_questions:
                used_words = set(used_q.split())
                if len(question_words) > 0 and len(used_words) > 0:
                    overlap = len(question_words & used_words)
                    denominator = min(len(question_words), len(used_words))
                    if denominator > 0:
                        similarity = overlap / denominator
                        if similarity > 0.6:
                            is_too_similar = True
                            break
            
            if not is_too_similar:
                selected.append(candidate)
                used_questions.add(question_text)
        
        logger.info(f"✅ Stage 4 complete: Selected {len(selected)} diverse, high-quality questions")
        if selected:
            logger.info(f"   Average score: {sum(float(c.overall_score or 0) for c in selected) / len(selected):.1f}")
        else:
            logger.info("   No questions selected")
        
        return selected
    
    async def _stage4_5_detect_duplicates(
        self,
        filtered_candidates: List[GeneratedQuestionCandidate],
        category: str,
        job_id: UUID
    ) -> Dict[int, List[Dict]]:
        """
        Stage 4.5: Duplicate Detection (1-2 minutes)
        Check for semantically similar questions in existing database
        """
        self._update_job_progress(job_id, "checking_duplicates", 
                                 "Stage 4.5: Checking for Duplicates", 85)
        
        logger.info("🔍 Stage 4.5: Checking for duplicate questions...")
        
        # Import and use duplicate detector
        from src.services.duplicate_detector import DuplicateDetectorService
        
        detector = DuplicateDetectorService(self.db)
        duplicates = await detector.check_duplicates(
            filtered_candidates,
            category
        )
        
        # Mark candidates with potential duplicates in their feedback
        rejected_count = 0
        for candidate_id, similar_list in duplicates.items():
            candidate = self.db.query(GeneratedQuestionCandidate).get(candidate_id)
            if candidate:
                if not candidate.validation_feedback:
                    candidate.validation_feedback = {}
                candidate.validation_feedback['potential_duplicates'] = similar_list
                
                # Add warning to feedback
                if similar_list:
                    max_similarity = max(q.get('similarity_score', 0) for q in similar_list)
                    
                    # REJECTION LOGIC (User Request: >= 95%)
                    if max_similarity >= 95:
                        candidate.status = "rejected"
                        candidate.validation_feedback['rejection_reason'] = f"Duplicate detected (Similarity: {max_similarity}%)"
                        candidate.validation_feedback['duplicate_warning'] = "❌ Rejected: Duplicate question"
                        rejected_count += 1
                        logger.info(f"   ❌ Candidate {candidate.id} rejected: Duplicate (Sim: {max_similarity}%)")
                    elif max_similarity >= 90:
                        candidate.validation_feedback['duplicate_warning'] = "⚠️ Very similar to existing question"
                    elif max_similarity >= 80:
                        candidate.validation_feedback['duplicate_warning'] = "⚠️ Similar to existing question"
                    else:
                        candidate.validation_feedback['duplicate_warning'] = "ℹ️ Somewhat similar to existing question"
        
        self.db.commit()
        
        logger.info(f"✅ Stage 4.5 complete: {len(duplicates)} candidates flagged, {rejected_count} rejected as duplicates")
        
        return duplicates
    
    async def _stage4_assemble(
        self,
        selected_questions: List[GeneratedQuestionCandidate],
        analysis: QuestionnaireAnalysis,
        job_id: UUID
    ) -> Dict[str, Any]:
        """
        Stage 4: Assembly & Knowledge Base (1-2 minutes)
        Create final questionnaire + knowledge base
        """
        self._update_job_progress(job_id, "assembling", "Stage 4: Creating Knowledge Base", 80)
        
        logger.info("📚 Stage 4: Assembling questionnaire and creating knowledge base...")
        
        # Build knowledge base in parallel with assembly
        kb_result = await self.client.call_model(
            model_key="llama-70b",
            system_prompt="You are a knowledge synthesis expert for healthcare assessments.",
            user_prompt=f"""Create a comprehensive knowledge base entry for this questionnaire:

ANALYSIS PERFORMED:
{json.dumps(analysis.analysis_map, indent=2)[:10000]}

SELECTED QUESTIONS ({len(selected_questions)} total):
{json.dumps([c.question_data for c in selected_questions], indent=2)}

Create a knowledge base entry with:
1. executive_summary: 3-4 paragraph overview
2. key_concepts: List of concepts with definitions (array of objects: term, definition, relevance)
3. assessment_implications: How to use this questionnaire effectively
4. scoring_guidelines: How to interpret responses
5. red_flags: Warning signs to watch for
6. cultural_considerations: Hong Kong-specific guidance
7. follow_up_recommendations: When to seek professional help

Return as valid JSON.""",
            temperature=0.5,
            max_tokens=6000
        )
        
        kb_data = self._safe_json_parse(kb_result["content"])
        
        # Save knowledge base
        knowledge_base = QuestionnaireKnowledgeBase(
            analysis_id=analysis.id,
            knowledge_base_data=kb_data,
            summary=kb_data.get("executive_summary", ""),
            key_concepts=kb_data.get("key_concepts", []),
            scoring_guidelines=kb_data.get("scoring_guidelines", {})
        )
        self.db.add(knowledge_base)
        self.db.commit()
        
        self._update_job_progress(job_id, "completed", "Stage 4: Complete", 100)
        logger.info(f"✅ Stage 4 complete: Knowledge base created (ID: {knowledge_base.id})")
        
        # Return summary
        return {
            "analysis_id": analysis.id,
            "knowledge_base_id": knowledge_base.id,
            "total_candidates": len(selected_questions),
            "selected_questions": [c.question_data for c in selected_questions],
            "usage_summary": self.client.get_usage_summary()
        }
    
    # Helper methods
    
    def _safe_json_parse(self, content: str) -> Dict:
        """Safely parse JSON from AI response, handling various formats"""
        if not content or not content.strip():
            logger.warning("Empty content provided to JSON parser")
            return {}
        
        # Strip whitespace first
        content = content.strip()
        
        try:
            # Try direct parse
            parsed = json.loads(content)
            # If it's a list, wrap it in a dict with 'questions' key
            if isinstance(parsed, list):
                logger.debug(f"Parsed JSON array with {len(parsed)} items, wrapping in dict")
                return {"questions": parsed}
            return parsed
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks or find JSON object/array
        try:
            # Method 1: Extract from ```json ... ``` blocks
            if "```json" in content:
                start = content.index("```json") + 7
                # Look for closing fence, but if not found, extract to end
                if "```" in content[start:]:
                    end = content.index("```", start)
                    json_str = content[start:end].strip()
                else:
                    # No closing fence found, extract from start to end
                    json_str = content[start:].strip()
                logger.debug(f"Extracted JSON from ```json block (len={len(json_str)})")
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    return {"questions": parsed}
                return parsed
            
            # Method 2: Extract from ``` ... ``` blocks
            elif "```" in content:
                start = content.index("```") + 3
                if "```" in content[start:]:
                    end = content.index("```", start)
                    json_str = content[start:end].strip()
                else:
                    json_str = content[start:].strip()
                logger.debug(f"Extracted JSON from ``` block (len={len(json_str)})")
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    return {"questions": parsed}
                return parsed
            
            # Method 3: Find JSON array by brackets (NEW!)
            if "[" in content and "]" in content:
                start = content.index("[")
                # Find matching closing bracket
                bracket_count = 0
                end = start
                for i in range(start, len(content)):
                    if content[i] == "[":
                        bracket_count += 1
                    elif content[i] == "]":
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break
                
                if end > start:
                    json_str = content[start:end]
                    logger.debug(f"Extracted JSON array from brackets (len={len(json_str)})")
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        logger.info(f"✅ Successfully parsed JSON array with {len(parsed)} items")
                        return {"questions": parsed}
                    return parsed
            
            # Method 4: Find JSON object by braces
            if "{" in content and "}" in content:
                start = content.index("{")
                # Find matching closing brace
                brace_count = 0
                end = start
                for i in range(start, len(content)):
                    if content[i] == "{":
                        brace_count += 1
                    elif content[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                
                if end > start:
                    json_str = content[start:end]
                    logger.debug(f"Extracted JSON object from braces (len={len(json_str)})")
                    return json.loads(json_str)
            
            # If all else fails, return empty dict
            logger.warning(f"Could not find JSON in content (len={len(content)})")
            return {}
            
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Content preview: {content[:500]}...")
            return {}
    
    def _extract_categories(self, structure: Dict, domain: Dict) -> List[str]:
        """Extract question categories from analysis"""
        categories = set()
        
        # From structure
        if "primary_focus" in structure:
            categories.update(structure["primary_focus"])
        
        # From domain
        if "domains" in domain:
            categories.update(domain["domains"])
        
        return list(categories)[:10]  # Limit to 10
    
    def _extract_age_bands(self, domain: Dict) -> List[Dict[str, int]]:
        """Extract age bands from domain analysis"""
        if "age_groups" in domain and domain["age_groups"]:
            return domain["age_groups"]
        # Default Hong Kong child/teen bands
        return [
            {"min": 8, "max": 12},
            {"min": 13, "max": 15},
            {"min": 16, "max": 18}
        ]
    
    def _extract_topics(self, structure: Dict, domain: Dict) -> List[str]:
        """Extract assessment topics"""
        topics = []
        
        if "behavioral_markers" in domain:
            topics.extend(domain["behavioral_markers"][:5])
        if "emotional_markers" in domain:
            topics.extend(domain["emotional_markers"][:5])
        
        return topics
    
    def _build_document_extraction_prompt(
        self,
        document_text: str,
        extracted_data: Dict[str, Any],
        consensus_data: Dict[str, Any],
        instance_id: str,
        focus_area: str,
        domain_data: Dict[str, Any]
    ) -> str:
        """Build document extraction prompt for a specific extractor instance"""
        
        # Load the new document-faithful prompt template
        prompt_template = self._load_prompt("stage2_question_generation")
        
        # Replace placeholders
        prompt = prompt_template.replace("{instance_name}", instance_id)
        prompt = prompt.replace("{focus_area}", focus_area)
        prompt = prompt.replace("{consensus_understanding}", json.dumps(consensus_data, indent=2)[:5000])
        prompt = prompt.replace("{document_text}", document_text[:50000])
        prompt = prompt.replace("{extracted_structure}", json.dumps(extracted_data, indent=2)[:5000])
        
        # Add domain-specific information
        domain_info = f"\n\nDOMAIN FOCUS: {focus_area}\n"
        if domain_data:
            domain_info += f"DOMAIN DATA:\n{json.dumps(domain_data, indent=2)[:3000]}\n"
        
        prompt += domain_info
        
        return prompt
    
    def _build_generation_prompt(
        self,
        analysis_map: Dict[str, Any],
        instance_id: str,
        focus_area: str,
        count: int
    ) -> str:
        """Build generation prompt for a specific generator instance"""
        return f"""You are question generator "{instance_id}" in a team of 5 parallel generators.

DOCUMENT ANALYSIS SUMMARY:
{json.dumps(analysis_map, indent=2)[:8000]}

YOUR UNIQUE FOCUS: {focus_area}
YOUR TASK: Generate {count} questions focusing on {focus_area} aspects

CRITICAL REQUIREMENTS:
1. Base questions DIRECTLY on the document content above
2. Focus on YOUR assigned area: {focus_area}
3. Make questions DIFFERENT from what other generators might create
4. Use bilingual format (English + Traditional Chinese)
5. Specify appropriate age_band for each question
6. Include proper question types (likert5, yes_no, short_answer)

QUESTION TYPES:
- likert5: 5-point scale (Never/Rarely/Sometimes/Often/Always)
- yes_no: Simple yes/no
- short_answer: Open-ended text response

AGE BANDS: 8-12, 13-15, 16-18

Return JSON array of {count} questions:
[
  {{
    "id": "q1",
    "age_band": "13-15",
    "type": "likert5",
    "question_en": "I feel worried about exams at school",
    "question_zh": "我對學校考試感到擔心",
    "category": "academic-stress",
    "scale_labels_en": ["Never", "Rarely", "Sometimes", "Often", "Always"],
    "scale_labels_zh": ["從不", "很少", "有時", "經常", "總是"]
  }}
]

Generate {count} UNIQUE, HIGH-QUALITY questions now:"""

