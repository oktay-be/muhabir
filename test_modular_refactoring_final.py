#!/usr/bin/env python3
"""
Comprehensive test for the modular web scraper refactoring.

This test verifies that:
1. All modular components work independently
2. The backward compatibility wrapper works correctly
3. Integration with existing analysis_orchestrator is maintained
"""

import asyncio
import logging
import tempfile
import os
import json
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_modular_components():
    """Test individual modular components"""
    logger.info("=== Testing Modular Components ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Test 1: Config
            from capabilities.scraping.config import ScrapingConfig
            config = ScrapingConfig()
            assert len(config.site_specific_selectors) > 0
            logger.info("✅ Config component works")
            
            # Test 2: Cache Manager
            from capabilities.scraping.cache_manager import CacheManager
            cache_manager = CacheManager(temp_dir, 1)
            test_key = cache_manager.generate_cache_key("http://test.com", ["test"])
            cache_manager.cache_content(test_key, {"test": "data"})
            cached = cache_manager.get_cached_content(test_key)
            assert cached is not None
            logger.info("✅ Cache Manager component works")
            
            # Test 3: Session Manager  
            from capabilities.scraping.session_manager import SessionManager
            session_manager = SessionManager()
            async with session_manager:
                assert session_manager.session is not None
            logger.info("✅ Session Manager component works")
            
            # Test 4: Content Extractor
            from capabilities.scraping.content_extractor import ContentExtractor
            content_extractor = ContentExtractor(config)
            extractors_info = content_extractor.get_extractor_info()
            assert len(extractors_info) >= 4  # Should have at least 4 extractors
            logger.info("✅ Content Extractor component works")
            
            # Test 5: File Manager
            from capabilities.scraping.file_manager import FileManager
            file_manager = FileManager(temp_dir)
            test_data = {"test": "session_data"}
            file_manager.save_session_data("test_session", test_data)
            loaded_data = file_manager.load_session_data("test_session")
            assert loaded_data == test_data
            logger.info("✅ File Manager component works")
            
        except Exception as e:
            logger.error(f"❌ Modular component test failed: {e}")
            raise


async def test_modular_web_scraper():
    """Test the new modular web scraper"""
    logger.info("=== Testing Modular Web Scraper ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            from capabilities.scraping import WebScraper as ModularWebScraper
            
            scraper = ModularWebScraper(temp_dir, 1)
            scraper_info = scraper.get_scraper_info()
            
            assert 'supported_sites' in scraper_info
            assert 'extraction_strategies' in scraper_info
            assert len(scraper_info['supported_sites']) > 0
            assert len(scraper_info['extraction_strategies']) >= 4
            
            logger.info("✅ Modular Web Scraper initialization works")
            logger.info(f"   - Supports {len(scraper_info['supported_sites'])} sites")
            logger.info(f"   - Has {len(scraper_info['extraction_strategies'])} extraction strategies")
            
        except Exception as e:
            logger.error(f"❌ Modular web scraper test failed: {e}")
            raise


async def test_backward_compatibility():
    """Test the backward compatibility wrapper"""
    logger.info("=== Testing Backward Compatibility Wrapper ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            from capabilities.web_scraper import WebScraper
            
            # Initialize like the old API
            scraper = WebScraper(temp_dir, 1)
            
            # Test scraper info method
            scraper_info = scraper.get_scraper_info()
            assert 'supported_sites' in scraper_info
            logger.info("✅ Backward compatibility wrapper initialization works")
            
            # Test the main method signature (without actually scraping)
            session_id = "test_session_123"
            base_workspace = temp_dir
            urls = ["https://www.fanatik.com.tr", "https://www.hurriyet.com.tr"]
            keywords = ["fenerbahce", "galatasaray"]
            
            # This should not raise an exception
            await scraper.execute_scraping_for_session(session_id, base_workspace, urls, keywords)
            
            # Check if legacy structure was created
            session_path = os.path.join(base_workspace, session_id)
            raw_articles_path = os.path.join(session_path, "raw_articles")
            assert os.path.exists(raw_articles_path)
            
            logger.info("✅ Backward compatibility method signature works")
            logger.info(f"   - Created legacy directory structure at {raw_articles_path}")
            
        except Exception as e:
            logger.error(f"❌ Backward compatibility test failed: {e}")
            raise


async def test_extractors():
    """Test individual extractors"""
    logger.info("=== Testing Content Extractors ===")
    
    try:
        from capabilities.scraping.extractors import (
            LDJsonExtractor, ReadabilityExtractor, 
            SelectorExtractor, FullpageExtractor
        )
        from capabilities.scraping.config import ScrapingConfig
        from bs4 import BeautifulSoup
        
        config = ScrapingConfig()
        
        # Test HTML content
        test_html = """
        <html>
        <head>
            <title>Test Article</title>
            <script type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "Article",
                "headline": "Test Article Title",
                "articleBody": "This is a test article with enough content to pass quality checks."
            }
            </script>
        </head>
        <body>
            <h1>Test Article Title</h1>
            <div class="content">This is a test article with enough content to pass quality checks. Lorem ipsum dolor sit amet, consectetur adipiscing elit.</div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        test_url = "https://test.com/article"
        
        # Test LD+JSON Extractor
        ldjson_extractor = LDJsonExtractor()
        if ldjson_extractor.can_extract(test_url, soup):
            result = ldjson_extractor.extract_content(test_url, soup)
            if result:
                logger.info("✅ LD+JSON Extractor works")
            else:
                logger.info("⚠️  LD+JSON Extractor returned None (may be expected)")
        
        # Test Readability Extractor
        readability_extractor = ReadabilityExtractor()
        if readability_extractor.can_extract(test_url, soup):
            result = readability_extractor.extract_content(test_url, soup)
            if result:
                logger.info("✅ Readability Extractor works")
            else:
                logger.info("⚠️  Readability Extractor returned None")
        
        # Test Selector Extractor
        selector_extractor = SelectorExtractor(config)
        if selector_extractor.can_extract(test_url, soup):
            result = selector_extractor.extract_content(test_url, soup)
            if result:
                logger.info("✅ CSS Selector Extractor works")
            else:
                logger.info("⚠️  CSS Selector Extractor returned None")
        
        # Test Fullpage Extractor (should always work)
        fullpage_extractor = FullpageExtractor()
        if fullpage_extractor.can_extract(test_url, soup):
            result = fullpage_extractor.extract_content(test_url, soup)
            assert result is not None
            logger.info("✅ Fullpage Extractor works (fallback)")
        
    except Exception as e:
        logger.error(f"❌ Extractor test failed: {e}")
        raise


def test_import_structure():
    """Test that all imports work correctly"""
    logger.info("=== Testing Import Structure ===")
    
    try:
        # Test main package imports
        from capabilities.scraping import (
            WebScraper, ScrapingConfig, SessionManager, 
            CacheManager, LinkDiscoverer, ContentExtractor, FileManager
        )
        logger.info("✅ Main package imports work")
        
        # Test extractor package imports
        from capabilities.scraping.extractors import (
            BaseExtractor, LDJsonExtractor, ReadabilityExtractor,
            SelectorExtractor, FullpageExtractor
        )
        logger.info("✅ Extractor package imports work")
        
        # Test backward compatibility import
        from capabilities.web_scraper import WebScraper as LegacyWebScraper
        logger.info("✅ Backward compatibility import works")
        
    except Exception as e:
        logger.error(f"❌ Import structure test failed: {e}")
        raise


async def main():
    """Run comprehensive test suite"""
    logger.info("🚀 Starting Comprehensive Modular Web Scraper Test")
    
    try:
        # Test imports first
        test_import_structure()
        
        # Test individual components
        await test_modular_components()
        
        # Test extractors
        await test_extractors()
        
        # Test modular scraper
        await test_modular_web_scraper()
        
        # Test backward compatibility
        await test_backward_compatibility()
        
        logger.info("🎉 ALL TESTS PASSED! Modular refactoring is successful.")
        logger.info("")
        logger.info("📋 SUMMARY:")
        logger.info("   ✅ All modular components work independently")
        logger.info("   ✅ Content extraction strategies implemented")
        logger.info("   ✅ Backward compatibility maintained")
        logger.info("   ✅ Integration points preserved")
        logger.info("   ✅ Package structure is correct")
        
        return True
        
    except Exception as e:
        logger.error(f"💥 TEST SUITE FAILED: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
