"""
Duplicate Detection Service for Question Candidates
Uses AI to detect semantically similar questions
"""
import json
import logging
import difflib
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from src.ai.unified_ai_client import AIRequest
from src.ai.providers.nova_bedrock_client import get_nova_client
from src.database.models_multistage_questionnaire import GeneratedQuestionCandidate
from src.database.models_questionnaire import QuestionnaireBank, QuestionnaireQuestion

logger = logging.getLogger(__name__)


class DuplicateDetectorService:
    """Detect duplicate questions across the question base using AI and Algorithms"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = get_nova_client()
    
    async def check_duplicates(
        self,
        new_candidates: List[GeneratedQuestionCandidate],
        category: Optional[str] = None
    ) -> Dict[int, List[Dict]]:
        """
        Check new candidates against existing questions and each other
        """
        logger.info(f"🔍 Checking {len(new_candidates)} candidates for duplicates...")
        
        # 1. Fetch existing active questions
        existing_questions = self._fetch_existing_questions(category)
        logger.info(f"   Comparing against {len(existing_questions)} existing questions")
        
        similarity_results = {}
        processed_candidates = []  # To check for self-duplicates
        
        for candidate in new_candidates:
            candidate_duplicates = []
            
            # Get text
            q_en = candidate.question_data.get('question_en', '').strip()
            q_zh = candidate.question_data.get('question_zh', '').strip()
            
            if not q_en and not q_zh:
                continue
                
            # 2. Check against EXISTING questions (Active/Draft)
            for ex_q in existing_questions:
                # Check English
                sim_en = self._check_text_similarity(q_en, ex_q.question_text)
                # Check Chinese
                sim_zh = self._check_text_similarity(q_zh, ex_q.question_text_zh) if q_zh and ex_q.question_text_zh else 0.0
                
                max_sim = max(sim_en, sim_zh)
                
                if max_sim >= 0.95:
                    logger.warning(f"⚠️ Candidate {candidate.id} is a duplicate of existing question {ex_q.id} (Sim: {max_sim:.2f})")
                    candidate_duplicates.append({
                        "existing_question_id": ex_q.id,
                        "existing_question_text": ex_q.question_text,
                        "similarity_score": round(max_sim * 100, 1),
                        "similarity_type": "exact_match" if max_sim > 0.99 else "high_similarity",
                        "reason": "Content is nearly identical to an active question"
                    })
            
            # 3. Check against OTHER NEW candidates (Batch deduplication)
            for processed in processed_candidates:
                p_en = processed.question_data.get('question_en', '').strip()
                p_zh = processed.question_data.get('question_zh', '').strip()
                
                sim_en = self._check_text_similarity(q_en, p_en)
                sim_zh = self._check_text_similarity(q_zh, p_zh) if q_zh and p_zh else 0.0
                
                max_sim = max(sim_en, sim_zh)
                
                if max_sim >= 0.95:
                    logger.warning(f"⚠️ Candidate {candidate.id} is a duplicate of another new candidate {processed.id} (Sim: {max_sim:.2f})")
                    candidate_duplicates.append({
                        "duplicate_candidate_id": processed.id,
                        "similarity_score": round(max_sim * 100, 1),
                        "similarity_type": "batch_duplicate",
                        "reason": "Duplicate of another question in this batch"
                    })
            
            # If duplicate found, record it
            if candidate_duplicates:
                similarity_results[candidate.id] = candidate_duplicates
            else:
                # Only check AI if no obvious algorithmic duplicate found (save tokens)
                # (Optional: Uncomment to enable AI semantic check for non-obvious ones)
                # ai_duplicates = await self._find_similar_questions(candidate, existing_questions)
                # if ai_duplicates:
                #     similarity_results[candidate.id] = ai_duplicates
                pass
            
            processed_candidates.append(candidate)
        
        return similarity_results

    def _check_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)"""
        if not text1 or not text2:
            return 0.0
        return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _fetch_existing_questions(
        self,
        category: Optional[str] = None
    ) -> List[QuestionnaireQuestion]:
        """Fetch existing questions from database"""
        query = self.db.query(QuestionnaireQuestion).join(
            QuestionnaireBank
        ).filter(
            QuestionnaireBank.status.in_(['active', 'draft'])
        )
        
        # Filter by category if specified
        if category and category not in ['general', '', None]:
            query = query.filter(QuestionnaireBank.category == category)
        
        # Limit to recent questions (last 1000)
        questions = query.order_by(QuestionnaireQuestion.id.desc()).limit(1000).all()
        
        return questions
    
    async def _find_similar_questions(
        self,
        new_candidate: GeneratedQuestionCandidate,
        existing_questions: List[QuestionnaireQuestion]
    ) -> List[Dict[str, Any]]:
        """
        Use AI to detect semantic similarity between new and existing questions
        
        Args:
            new_candidate: New question candidate
            existing_questions: List of existing questions from database
        
        Returns:
            List of similar questions with similarity scores
        """
        # Extract question text
        new_question_en = new_candidate.question_data.get('question_en', '')
        new_question_zh = new_candidate.question_data.get('question_zh', '')
        
        if not new_question_en and not new_question_zh:
            return []
        
        # Prepare existing questions for comparison (limit to 20 for API efficiency)
        existing_sample = existing_questions[:20]
        existing_questions_data = [
            {
                'id': q.id,
                'text': q.question_text,
                'text_zh': q.question_text_zh if hasattr(q, 'question_text_zh') else None
            }
            for q in existing_sample
        ]
        
        # Load duplicate detection prompt
        from pathlib import Path
        prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "questionnaire_generation"
        prompt_file = prompt_dir / "stage4_5_duplicate_detection.txt"
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            logger.warning(f"Duplicate detection prompt not found: {prompt_file}, using inline prompt")
            prompt_template = self._get_fallback_prompt()
        
        # Format prompt
        prompt = f"""{prompt_template}

NEW QUESTION:
English: {new_question_en}
Chinese: {new_question_zh}

EXISTING QUESTIONS:
{json.dumps(existing_questions_data, indent=2, ensure_ascii=False)}

Return JSON array of similar questions with similarity >= 70.
"""
        
        try:
            # Call AI to detect duplicates
            request = AIRequest(
                system_prompt="You are a semantic similarity expert for healthcare questionnaires.",
                user_prompt=prompt,
                task_type="questionnaire",
                temperature=0.3,
                max_tokens=2000
            )
            response = await self.client.make_request(request=request)
            
            # Parse JSON response
            similar_questions = self._safe_json_parse(response.content)
            
            return similar_questions if isinstance(similar_questions, list) else []
            
        except Exception as e:
            logger.error(f"Error detecting duplicates: {e}")
            return []
    
    def _safe_json_parse(self, content: str) -> Any:
        """Safely parse JSON from AI response"""
        try:
            # Try direct JSON parse
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                # Try to extract JSON array from markdown
                if "```json" in content:
                    start = content.index("```json") + 7
                    end = content.index("```", start)
                    return json.loads(content[start:end].strip())
                elif "```" in content:
                    start = content.index("```") + 3
                    end = content.index("```", start)
                    return json.loads(content[start:end].strip())
                elif "[" in content and "]" in content:
                    # Try to find JSON array
                    start = content.index("[")
                    end = content.rindex("]") + 1
                    return json.loads(content[start:end])
                else:
                    logger.warning("Could not parse JSON from AI response")
                    return []
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}")
                return []
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file not found"""
        return """Compare this NEW question against EXISTING questions to find semantic duplicates.

Return JSON array of similar questions with similarity >= 70:
[
  {
    "existing_question_id": 42,
    "existing_question_text": "question text...",
    "similarity_score": 85,
    "similarity_type": "semantic|exact|paraphrase",
    "reason": "explanation of similarity",
    "recommendation": "skip|modify|keep"
  }
]

Only include questions with similarity score >= 70.
"""













