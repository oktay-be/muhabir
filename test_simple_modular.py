#!/usr/bin/env python3
"""
Simple test to verify modular components can be imported and initialized
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_imports():
    """Test that all modular components can be imported"""
    try:
        print("Testing imports...")
          # Test main scraping components
        from capabilities.scraping import (
            WebScraper, ScrapingConfig, SessionManager, CacheManager, 
            LinkDiscoverer, ContentExtractor, FileManager
        )
        print("SUCCESS: Main scraping components imported successfully")
          # Test extractors
        from capabilities.scraping.extractors import (
            LdJsonExtractor, ReadabilityExtractor, 
            SelectorExtractor, FullpageExtractor
        )
        print("SUCCESS: Extractor components imported successfully")
        
        # Test backward compatibility
        from capabilities.web_scraper import WebScraper as LegacyScraper
        print("SUCCESS: Legacy compatibility import works")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Import failed: {e}")
        return False

def test_basic_initialization():
    """Test basic initialization of components"""
    try:
        print("\nTesting basic initialization...")
        
        from capabilities.scraping import ScrapingConfig, SessionManager, CacheManager
        
        # Test Config
        config = ScrapingConfig()
        print(f"SUCCESS: Config initialized with {len(config.site_specific_selectors)} sites")
          # Test SessionManager
        session_mgr = SessionManager()
        print("SUCCESS: SessionManager initialized")
        
        # Test CacheManager
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_mgr = CacheManager(cache_dir=temp_dir)
            print("SUCCESS: CacheManager initialized")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Initialization failed: {e}")
        return False

def main():
    """Run simple tests"""
    print("*** Running Simple Modular Component Tests ***")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
        
    # Test basic initialization
    if not test_basic_initialization():
        success = False
        
    print("\n" + "=" * 50)
    if success:
        print("SUCCESS: All simple tests passed!")
        print("SUCCESS: Modular refactoring is working correctly!")
    else:
        print("ERROR: Some tests failed!")
        
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
