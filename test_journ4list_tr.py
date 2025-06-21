#!/usr/bin/env python3
"""
Lean test for journ4list library with Turkish parameters.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from journalist import Journalist

# Simple logging setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def test_journ4list_with_tr_params():
    """Test journ4list library with Turkish search parameters."""
    logger.info("Starting journ4list test with Turkish parameters...")
      # Inline parameters
    urls = [
        "https://www.fanatik.com.tr/",
        "https://www.fotomac.com.tr/"
    ]
    keywords = ["Fenerbahce", "Mourinho"]
    
    # Initialize journalist
    journalist = Journalist()
    logger.info("Journalist initialized")
    
    # Test all URLs at once
    try:
        result = await journalist.read(urls=urls, keywords=keywords)
        articles = result.get('articles', [])
        
        logger.info(f"Extracted {len(articles)} articles from {len(urls)} URLs")
        
        # Show sample articles
        for i, article in enumerate(articles[:3], 1):  # Show first 3
            logger.info(f"Article {i}: {article.get('title', 'N/A')}")
        
        return {"articles_count": len(articles), "articles": articles}
        
    except Exception as e:
        logger.error(f"Failed to extract content: {e}")
        return {"articles_count": 0, "articles": [], "error": str(e)}


def generate_summary_report(results: List[Dict], keywords: List[str]):
    """Generate a lean summary report"""
    total_articles = sum(r.get("articles_count", 0) for r in results)
    successful_urls = sum(1 for r in results if "error" not in r)
    
    logger.info(f"Keywords: {keywords}")
    logger.info(f"URLs tested: {len(results)}, Successful: {successful_urls}")
    logger.info(f"Total articles: {total_articles}")
    
    # Save results
    with open("journ4list_tr_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Results saved to journ4list_tr_results.json")


def main():
    """Run the lean test"""
    try:
        result = asyncio.run(test_journ4list_with_tr_params())
        if result:
            generate_summary_report([result], ["Fenerbahce", "Mourinho"])
        logger.info("Test completed!")
    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == "__main__":
    main()
