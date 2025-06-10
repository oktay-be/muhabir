#!/usr/bin/env python3
"""
Test script for the enhanced web scraper with multi-strategy content extraction.
This test verifies that HTML entities are properly decoded.
"""

import asyncio
import os
import json
import sys
import logging

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from capabilities.scraping.web_scraper import WebScraper

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_enhanced_scraper():
    """Test the enhanced scraper with a problematic Turkish article"""
    
    # Use a test cache directory
    cache_dir = "test_cache_enhanced"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Initialize the enhanced scraper
    scraper = WebScraper(cache_dir=cache_dir, cache_expiration_hours=1)
    
    # Test with the problematic fotomac.com.tr URL
    test_url = "https://www.fotomac.com.tr/galatasaray/2025/06/10/galatasaraya-victor-osimhen-mujdesi-transfer-yarisinda-sona-yaklasildi"
    keywords = ["galatasaray", "transfer", "osimhen"]
    
    print(f"Testing enhanced scraper with URL: {test_url}")
    print(f"Keywords: {keywords}")
    
    try:
        async with scraper:
            # Test the multi-strategy extraction
            article_data = await scraper._scrape_single_article(test_url, keywords)
            
            if article_data:
                print(f"\n✅ SUCCESS: Article extracted successfully!")
                print(f"Title: {article_data['title']}")
                print(f"Content length: {len(article_data['content'])}")
                print(f"Extraction method: {article_data['extraction_method']}")
                
                # Check for HTML entities in the content
                content = article_data['content']
                title = article_data['title']
                
                # Check for common HTML entities that should be decoded
                entities_to_check = ['&apos;', '&hellip;', '&ndash;', '&mdash;', '&quot;', '&amp;', '&lt;', '&gt;']
                found_entities = []
                
                for entity in entities_to_check:
                    if entity in content or entity in title:
                        found_entities.append(entity)
                
                if found_entities:
                    print(f"\n⚠️  WARNING: Found unescaped HTML entities: {found_entities}")
                    print("This indicates the HTML entity decoding may not be working properly.")
                else:
                    print(f"\n✅ HTML Entity Check: All entities properly decoded!")
                
                # Show a sample of the content
                print(f"\n📄 Content Preview (first 300 chars):")
                print(f"{content[:300]}...")
                
                # Save test result
                test_result_file = os.path.join(cache_dir, "test_result.json")
                with open(test_result_file, 'w', encoding='utf-8') as f:
                    json.dump(article_data, f, indent=2, ensure_ascii=False)
                print(f"\nTest result saved to: {test_result_file}")
                
            else:
                print("❌ FAILED: No article data extracted")
                
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_enhanced_scraper())
