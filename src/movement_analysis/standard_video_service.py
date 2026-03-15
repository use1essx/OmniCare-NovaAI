"""
Healthcare AI V2 - Standard Video Analysis Service
Analyzes standard tutorial videos to automatically generate assessment rules
"""

import json
import logging
from typing import Dict, Any
import re

from src.movement_analysis.video_processor import VideoProcessor

logger = logging.getLogger(__name__)


class StandardVideoAnalyzer:
    """
    Analyzes standard tutorial videos to extract movement patterns
    and generate assessment rule data
    """
    
    def __init__(self):
        self.video_processor = VideoProcessor()
    
    async def analyze_and_create_rule(
        self,
        video_path: str,
        movement_title: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Analyze a standard tutorial video and generate rule data
        
        Args:
            video_path: Path to the uploaded video file
            movement_title: Name of the movement (e.g., "Single-leg stance")
            user_id: ID of the user creating this rule
            
        Returns:
            Dictionary with rule data ready for AssessmentRule creation
        """
        logger.info(f"Analyzing standard video: {movement_title} at {video_path}")
        
        try:
            # Extract frames from video (sync function, don't await)
            frames, total_frames = self.video_processor.extract_frames(video_path, max_frames=5)
            
            if not frames:
                raise ValueError("No frames could be extracted from video")
            
            logger.info(f"Extracted {len(frames)} frames from standard video (total: {total_frames})")
            
            # Build specialized AI prompt for standard video analysis
            prompt = self._build_standard_analysis_prompt(movement_title)
            
            # Call AI vision model
            ai_result = await self.video_processor.analyze_video_with_ai(frames, prompt)
            
            # Extract content from AI response
            if not ai_result.get("success"):
                raise ValueError(f"AI analysis failed: {ai_result.get('error', 'Unknown error')}")
            
            ai_response = ai_result.get("content", "")
            
            # Parse AI response
            rule_data = self._parse_ai_response(ai_response, movement_title)
            
            # Generate auto index code
            rule_data['index_code'] = self._generate_index_code(movement_title)
            rule_data['created_by'] = user_id
            rule_data['is_active'] = False  # Require manual review before activation
            
            logger.info(f"Successfully generated rule data for: {rule_data['category']}")
            
            return rule_data
            
        except Exception as e:
            logger.error(f"Error analyzing standard video: {e}")
            raise
    
    def _build_standard_analysis_prompt(self, movement_title: str) -> str:
        """
        Build AI prompt for analyzing standard movement video
        """
        return f"""You are a professional physical therapist and movement analysis expert.

Analyze this standard demonstration video showing: "{movement_title}"

Your task is to extract comprehensive movement analysis data that will be used to create an assessment rule for ALL AGE GROUPS (children, teens, adults, elderly).

Generate a JSON response with the following structure:

{{
  "category": "Brief, clear name for this movement assessment (e.g., 'Single-Leg Balance', 'Gait Analysis', 'Pickleball Serve')",
  "description": "2-3 sentence description of what this movement pattern assesses and why it's clinically important for movement analysis across all ages",
  "ai_role": "Suggested AI role/persona for analyzing videos (e.g., 'Movement Analysis Specialist', 'Gait Analysis Expert', 'Sports Movement Analyst'). DO NOT use 'Pediatric' or child-specific roles.",
  "reference_description": "Detailed description of the ideal/standard movement pattern shown in this video. Use age-neutral language (e.g., 'the player', 'the person', 'the individual'). Include specific details about:
    - Body positioning and alignment
    - Joint angles and ranges of motion
    - Timing and sequencing
    - What 'good' performance looks like",
  "analysis_instruction": "Step-by-step instructions for AI to follow when analyzing a video against this standard. Use age-neutral language (e.g., 'the player', 'the person'). Be specific about:
    - What to observe frame by frame
    - Key biomechanical markers to look for
    - How to compare the person's movement to this standard
    - What deviations to flag",
  "text_standards": {{
    "source_files": "Based on uploaded standard demonstration video",
    "rubric": "Detailed assessment rubric for ALL AGE GROUPS. Include:
      - Scoring criteria (what constitutes good vs concerning)
      - Age-appropriate expectations for: Infant/Toddler (0-5), Child (6-13), Teen (14-19), Adult (20-64), Elderly (65+)
      - Common deviations and their significance
      - Red flags that require professional evaluation
      - Adjust expectations based on age and experience level"
  }}
}}

CRITICAL REQUIREMENTS:
1. Use ONLY age-neutral language: 'player', 'person', 'individual', 'performer' (NOT 'child')
2. AI role must be age-neutral (NOT 'Pediatric' or child-specific)
3. Include age expectations for ALL groups: 0-5, 6-13, 14-19, 20-64, 65+
4. Make the rule applicable to any age group

Focus your analysis on:
1. **Biomechanics**: Joint angles, limb positioning, body alignment
2. **Motor Control**: Movement smoothness, timing, coordination
3. **Balance & Stability**: Base of support, center of mass control
4. **Functional Quality**: Efficiency, safety, age-appropriateness

Return ONLY valid JSON. Do not include any text before or after the JSON object."""
    
    def _parse_ai_response(self, ai_response: str, fallback_title: str) -> Dict[str, Any]:
        """
        Parse AI response and extract rule data
        
        Args:
            ai_response: Raw AI response text
            fallback_title: Fallback name if parsing fails
            
        Returns:
            Parsed rule data dictionary
        """
        try:
            # Log the raw AI response for debugging
            logger.info(f"Raw AI response length: {len(ai_response)} characters")
            logger.debug(f"Raw AI response (first 500 chars): {ai_response[:500]}")
            
            # Remove markdown code blocks if present
            cleaned_response = ai_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]  # Remove ```
            
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  # Remove trailing ```
            
            cleaned_response = cleaned_response.strip()
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                logger.info(f"Extracted JSON length: {len(json_str)} characters")
                data = json.loads(json_str)
            else:
                # If no JSON found, try parsing the whole cleaned response
                logger.warning("No JSON object found in AI response, trying to parse entire response")
                data = json.loads(cleaned_response)
            
            # Validate and extract required fields
            rule_data = {
                'category': data.get('category', fallback_title),
                'description': data.get('description', ''),
                'ai_role': data.get('ai_role', 'Movement Analysis Specialist'),
                'reference_description': data.get('reference_description', ''),
                'analysis_instruction': data.get('analysis_instruction', ''),
                'text_standards': data.get('text_standards', {
                    'source_files': 'Standard demonstration video',
                    'rubric': 'Auto-generated from video analysis'
                }),
                'response_template': {
                    'structure': {
                        'User_View': 'Parent-friendly assessment summary',
                        'Staff_View': 'Professional clinical assessment',
                        'Storage_JSON': 'Structured data with metrics and findings'
                    },
                    'instruction': 'Provide assessment in three formats as specified'
                }
            }
            
            logger.info(f"Successfully parsed rule data: category='{rule_data['category']}', ai_role='{rule_data['ai_role']}'")
            logger.info(f"Parsed field lengths - ref_desc: {len(rule_data['reference_description'])}, analysis: {len(rule_data['analysis_instruction'])}")
            
            return rule_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI JSON response: {e}")
            logger.error(f"AI response that failed to parse: {ai_response[:1000]}")
            # Return basic rule with raw AI response
            return {
                'category': fallback_title,
                'description': 'Auto-generated from standard video analysis',
                'ai_role': 'Movement Analysis Specialist',
                'reference_description': ai_response[:500],  # Truncate if too long
                'analysis_instruction': 'Analyze movement patterns and compare to standard',
                'text_standards': {
                    'source_files': 'Standard demonstration video',
                    'rubric': 'Review and refine this auto-generated rule'
                },
                'response_template': {
                    'structure': {
                        'User_View': 'Parent-friendly summary',
                        'Staff_View': 'Clinical assessment',
                        'Storage_JSON': 'Structured data'
                    }
                }
            }
    
    def _generate_index_code(self, movement_title: str) -> str:
        """
        Generate a unique index code for the rule
        
        Args:
            movement_title: Movement name
            
        Returns:
            Index code string (e.g., "AUTO_SINGLE_LEG_BALANCE_20260131")
        """
        import datetime
        
        # Clean and normalize title
        clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', movement_title)
        clean_title = '_'.join(clean_title.upper().split())
        
        # Limit length to leave room for timestamp
        if len(clean_title) > 20:
            clean_title = clean_title[:20]
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return f"AUTO_{clean_title}_{timestamp}"


# Singleton instance
_analyzer = None

def get_standard_video_analyzer() -> StandardVideoAnalyzer:
    """Get or create singleton StandardVideoAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = StandardVideoAnalyzer()
    return _analyzer
