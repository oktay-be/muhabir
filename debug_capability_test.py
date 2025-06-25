#!/usr/bin/env python3

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from capabilities.scraping.web_scraper import WebScraper

async def debug_scrape_single_article():
    """Debug the scrape_single_article method to see what's happening"""
    
    # Mock HTML content that should trigger all the expected behaviors
    mock_html = """
    <html>
    <head>
        <title>Test Article Title</title>
    </head>
    <body>
        <article>
            <h1>Test Article Title</h1>
            <p>This is the first paragraph of content.</p>
            <p>This is the second paragraph with more details.</p>
        </article>
    </body>
    </html>
    """
    
    # Mock session response
    async_mock_response = AsyncMock()
    async_mock_response.read.return_value = mock_html.encode('utf-8')
    async_mock_response.status = 200
    async_mock_response.headers = {'content-type': 'text/html'}
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value = async_mock_response

        cache_dir_path = os.path.join(os.path.dirname(__file__), 'tmp_cache_scraper_details')
        if not os.path.exists(cache_dir_path):
            os.makedirs(cache_dir_path, exist_ok=True)
            
        scraper = WebScraper(cache_dir=cache_dir_path)
        
        url = "https://example.com/article1"
        keywords = ["test"]
        
        # Mock the cache to return None initially (no cached content)
        with patch.object(scraper.cache_manager, 'get_cached_content', return_value=None) as mock_get_cached, \
             patch.object(scraper.cache_manager, 'cache_content', MagicMock()) as mock_cache_content, \
             patch.object(scraper, '_save_article_with_url_filename', MagicMock()) as mock_save_article:

            print("=== Starting scrape_single_article ===")
            
            # Use the new modular API
            try:
                article_details = await scraper._scrape_single_article(url, keywords)
                print(f"Article details: {article_details}")
                
                print(f"\nMock call checks:")
                print(f"get_cached_content called: {mock_get_cached.called}")
                print(f"cache_content called: {mock_cache_content.called}")
                print(f"_save_article_with_url_filename called: {mock_save_article.called}")
                
                if article_details:
                    print(f"\nTitle: {article_details.get('title', 'N/A')}")
                    print(f"Content length: {len(article_details.get('content', ''))}")
                    print(f"URL: {article_details.get('url', 'N/A')}")
                else:
                    print("Article details is None!")
                    
            except Exception as e:
                print(f"Exception occurred: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_scrape_single_article())
