import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from bs4 import BeautifulSoup

from capabilities.scraping.config import ScrapingConfig
from capabilities.scraping.content_extractor import ContentExtractor
from capabilities.scraping.extractors.base_extractor import BaseExtractor

# Sample HTML content for testing
SAMPLE_HTML = """
<html>
<head><title>Test Title</title></head>
<body>
    <h1>Main Heading</h1>
    <p>This is a paragraph of sufficient length for testing.</p>
    <div class="ld-json">{"@context": "http://schema.org", "@type": "Article", "headline": "LD-JSON Title"}</div>
    <article>This is readability content, also long enough.</article>
</body>
</html>
"""

SAMPLE_HTML_SHORT_BODY = """
<html>
<head><title>Short Body Test</title></head>
<body>
    <p>Too short.</p>
</body>
</html>
"""

SAMPLE_HTML_SUSPICIOUS = """
<html>
<head><title>Suspicious Content</title></head>
<body>
    <p>Please enable JavaScript to continue. This page requires JavaScript and is long enough.</p>
</body>
</html>
"""

@pytest.fixture
def mock_config():
    config = MagicMock(spec=ScrapingConfig)
    config.min_content_length = 20
    config.min_title_length = 5
    config.suspicious_patterns = ["enable javascript"]
    config.title_body_ratio_threshold = 0.8 # Title can be 80% of body length
    return config

@pytest.fixture
def mock_ldjson_extractor(mock_config):
    extractor = AsyncMock(spec=BaseExtractor)
    mock_class_attr = MagicMock()
    mock_class_attr.__name__ = "LdJsonExtractor"
    extractor.__class__ = mock_class_attr
    extractor.get_extraction_priority.return_value = 50
    
    async def extract_side_effect(html_content, url, soup=None):
        if "LD-JSON Title" in html_content:
            return {"title": "LD-JSON Title", "body": "LD-JSON body content, long enough.", "extraction_method": "LdJsonExtractor"}
        return None
    
    extractor.extract = AsyncMock(side_effect=extract_side_effect)
    return extractor

@pytest.fixture
def mock_readability_extractor(mock_config):
    extractor = AsyncMock(spec=BaseExtractor)
    mock_class_attr = MagicMock()
    mock_class_attr.__name__ = "ReadabilityExtractor"
    extractor.__class__ = mock_class_attr
    extractor.get_extraction_priority.return_value = 40
    
    async def extract_side_effect(html_content, url, soup=None):
        if "This is readability content" in html_content:
            return {"title": "Readability Title", "body": "This is readability content, also long enough.", "extraction_method": "ReadabilityExtractor"}
        return None
    
    extractor.extract = AsyncMock(side_effect=extract_side_effect)
    return extractor
    
@pytest.fixture
def mock_selector_extractor(mock_config):
    extractor = AsyncMock(spec=BaseExtractor)
    mock_class_attr = MagicMock()
    mock_class_attr.__name__ = "SelectorExtractor"
    extractor.__class__ = mock_class_attr
    extractor.get_extraction_priority.return_value = 30
    
    async def extract_side_effect(html_content, url, soup=None):
        if "Main Heading" in html_content: # Assume selector would find this
            return {"title": "Selector Title", "body": "Selector body from main heading paragraph, long enough.", "extraction_method": "SelectorExtractor"}
        return None
    
    extractor.extract = AsyncMock(side_effect=extract_side_effect)
    return extractor

@pytest.fixture
def mock_fullpage_extractor(mock_config):
    extractor = AsyncMock(spec=BaseExtractor)
    mock_class_attr = MagicMock()
    mock_class_attr.__name__ = "FullPageExtractor"
    extractor.__class__ = mock_class_attr
    extractor.get_extraction_priority.return_value = 10
    
    async def extract_side_effect(html_content, url, soup=None):
        return {"title": "Full Page Title", "body": html_content, "extraction_method": "FullPageExtractor"} # Simplified
    
    extractor.extract = AsyncMock(side_effect=extract_side_effect)
    return extractor

@pytest.fixture
@patch('capabilities.scraping.content_extractor.LdJsonExtractor', new_callable=MagicMock)
@patch('capabilities.scraping.content_extractor.ReadabilityExtractor', new_callable=MagicMock)
@patch('capabilities.scraping.content_extractor.SelectorExtractor', new_callable=MagicMock)
@patch('capabilities.scraping.content_extractor.FullPageExtractor', new_callable=MagicMock)
def content_extractor(
    MockFullPageExtractor, MockSelectorExtractor, 
    MockReadabilityExtractor, MockLdJsonExtractor, 
    mock_config, mock_ldjson_extractor, mock_readability_extractor, 
    mock_selector_extractor, mock_fullpage_extractor
):
    # Configure the class mocks to return our instance mocks
    MockLdJsonExtractor.return_value = mock_ldjson_extractor
    MockReadabilityExtractor.return_value = mock_readability_extractor
    MockSelectorExtractor.return_value = mock_selector_extractor
    MockFullPageExtractor.return_value = mock_fullpage_extractor
    
    # Instantiate ContentExtractor, which will use the mocked extractor classes
    extractor_instance = ContentExtractor(config=mock_config)
    # Ensure extractors are sorted as expected by priority
    assert extractor_instance.extractors[0].__class__.__name__ == "LdJsonExtractor"
    assert extractor_instance.extractors[1].__class__.__name__ == "ReadabilityExtractor"
    assert extractor_instance.extractors[2].__class__.__name__ == "SelectorExtractor"
    assert extractor_instance.extractors[3].__class__.__name__ == "FullPageExtractor"
    return extractor_instance


def test_content_extractor_initialization(content_extractor: ContentExtractor, mock_config):
    assert content_extractor.config == mock_config
    assert len(content_extractor.extractors) == 4
    names = [e.__class__.__name__ for e in content_extractor.extractors]
    assert "LdJsonExtractor" in names
    assert "ReadabilityExtractor" in names
    assert "SelectorExtractor" in names
    assert "FullPageExtractor" in names
    
    priorities = [e.get_extraction_priority() for e in content_extractor.extractors]
    assert priorities == sorted(priorities, reverse=True)

@pytest.mark.asyncio
async def test_extract_content_uses_highest_priority_successful_extractor(content_extractor: ContentExtractor, mock_ldjson_extractor):
    url = "http://example.com/article_ldjson"
    result = await content_extractor.extract_content(url, SAMPLE_HTML)
    
    assert result is not None
    assert result["title"] == "LD-JSON Title"
    assert result["body"] == "LD-JSON body content, long enough."
    assert result["extraction_method"] == "LdJsonExtractor"
    mock_ldjson_extractor.extract.assert_awaited_once()

@pytest.mark.asyncio
async def test_extract_content_falls_back_to_next_priority(content_extractor: ContentExtractor, mock_ldjson_extractor, mock_readability_extractor):
    url = "http://example.com/article_readability"
    mock_ldjson_extractor.extract = AsyncMock(return_value=None)
    
    html_for_readability = """
    <html><head><title>Test Title</title></head>
    <body><article>This is readability content, also long enough.</article></body></html>
    """
    result = await content_extractor.extract_content(url, html_for_readability)
    
    assert result is not None
    assert result["title"] == "Readability Title"
    assert result["body"] == "This is readability content, also long enough."
    assert result["extraction_method"] == "ReadabilityExtractor"
    mock_ldjson_extractor.extract.assert_awaited_once() 
    mock_readability_extractor.extract.assert_awaited_once()

@pytest.mark.asyncio
async def test_extract_content_all_extractors_fail_returns_none(content_extractor: ContentExtractor, mock_ldjson_extractor, mock_readability_extractor, mock_selector_extractor, mock_fullpage_extractor):
    url = "http://example.com/article_empty"
    empty_html = "<html><body></body></html>"
    
    mock_ldjson_extractor.extract = AsyncMock(return_value=None)
    mock_readability_extractor.extract = AsyncMock(return_value=None)
    mock_selector_extractor.extract = AsyncMock(return_value=None)
    mock_fullpage_extractor.extract = AsyncMock(return_value={"title": "", "body": "", "extraction_method": "FullPageExtractor"})

    result = await content_extractor.extract_content(url, empty_html)
    
    assert result is None
    mock_ldjson_extractor.extract.assert_awaited_once()
    mock_readability_extractor.extract.assert_awaited_once()
    mock_selector_extractor.extract.assert_awaited_once()
    mock_fullpage_extractor.extract.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_content_quality_check_rejects_short_body(content_extractor: ContentExtractor, mock_config, mock_fullpage_extractor):
    url = "http://example.com/short_article"
    content_extractor.extractors = [mock_fullpage_extractor] 
    mock_fullpage_extractor.extract = AsyncMock(return_value={"title": "Short Body Test", "body": "Too short.", "extraction_method": "FullPageExtractor"})
    
    mock_config.min_content_length = 20
    
    result = await content_extractor.extract_content(url, SAMPLE_HTML_SHORT_BODY)
    assert result is None 
    mock_fullpage_extractor.extract.assert_awaited_once()

@pytest.mark.asyncio
async def test_extract_content_quality_check_rejects_suspicious_content(content_extractor: ContentExtractor, mock_config, mock_fullpage_extractor):
    url = "http://example.com/suspicious_article"
    content_extractor.extractors = [mock_fullpage_extractor]
    mock_fullpage_extractor.extract = AsyncMock(return_value={"title": "Suspicious Content", "body": "Please enable JavaScript to continue. This page requires JavaScript and is long enough.", "extraction_method": "FullPageExtractor"})
    
    mock_config.suspicious_patterns = ["enable javascript"]
    mock_config.min_content_length = 20

    result = await content_extractor.extract_content(url, SAMPLE_HTML_SUSPICIOUS)
    assert result is None 
    mock_fullpage_extractor.extract.assert_awaited_once()

@pytest.mark.asyncio
async def test_extract_content_adds_extraction_method_if_missing(content_extractor: ContentExtractor, mock_readability_extractor, mock_config):
    url = "http://example.com/article_no_method"
    mock_readability_extractor.extract = AsyncMock(return_value={"title": "A Title", "body": "Some valid body content here that is long enough."})
    
    # Re-initialize ContentExtractor with only this mock to ensure it's used
    with patch('capabilities.scraping.content_extractor.LdJsonExtractor', MagicMock(return_value=AsyncMock(extract=AsyncMock(return_value=None), get_extraction_priority=lambda:0))), \
         patch('capabilities.scraping.content_extractor.ReadabilityExtractor', MagicMock(return_value=mock_readability_extractor)), \
         patch('capabilities.scraping.content_extractor.SelectorExtractor', MagicMock(return_value=AsyncMock(extract=AsyncMock(return_value=None), get_extraction_priority=lambda:0))), \
         patch('capabilities.scraping.content_extractor.FullPageExtractor', MagicMock(return_value=AsyncMock(extract=AsyncMock(return_value=None), get_extraction_priority=lambda:0))):
        current_content_extractor = ContentExtractor(config=mock_config)
        # Ensure Readability is primary for this test after re-patching
        assert current_content_extractor.extractors[0].__class__.__name__ == "ReadabilityExtractor"


    result = await current_content_extractor.extract_content(url, SAMPLE_HTML)
    assert result is not None
    assert result["extraction_method"] == "ReadabilityExtractor"

@pytest.mark.asyncio
async def test_extract_content_handles_extractor_exception_gracefully(content_extractor: ContentExtractor, mock_ldjson_extractor, mock_readability_extractor, caplog, mock_config):
    url = "http://example.com/extractor_exception"
    mock_ldjson_extractor.extract = AsyncMock(side_effect=Exception("LD-JSON boom!"))
    mock_readability_extractor.extract = AsyncMock(return_value={"title": "Readability Fallback", "body": "Body after LD-JSON failed due to exception, long enough.", "extraction_method": "ReadabilityExtractor"})
    
    # Re-initialize ContentExtractor with these specific mocks in order
    with patch('capabilities.scraping.content_extractor.LdJsonExtractor', MagicMock(return_value=mock_ldjson_extractor)), \
         patch('capabilities.scraping.content_extractor.ReadabilityExtractor', MagicMock(return_value=mock_readability_extractor)), \
         patch('capabilities.scraping.content_extractor.SelectorExtractor', MagicMock(return_value=AsyncMock(extract=AsyncMock(return_value=None), get_extraction_priority=lambda:0))), \
         patch('capabilities.scraping.content_extractor.FullPageExtractor', MagicMock(return_value=AsyncMock(extract=AsyncMock(return_value=None), get_extraction_priority=lambda:0))):
        current_content_extractor = ContentExtractor(config=mock_config)

    result = await current_content_extractor.extract_content(url, SAMPLE_HTML)
    
    assert result is not None
    assert result["title"] == "Readability Fallback"
    assert "LD-JSON boom!" in caplog.text 
    assert "Extractor LdJsonExtractor failed" in caplog.text
    mock_ldjson_extractor.extract.assert_awaited_once()
    mock_readability_extractor.extract.assert_awaited_once()

def test_get_extractor_info(content_extractor: ContentExtractor):
    info = content_extractor.get_extractor_info()
    assert len(info) == 4
    # Order is LdJson, Readability, Selector, FullPage due to priority
    expected_names = ["LdJsonExtractor", "ReadabilityExtractor", "SelectorExtractor", "FullPageExtractor"]
    actual_names = [item['name'] for item in info]
    
    # We need to check the names based on the priorities from the mocks
    # mock_ldjson_extractor priority 50
    # mock_readability_extractor priority 40
    # mock_selector_extractor priority 30
    # mock_fullpage_extractor priority 10
    assert actual_names[0] == "LdJsonExtractor"
    assert actual_names[1] == "ReadabilityExtractor"
    assert actual_names[2] == "SelectorExtractor"
    assert actual_names[3] == "FullPageExtractor"
    
    for item in info:
        assert 'name' in item
        assert 'priority' in item
        assert 'description' in item
        assert isinstance(item['priority'], int)

@pytest.mark.asyncio
async def test_extract_content_beautifulsoup_creation_failure(content_extractor: ContentExtractor, caplog):
    url = "http://example.com/bad_html_structure"
    with patch('capabilities.scraping.content_extractor.BeautifulSoup', side_effect=Exception("Soup parsing failed!")):
        result = await content_extractor.extract_content(url, "<malformed>")
    
    assert result is None
    assert "Soup parsing failed!" in caplog.text
    assert f"Content extraction orchestrator failed for {url}" in caplog.text

def test_is_quality_content_various_scenarios(content_extractor: ContentExtractor, mock_config):
    assert content_extractor._is_quality_content(
        {"title": "Good Title", "body": "This is a good body of sufficient length."}, "url1"
    ) == True

    assert content_extractor._is_quality_content(
        {"title": "Good Title", "body": "Too short."}, "url2"
    ) == False

    mock_config.min_title_length = 10
    assert content_extractor._is_quality_content(
        {"title": "Short", "body": "This body is perfectly fine and long enough."}, "url3"
    ) == True 

    assert content_extractor._is_quality_content(
        {"title": "Title Only", "body": ""}, "url4"
    ) == False
    assert content_extractor._is_quality_content(
        {"title": "Title Only", "body": None}, "url4_none"
    ) == False

    mock_config.suspicious_patterns = ["buy now"]
    mock_config.min_content_length = 20
    # Body length is 48. min_content_length (20) + 200 = 220. 48 < 220, so suspicious check applies.
    assert content_extractor._is_quality_content(
        {"title": "Ad Page", "body": "This is an ad, buy now! It's just long enough."}, "url5" 
    ) == False 

    long_body_with_suspicion = "This is a very long article about finance. " + \
                               "It explains many concepts. Eventually, it mentions that you might want to " + \
                               "buy now if you are interested. " * 20 
    assert content_extractor._is_quality_content(
        {"title": "Long Article", "body": long_body_with_suspicion}, "url6"
    ) == True


    mock_config.title_body_ratio_threshold = 0.5
    # title=50, body=11. ratio = 50/11 = 4.5 which is > 0.5. Title len > 20.
    assert content_extractor._is_quality_content(
        {"title": "This Title Is Extremely Long For Such A Small Body", "body": "Short body."}, "url7" 
    ) == False

    assert content_extractor._is_quality_content(
        {"title": "Decent Title", "body": "This body is much longer than the title, which is good."}, "url8"
    ) == True
    
    assert content_extractor._is_quality_content(None, "url9") == False
    assert content_extractor._is_quality_content("not a dict", "url10") == False

    # Test with body as a list (should be handled as not quality by current logic because len check fails)
    assert content_extractor._is_quality_content(
        {"title": "List Body", "body": ["item1", "item2 that is long enough"]}, "url11"
    ) == False 

    mock_config.min_content_length = 15
    assert content_extractor._is_quality_content(
        {"title": "List Body", "body": ["item1", "item2 that is long enough"]}, "url11_pass_if_joined"
    ) == False 

    assert content_extractor._is_quality_content(
        {"title": "None Body", "body": None}, "url12"
    ) == False
