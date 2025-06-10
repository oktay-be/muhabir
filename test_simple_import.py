#!/usr/bin/env python3
"""
Simple test to verify enhanced scraper functionality.
"""

import sys
import traceback

def test_import():
    """Test if we can import the enhanced scraper."""
    try:
        print("Testing imports...")
        from capabilities.scraping.web_scraper import WebScraper
        print("✅ WebScraper import successful")
        
        print("Testing initialization...")
        scraper = WebScraper(cache_dir="test_cache", cache_expiration_hours=1)
        print("✅ WebScraper initialization successful")
        
        print("Testing method availability...")
        assert hasattr(scraper, '_extract_content_multi_strategy'), "Multi-strategy method missing"
        print("✅ Multi-strategy method available")
        
        print("\n🎉 All tests passed! Enhanced scraper is ready.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1)
