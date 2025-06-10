#!/usr/bin/env python3
"""
Debug import issues step by step.
"""

def test_step_by_step():
    try:
        print("Step 1: Testing basic imports...")
        import logging
        import asyncio
        print("✅ Basic imports OK")
        
        print("Step 2: Testing config import...")
        from capabilities.scraping.config import ScrapingConfig
        print("✅ Config import OK")
        
        print("Step 3: Testing session manager import...")
        from capabilities.scraping.session_manager import SessionManager
        print("✅ SessionManager import OK")
        
        print("Step 4: Testing cache manager import...")
        from capabilities.scraping.cache_manager import CacheManager
        print("✅ CacheManager import OK")
        
        print("Step 5: Testing link discoverer import...")
        from capabilities.scraping.link_discoverer import LinkDiscoverer
        print("✅ LinkDiscoverer import OK")
        
        print("Step 6: Testing content extractor import...")
        from capabilities.scraping.content_extractor import ContentExtractor
        print("✅ ContentExtractor import OK")
        
        print("Step 7: Testing file manager import...")
        from capabilities.scraping.file_manager import FileManager
        print("✅ FileManager import OK")
        
        print("Step 8: Testing web scraper import...")
        from capabilities.scraping.web_scraper import WebScraper
        print("✅ WebScraper import OK")
        
        print("\n🎉 All imports successful!")
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_step_by_step()
