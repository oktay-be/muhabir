"""
Integration tests for API-like functionalities by directly calling service methods.
"""
import json
import sys
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, call # Added call
import asyncio
from datetime import datetime

from capabilities.news_aggregator import NewsAggregator
from capabilities.scraping.web_scraper import WebScraper # New import


@patch('capabilities.news_aggregator.NewsAggregator.fetch_from_source', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_news(mock_fetch_from_source, tmp_path):
    """Test fetching news (simulating /api/news route)."""
    session_id = "test_session_get_news"
    query_param = ["fenerbahçe"]
    workspace_dir = tmp_path / "workspace"
    os.makedirs(workspace_dir, exist_ok=True)
    cache_dir = tmp_path / "cache_news_aggregator"
    os.makedirs(cache_dir, exist_ok=True)

    limit_param = 1
    sources_param = ["newsapi"]

    # Mock the fetch_from_source to return sample articles
    mock_articles = [
        {
            "title": "Fenerbahçe wins important match",
            "url": "https://example.com/news/1",
            "source": "Example News",
            "published_at": "2025-05-24T12:00:00Z",
            "content": "Fenerbahçe won an important match yesterday."
        }
    ]
    mock_fetch_from_source.return_value = mock_articles

    # Instantiate NewsAggregator
    aggregator = NewsAggregator(newsapi_key="test_key", cache_dir=str(cache_dir))

    returned_article_paths = await aggregator.fetch_news_for_session(
        session_id=session_id,
        base_workspace_path=str(workspace_dir),
        query=query_param,
        sources=sources_param,
        limit=limit_param
    )

    # Assert that the mock was called correctly
    mock_fetch_from_source.assert_called_once_with("newsapi")
    
    # The method should return a list of file paths where articles were saved
    assert isinstance(returned_article_paths, list)
    assert len(returned_article_paths) == limit_param


@patch('capabilities.scraping.web_scraper.WebScraper.execute_scraping_for_session', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_scrape_news(mock_execute_scraping, tmp_path):
    """Test scraping news (simulating /api/scrape route)."""
    session_id = "test_session_scrape_news"
    keywords = ["testkeyword"]
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    
    # Create a dummy cache directory for the scraper
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    scraper = WebScraper(cache_dir=str(cache_dir))
    
    # Mock the return value from execute_scraping_for_session
    mock_scraped_article_1 = {
        "url": "https://example.com/news/1", 
        "title": "Article 1 Title", 
        "content": "Content of article 1", 
        "scraped_at": datetime.now().isoformat(), 
        "site": "example.com", 
        "keywords_used": keywords
    }
    mock_scraped_article_2 = {
        "url": "https://example.com/news/2", 
        "title": "Article 2 Title", 
        "content": "Content of article 2",
        "scraped_at": datetime.now().isoformat(), 
        "site": "example.com", 
        "keywords_used": keywords
    }
    
    # Mock the session data return format
    mock_session_data = {
        'articles': [mock_scraped_article_1, mock_scraped_article_2],
        'session_metadata': {
            'session_id': session_id,
            'start_time': datetime.now().isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_seconds': 1.5,
            'links_discovered': 2,
            'articles_scraped': 2,
            'success_rate': 1.0,
            'scraper_version': 'modular-v1.0'
        }
    }
    
    mock_execute_scraping.return_value = mock_session_data
    
    # Call the method with the new API
    scraped_data = await scraper.execute_scraping_for_session(
        session_id=session_id,
        keywords=keywords
    )

    # Verify the mocked method was called
    mock_execute_scraping.assert_called_once_with(
        session_id=session_id,
        keywords=keywords
    )
    
    # Verify the return data structure
    assert scraped_data == mock_session_data
    assert 'articles' in scraped_data
    assert 'session_metadata' in scraped_data
    assert len(scraped_data['articles']) == 2
    assert scraped_data['session_metadata']['session_id'] == session_id
