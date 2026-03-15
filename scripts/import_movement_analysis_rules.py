"""
Healthcare AI V2 - Movement Analysis Rules Import Script
Allows staff to import assessment rules from JSON files
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy import select
from src.database.connection import get_async_session_context
from src.movement_analysis.models import AssessmentRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def import_rules_from_json(
    json_path: str,
    organization_id: int = None,
    created_by: int = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Import assessment rules from a JSON file
    
    Args:
        json_path: Path to JSON file containing rules
        organization_id: Optional organization ID (None = system-wide)
        created_by: Optional user ID who created these rules
        dry_run: If True, only validate without importing
        
    Returns:
        Dictionary with import statistics
    """
    stats = {
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": []
    }
    
    # Load JSON file
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON file: {e}")
        stats["errors"].append(f"File load error: {str(e)}")
        return stats
    
    # Ensure it's a list
    if not isinstance(rules_data, list):
        rules_data = [rules_data]
    
    stats["total"] = len(rules_data)
    
    if dry_run:
        logger.info(f"DRY RUN: Would import {len(rules_data)} rules")
    
    async with get_async_session_context() as db:
        for idx, rule_json in enumerate(rules_data):
            try:
                # Extract fields from JSON
                index_code = rule_json.get("index", rule_json.get("index_code"))
                category = rule_json.get("category")
                description = rule_json.get("description")
                ai_role = rule_json.get("ai_role")
                reference_video_url = rule_json.get("reference_video_url")
                reference_description = rule_json.get("reference_description")
                analysis_instruction = rule_json.get("analysis_instruction")
                
                # Get text_standards
                text_standards = rule_json.get("text_standards", {})
                
                # Get response template
                response_template = rule_json.get(
                    "response_formatting_template",
                    rule_json.get("response_template", {})
                )
                
                # Validation
                if not category:
                    stats["errors"].append(f"Rule {idx+1}: Missing category")
                    stats["skipped"] += 1
                    continue
                
                if dry_run:
                    logger.info(f"  [{idx+1}] Would import: {category}")
                    stats["created"] += 1
                    continue
                
                # Check if rule exists (by index_code or category)
                existing = None
                if index_code:
                    result = await db.execute(
                        select(AssessmentRule).where(
                            AssessmentRule.index_code == index_code
                        )
                    )
                    existing = result.scalar_one_or_none()
                
                if not existing:
                    # Also check by category for system rules
                    result = await db.execute(
                        select(AssessmentRule).where(
                            AssessmentRule.category == category,
                            AssessmentRule.organization_id.is_(None)
                        )
                    )
                    existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing rule
                    existing.description = description
                    existing.ai_role = ai_role
                    existing.reference_video_url = reference_video_url
                    existing.reference_description = reference_description
                    existing.text_standards = text_standards
                    existing.analysis_instruction = analysis_instruction
                    existing.response_template = response_template
                    
                    logger.info(f"✓ Updated rule: {category} (ID: {existing.id})")
                    stats["updated"] += 1
                else:
                    # Create new rule
                    new_rule = AssessmentRule(
                        index_code=index_code,
                        category=category,
                        description=description,
                        ai_role=ai_role,
                        reference_video_url=reference_video_url,
                        reference_description=reference_description,
                        text_standards=text_standards,
                        analysis_instruction=analysis_instruction,
                        response_template=response_template,
                        is_active=True,
                        created_by=created_by,
                        organization_id=organization_id
                    )
                    
                    db.add(new_rule)
                    await db.flush()  # Get the ID
                    
                    logger.info(f"✓ Created rule: {category} (ID: {new_rule.id})")
                    stats["created"] += 1
                
            except Exception as e:
                logger.error(f"Error processing rule {idx+1}: {e}")
                stats["errors"].append(f"Rule {idx+1} ({rule_json.get('category', 'unknown')}): {str(e)}")
                stats["skipped"] += 1
                continue
        
        if not dry_run:
            await db.commit()
            logger.info("✅ Import complete! Changes committed to database.")
        else:
            logger.info("✅ Dry run complete! No changes made.")
    
    return stats


async def import_from_assessment_system(
    assessment_dir: str = "/workspaces/fyp2526-use1essx/assessment/rule",
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Import all rules from the assessment system
    
    Args:
        assessment_dir: Path to assessment/rule directory
        dry_run: If True, only validate
        
    Returns:
        Combined statistics
    """
    assessment_path = Path(assessment_dir)
    
    if not assessment_path.exists():
        logger.error(f"Assessment directory not found: {assessment_dir}")
        return {"error": "Directory not found"}
    
    all_stats = {
        "files": [],
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": []
    }
    
    # Find all JSON files
    json_files = list(assessment_path.glob("*.json"))
    
    if not json_files:
        logger.warning(f"No JSON files found in {assessment_dir}")
        return all_stats
    
    logger.info(f"Found {len(json_files)} JSON files to import")
    
    for json_file in json_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Importing from: {json_file.name}")
        logger.info(f"{'='*60}")
        
        stats = await import_rules_from_json(
            str(json_file),
            organization_id=None,  # System-wide rules
            created_by=None,
            dry_run=dry_run
        )
        
        all_stats["files"].append({
            "filename": json_file.name,
            "stats": stats
        })
        
        all_stats["total"] += stats["total"]
        all_stats["created"] += stats["created"]
        all_stats["updated"] += stats["updated"]
        all_stats["skipped"] += stats["skipped"]
        all_stats["errors"].extend(stats["errors"])
    
    return all_stats


async def main():
    """Main entry point for manual imports"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python import_rules.py <json_file>              # Import specific file")
        print("  python import_rules.py --from-assessment        # Import all from assessment")
        print("  python import_rules.py --dry-run <json_file>    # Test without importing")
        return
    
    dry_run = "--dry-run" in sys.argv
    
    if "--from-assessment" in sys.argv:
        logger.info("Importing from assessment system...")
        stats = await import_from_assessment_system(dry_run=dry_run)
    else:
        json_path = sys.argv[-1]
        stats = await import_rules_from_json(json_path, dry_run=dry_run)
    
    # Print summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"Total rules processed: {stats['total']}")
    print(f"Created: {stats['created']}")
    print(f"Updated: {stats['updated']}")
    print(f"Skipped: {stats['skipped']}")
    
    if stats.get("errors"):
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats["errors"]:
            print(f"  - {error}")
    
    if dry_run:
        print("\n⚠️  DRY RUN - No changes were made to the database")
    else:
        print("\n✅ Import complete!")


if __name__ == "__main__":
    asyncio.run(main())
