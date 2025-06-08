#!/usr/bin/env python3
"""
Simple test to verify modular imports work without circular dependencies.
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_modular_imports():
    """Test that each modular component can be imported independently"""
    logger.info("Testing modular imports...")
    
    try:
        # Test 1: Config
        from capabilities.scraping.config import ScrapingConfig
        config = ScrapingConfig()
        logger.info("✅ ScrapingConfig imported successfully")
        
        # Test 2: Session Manager  
        from capabilities.scraping.session_manager import SessionManager
        session_manager = SessionManager()
        logger.info("✅ SessionManager imported successfully")
        
        # Test 3: Cache Manager
        from capabilities.scraping.cache_manager import CacheManager
        cache_manager = CacheManager('./test_cache', 1)
        logger.info("✅ CacheManager imported successfully")
        
        # Test 4: Link Discoverer
        from capabilities.scraping.link_discoverer import LinkDiscoverer
        link_discoverer = LinkDiscoverer(config)
        logger.info("✅ LinkDiscoverer imported successfully")
        
        # Test 5: File Manager
        from capabilities.scraping.file_manager import FileManager
        file_manager = FileManager('./test_cache')
        logger.info("✅ FileManager imported successfully")
        
        # Test 6: Base Extractor
        from capabilities.scraping.extractors.base_extractor import BaseExtractor
        logger.info("✅ BaseExtractor imported successfully")
        
        # Test 7: Content Extractor (this one coordinates all extractors)
        from capabilities.scraping.content_extractor import ContentExtractor
        content_extractor = ContentExtractor(config)
        logger.info("✅ ContentExtractor imported successfully")
        
        # Test 8: Modular Web Scraper
        from capabilities.scraping.web_scraper import WebScraper as ModularWebScraper
        modular_scraper = ModularWebScraper('./test_cache', 1)
        logger.info("✅ ModularWebScraper imported successfully")
        
        # Test 9: Package-level imports
        from capabilities.scraping import WebScraper, ScrapingConfig
        logger.info("✅ Package-level imports work")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backward_compatibility():
    """Test backward compatibility wrapper"""
    logger.info("Testing backward compatibility...")
    
    try:
        from capabilities.web_scraper import WebScraper
        scraper = WebScraper('./test_cache', 1)
        logger.info("✅ Backward compatibility wrapper works")
        return True
        
    except Exception as e:
        logger.error(f"❌ Backward compatibility failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting modular import test")
    
    modular_success = test_modular_imports()
    compat_success = test_backward_compatibility()
    
    if modular_success and compat_success:
        logger.info("🎉 All imports successful! Circular dependencies resolved.")
    else:
        logger.error("💥 Some imports failed")
        
    sys.exit(0 if (modular_success and compat_success) else 1)
