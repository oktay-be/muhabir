"""
Test script for the new refactored AISports architecture.
Tests the separated scraping and analysis services.
"""

import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from capabilities.services.scraping_service import ScrapingService
from capabilities.ai_summarizer import AISummarizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_scraping_service():
    """Test the new ScrapingService with journ4list."""
    print("\n" + "="*60)
    print("🔧 TESTING SCRAPING SERVICE")
    print("="*60)
    
    try:
        scraping_service = ScrapingService()
        
        # Test URLs (Turkish sports sites)
        test_urls = [
            "https://www.fanatik.com.tr",
            "https://www.fotomac.com.tr"
        ]
        
        test_keywords = ["Fenerbahçe", "transfer", "futbol"]
        
        print(f"📰 Testing ScrapingService with journ4list...")
        print(f"🔗 URLs: {test_urls}")
        print(f"🔍 Keywords: {test_keywords}")
        
        # Test scraping with keywords
        result = await scraping_service.scrape_with_keywords(
            urls=test_urls,
            keywords=test_keywords,
            persist=True,
            scrape_depth=1
        )
        
        print(f"\n✅ Scraping Results:")
        print(f"   Session ID: {result.get('session_id')}")
        print(f"   Articles found: {len(result.get('articles', []))}")
        print(f"   Extraction summary: {result.get('extraction_summary')}")
        
        # Test session management
        latest = scraping_service.find_latest_session()
        print(f"\n📁 Latest session file: {latest}")
        
        all_sessions = scraping_service.list_all_sessions()
        print(f"📚 Total sessions available: {len(all_sessions)}")
        
        return result
        
    except Exception as e:
        print(f"❌ ScrapingService test failed: {e}")
        return None

async def test_analysis_service(session_data=None):
    """Test the AI analysis service."""
    print("\n" + "="*60)
    print("🧠 TESTING ANALYSIS SERVICE")
    print("="*60)
    
    try:
        # Get Google API key from environment
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if not google_api_key:
            print("⚠️  GOOGLE_API_KEY not set. Skipping AI tests.")
            return None
        
        ai_summarizer = AISummarizer(google_api_key=google_api_key)
        
        if not ai_summarizer.model:
            print("❌ AI model not initialized")
            return None
        
        print("✅ AI Summarizer initialized successfully")
        
        # Test 1: Use provided session data (persist=false scenario)
        if session_data and session_data.get('session_id'):
            print(f"\n🔄 Testing persist=false scenario (direct session data)")
            result = await ai_summarizer.process_news_with_claude4_prompt(
                session_data=session_data,
                use_claude4=True
            )
            
            print(f"✅ Analysis completed:")
            print(f"   Input articles: {len(session_data.get('articles', []))}")
            print(f"   Processed articles: {len(result.get('processed_articles', []))}")
            print(f"   Processing summary: {result.get('processing_summary', {})}")
            
        # Test 2: Use latest session file (persist=true scenario)
        print(f"\n🔄 Testing persist=true scenario (auto-discovery)")
        auto_result = await ai_summarizer.process_latest_journ4list_session(use_claude4=True)
        
        if "error" in auto_result:
            print(f"⚠️  Auto-discovery result: {auto_result['error']}")
        else:
            print(f"✅ Auto-discovery analysis completed:")
            print(f"   Processed articles: {len(auto_result.get('processed_articles', []))}")
        
        return auto_result
        
    except Exception as e:
        print(f"❌ Analysis service test failed: {e}")
        return None

async def test_full_workflow():
    """Test the complete separated workflow."""
    print("\n" + "="*60)
    print("🚀 TESTING FULL SEPARATED WORKFLOW")
    print("="*60)
    
    # Step 1: Scraping
    print("Step 1: Scraping with journ4list...")
    scraping_result = await test_scraping_service()
    
    if scraping_result and scraping_result.get('session_id'):
        print(f"✅ Scraping completed successfully")
        
        # Step 2: Analysis
        print(f"\nStep 2: AI Analysis...")
        analysis_result = await test_analysis_service(scraping_result)
        
        if analysis_result and "error" not in analysis_result:
            print(f"✅ Full workflow completed successfully!")
            return True
        else:
            print(f"⚠️  Analysis step had issues")
            return False
    else:
        print(f"⚠️  Scraping step failed, skipping analysis")
        return False

def test_service_status():
    """Test service status and configuration."""
    print("\n" + "="*60)
    print("📊 TESTING SERVICE STATUS")
    print("="*60)
    
    try:
        # Test ScrapingService status
        scraping_service = ScrapingService()
        print(f"📁 Workspace directory: {scraping_service.workspace_dir}")
        print(f"📁 Workspace exists: {os.path.exists(scraping_service.workspace_dir)}")
        
        sessions = scraping_service.list_all_sessions()
        print(f"📚 Available sessions: {len(sessions)}")
        
        latest = scraping_service.find_latest_session()
        if latest:
            info = scraping_service.get_session_info(latest)
            print(f"📊 Latest session info: {info}")
        
        # Test AI service status
        google_api_key = os.getenv('GOOGLE_API_KEY')
        print(f"\n🤖 Google API key configured: {bool(google_api_key)}")
        
        if google_api_key:
            try:
                ai_summarizer = AISummarizer(google_api_key=google_api_key)
                print(f"🤖 AI model ready: {bool(ai_summarizer.model)}")
                
                # Test Claude 4 prompt loading
                from capabilities.ai_summarizer import load_claude4_prompt
                prompt = load_claude4_prompt()
                print(f"📝 Claude 4 prompt loaded: {not prompt.startswith('Error:')}")
                
            except Exception as e:
                print(f"🤖 AI initialization error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Status test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🚀 AISports Refactored Architecture Tests")
    print("Using journ4list + separated services")
    print("="*80)
    
    # Test 1: Service status
    status_ok = test_service_status()
    
    # Test 2: Individual services
    if status_ok:
        # Test full workflow
        workflow_ok = await test_full_workflow()
        
        if workflow_ok:
            print("\n" + "="*60)
            print("🎉 ALL TESTS PASSED!")
            print("✅ ScrapingService working with journ4list")
            print("✅ AnalysisService working with AI")
            print("✅ Separated architecture functioning correctly")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("⚠️  SOME TESTS HAD ISSUES")
            print("Check the logs above for details")
            print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ SERVICE STATUS CHECKS FAILED")
        print("Please check configuration and dependencies")
        print("="*60)

if __name__ == "__main__":
    # Load environment variables if .env file exists
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()
    
    asyncio.run(main())
