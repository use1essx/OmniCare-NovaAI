#!/usr/bin/env python3
"""
Healthcare AI V2 - Seed Assessment Rules
Migrates default assessment rules from gemini.json to database
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import init_database, get_async_session_context
from src.movement_analysis.models import AssessmentRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default rules based on gemini.json
DEFAULT_RULES = [
    {
        "index_code": "01_Core_Gait_and_Alignment",
        "category": "Walking and Leg Alignment",
        "description": "Assesses straight-line walking gait and lower limb alignment in children aged 3–10 years, combining dynamic gait features with static posture cues (O-legs/X-legs, in-toeing/out-toeing, trunk alignment).",
        "ai_role": "Pediatric Gait and Alignment Screener",
        "reference_video_url": "https://www.youtube.com/watch?v=C_8GqQiTOzQ; https://www.theseus.fi/bitstream/10024/510152/2/Juuti_Savimaki.pdf",
        "reference_description": "Use a typically developing 3–14 year old child with normal gait and neutral alignment as a 0-point visual benchmark. Observe heel strike pattern, step symmetry, cadence, pelvic stability, knee alignment and foot progression angle.",
        "text_standards": {
            "source_files": "pediatric_gait_indicators_v1_1_bilingual.docx, AAPM&R Biomechanics, Gait-Concerns-.pdf, F-4200-PA-011, Juuti_Savimaki.pdf",
            "rubric": """Use a 0–32 scale for overall gait and alignment.
1. **Heel strike**: 0 = clear heel-first contact; 1 = flat-foot contact; 2 = tip-toe or forefoot-first pattern.
2. **Step symmetry**: 0 = symmetrical; 1 = mild difference; 2 = obvious limping or asymmetry.
3. **Cadence stability**: 0 = stable rhythm; 2 = frequent stops, hesitations, or sudden speed changes.
4. **Knee alignment by age**:
   - <2 years: physiologic genu varum (bow-legs) is usually normal.
   - 2–4 years: mild genu valgum (knock-knees, knee gap < 8 cm) is usually normal.
   - >7 years: legs should be near neutral; knee gap > 8 cm or clearly asymmetric is concerning.
5. **Rotation pattern**:
   - In-toeing: look for habitual 'W-sitting', medially curved forefoot, or excessive internal rotation during gait.
   - Out-toeing: in toddlers, mild external rotation can be physiologic; marked or asymmetric patterns require attention.
6. **Spine and trunk alignment**: check the ear-shoulder-hip vertical line, presence of forward head posture, high/low shoulder, or obvious lateral trunk lean.
7. **Overall developmental appropriateness**: compare observed gait and alignment with age-expected norms and red-flag features."""
        },
        "analysis_instruction": "From the single uploaded video, sample both quasi-static standing frames and walking frames. Estimate knee-to-knee and ankle-to-ankle distance, and observe the foot progression angle (in-toeing or out-toeing). Combine these findings with the child's age to judge whether the pattern is likely physiologic variation or potentially pathological. Highlight any red flags such as marked asymmetry, persistent tip-toe gait, or trunk lean.",
        "response_template": {
            "instruction": "Strictly follow the Markdown + JSON structure below. Do not change key names.",
            "structure": {
                "User_View": "Plain-language summary: whether the child's gait and leg alignment look within the typical range for their age. Avoid medical jargon; use phrases like 'knees slightly closer together' or 'feet point a little inward'. Include 1–3 key observations and 1–2 simple practice suggestions or when to consider re-testing.",
                "Staff_View": "More technical view for clinicians: include brief metadata, key visual findings, and a combined 'Gait and Alignment' section with level (Normal / Attention / High Attention), quantitative estimates (e.g., step length difference %, approximate knee gap, foot progression tendency), and time-stamped evidence where possible.",
                "Storage_JSON": "One-line compact JSON with findings (category = 'gait_alignment'), metrics (e.g., step_len_diff_pct, cadence, knee_dist_cm_approx, foot_progression_tendency), and recommendations."
            }
        }
    },
    {
        "index_code": "02_Functional_Mobility_TUG",
        "category": "Balance and Everyday Mobility",
        "description": "Evaluates the Timed Up and Go (TUG) task and Single-Leg Stance (SLS) to quantify dynamic balance and fall risk.",
        "ai_role": "Functional Assessment Specialist",
        "reference_video_url": "https://www.youtube.com/watch?v=tNay64Mab78",
        "reference_description": "Standard TUG sequence: sit-to-stand, walk 3 meters, turn, walk back, and sit down. Use this as a reference for segmenting the movement and judging fluency.",
        "text_standards": {
            "source_files": "SRAlab TUG, Physiopedia SLS, Gross Motor Developmental Milestones.pdf",
            "rubric": """1. **TUG time**:
   - Typical threshold: < 12 seconds for school-aged children.
   - Elevated fall risk: > 14 seconds or clearly slower than peers.
   - Observe: need for hand support when standing up, number of steps during turning, and freezing or hesitation.
2. **Single-Leg Stance (SLS)**:
   - Around 3 years: can often hold > 2 seconds.
   - Around 5 years: can often hold > 10 seconds.
   - Red flags: trunk sway > ~5 degrees, frequent use of arms for balance, or non-stance foot repeatedly touching the floor."""
        },
        "analysis_instruction": "Automatically detect the approximate start and end of the TUG sequence in the uploaded video. Estimate total TUG time and, where possible, split into phases (sit-to-stand, walking out, turning, walking back, sit-down). For SLS, estimate left and right single-leg stance duration and trunk sway amplitude. Compare with age-appropriate expectations and highlight increased fall-risk patterns.",
        "response_template": {
            "instruction": "Strictly follow the Markdown + JSON structure below.",
            "structure": {
                "User_View": "Explain balance and mobility in everyday language, e.g. 'turning was a bit wobbly' or 'stood on one leg for a few seconds'. Avoid raw seconds; instead describe performance relative to same-age peers (e.g. 'similar to most children' / 'a bit slower than peers'). Include gentle suggestions and when to consider in-person assessment.",
                "Staff_View": "Provide a structured summary for professionals: precise or estimated times (TUG total time, left/right SLS duration), turning performance, trunk sway angle, and any compensatory strategies. Note uncertainty when video quality or framing limits accuracy.",
                "Storage_JSON": "findings (category = 'balance_sls' and/or 'tug'), metrics (e.g., tug_time_sec_est, sls_L_sec_est, sls_R_sec_est, trunk_sway_deg_est), and recommendations."
            }
        }
    },
    {
        "index_code": "03_Advanced_Motor_Skills_TGMD",
        "category": "Advanced Motor Skills and Play",
        "description": "Screens running, jumping, hopping, skipping and related gross motor patterns based on TGMD-3 style criteria to identify coordination issues.",
        "ai_role": "Pediatric Motor Skills Assessor",
        "reference_video_url": "https://www.youtube.com/watch?v=ZNGn5NKgyIU",
        "reference_description": "Video demonstrating TGMD-3 reference movements (run, gallop, hop, skip, jump). Use as a visual template for a 'Mastery' level pattern.",
        "text_standards": {
            "source_files": "PMC11978908, Gross Motor Developmental Milestones.pdf",
            "rubric": """1. **Run**: clear flight phase (both feet off the ground), arms swing opposite to legs, trunk stable.
2. **Gallop**: same lead leg stays in front, rhythmical and fluent movement pattern.
3. **Hop (single-leg jump)**: non-support leg swings to generate power, landing is stable without repeated hops to regain balance.
4. **Skip**: consistent 'step-hop' pattern with regular rhythm.
5. **Coordination**: upper and lower limbs move in a coordinated, non-stiff manner; abrupt or segmented movement suggests poor coordination."""
        },
        "analysis_instruction": "Identify which gross motor skills (run, hop, jump, skip, etc.) appear in the uploaded video. For each, compare key movement features to the mastery template: presence of flight phase, arm-leg coordination, rhythm, and landing stability. Classify each observed skill as 'Mastery', 'Emerging', or 'Needs Support'.",
        "response_template": {
            "instruction": "Strictly follow the Markdown + JSON structure below.",
            "structure": {
                "User_View": "Describe coordination in simple terms, such as 'arm swing looks natural when running' or 'single-leg jumps are still a bit unsteady'. Suggest age-appropriate, playful home activities (e.g. obstacle runs, hopscotch).",
                "Staff_View": "Provide a brief professional summary of coordination, including which TGMD-style criteria are met or missing (e.g. 'no clear flight phase during run', 'skip rhythm inconsistent').",
                "Storage_JSON": "findings (category = 'coordination'), metrics (e.g., skill_level_score, movement_smoothness_est), and recommendations (e.g., 'practice obstacle course with varied stepping patterns')."
            }
        }
    }
]


async def seed_assessment_rules():
    """Seed default assessment rules to database"""
    logger.info("Starting assessment rules seeding...")
    
    # Initialize database
    await init_database()
    
    async with get_async_session_context() as db:
        created_count = 0
        skipped_count = 0
        
        for rule_data in DEFAULT_RULES:
            # Check if rule already exists
            result = await db.execute(
                select(AssessmentRule).where(
                    AssessmentRule.index_code == rule_data["index_code"]
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"Rule '{rule_data['index_code']}' already exists, skipping...")
                skipped_count += 1
                continue
            
            # Create new rule
            rule = AssessmentRule(
                index_code=rule_data["index_code"],
                category=rule_data["category"],
                description=rule_data["description"],
                ai_role=rule_data["ai_role"],
                reference_video_url=rule_data["reference_video_url"],
                reference_description=rule_data["reference_description"],
                text_standards=rule_data["text_standards"],
                analysis_instruction=rule_data["analysis_instruction"],
                response_template=rule_data["response_template"],
                is_active=True,
                created_by=None,  # System-created rule
                organization_id=None  # System-wide rule
            )
            
            db.add(rule)
            created_count += 1
            logger.info(f"Created rule: {rule_data['category']}")
        
        await db.commit()
        
        logger.info(f"Seeding complete: {created_count} created, {skipped_count} skipped")
        return created_count, skipped_count


async def main():
    """Main entry point"""
    try:
        created, skipped = await seed_assessment_rules()
        print(f"\n✅ Assessment rules seeded successfully!")
        print(f"   Created: {created}")
        print(f"   Skipped (already exist): {skipped}")
    except Exception as e:
        logger.error(f"Failed to seed rules: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

