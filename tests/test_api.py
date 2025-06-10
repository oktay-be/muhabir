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


@patch('capabilities.web_scraper.WebScraper.scrape_urls', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_scrape_news(mock_scrape_urls, tmp_path):
    """Test scraping news (simulating /api/scrape route)."""
    session_id = "test_session_scrape_news"
    initial_urls_param = ["https://example.com/news"] # Renamed from base_urls
    keywords = ["testkeyword"]
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    
    # Create a dummy cache directory for the scraper
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    scraper = WebScraper(cache_dir=str(cache_dir))    # Mock the underlying methods of WebScraper
    mock_discovered_links = [
        {"url": "https://example.com/news/1", "title_anchor": "Article 1", "source_page_domain": "example.com"},
        {"url": "https://example.com/news/2", "title_anchor": "Article 2", "source_page_domain": "example.com"}
    ]
    mock_scraped_article_1 = {
        "url": "https://example.com/news/1", "title": "Article 1 Title", "body": "Content of article 1", 
        "scraped_at": datetime.now().isoformat(), "source_page_domain": "example.com", "keywords_found": keywords
    }
    mock_scraped_article_2 = {
        "url": "https://example.com/news/2", "title": "Article 2 Title", "body": "Content of article 2",
        "scraped_at": datetime.now().isoformat(), "source_page_domain": "example.com", "keywords_found": keywords
    }
    # Create a mock session object
    mock_session = AsyncMock()
    
    # Mock _ensure_session to actually set scraper.session
    async def mock_ensure_session_func():
        scraper.session = mock_session
        return mock_session
    
    # Corrected with statement:
    with patch.object(scraper, '_ensure_session', side_effect=mock_ensure_session_func) as mock_ensure_session, \
         patch.object(scraper, 'close_session', AsyncMock()) as mock_close_session, \
         patch.object(scraper, '_discover_links_from_page', AsyncMock(return_value=mock_discovered_links)) as mock_discover, \
         patch.object(scraper, '_scrape_article_details', AsyncMock()) as mock_scrape_details:

        mock_scrape_details.side_effect = [mock_scraped_article_1, mock_scraped_article_2]        # Call the actual method that orchestrates the scraping
        scraped_data = await scraper.execute_scraping_for_session(
            session_id=session_id,
            base_workspace_path=str(workspace_dir),
            urls=initial_urls_param, # Corrected parameter name
            keywords=keywords
        )

        assert mock_discover.called # Check if discovery was attempted
        # Ensure _discover_links_from_page was called for each base_url
        # For simplicity, we\'ll check the number of calls and the first call\'s arguments if needed.
        # More specific argument checking can be added if there are issues.
        assert mock_discover.call_count == len(initial_urls_param) # Use corrected variable
        # Example of checking the first call\'s arguments (keywords part):
        # discover_args, discover_kwargs = mock_discover.call_args_list[0]
        # assert keywords == discover_args[1] # Assuming keywords is the second positional arg to _discover_links_from_page

        assert mock_scrape_details.called # Check if scraping was attempted
        # Ensure _scrape_article_details was called for each discovered link        assert mock_scrape_details.call_count == len(mock_discovered_links)
        # Example of checking the first call's arguments (keywords part):
        # scrape_args, scrape_kwargs = mock_scrape_details.call_args_list[0]
        # assert keywords == scrape_args[1] # Assuming keywords is the second positional arg to _scrape_article_details

        # Verify the output file was created and contains the scraped data
        session_scrape_dir = workspace_dir / session_id  # Files are saved directly to session directory        # Find the files that were saved
        found_files = list(session_scrape_dir.glob("*.json"))
        assert len(found_files) == 2, f"Expected 2 output files, found {len(found_files)} in {session_scrape_dir}"

        # Load and verify both articles were saved correctly
        saved_articles = []
        for file_path in found_files:
            with open(file_path, "r", encoding="utf-8") as f:
                article_data = json.load(f)
                saved_articles.append(article_data)
        
        # Sort by URL for consistent comparison
        saved_articles.sort(key=lambda x: x["url"])
        expected_articles = [mock_scraped_article_1, mock_scraped_article_2]
        expected_articles.sort(key=lambda x: x["url"])
        
        assert len(saved_articles) == 2
        assert saved_articles[0]["url"] == expected_articles[0]["url"]
        assert saved_articles[1]["url"] == expected_articles[1]["url"]
        assert saved_articles[0]["title"] == expected_articles[0]["title"]
        assert saved_articles[1]["title"] == expected_articles[1]["title"]

        # Assert that the scraper's session was closed
        mock_close_session.assert_called_once()
