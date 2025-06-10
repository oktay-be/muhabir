#!/usr/bin/env python3
"""
Test the enhanced scraper with actual problematic content.
"""

import asyncio
import logging
import json
from capabilities.scraping.web_scraper import WebScraper

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_enhanced_scraper_with_problematic_data():
    """Test the enhanced scraper with previously problematic content."""
    
    # Sample URL that had entity encoding issues
    test_url = "https://www.fotomac.com.tr/galatasaray/2025/06/10/galatasaraya-victor-osimhen-mujdesi-transfer-yarisinda-sona-yaklasildi"
    
    # Initialize the enhanced scraper
    cache_dir = "test_cache_enhanced_final"
    scraper = WebScraper(cache_dir=cache_dir, cache_expiration_hours=1)
    
    print("=== Testing Enhanced Multi-Strategy Scraper ===")
    print(f"Test URL: {test_url}")
    
    try:
        # Test single article extraction
        async with scraper:
            result = await scraper._scrape_single_article(test_url, ["galatasaray", "victor osimhen"])
            
            if result:
                print(f"\n✅ Successfully extracted content!")
                print(f"Extraction method: {result.get('extraction_method', 'unknown')}")
                print(f"Title: {result.get('title', 'No title')}")
                print(f"Content length: {len(result.get('content', ''))}")
                print(f"Content preview: {result.get('content', '')[:200]}...")
                
                # Check for entity encoding issues
                title = result.get('title', '')
                content = result.get('content', '')
                
                has_entity_issues = ('&apos;' in title or '&apos;' in content or 
                                   '&hellip;' in title or '&hellip;' in content or
                                   '&amp;' in title or '&amp;' in content)
                
                if has_entity_issues:
                    print("\n❌ ISSUE: Content still contains HTML entities!")
                    if '&apos;' in title or '&apos;' in content:
                        print("  Found &apos; entities")
                    if '&hellip;' in title or '&hellip;' in content:
                        print("  Found &hellip; entities")
                    if '&amp;' in title or '&amp;' in content:
                        print("  Found &amp; entities")
                else:
                    print("\n✅ SUCCESS: No HTML entity encoding issues detected!")
                
                # Save result for inspection
                output_file = "enhanced_scraper_test_result.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\nResult saved to: {output_file}")
                
            else:
                print("\n❌ FAILED: No content extracted")
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_enhanced_scraper_with_problematic_data())
