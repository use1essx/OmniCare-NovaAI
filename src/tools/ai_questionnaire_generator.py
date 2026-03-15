"""
AI Questionnaire Generator
Converts teammate's JavaScript AI client to Python for questionnaire generation
Uses AWS Nova for all AI operations
"""

import os
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.ai.unified_ai_client import AIRequest
from src.ai.providers.nova_bedrock_client import get_nova_client

logger = logging.getLogger(__name__)


class ChildMentalHealthAIClient:
    """Child Mental Health AI Questionnaire Generation and Analysis Client"""
    
    def __init__(self, api_key: Optional[str] = None):
        # Use Nova client for all AI operations
        self.nova_client = get_nova_client()
        logger.info("✅ Initialized ChildMentalHealthAIClient with AWS Nova")
    
    # ==================== Stage 1: Intelligent Document Extraction ====================
    
    async def extract_mental_health_concepts(self, content: str) -> Dict[str, Any]:
        """
        Intelligently extract core mental health concepts from documents
        Returns categorized symptoms, behaviors, and contexts
        """
        logger.info("🧠 Stage 1: Extracting mental health core concepts from document")
        
        
        prompt = f"""# Task: Extract child mental health related concepts from document

You are a child psychologist analyzing documents to create child psychological assessment tools.

## Analysis Goals:
1. Identify all concepts related to child (3-12 years) mental health
2. Categorize these concepts into standard psychological assessment dimensions
3. Extract specific behaviors, emotions, and situational descriptions

## Key Principles:
- Focus on mental health and emotional regulation related content
- Ignore purely cognitive development, academic performance, physical skills, etc.
- Extract observable behaviors and emotional expressions

## Input Document:
{content[:12000]}

## Categorization Dimensions:
Categorize extracted concepts into these dimensions:

### 1. Emotional Experience
- Anxiety symptoms: tension, worry, fear, separation anxiety
- Depression symptoms: sadness, loss of interest, self-blame, helplessness
- Anger/Frustration: irritability, tantrums, aggression
- Shame/Guilt: excessive self-blame, shame


### 2. Emotional Regulation
- Emotion recognition: identifying own and others' emotions
- Emotion expression: expressing emotions through language or appropriate means
- Emotion management: strategies for handling intense emotions
- Resilience: recovery speed from setbacks

### 3. Social Functioning
- Peer relationships: making friends, sharing, cooperation, conflict resolution
- Family relationships: interactions with parents, siblings
- Social withdrawal: avoiding social situations, self-isolation
- Social anxiety: nervousness in social situations, fear of evaluation

### 4. Behavioral Manifestations
- Attention/concentration: focus, distractibility
- Activity level: hyperactivity or insufficient activity
- Sleep problems: difficulty falling asleep, nightmares, night waking
- Eating problems: appetite changes, picky eating

### 5. Daily Functioning
- School adaptation: willingness to attend school, classroom participation
- Interest activities: play interests, engagement level
- Self-care: completion of daily tasks

## Output Format Requirements:
Output strict JSON format:

{{
  "summary": "Document core content summary (within 100 words)",
  "concepts_by_category": {{
    "emotional_experience": [
      {{
        "concept": "Specific concept description (English and Chinese)",
        "symptom_description": "Specific symptom manifestation",
        "age_relevance": ["3-5", "6-8", "9-12"],
        "severity_indicators": ["mild", "moderate", "severe"]
      }}
    ],
    "emotional_regulation": [...],
    "social_functioning": [...],
    "behavioral_manifestations": [...],
    "daily_functioning": [...]
  }},
  "extraction_metadata": {{
    "total_concepts": 10,
    "primary_focus": "Document's main focus",
    "age_group_coverage": "Covered age groups"
  }}
}}

## Extraction Rules:
1. Each concept must be specific, observable behavior or emotion
2. Avoid abstract terms, use language children can understand
3. Indicate which age groups this concept is most relevant to
4. Extract 5-15 core concepts (1-3 per dimension)

Now, analyze the document and extract relevant concepts:"""
        
        try:
            response = await self._call_ai_with_model(
                prompt=prompt,
                task_type="report_generation",
                temperature=0.4,
                max_tokens=4000
            )
            
            concepts_data = self._extract_json_from_response(response)
            total_concepts = concepts_data.get('extraction_metadata', {}).get('total_concepts', 0)
            logger.info(f"✅ Concept extraction completed: Extracted {total_concepts} core concepts")
            
            return {
                "success": True,
                "stage": "concept_extraction",
                "concepts": concepts_data,
                "raw_response": response[:500] if concepts_data.get("extraction_metadata") else response
            }
            
                
        except Exception as e:
            logger.error(f"❌ Concept extraction failed: {e}")
            return {
                "success": False,
                "stage": "concept_extraction",
                "error": str(e)
            }
    
    # ==================== Stage 2: Questionnaire Generation ====================
    
    async def generate_conversational_questions(
        self, 
        concepts_data: Dict[str, Any],
        question_count: int = 10,
        target_age: int = 8,
        question_types: List[str] = ["feelings", "situations", "coping"]
    ) -> Dict[str, Any]:
        """
        Generate conversational questions based on extracted concepts
        """
        logger.info(f"🗣️ Stage 2: Generating conversational questions (target age: {target_age})")
        
        # Adjust language complexity based on target age
        age_language_map = {
            "3-5": "Use extremely simple vocabulary, sentences no longer than 5 words",
            "6-8": "Use simple sentences with concrete situations",
            "9-12": "Can include slightly complex emotion vocabulary and hypothetical situations"
        }
        
        age_group = "3-5" if target_age <= 5 else ("6-8" if target_age <= 8 else "9-12")
        language_guide = age_language_map[age_group]

        
        # Build concepts list for prompt
        concepts_text = self._format_concepts_for_prompt(concepts_data)

        
        prompt = f"""Generate EXACTLY {question_count} UNIQUE child mental health assessment questions.

TARGET: {question_count} questions for {target_age}-year-old children in Hong Kong

CRITICAL RULES:
1. Generate EXACTLY {question_count} questions (count them before submitting!)
2. Each question MUST be completely DIFFERENT - no similar or repeated questions
3. question_en = English ONLY (no Chinese characters)
4. question_zh = Traditional Chinese (繁體中文)
5. Both must end with ? or ？
6. NO empty or blank questions

DIVERSITY REQUIREMENTS:
- Use different situations (school, home, friends, family, play)
- Cover different emotions (happy, sad, angry, worried, scared, excited)
- Vary question types (feelings, actions, coping, relationships)
- Each question should explore a DIFFERENT aspect of mental health

MENTAL HEALTH CONCEPTS TO COVER:
{concepts_text}

OUTPUT FORMAT (JSON):
{{
  "questions": [
    {{
      "id": "q1",
      "question_en": "How do you feel when you have to try something new at school?",
      "question_zh": "當你在學校需要嘗試新事物時，你感覺如何？",
      "type": "emotion_identification",
      "psychological_dimension": "anxiety"
    }},
    {{
      "id": "q2",
      "question_en": "What do you do when a friend makes you angry?",
      "question_zh": "當朋友讓你生氣時，你會做什麼？",
      "type": "coping_strategy",
      "psychological_dimension": "emotional_regulation"
    }},
    {{
      "id": "q3",
      "question_en": "Who do you talk to when you feel sad?",
      "question_zh": "當你感到難過時，你會跟誰說？",
      "type": "social_support",
      "psychological_dimension": "help_seeking"
    }}
    ... continue with DIFFERENT questions until you have {question_count} total
  ]
}}

EXAMPLES OF DIVERSE QUESTIONS:
- "How do you feel before going to school?"
- "What makes you happy when you're at home?"
- "How do you calm down when you're upset?"
- "What do you do when you can't sleep?"
- "How do you feel when playing with friends?"
- "What helps you when you're worried about something?"

IMPORTANT: 
- Count your questions! Must be EXACTLY {question_count}
- Each question must be UNIQUE - check for duplicates
- NO blank or empty questions
- Cover diverse situations and emotions

Generate {question_count} UNIQUE questions now:"""
        
        try:
            # Try generating questions with retry logic
            max_attempts = 3
            best_result = None
            best_question_count = 0
            
            for attempt in range(max_attempts):
                logger.info(f"🎲 Question generation attempt {attempt + 1}/{max_attempts}")
                
                # Use Nova Pro for better quality
                task_type = "questionnaire"
                temp = 0.85 if attempt == 0 else 0.9
                
                logger.info(f"   Using Nova Pro, temperature: {temp}")
                
                response = await self._call_ai_with_model(
                    prompt=prompt,
                    task_type=task_type,
                    temperature=temp,
                    max_tokens=8000  # More tokens for complete generation
                )
                
                logger.debug(f"AI response length: {len(response)} chars")
                logger.debug(f"Response preview: {response[:300]}...")
                
                questionnaire_data = self._extract_json_from_response(response)
                
                # Log what we got
                raw_questions = questionnaire_data.get("questions", [])
                logger.info(f"   Extracted {len(raw_questions)} questions from JSON")
                
                # Filter out empty questions immediately
                non_empty_questions = [
                    q for q in raw_questions 
                    if q.get("question_en", "").strip() and q.get("question_zh", "").strip()
                ]
                
                if len(non_empty_questions) < len(raw_questions):
                    empty_count = len(raw_questions) - len(non_empty_questions)
                    logger.warning(f"   Filtered out {empty_count} empty questions")
                
                # Validate question quality
                validated_questions = self._validate_questions(non_empty_questions)
                
                logger.info(f"   Attempt {attempt + 1}: Generated {len(validated_questions)} valid questions (target: {question_count})")
                
                # Keep best result
                if len(validated_questions) > best_question_count:
                    best_question_count = len(validated_questions)
                    best_result = {
                        "questionnaire_data": questionnaire_data,
                        "validated_questions": validated_questions
                    }
                
                # If we got enough questions, use this result
                if len(validated_questions) >= question_count * 0.8:  # Accept if we got at least 80% of target
                    logger.info(f"✅ Sufficient questions generated: {len(validated_questions)}/{question_count}")
                    break
                
                # If not enough questions and not last attempt, try again
                if attempt < max_attempts - 1:
                    logger.warning(f"⚠️  Only got {len(validated_questions)}/{question_count} questions, retrying...")
            
            # Use best result
            if best_result:
                validated_questions = best_result["validated_questions"]
                questionnaire_data = best_result["questionnaire_data"]
                
                logger.info(f"✅ Question generation completed: {len(validated_questions)} valid questions")
                
                return {
                    "success": True,
                    "stage": "question_generation",
                    "questionnaire": {
                        **questionnaire_data,
                        "questions": validated_questions
                    },
                    "validation_stats": {
                        "total_generated": len(questionnaire_data.get("questions", [])),
                        "validated": len(validated_questions),
                        "target_age": target_age,
                        "target_count": question_count,
                        "success_rate": f"{len(validated_questions)/question_count*100:.1f}%"
                    }
                }
            else:
                raise Exception("Failed to generate any valid questions after all attempts")
            
        except Exception as e:
            logger.error(f"❌ Question generation failed: {e}")
            return {
                "success": False,
                "stage": "question_generation",
                "error": str(e)
            }
    
    # ==================== Stage 3: Response Analysis ====================
    
    async def analyze_child_responses(
        self,
        questionnaire: Dict[str, Any],
        child_responses: List[Dict[str, Any]],
        child_age: int,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze child responses and calculate psychological risk scores
        """
        logger.info(f"📊 Stage 3: Analyzing child responses (age: {child_age})")
        
        # Prepare analysis data
        questions = questionnaire.get("questions", [])
        analysis_data = {
            "responses": child_responses,
            "questions": questions,
            "child_age": child_age,
            "context": additional_context or "No additional context"
        }
        
        prompt = f"""# Task: Analyze child psychological responses and calculate risk scores

You are a child clinical psychologist analyzing AI-child conversation records to assess child mental health risks.

## Analysis Data:
{json.dumps(analysis_data, ensure_ascii=False, indent=2)[:6000]}

## Analysis Framework:

### 1. Anxiety Score Calculation (0-100)
Consider these indicators:
- Tolerance for uncertainty
- Separation anxiety manifestations
- Nervousness in social situations
- Somatic symptom mentions (stomach ache, headache)
- Perfectionism tendencies

### 2. Emotional Regulation Risk Score (0-100)
Consider these indicators:
- Emotion recognition ability (can accurately describe feelings)
- Appropriateness of emotional expression
- Effectiveness of coping strategies
- Recovery speed from negative emotions
- Match between emotion intensity and situation

### 3. Social Functioning Score (0-100)
Consider these indicators:
- Peer relationship descriptions
- Family interaction quality
- Social avoidance tendencies
- Conflict resolution strategies
- Empathy manifestations

### 4. Overall Mental Health Index (0-100)
Weighted calculation: Anxiety(30%) + Emotional Regulation(40%) + Social Functioning(30%)

## Scoring Rules:
- Each dimension 0-100, higher score indicates higher risk/poorer functioning
- Consider age development standards: normal range for {child_age}-year-old children
- Identify "red flags": high-risk expressions requiring immediate attention
- Note protective factors: strengths and resources child demonstrates

## Analysis Steps:
1. Analyze child's responses sentence by sentence
2. Identify emotion keywords and expression patterns
3. Assess response consistency and depth
4. Consider developmental age appropriateness
5. Calculate scores for each dimension

## Output Format:
{{
  "analysis_summary": "Overall analysis summary (within 200 words)",
  "risk_scores": {{
    "anxiety_score": {{
      "score": 35.5,
      "level": "low_risk",
      "confidence": 0.85,
      "key_indicators": ["indicator1", "indicator2"],
      "age_adjusted_note": "Considering {child_age} years old, this performance..."
    }},
    "emotional_regulation_score": {{
      "score": 62.0,
      "level": "medium_risk",
      "confidence": 0.78,
      "key_indicators": [...]
    }},
    "social_functioning_score": {{
      "score": 41.0,
      "level": "low_risk",
      "confidence": 0.82,
      "key_indicators": [...]
    }},
    "overall_mental_health_index": 65.3
  }},
  "detailed_analysis": [
    {{
      "question_id": "q1",
      "child_response": "Child's original response",
      "emotional_themes": ["theme1", "theme2"],
      "risk_flags": ["risk_flag1", "risk_flag2"],
      "strength_flags": ["strength_flag1", "strength_flag2"],
      "interpretation": "Psychologist interpretation"
    }}
  ],
  "recommendations": {{
    "immediate_actions": ["suggestion1", "suggestion2"],
    "follow_up_assessments": ["areas requiring further assessment"],
    "strengths_to_build_on": ["strengths to develop"],
    "referral_suggestions": ["referral suggestions (if needed)"]
  }},
  "analysis_metadata": {{
    "analyst": "AI Child Psychologist",
    "analysis_date": "{datetime.now().strftime('%Y-%m-%d')}",
    "child_age": {child_age},
    "total_responses_analyzed": {len(child_responses)}
  }}
}}

## Special Considerations:
1. **Developmental sensitivity**: Consider normal emotional expression range for {child_age}-year-old children
2. **Cultural sensitivity**: Consider Hong Kong children's cultural background
3. **Protective factors**: Identify child's strengths and support systems
4. **Risk assessment conservative principle**: When uncertain, adopt more conservative assessment
5. **Referral criteria**: Clarify when professional intervention is recommended

Now, analyze child responses and calculate risk scores:"""
        
        try:
            response = await self._call_ai_with_model(
                prompt=prompt,
                task_type="report_generation",
                temperature=0.2,
                max_tokens=8000
            )
            analysis_results = self._extract_json_from_response(response)
            
            overall_index = analysis_results.get('risk_scores', {}).get('overall_mental_health_index', 0)
            logger.info(f"✅ Analysis completed: Overall mental health index = {overall_index}")
            
            return {
                "success": True,
                "stage": "response_analysis",
                "analysis": analysis_results,
                "raw_analysis": response[:1000]
            }
        except Exception as e:
            logger.error(f"❌ Response analysis failed: {e}")
            return {
                "success": False,
                "stage": "response_analysis",
                "error": str(e)
            }
    
    # ==================== Main Pipeline: End-to-End Processing ====================
    
    async def process_document_to_questionnaire(
        self,
        file_content: str,
        target_age: int = 8,
        question_count: int = 10
    ) -> Dict[str, Any]:
        """
        Complete pipeline: Document -> Concept Extraction -> Question Generation
        (For questionnaire creation workflow)
        """
        logger.info(f"🚀 Starting questionnaire generation pipeline: target age {target_age}")
        
        results = {
            "processing_id": f"proc_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stages": {}
        }
        
        try:
            # Stage 1: Concept Extraction
            logger.info("📖 Stage 1/2: Extracting mental health concepts...")
            concepts_result = await self.extract_mental_health_concepts(file_content)
            results["stages"]["concept_extraction"] = concepts_result
            
            if not concepts_result.get("success"):
                results["success"] = False
                results["error"] = "Concept extraction failed"
                return results
            
            # Stage 2: Question Generation
            logger.info("💬 Stage 2/2: Generating conversational questions...")
            questions_result = await self.generate_conversational_questions(
                concepts_data=concepts_result["concepts"],
                question_count=question_count,
                target_age=target_age
            )
            results["stages"]["question_generation"] = questions_result
            
            if not questions_result.get("success"):
                results["success"] = False
                results["error"] = "Question generation failed"
                return results
            
            results["success"] = True
            results["questionnaire"] = questions_result["questionnaire"]
            results["summary"] = self._generate_processing_summary(results)
            
            logger.info("✅ Questionnaire generation completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Pipeline processing failed: {e}")
            results["success"] = False
            results["error"] = str(e)
        
        return results
    
    # ==================== Helper Methods ====================
    
    async def _call_ai_with_model(
        self,
        prompt: str,
        task_type: str = "questionnaire",
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> str:
        """
        Call AI model using Nova client
        
        Args:
            prompt: The prompt to send to the AI
            task_type: Task type for model selection (e.g., 'questionnaire', 'report_generation')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            AI-generated response text
            
        Raises:
            Exception: If AI call fails
        """
        try:
            # MIGRATION: Use Nova client with unified interface
            from src.ai.unified_ai_client import select_model_tier
            
            # Select appropriate model tier based on task type
            model_tier = select_model_tier(task_type)
            
            # Make request using Nova client
            response = await self.nova_client.make_request(
                model_tier=model_tier,
                system_prompt="You are a child mental health assessment expert.",
                user_prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                task_type=task_type
            )
            
            # Extract content from Nova response
            return response.content
                
        except Exception as e:
            logger.error(f"AI call error: {e}")
            raise
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from response with improved parsing"""
        try:
            # Log response length for debugging
            logger.debug(f"Response length: {len(response)} chars")
            
            # Try to find JSON block with markers (non-greedy)
            if "```json" in response:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    logger.debug(f"Extracted JSON from markdown block: {len(json_str)} chars")
                    return json.loads(json_str)
            
            # Try to find JSON with proper brace matching
            # Find first { and last }
            first_brace = response.find('{')
            last_brace = response.rfind('}')
            
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = response[first_brace:last_brace + 1]
                logger.debug(f"Extracted JSON by brace matching: {len(json_str)} chars")
                
                # Try to parse
                parsed = json.loads(json_str)
                
                # Validate it has expected structure
                if "questions" in parsed or "questionnaire_info" in parsed:
                    return parsed
                else:
                    logger.warning("Parsed JSON but missing expected keys")
            
            # Last resort: try parsing entire response
            logger.debug("Attempting to parse entire response as JSON")
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response preview: {response[:500]}...")
            return {
                "success": False,
                "raw_response": response[:1000],  # Save first 1000 chars for debugging
                "error": f"JSON parsing failed: {str(e)}",
                "questions": []  # Return empty questions list to avoid crashes
            }
    
    def _format_concepts_for_prompt(self, concepts_data: Dict[str, Any]) -> str:
        """Format concepts data for prompt"""
        try:
            concepts_by_category = concepts_data.get("concepts_by_category", {})
            formatted = []
            
            for category, concepts in concepts_by_category.items():
                if concepts:
                    formatted.append(f"\n### {category.replace('_', ' ').title()}:")
                    for i, concept in enumerate(concepts[:3], 1):
                        desc = concept.get('concept', 'Unknown concept')
                        formatted.append(f"{i}. {desc}")
            
            return "\n".join(formatted) if formatted else "No specific concepts extracted"
        except Exception as e:
            logger.error(f"Formatting concepts failed: {e}")
            return "Concept data format error"
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using multiple methods"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # Exact match
        if t1 == t2:
            return 1.0
        
        # Word-based similarity (Jaccard)
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # Character-based similarity (for catching minor variations)
        # Simple character overlap
        chars1 = set(t1.replace(" ", ""))
        chars2 = set(t2.replace(" ", ""))
        char_intersection = chars1.intersection(chars2)
        char_union = chars1.union(chars2)
        char_similarity = len(char_intersection) / len(char_union) if char_union else 0.0
        
        # Combine both metrics (weighted average)
        # Jaccard is more important for semantic similarity
        combined = (jaccard * 0.7) + (char_similarity * 0.3)
        
        return combined
    
    def _deduplicate_questions(self, questions: List[Dict], similarity_threshold: float = 0.7) -> List[Dict]:
        """Remove duplicate or very similar questions"""
        if not questions:
            return []
        
        unique_questions = []
        seen_questions = []
        duplicate_count = 0
        
        for q in questions:
            en = q.get("question_en", "").strip()
            zh = q.get("question_zh", "").strip()
            
            # Skip if empty
            if not en or not zh:
                duplicate_count += 1
                continue
            
            # Check similarity with existing questions
            is_duplicate = False
            for seen_en, seen_zh in seen_questions:
                en_similarity = self._calculate_similarity(en, seen_en)
                zh_similarity = self._calculate_similarity(zh, seen_zh)
                
                # If either language is too similar, consider it a duplicate
                if en_similarity > similarity_threshold or zh_similarity > similarity_threshold:
                    is_duplicate = True
                    duplicate_count += 1
                    logger.debug(f"🔄 Duplicate detected: '{en[:40]}...' (similarity: {max(en_similarity, zh_similarity):.2f})")
                    break
            
            if not is_duplicate:
                unique_questions.append(q)
                seen_questions.append((en, zh))
        
        if duplicate_count > 0:
            logger.info(f"🔄 Deduplication: Removed {duplicate_count} duplicates, kept {len(unique_questions)} unique")
        
        return unique_questions
    
    def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
        """Validate question quality with detailed logging"""
        valid_questions = []
        rejected_count = 0
        rejection_reasons = {}
        
        logger.info(f"🔍 Validating {len(questions)} questions...")
        
        # First, deduplicate
        questions = self._deduplicate_questions(questions)
        logger.info(f"   After deduplication: {len(questions)} questions")
        
        for idx, q in enumerate(questions, 1):
            # Check required fields
            required_fields = ["question_en", "question_zh"]
            missing_fields = [f for f in required_fields if not q.get(f)]
            
            if missing_fields:
                rejected_count += 1
                rejection_reasons["missing_fields"] = rejection_reasons.get("missing_fields", 0) + 1
                logger.warning(f"❌ Q{idx} Rejected: Missing fields {missing_fields}")
                continue
            
            # Check bilingual completeness
            en = q.get("question_en", "").strip()
            zh = q.get("question_zh", "").strip()
            
            if not en or not zh:
                rejected_count += 1
                rejection_reasons["empty_text"] = rejection_reasons.get("empty_text", 0) + 1
                logger.warning(f"❌ Q{idx} Rejected: Empty question text")
                continue
            
            # Check if English field contains Chinese characters
            has_chinese_in_en = any('\u4e00' <= char <= '\u9fff' for char in en)
            if has_chinese_in_en:
                rejected_count += 1
                rejection_reasons["chinese_in_english"] = rejection_reasons.get("chinese_in_english", 0) + 1
                logger.warning(f"❌ Q{idx} Rejected: English has Chinese - '{en[:50]}...'")
                continue
            
            # Check if Chinese field contains mostly English (should be mostly Chinese)
            chinese_char_count = sum(1 for char in zh if '\u4e00' <= char <= '\u9fff')
            if len(zh) > 10 and chinese_char_count < len(zh) * 0.3:  # Less than 30% Chinese chars
                rejected_count += 1
                rejection_reasons["insufficient_chinese"] = rejection_reasons.get("insufficient_chinese", 0) + 1
                logger.warning(f"❌ Q{idx} Rejected: Chinese field insufficient - '{zh[:50]}...'")
                continue
            
            # Check question format (should end with question mark) - RELAXED
            has_en_question_mark = en.endswith('?') or en.endswith('？')
            has_zh_question_mark = zh.endswith('？') or zh.endswith('?')
            
            if not has_en_question_mark and not has_zh_question_mark:
                # Both missing question marks - reject
                rejected_count += 1
                rejection_reasons["no_question_mark"] = rejection_reasons.get("no_question_mark", 0) + 1
                logger.warning(f"❌ Q{idx} Rejected: No question marks - EN: '{en[:50]}...', ZH: '{zh[:50]}...'")
                continue
            elif not has_en_question_mark or not has_zh_question_mark:
                # Only one missing - add it
                if not has_en_question_mark:
                    q["question_en"] = en + "?"
                    logger.info(f"✏️  Q{idx} Fixed: Added ? to English")
                if not has_zh_question_mark:
                    q["question_zh"] = zh + "？"
                    logger.info(f"✏️  Q{idx} Fixed: Added ？ to Chinese")
            
            # Filter out obvious titles/categories - RELAXED
            if len(en.split()) <= 2 and not any(word in en.lower() for word in ['do', 'are', 'can', 'have', 'feel', 'when', 'how', 'what', 'why', 'who', 'where']):
                rejected_count += 1
                rejection_reasons["title_or_category"] = rejection_reasons.get("title_or_category", 0) + 1
                logger.warning(f"❌ Q{idx} Rejected: Appears to be a title - '{en}'")
                continue
            
            # Check age appropriateness (question not too long) - WARNING ONLY
            if len(en.split()) > 30 or len(zh) > 60:
                logger.warning(f"⚠️  Q{idx} Long question: {en[:50]}...")
            
            # Add default psychological_dimension if missing
            if not q.get("psychological_dimension"):
                q["psychological_dimension"] = "general"
                logger.debug(f"✏️  Q{idx} Added default psychological_dimension")
            
            logger.debug(f"✅ Q{idx} Valid: {en[:60]}...")
            valid_questions.append(q)
        
        if rejected_count > 0:
            logger.info(f"📊 Validation: {len(valid_questions)} valid, {rejected_count} rejected")
            logger.info(f"   Rejection breakdown: {rejection_reasons}")
        else:
            logger.info(f"📊 Validation: All {len(valid_questions)} questions passed")
        
        return valid_questions
    
    def _generate_processing_summary(self, results: Dict) -> str:
        """Generate processing summary"""
        stages = results.get("stages", {})
        
        summary_parts = []
        
        if "concept_extraction" in stages and stages["concept_extraction"].get("success"):
            concepts = stages["concept_extraction"].get("concepts", {})
            total = concepts.get("extraction_metadata", {}).get("total_concepts", 0)
            summary_parts.append(f"Extracted {total} mental health concepts")
        
        if "question_generation" in stages and stages["question_generation"].get("success"):
            stats = stages["question_generation"].get("validation_stats", {})
            valid_q = stats.get("validated", 0)
            summary_parts.append(f"Generated {valid_q} validated conversational questions")
        
        if "response_analysis" in stages and stages["response_analysis"].get("success"):
            analysis = stages["response_analysis"].get("analysis", {})
            risk_scores = analysis.get("risk_scores", {})
            overall = risk_scores.get("overall_mental_health_index", 0)
            summary_parts.append(f"Analysis completed, overall mental health index: {overall:.1f}/100")
        
        return " | ".join(summary_parts) if summary_parts else "Processing completed"
    
    # ==================== File Processing (Preserving original functionality) ====================
    
    async def process_file_for_text(
        self,
        file_base64: str,
        mime_type: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        Process uploaded file and extract text
        
        NOTE: Vision/OCR processing not currently supported.
        Use traditional file parsers for PDF, Word, Excel, etc.
        """
        logger.warning(f"📄 Vision/OCR not supported for file: {file_name}")
        
        return {
            "success": False,
            "error": "Vision/OCR processing not available. Please use PDF, Word, Excel, or text files instead.",
            "file_name": file_name
        }


# ==================== Backward Compatibility: Legacy API ====================

class AIQuestionnaireClient:
    """
    Legacy wrapper for backward compatibility
    Wraps new ChildMentalHealthAIClient with old API
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.new_client = ChildMentalHealthAIClient(api_key)
        logger.info("⚠️  Using legacy AIQuestionnaireClient (compatibility mode)")
    
    async def call_ai_with_file(
        self,
        file_base64: str,
        mime_type: str,
        file_name: str,
        custom_prompt: Optional[str] = None
    ) -> str:
        """Legacy method: Extract text from file"""
        result = await self.new_client.process_file_for_text(file_base64, mime_type, file_name)
        if result.get("success"):
            return result["extracted_text"]
        else:
            raise Exception(result.get("error", "File processing failed"))
    
    async def generate_questionnaire(
        self,
        content: str,
        question_count: int = 10,
        language: str = "en",
        purpose: str = "child-screening"
    ) -> Dict[str, Any]:
        """
        Legacy method: Generate questionnaire
        Now uses new 2-stage pipeline
        """
        logger.info(f"🔄 Converting legacy generate_questionnaire call to new pipeline")
        
        # Determine target age based on purpose
        target_age = 8  # Default
        if "3-5" in purpose or "preschool" in purpose.lower():
            target_age = 4
        elif "6-8" in purpose or "early" in purpose.lower():
            target_age = 7
        elif "9-12" in purpose or "late" in purpose.lower():
            target_age = 10
        
        # Run new pipeline
        result = await self.new_client.process_document_to_questionnaire(
            file_content=content,
            target_age=target_age,
            question_count=question_count
        )
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Processing failed")
            }
        
        # Convert new format to legacy format
        questionnaire = result.get("questionnaire", {})
        questions = questionnaire.get("questions", [])
        
        # Convert to legacy format
        legacy_questions = []
        for q in questions:
            legacy_questions.append({
                "id": q.get("id"),
                "type": q.get("type", "yes_no"),
                "question_text": q.get("question_en"),
                "question_text_zh": q.get("question_zh"),
                "category": q.get("psychological_dimension", "general"),
                "required": True,
                "fidelity_score": 1.0
            })
        
        return {
            "success": True,
            "questionnaire": {
                "title": f"Child Mental Health Assessment (Age {target_age})",
                "title_zh": f"儿童心理健康评估 ({target_age}岁)",
                "description": questionnaire.get("questionnaire_info", {}).get("purpose", "Mental health screening"),
                "questions": legacy_questions
            },
            "truncated": False,
            "processing_method": "new_3stage_pipeline"
        }

