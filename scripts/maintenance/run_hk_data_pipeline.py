#!/usr/bin/env python3
"""
Healthcare AI V2 - Hong Kong Data Pipeline Runner
Simple standalone script for HK data collection
"""

import asyncio
import logging
import time
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.config import get_settings
    settings = get_settings()
except Exception as e:
    print(f"❌ Configuration error: {e}")
    print("ℹ️  HK Data Pipeline will run in fallback mode")
    settings = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleHKDataPipeline:
    """Simple HK Data Pipeline for basic data collection"""
    
    def __init__(self):
        self.running = True
        logger.info("🇭🇰 Simple HK Data Pipeline initialized")
    
    async def fetch_hk_data(self):
        """Simulate HK data fetching"""
        try:
            logger.info("📊 Fetching Hong Kong healthcare data...")
            
            # Simulate data sources
            data_sources = [
                "Hospital Authority A&E waiting times",
                "Government clinic information", 
                "Health advisory updates",
                "Emergency service locations"
            ]
            
            for source in data_sources:
                logger.info(f"  • Processing: {source}")
                await asyncio.sleep(1)  # Simulate processing time
            
            logger.info("✅ HK data fetch completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error fetching HK data: {e}")
            return False
    
    async def run_pipeline(self):
        """Main pipeline loop"""
        logger.info("🚀 Starting HK Data Pipeline...")
        
        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                logger.info(f"🔄 Pipeline cycle #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Fetch data
                success = await self.fetch_hk_data()
                
                if success:
                    logger.info("📈 Data pipeline cycle completed successfully")
                else:
                    logger.warning("⚠️  Data pipeline cycle completed with errors")
                
                # Wait before next cycle (1 hour in production, 5 minutes in demo)
                wait_time = 300 if settings else 300  # 5 minutes for demo
                logger.info(f"⏰ Waiting {wait_time//60} minutes until next cycle...")
                
                await asyncio.sleep(wait_time)
                
            except KeyboardInterrupt:
                logger.info("🛑 Pipeline stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Pipeline error: {e}")
                logger.info("🔄 Retrying in 60 seconds...")
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop the pipeline"""
        self.running = False
        logger.info("🛑 Pipeline stop requested")

async def main():
    """Main entry point"""
    logger.info("🏥 Healthcare AI V2 - HK Data Pipeline Starting")
    
    pipeline = SimpleHKDataPipeline()
    
    try:
        await pipeline.run_pipeline()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down HK Data Pipeline...")
    except Exception as e:
        logger.error(f"❌ Fatal pipeline error: {e}")
    finally:
        pipeline.stop()
        logger.info("👋 HK Data Pipeline shutdown complete")

if __name__ == "__main__":
    # Run the pipeline
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 HK Data Pipeline stopped by user")
    except Exception as e:
        print(f"❌ Pipeline startup error: {e}")
        sys.exit(1)