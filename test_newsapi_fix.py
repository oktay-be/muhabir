#!/usr/bin/env python3
"""
Test script to verify the NewsAPI parameter fixes in NewsAggregator
"""

import asyncio
import os
import sys
sys.path.append('.')

from capabilities.news_aggregator import NewsAggregator

async def test_newsapi_fix():
    """Test the fixed NewsAPI parameters"""
    
    # Get API key from environment
    api_key = os.environ.get("NEWSAPI_KEY", "7d518cdcc9ca4ccba0040eaf1e6334af")
    
    # Create NewsAggregator instance
    aggregator = NewsAggregator(
        newsapi_key=api_key,
        cache_dir="./cache",
        cache_expiration_hours=1
    )
    
    # Set test keywords
    aggregator.update_keywords(["Fenerbahce", "Mourinho"])
    
    print("Testing NewsAPI with fixed parameters...")
    print(f"Keywords: {aggregator.additional_keywords}")
    print(f"Languages: {aggregator.languages}")
    print(f"Max results: {aggregator.max_results}")
    
    try:
        # Fetch articles
        articles = await aggregator.fetch_newsapi_articles()
        
        print(f"\n✅ SUCCESS: Received {len(articles)} articles from NewsAPI")
        
        if articles:
            print(f"\nFirst article:")
            print(f"  Title: {articles[0].get('title')}")
            print(f"  Source: {articles[0].get('source')}")
            print(f"  URL: {articles[0].get('url')}")
        
        return len(articles) > 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_newsapi_fix())
    if success:
        print("\n🎉 NewsAPI parameter fix is working!")
    else:
        print("\n😞 NewsAPI parameter fix needs more work.")
