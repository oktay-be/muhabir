import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from datetime import datetime

from capabilities.scraping.web_scraper import WebScraper
from capabilities.scraping.config import ScrapingConfig
# Assuming other components might be needed for deeper mocking if not already covered by WebScraper's mocks

CACHE_DIR = "./test_cache"
SESSION_ID = "test_session_123"
KEYWORDS = ["test", "news"]
SITES = ["http://site1.example.com", "http://site2.example.com"]

@pytest.fixture
def mock_config_instance(): # Renamed to avoid conflict if ScrapingConfig itself is mocked
    config = MagicMock(spec=ScrapingConfig)
    config.site_specific_selectors = {
        "site1.example.com": {"title": "h1", "body": "p"}, # Simplified
        "site2.example.com": {"title": "h1.article-title", "body": "div.content"}
    }
    config.link_discovery_depth = 1
    config.http_timeout = 10
    config.max_retries = 2
    return config

@pytest.fixture
@patch('capabilities.scraping.web_scraper.SessionManager')
@patch('capabilities.scraping.web_scraper.CacheManager')
@patch('capabilities.scraping.web_scraper.LinkDiscoverer')
@patch('capabilities.scraping.web_scraper.ContentExtractor')
@patch('capabilities.scraping.web_scraper.FileManager')
@patch('capabilities.scraping.web_scraper.ScrapingConfig') # Patch the class itself
def web_scraper_instance(
    MockScrapingConfig, MockFileManager, MockContentExtractor, 
    MockLinkDiscoverer, MockCacheManager, MockSessionManager, 
    mock_config_instance # Use the fixture that returns a MagicMock spec'd as ScrapingConfig
):
    # Configure the ScrapingConfig mock to return our specific config mock instance
    MockScrapingConfig.return_value = mock_config_instance     # Configure other component mocks as needed
    mock_session_manager_instance = MockSessionManager.return_value
    # Create a proper mock session that the session manager returns
    mock_aiohttp_session = AsyncMock()
    mock_session_manager_instance.get_session = AsyncMock(return_value=mock_aiohttp_session) # For _discover_links_for_site
    mock_session_manager_instance.fetch_content = AsyncMock(return_value="<html>Mock HTML</html>")

    mock_cache_manager_instance = MockCacheManager.return_value
    mock_cache_manager_instance.get_cached_content = MagicMock(return_value=None)
    mock_cache_manager_instance.generate_cache_key = MagicMock(return_value="test_cache_key")

    mock_link_discoverer_instance = MockLinkDiscoverer.return_value
    mock_link_discoverer_instance.discover_links = AsyncMock(return_value=[
        {'url': 'http://site1.example.com/article1', 'title_anchor': 'Article 1', 'source_page_url': SITES[0]},
        {'url': 'http://site2.example.com/news1', 'title_anchor': 'News 1', 'source_page_url': SITES[1]}
    ])

    mock_content_extractor_instance = MockContentExtractor.return_value
    mock_content_extractor_instance.extract_content = AsyncMock(return_value={
        'title': 'Mock Title', 'body': 'Mock body content.', 'extraction_method': 'MockExtractor'
    })
    mock_content_extractor_instance.get_extractor_info = MagicMock(return_value=[{'name': 'MockExtractor'}])

    mock_file_manager_instance = MockFileManager.return_value
    mock_file_manager_instance.load_session_data = MagicMock(return_value=None)
    mock_file_manager_instance.cleanup_old_sessions = MagicMock(return_value=0)
    mock_file_manager_instance.cleanup_old_articles = MagicMock(return_value=0)
    
    # Instantiate WebScraper - it will use the mocked components
    scraper = WebScraper(cache_dir=CACHE_DIR, cache_expiration_hours=1)
    return scraper

def test_web_scraper_initialization(web_scraper_instance, mock_config_instance):
    assert web_scraper_instance.cache_dir == CACHE_DIR
    assert web_scraper_instance.cache_expiration_hours == 1
    assert web_scraper_instance.config == mock_config_instance
    assert web_scraper_instance.session_manager is not None
    assert web_scraper_instance.cache_manager is not None
    assert web_scraper_instance.link_discoverer is not None
    assert web_scraper_instance.content_extractor is not None
    assert web_scraper_instance.file_manager is not None
    assert web_scraper_instance.discover_semaphore._value == 3
    assert web_scraper_instance.scrape_semaphore._value == 5

@pytest.mark.asyncio
async def test_execute_scraping_for_session_success(web_scraper_instance):
    session_data = await web_scraper_instance.execute_scraping_for_session(SESSION_ID, KEYWORDS, SITES)
    
    assert session_data is not None
    assert 'articles' in session_data
    assert 'session_metadata' in session_data
    assert len(session_data['articles']) == 2 # Based on mock_link_discoverer
    
    article = session_data['articles'][0]
    assert article['title'] == 'Mock Title'
    assert article['content'] == 'Mock body content.'
    assert article['extraction_method'] == 'MockExtractor'
    assert article['url'] in ['http://site1.example.com/article1', 'http://site2.example.com/news1']

    metadata = session_data['session_metadata']
    assert metadata['session_id'] == SESSION_ID
    assert metadata['links_discovered'] == 2
    assert metadata['articles_scraped'] == 2
    assert metadata['success_rate'] == 1.0

    web_scraper_instance.link_discoverer.discover_links.assert_any_call(
        site_url=SITES[0], keywords=KEYWORDS, session=pytest.ANY, search_depth=web_scraper_instance.config.link_discovery_depth
    )
    web_scraper_instance.link_discoverer.discover_links.assert_any_call(
        site_url=SITES[1], keywords=KEYWORDS, session=pytest.ANY, search_depth=web_scraper_instance.config.link_discovery_depth
    )
    assert web_scraper_instance.content_extractor.extract_content.call_count == 2
    web_scraper_instance.file_manager.save_session_data.assert_called_once()
    web_scraper_instance.file_manager.save_article.call_count == 2

@pytest.mark.asyncio
async def test_execute_scraping_for_session_cached_session(web_scraper_instance):
    cached_data = {
        'articles': [{'title': 'Cached Title', 'content': 'Cached Content'}],
        'session_metadata': {'session_id': SESSION_ID, 'links_discovered': 1, 'articles_scraped': 1}
    }
    web_scraper_instance.file_manager.load_session_data.return_value = cached_data
    
    session_data = await web_scraper_instance.execute_scraping_for_session(SESSION_ID, KEYWORDS, SITES)
    
    assert session_data == cached_data
    web_scraper_instance.link_discoverer.discover_links.assert_not_called()
    web_scraper_instance.content_extractor.extract_content.assert_not_called()

@pytest.mark.asyncio
async def test_execute_scraping_no_links_discovered(web_scraper_instance):
    web_scraper_instance.link_discoverer.discover_links.return_value = []
    session_data = await web_scraper_instance.execute_scraping_for_session(SESSION_ID, KEYWORDS, SITES)
    
    assert len(session_data['articles']) == 0
    assert session_data['session_metadata']['links_discovered'] == 0
    assert session_data['session_metadata']['articles_scraped'] == 0

@pytest.mark.asyncio
async def test_execute_scraping_no_valid_links_after_processing(web_scraper_instance):
    # Mock discover_links to return links that will be filtered out
    web_scraper_instance.link_discoverer.discover_links.return_value = [
        {'url': 'ftp://invalid.com/file', 'title_anchor': 'Invalid', 'source_page_url': SITES[0]}
    ]
    with patch('capabilities.scraping.web_scraper.is_valid_url', MagicMock(return_value=False)):
        session_data = await web_scraper_instance.execute_scraping_for_session(SESSION_ID, KEYWORDS, SITES)
    
    assert len(session_data['articles']) == 0
    assert session_data['session_metadata']['links_discovered'] == 0 # Because no valid links processed
    assert session_data['session_metadata']['articles_scraped'] == 0

@pytest.mark.asyncio
async def test_discover_links_for_site_success(web_scraper_instance):
    # This method is indirectly tested via execute_scraping_for_session
    # Direct test to ensure it calls link_discoverer correctly
    site_url = SITES[0]
    expected_links = [{'url': 'http://site1.example.com/article1'}]
    web_scraper_instance.link_discoverer.discover_links.return_value = expected_links
    
    # Need to mock get_session if it's not already done in the main fixture
    mock_aiohttp_session = AsyncMock()
    web_scraper_instance.session_manager.get_session = AsyncMock(return_value=mock_aiohttp_session)

    links = await web_scraper_instance._discover_links_for_site(site_url, KEYWORDS)
    
    assert links == expected_links
    web_scraper_instance.link_discoverer.discover_links.assert_called_with(
        site_url=site_url, 
        keywords=KEYWORDS, 
        session=mock_aiohttp_session, 
        search_depth=web_scraper_instance.config.link_discovery_depth
    )

@pytest.mark.asyncio
async def test_scrape_single_article_success_no_cache(web_scraper_instance):
    url = "http://site1.example.com/article1_nocache"
    expected_article_data = {
        'url': url, # Assuming normalize_url returns it as is for simplicity here
        'original_url': url,
        'scraped_at': ANY, # datetime.now().isoformat()
        'keywords_used': KEYWORDS,
        'title': 'Mock Title',
        'content': 'Mock body content.',
        'extraction_method': 'MockExtractor',
        'site': 'site1.example.com'
    }
    
    # Ensure cache returns None
    web_scraper_instance.cache_manager.get_cached_content.return_value = None
    # Mock fetch_content for this specific call if needed, or rely on fixture's default
    web_scraper_instance.session_manager.fetch_content = AsyncMock(return_value="<html>Mock HTML for nocache</html>")
    web_scraper_instance.content_extractor.extract_content.return_value = {
        'title': 'Mock Title', 'body': 'Mock body content.', 'extraction_method': 'MockExtractor'
    }

    with patch('capabilities.scraping.web_scraper.normalize_url', lambda x: x) as mock_norm, \
         patch('capabilities.scraping.web_scraper.is_valid_url', lambda x: True) as mock_valid:
        article_data = await web_scraper_instance._scrape_single_article(url, KEYWORDS)

    assert article_data is not None
    # Compare fields, ignoring scraped_at due to dynamic nature
    for key, value in expected_article_data.items():
        if key == 'scraped_at':
            assert key in article_data
        else:
            assert article_data[key] == value
            
    web_scraper_instance.cache_manager.get_cached_content.assert_called_once()
    web_scraper_instance.session_manager.fetch_content.assert_called_once_with(url)
    web_scraper_instance.content_extractor.extract_content.assert_called_once_with(url, "<html>Mock HTML for nocache</html>")
    web_scraper_instance.cache_manager.cache_content.assert_called_once()
    web_scraper_instance.file_manager.save_article.assert_called_once()

@pytest.mark.asyncio
async def test_scrape_single_article_cached(web_scraper_instance):
    url = "http://site1.example.com/article_cached"
    cached_data = {
        'url': url, 'title': 'Cached Title', 'content': 'Cached Content', 
        'extraction_method': 'CachedExtractor', 'original_url': url, 
        'scraped_at': datetime.now().isoformat(), 'keywords_used': KEYWORDS, 'site': 'site1.example.com'
    }
    web_scraper_instance.cache_manager.get_cached_content.return_value = cached_data
    
    with patch('capabilities.scraping.web_scraper.normalize_url', lambda x: x), \
         patch('capabilities.scraping.web_scraper.is_valid_url', lambda x: True):
        article_data = await web_scraper_instance._scrape_single_article(url, KEYWORDS)
    
    assert article_data == cached_data
    web_scraper_instance.session_manager.fetch_content.assert_not_called()
    web_scraper_instance.content_extractor.extract_content.assert_not_called()

@pytest.mark.asyncio
async def test_scrape_single_article_fetch_fails(web_scraper_instance):
    url = "http://site1.example.com/fetch_fail"
    web_scraper_instance.cache_manager.get_cached_content.return_value = None
    web_scraper_instance.session_manager.fetch_content.return_value = None # Simulate fetch failure
    
    with patch('capabilities.scraping.web_scraper.normalize_url', lambda x: x), \
         patch('capabilities.scraping.web_scraper.is_valid_url', lambda x: True):
        article_data = await web_scraper_instance._scrape_single_article(url, KEYWORDS)
        
    assert article_data is None
    web_scraper_instance.content_extractor.extract_content.assert_not_called()

@pytest.mark.asyncio
async def test_scrape_single_article_extraction_fails(web_scraper_instance):
    url = "http://site1.example.com/extract_fail"
    web_scraper_instance.cache_manager.get_cached_content.return_value = None
    web_scraper_instance.session_manager.fetch_content.return_value = "<html>Some HTML</html>"
    web_scraper_instance.content_extractor.extract_content.return_value = None # Simulate extraction failure
    
    with patch('capabilities.scraping.web_scraper.normalize_url', lambda x: x), \
         patch('capabilities.scraping.web_scraper.is_valid_url', lambda x: True):
        article_data = await web_scraper_instance._scrape_single_article(url, KEYWORDS)
        
    assert article_data is None

@pytest.mark.asyncio
async def test_scrape_single_article_invalid_url(web_scraper_instance):
    url = "ftp://invalid.url"
    with patch('capabilities.scraping.web_scraper.normalize_url', lambda x: x), \
         patch('capabilities.scraping.web_scraper.is_valid_url', lambda x: False): # Simulate invalid URL
        article_data = await web_scraper_instance._scrape_single_article(url, KEYWORDS)
    assert article_data is None
    web_scraper_instance.cache_manager.get_cached_content.assert_not_called()
    web_scraper_instance.session_manager.fetch_content.assert_not_called()

def test_create_session_metadata(web_scraper_instance):
    start_time = datetime(2023, 1, 1, 12, 0, 0)
    # Patch datetime.now() if precise duration testing is needed, or accept small variance
    metadata = web_scraper_instance._create_session_metadata(SESSION_ID, start_time, 10, 8)
    
    assert metadata['session_id'] == SESSION_ID
    assert metadata['start_time'] == start_time.isoformat()
    assert 'end_time' in metadata
    assert metadata['duration_seconds'] >= 0
    assert metadata['links_discovered'] == 10
    assert metadata['articles_scraped'] == 8
    assert metadata['success_rate'] == 0.8
    assert metadata['scraper_version'] == 'modular-v1.0'

def test_get_scraper_info(web_scraper_instance, mock_config_instance):
    info = web_scraper_instance.get_scraper_info()
    assert info['cache_dir'] == CACHE_DIR
    assert info['cache_expiration_hours'] == 1
    assert info['supported_sites'] == list(mock_config_instance.site_specific_selectors.keys())
    assert info['extraction_strategies'] == [{'name': 'MockExtractor'}]
    assert info['http_timeout'] == mock_config_instance.http_timeout
    assert info['max_retries'] == mock_config_instance.max_retries

def test_cleanup_old_data(web_scraper_instance):
    web_scraper_instance.file_manager.cleanup_old_sessions.return_value = 5
    web_scraper_instance.file_manager.cleanup_old_articles.return_value = 10
    web_scraper_instance.cache_manager.cleanup_expired_cache.return_value = 20 # Updated method name
    
    cleanup_stats = web_scraper_instance.cleanup_old_data(session_days=5, article_days=10)
    
    assert cleanup_stats['sessions_removed'] == 5
    assert cleanup_stats['articles_removed'] == 10
    assert cleanup_stats['cache_files_removed'] == 20
    web_scraper_instance.file_manager.cleanup_old_sessions.assert_called_once_with(5)
    web_scraper_instance.file_manager.cleanup_old_articles.assert_called_once_with(10)
    web_scraper_instance.cache_manager.cleanup_expired_cache.assert_called_once()

@pytest.mark.asyncio
async def test_web_scraper_async_context_manager(web_scraper_instance):
    async with web_scraper_instance as scraper:
        assert scraper == web_scraper_instance
        scraper.session_manager.__aenter__.assert_called_once()
    scraper.session_manager.__aexit__.assert_called_once()

@pytest.mark.asyncio
async def test_execute_scraping_general_exception_handling(web_scraper_instance, caplog):
    web_scraper_instance.link_discoverer.discover_links.side_effect = Exception("Major discovery fail")
    
    session_data = await web_scraper_instance.execute_scraping_for_session(SESSION_ID, KEYWORDS, SITES)
    
    assert 'error' in session_data
    assert session_data['error'] == "Major discovery fail"
    assert len(session_data['articles']) == 0
    assert f"Scraping session {SESSION_ID} failed: Major discovery fail" in caplog.text
