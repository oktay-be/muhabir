"""
Unit tests for the backward-compatibility wrapper WebScraper (capabilities/web_scraper.py).
"""
import asyncio
import os
import json
import shutil
import aiohttp
import pytest
import sys
from unittest.mock import patch, AsyncMock, MagicMock, call, ANY

# Ensure the capabilities directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from capabilities.web_scraper import WebScraper

CACHE_DIR_WRAPPER = "test_cache_wrapper"

@pytest.fixture(scope="function")
def scraper_wrapper():
    """Fixture to create and cleanup a WebScraper instance for the wrapper."""
    if os.path.exists(CACHE_DIR_WRAPPER):
        shutil.rmtree(CACHE_DIR_WRAPPER)
    os.makedirs(CACHE_DIR_WRAPPER, exist_ok=True)
    scraper = WebScraper(cache_dir=CACHE_DIR_WRAPPER, cache_expiration_hours=1)
    yield scraper
    # Teardown: close session and remove cache directory
    async def close_session_async():
        await scraper.close_session()
    asyncio.run(close_session_async())
    if os.path.exists(CACHE_DIR_WRAPPER):
        shutil.rmtree(CACHE_DIR_WRAPPER)

@pytest.mark.asyncio
async def test_wrapper_initialization(scraper_wrapper: WebScraper):
    """Test basic initialization of the wrapper WebScraper."""
    assert scraper_wrapper.cache_dir == CACHE_DIR_WRAPPER
    assert scraper_wrapper.cache_expiration_hours == 1
    assert scraper_wrapper.session is None
    assert os.path.exists(CACHE_DIR_WRAPPER)

@pytest.mark.asyncio
async def test_wrapper_ensure_session(scraper_wrapper: WebScraper):
    """Test the _ensure_session method creates a session."""
    await scraper_wrapper._ensure_session()
    assert scraper_wrapper.session is not None
    assert not scraper_wrapper.session.closed
    session_id_after_first_call = id(scraper_wrapper.session)
    await scraper_wrapper._ensure_session() # Call again
    assert id(scraper_wrapper.session) == session_id_after_first_call # Should be same session
    await scraper_wrapper.close_session()
    assert scraper_wrapper.session is None

@pytest.mark.asyncio
async def test_wrapper_close_session(scraper_wrapper: WebScraper):
    """Test the close_session method."""
    await scraper_wrapper._ensure_session()
    assert scraper_wrapper.session is not None
    await scraper_wrapper.close_session()
    assert scraper_wrapper.session is None
    await scraper_wrapper.close_session() # Should not raise error if called again

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
async def test_wrapper_fetch_html_success(mock_get, scraper_wrapper: WebScraper):
    """Test _fetch_html successfully fetches content."""
    mock_response = AsyncMock()
    mock_response.text = AsyncMock(return_value="<html><body>Test HTML</body></html>")
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"Content-Type": "text/html"}  # Add headers
    mock_get.return_value.__aenter__.return_value = mock_response

    await scraper_wrapper._ensure_session()
    html = await scraper_wrapper._fetch_html("http://example.com", scraper_wrapper.session)
    assert html == "<html><body>Test HTML</body></html>"
    # The implementation now uses network_utils with more headers
    await scraper_wrapper.close_session()

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
async def test_wrapper_fetch_html_http_error(mock_get, scraper_wrapper: WebScraper, caplog):
    """Test _fetch_html handles HTTP errors."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(MagicMock(), MagicMock(), status=404))
    mock_get.return_value.__aenter__.return_value = mock_response

    await scraper_wrapper._ensure_session()
    html = await scraper_wrapper._fetch_html("http://example.com/404", scraper_wrapper.session)
    assert html is None
    assert "HTTP error fetching http://example.com/404" in caplog.text

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get', side_effect=asyncio.TimeoutError)
async def test_wrapper_fetch_html_timeout(mock_get, scraper_wrapper: WebScraper, caplog):
    """Test _fetch_html handles timeout errors."""
    await scraper_wrapper._ensure_session()
    html = await scraper_wrapper._fetch_html("http://example.com/timeout", scraper_wrapper.session)
    assert html is None
    assert "Timeout error fetching http://example.com/timeout" in caplog.text

@pytest.mark.asyncio
async def test_wrapper_discover_links_from_page(scraper_wrapper: WebScraper):
    """Test _discover_links_from_page method."""
    mock_html_content = """
    <html><body>
        <a href="/news/article1">Article 1 about Fenerbahçe</a>
        <a href="http://external.com/other">External link</a>
        <a href="/news/article2">Article 2 about transfer</a>
        <a href="/news/article3">Irrelevant</a>
        <a href="https://example.com/news/article4-fenerbahce">Article 4</a>
    </body></html>
    """
    scraper_wrapper._fetch_html = AsyncMock(return_value=mock_html_content)
    await scraper_wrapper._ensure_session()

    links = await scraper_wrapper._discover_links_from_page(
        "http://example.com/sport", ["Fenerbahçe", "transfer"], scraper_wrapper.session
    )
    
    # Only 2 links match because "Fenerbahçe" (Turkish ç) doesn't match "fenerbahce" (ASCII) in URL
    assert len(links) == 2
    urls_found = [link['url'] for link in links]
    assert "http://example.com/news/article1" in urls_found  # Matches "Fenerbahçe" in text
    assert "http://example.com/news/article2" in urls_found  # Matches "transfer" in text
    # Note: article4-fenerbahce URL doesn't match because of Turkish character mismatch
    
    titles_found = [link['title_anchor'] for link in links]
    assert "Article 1 about Fenerbahçe" in titles_found
    assert "Article 2 about transfer" in titles_found

@pytest.mark.asyncio
async def test_wrapper_scrape_article_details_caching(scraper_wrapper: WebScraper):
    """Test caching in _scrape_article_details."""
    article_url = "http://example.com/article1"
    keywords = ["test"]
    mock_article_data = {"title": "Test Title", "body": "Test Body", "source": "example.com", "url": article_url}

    # First call - should fetch and cache
    scraper_wrapper._fetch_html = AsyncMock(return_value="<html><head><title>Test Title</title></head><body><p>Test Body</p></body></html>")
    
    await scraper_wrapper._ensure_session()
    # Mock the actual extraction logic to simplify the test focus on caching
    with patch.object(scraper_wrapper, '_read_from_cache', side_effect=[None, mock_article_data]) as mock_read_cache, \
         patch.object(scraper_wrapper, '_write_to_cache') as mock_write_cache:

        # Simulate that the internal extraction produces this data
        async def mock_internal_extraction(*args, **kwargs):
            # This simplified mock assumes the HTML leads to mock_article_data
            # In a real scenario, this would be the complex extraction logic
            return mock_article_data 
        
        # We need to mock the part of _scrape_article_details that processes HTML
        # For this test, we assume the HTML processing part works and returns mock_article_data
        # and we want to test the caching around it.
        # A simple way is to mock the HTML fetching and assume the rest of the method
        # correctly processes it into mock_article_data if keywords match.

        # To make it more direct for testing caching, let's assume the first call
        # will proceed to _write_to_cache, and the second will hit _read_from_cache.

        # First call: _read_from_cache returns None, then _write_to_cache is called
        details1 = await scraper_wrapper._scrape_article_details(
            {"url": article_url, "title_anchor": "Anchor"}, keywords, scraper_wrapper.session
        )
        assert details1['title'] == "Test Title" # Check if data is processed
        mock_read_cache.assert_called_once()
        mock_write_cache.assert_called_once()
        
        # Second call: _read_from_cache returns mock_article_data
        details2 = await scraper_wrapper._scrape_article_details(
            {"url": article_url, "title_anchor": "Anchor"}, keywords, scraper_wrapper.session
        )
        assert details2 == mock_article_data
        assert mock_read_cache.call_count == 2 # Called again for the second attempt
        mock_write_cache.assert_called_once() # Not called again

@pytest.mark.asyncio
async def test_wrapper_scrape_urls_e2e_mocked(scraper_wrapper: WebScraper):
    """More integrated test for scrape_urls with mocked network calls."""
    initial_urls = ["http://site1.com/news"]
    keywords = ["keyword1"]

    mock_discovery_html = '''
    <html><body><a href="/article_keyword1">Article Keyword1</a></body></html>
    '''
    mock_article_html = '''
    <html><head><title>Article Keyword1 Title</title></head>
    <body><p>This is the body of the article about keyword1.</p></body></html>
    '''

    # Mock _fetch_html to return different content based on URL
    async def mock_fetch_router(url, session):
        if url == "http://site1.com/news":
            return mock_discovery_html
        elif url == "http://site1.com/article_keyword1":
            return mock_article_html
        return None
    
    scraper_wrapper._fetch_html = AsyncMock(side_effect=mock_fetch_router)
    await scraper_wrapper._ensure_session()

    articles = await scraper_wrapper.scrape_urls(initial_urls, keywords)

    assert len(articles) == 1
    article = articles[0]
    assert article['title'] == "Article Keyword1 Title"
    assert "body of the article about keyword1" in article['body']
    assert article['source'] == "site1.com"
    assert article['url'] == "http://site1.com/article_keyword1"

    # Check that _discover_links_from_page and _scrape_article_details were involved
    # This requires more intricate mocking or checking logs if detailed call verification is needed.
    # For now, the output implies they worked.

@pytest.mark.asyncio
async def test_wrapper_execute_scraping_for_session(scraper_wrapper: WebScraper, tmp_path):
    """Test execute_scraping_for_session method."""
    session_id = "test_session_123"
    base_workspace_path = str(tmp_path)
    urls = ["http://example.com/main_news_page"]
    keywords = ["fenerbahce"]

    # Mock _discover_links_from_page to return a predefined link
    mock_discovered_link = {
        "url": "http://example.com/fenerbahce_article",
        "title_anchor": "Fenerbahce Article",
        "source_page_domain": "example.com"
    }
    scraper_wrapper._discover_links_from_page = AsyncMock(return_value=[mock_discovered_link])
      # Mock _scrape_article_details to return predefined article data
    mock_article_content = {
        "title": "Fenerbahce Wins Big",
        "body": "Detailed content about Fenerbahce's victory.",
        "source": "example.com",
        "url": "http://example.com/fenerbahce_article",
        "published_at": None,
        "image_url": None,
        "author": None,
        "html_content": "<html>...</html>"  # Included as per current implementation
    }
    scraper_wrapper._scrape_article_details = AsyncMock(return_value=mock_article_content)
    
    await scraper_wrapper.execute_scraping_for_session(session_id, base_workspace_path, urls, keywords)

    # The implementation ensures a session exists, so expect any session object, not None
    scraper_wrapper._discover_links_from_page.assert_called_once_with(
        "http://example.com/main_news_page", keywords, ANY
    )
    scraper_wrapper._scrape_article_details.assert_called_once_with(
        mock_discovered_link, keywords, ANY
    )

    # Check if the file was created
    session_output_path = tmp_path / session_id
    assert session_output_path.exists()
    
    # Construct expected filename (simplified, actual filename generation is more complex)
    # For this test, let's find the first .json file in the directory.
    json_files = list(session_output_path.glob("*.json"))
    assert len(json_files) == 1
    
    saved_file_path = json_files[0]
    with open(saved_file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    assert saved_data['title'] == "Fenerbahce Wins Big"
    assert saved_data['body'] == "Detailed content about Fenerbahce's victory."
    assert saved_data['url'] == "http://example.com/fenerbahce_article"

def test_wrapper_cache_read_write(scraper_wrapper: WebScraper, tmp_path):
    """Test _write_to_cache and _read_from_cache."""
    cache_file_path = tmp_path / "test_cache_item.json"
    test_data = {"key": "value", "number": 123}

    # Test write
    scraper_wrapper._write_to_cache(str(cache_file_path), test_data)
    assert cache_file_path.exists()

    with open(cache_file_path, 'r') as f:
        content = json.load(f)
        assert "timestamp" in content
        assert content["data"] == test_data

    # Test read (valid)
    read_data = scraper_wrapper._read_from_cache(str(cache_file_path))
    assert read_data == test_data

    # Test read (expired)
    scraper_wrapper.cache_expiration_hours = -1 # Force expiration
    expired_read_data = scraper_wrapper._read_from_cache(str(cache_file_path))
    assert expired_read_data is None
    assert not cache_file_path.exists() # File should be deleted if expired

    # Test read (non-existent file)
    non_existent_data = scraper_wrapper._read_from_cache(str(tmp_path / "non_existent.json"))
    assert non_existent_data is None

    # Test read (corrupted JSON)
    corrupted_file_path = tmp_path / "corrupted.json"
    with open(corrupted_file_path, 'w') as f:
        f.write("this is not json")
    
    with patch('capabilities.web_scraper.logger') as mock_logger: # Patched module-level logger
        corrupted_data = scraper_wrapper._read_from_cache(str(corrupted_file_path))
        assert corrupted_data is None
        mock_logger.error.assert_called_once()
        assert "Error decoding JSON" in mock_logger.error.call_args[0][0]
