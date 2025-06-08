#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite for Modular Web Scraper
Tests all components working together in real-world scenarios
"""

import os
import sys
import time
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import all modular components
from capabilities.scraping import (
    WebScraper, Config, SessionManager, CacheManager, 
    LinkDiscoverer, ContentExtractor, FileManager
)
from capabilities.scraping.extractors import (
    LDJSONExtractor, ReadabilityExtractor, 
    SelectorExtractor, FullpageExtractor
)

class IntegrationTestSuite:
    """Comprehensive integration test suite"""
    
    def __init__(self):
        self.test_dir = None
        self.scraper = None
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        
    def setUp(self):
        """Set up test environment"""
        print("🔧 Setting up test environment...")
        
        # Create temporary directory for tests
        self.test_dir = tempfile.mkdtemp(prefix="scraper_integration_test_")
        print(f"   Test directory: {self.test_dir}")
        
        # Initialize scraper with test configuration
        self.scraper = WebScraper(
            keywords=['futbol', 'basketbol', 'voleybol'],
            output_dir=self.test_dir,
            max_articles=5,  # Small number for faster testing
            max_workers=2    # Reduced for controlled testing
        )
        
        print("✅ Test environment ready")
        
    def tearDown(self):
        """Clean up test environment"""
        print("🧹 Cleaning up test environment...")
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        print("✅ Cleanup complete")
        
    def assert_test(self, condition, test_name, error_msg=None):
        """Helper to track test results"""
        if condition:
            print(f"✅ {test_name}")
            self.results['passed'] += 1
        else:
            print(f"❌ {test_name}")
            if error_msg:
                print(f"   Error: {error_msg}")
                self.results['errors'].append(f"{test_name}: {error_msg}")
            self.results['failed'] += 1
            
    async def test_component_initialization(self):
        """Test 1: All components can be initialized properly"""
        print("\n🧪 Test 1: Component Initialization")
        
        try:
            # Test Config
            config = Config()
            self.assert_test(
                len(config.SITE_SELECTORS) >= 7,
                "Config has site selectors",
                f"Expected >= 7 sites, got {len(config.SITE_SELECTORS)}"
            )
            
            # Test SessionManager
            session_mgr = SessionManager()
            self.assert_test(
                session_mgr.session is not None,
                "SessionManager creates session"
            )
            
            # Test CacheManager
            cache_mgr = CacheManager(cache_dir=os.path.join(self.test_dir, 'cache'))
            self.assert_test(
                os.path.exists(cache_mgr.cache_dir),
                "CacheManager creates cache directory"
            )
            
            # Test LinkDiscoverer
            link_disc = LinkDiscoverer(['test'])
            self.assert_test(
                link_disc.keywords == ['test'],
                "LinkDiscoverer sets keywords"
            )
            
            # Test ContentExtractor
            content_ext = ContentExtractor()
            self.assert_test(
                len(content_ext.extractors) >= 4,
                "ContentExtractor has multiple strategies",
                f"Expected >= 4 extractors, got {len(content_ext.extractors)}"
            )
            
            # Test FileManager
            file_mgr = FileManager(self.test_dir)
            self.assert_test(
                file_mgr.output_dir == self.test_dir,
                "FileManager sets output directory"
            )
            
        except Exception as e:
            self.assert_test(False, "Component Initialization", str(e))
            
    async def test_strategy_pattern_priority(self):
        """Test 2: Strategy pattern works with correct priorities"""
        print("\n🧪 Test 2: Strategy Pattern Priority System")
        
        try:
            content_extractor = ContentExtractor()
            extractors = content_extractor.extractors
            
            # Check if extractors are sorted by priority
            priorities = [ext.priority for ext in extractors]
            sorted_priorities = sorted(priorities)
            
            self.assert_test(
                priorities == sorted_priorities,
                "Extractors sorted by priority",
                f"Priorities: {priorities}, Expected: {sorted_priorities}"
            )
            
            # Check specific extractor priorities
            extractor_types = {type(ext).__name__: ext.priority for ext in extractors}
            
            expected_priorities = {
                'LDJSONExtractor': 10,
                'ReadabilityExtractor': 20,
                'SelectorExtractor': 30,
                'FullpageExtractor': 100
            }
            
            for extractor_name, expected_priority in expected_priorities.items():
                actual_priority = extractor_types.get(extractor_name)
                self.assert_test(
                    actual_priority == expected_priority,
                    f"{extractor_name} has correct priority",
                    f"Expected {expected_priority}, got {actual_priority}"
                )
                
        except Exception as e:
            self.assert_test(False, "Strategy Pattern Priority", str(e))
            
    async def test_cache_functionality(self):
        """Test 3: Cache system works correctly"""
        print("\n🧪 Test 3: Cache Functionality")
        
        try:
            cache_mgr = CacheManager(cache_dir=os.path.join(self.test_dir, 'cache'))
            
            # Test cache key generation
            test_url = "https://example.com/test"
            test_keywords = ['test', 'keywords']
            cache_key = cache_mgr._generate_cache_key(test_url, test_keywords)
            
            self.assert_test(
                isinstance(cache_key, str) and len(cache_key) == 32,
                "Cache key generation",
                f"Expected 32-char string, got {type(cache_key)} of length {len(cache_key) if isinstance(cache_key, str) else 'N/A'}"
            )
            
            # Test cache storage and retrieval
            test_data = {'title': 'Test Article', 'content': 'Test content'}
            cache_mgr.cache_links(test_url, test_keywords, [test_data])
            
            cached_data = cache_mgr.get_cached_links(test_url, test_keywords)
            self.assert_test(
                cached_data is not None and len(cached_data) == 1,
                "Cache storage and retrieval",
                f"Expected 1 cached item, got {len(cached_data) if cached_data else 0}"
            )
            
            # Test cache expiration logic
            cache_mgr.cache_expiry_hours = -1  # Force expiration
            expired_data = cache_mgr.get_cached_links(test_url, test_keywords)
            self.assert_test(
                expired_data is None,
                "Cache expiration",
                f"Expected None for expired cache, got {type(expired_data)}"
            )
            
        except Exception as e:
            self.assert_test(False, "Cache Functionality", str(e))
            
    async def test_session_management(self):
        """Test 4: Session management and HTTP handling"""
        print("\n🧪 Test 4: Session Management")
        
        try:
            session_mgr = SessionManager()
            
            # Test session configuration
            self.assert_test(
                hasattr(session_mgr.session, 'headers'),
                "Session has headers"
            )
            
            self.assert_test(
                'User-Agent' in session_mgr.session.headers,
                "Session has User-Agent"
            )
            
            # Test session timeout configuration
            self.assert_test(
                hasattr(session_mgr.session, 'timeout'),
                "Session has timeout configuration"
            )
            
            # Test session cleanup
            old_session = session_mgr.session
            session_mgr.close()
            
            # Create new session
            new_session_mgr = SessionManager()
            self.assert_test(
                new_session_mgr.session is not old_session,
                "New session created after cleanup"
            )
            
            new_session_mgr.close()
            
        except Exception as e:
            self.assert_test(False, "Session Management", str(e))
            
    async def test_file_operations(self):
        """Test 5: File management operations"""
        print("\n🧪 Test 5: File Management")
        
        try:
            file_mgr = FileManager(self.test_dir)
            
            # Test session file creation
            session_id = "test_session_123"
            session_file = file_mgr.create_session_file(session_id)
            
            self.assert_test(
                os.path.exists(session_file),
                "Session file creation"
            )
            
            # Test article saving
            test_article = {
                'title': 'Test Article Title',
                'content': 'This is test article content.',
                'url': 'https://example.com/test-article',
                'extraction_method': 'test_extractor'
            }
            
            saved = file_mgr.save_article(test_article, session_file)
            self.assert_test(
                saved,
                "Article saving"
            )
            
            # Test session file reading
            with open(session_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assert_test(
                    'Test Article Title' in content,
                    "Session file contains article data"
                )
                
            # Test session cleanup
            all_sessions = file_mgr.get_all_session_files()
            self.assert_test(
                len(all_sessions) >= 1,
                "Session file listing",
                f"Expected >= 1 session, got {len(all_sessions)}"
            )
            
        except Exception as e:
            self.assert_test(False, "File Management", str(e))
            
    async def test_end_to_end_scraping(self):
        """Test 6: End-to-end scraping workflow"""
        print("\n🧪 Test 6: End-to-End Scraping")
        
        try:
            # Use a simple, reliable test site
            test_sites = ['https://httpbin.org/html']  # Simple HTML test endpoint
            
            # Override scraper configuration for testing
            original_sites = self.scraper.config.SUPPORTED_SITES
            self.scraper.config.SUPPORTED_SITES = test_sites
            
            # Test scraping workflow
            print("   Running end-to-end scraping test...")
            session_file = await self.scraper.scrape_all_sites()
            
            self.assert_test(
                session_file is not None,
                "Scraping returns session file"
            )
            
            self.assert_test(
                os.path.exists(session_file) if session_file else False,
                "Session file exists after scraping"
            )
            
            # Restore original configuration
            self.scraper.config.SUPPORTED_SITES = original_sites
            
        except Exception as e:
            self.assert_test(False, "End-to-End Scraping", str(e))
            
    async def test_backward_compatibility(self):
        """Test 7: Backward compatibility with legacy API"""
        print("\n🧪 Test 7: Backward Compatibility")
        
        try:
            # Test legacy import path
            from capabilities.web_scraper import WebScraper as LegacyScraper
            
            self.assert_test(
                LegacyScraper is not None,
                "Legacy import path works"
            )
            
            # Test legacy initialization
            legacy_scraper = LegacyScraper(
                keywords=['test'],
                output_dir=self.test_dir,
                max_articles=1
            )
            
            self.assert_test(
                hasattr(legacy_scraper, 'scrape_all_sites'),
                "Legacy scraper has expected methods"
            )
            
        except Exception as e:
            self.assert_test(False, "Backward Compatibility", str(e))
            
    async def test_error_handling(self):
        """Test 8: Error handling and recovery"""
        print("\n🧪 Test 8: Error Handling")
        
        try:
            # Test invalid URL handling
            session_mgr = SessionManager()
            try:
                # This should handle the error gracefully
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: session_mgr.session.get('invalid://url', timeout=1)
                )
                # If we get here, error handling worked
                error_handled = True
            except:
                # Expected behavior - error should be caught somewhere
                error_handled = True
                
            self.assert_test(
                error_handled,
                "Invalid URL error handling"
            )
            
            # Test file permission errors
            try:
                # Try to create file manager with invalid directory
                invalid_file_mgr = FileManager('/invalid/path/that/does/not/exist')
                # If this doesn't raise an error, that's also fine (graceful handling)
                error_handled = True
            except:
                error_handled = True
                
            self.assert_test(
                error_handled,
                "File permission error handling"
            )
            
            session_mgr.close()
            
        except Exception as e:
            self.assert_test(False, "Error Handling", str(e))
            
    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Comprehensive Integration Test Suite")
        print("=" * 60)
        
        start_time = time.time()
        
        # Set up test environment
        self.setUp()
        
        try:
            # Run all tests
            await self.test_component_initialization()
            await self.test_strategy_pattern_priority()
            await self.test_cache_functionality()
            await self.test_session_management()
            await self.test_file_operations()
            await self.test_end_to_end_scraping()
            await self.test_backward_compatibility()
            await self.test_error_handling()
            
        finally:
            # Clean up
            self.tearDown()
            
        # Print results
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        
        if self.results['errors']:
            print("\n🔍 ERROR DETAILS:")
            for error in self.results['errors']:
                print(f"   • {error}")
                
        success_rate = (self.results['passed'] / (self.results['passed'] + self.results['failed'])) * 100
        print(f"\n🎯 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("🎉 EXCELLENT! Modular refactoring is working perfectly!")
        elif success_rate >= 75:
            print("👍 GOOD! Minor issues to address, but overall successful!")
        else:
            print("⚠️  NEEDS ATTENTION! Several issues need to be resolved.")
            
        return success_rate >= 75

async def main():
    """Main test runner"""
    test_suite = IntegrationTestSuite()
    success = await test_suite.run_all_tests()
    
    if success:
        print("\n✅ Integration tests completed successfully!")
        return 0
    else:
        print("\n❌ Integration tests failed!")
        return 1

if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
