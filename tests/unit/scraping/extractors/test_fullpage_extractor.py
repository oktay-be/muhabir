# filepath: c:\\Users\\oktay\\Documents\\aisports\\tests\\unit\\scraping\\extractors\\test_fullpage_extractor.py
import pytest
import asyncio
from unittest.mock import MagicMock
from bs4 import BeautifulSoup
from capabilities.scraping.extractors.fullpage_extractor import FullPageExtractor

@pytest.fixture
def extractor():
    return FullPageExtractor()

def test_get_extraction_priority(extractor: FullPageExtractor):
    assert extractor.get_extraction_priority() == 10 # Lowest priority

@pytest.mark.asyncio
async def test_extract_full_page_with_title_tag(extractor: FullPageExtractor):
    html_content = "<html><head><title>Test Page Title</title></head><body><p>Some content.</p><h1>Another Heading</h1></body></html>"
    url = "http://example.com/fullpage_title"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Test Page Title"
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_fallback_to_h1(extractor: FullPageExtractor):
    html_content = "<html><head></head><body><h1>Main Heading Title</h1><p>Some content.</p></body></html>"
    url = "http://example.com/fullpage_h1"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Main Heading Title"
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_title_tag_preferred_over_h1(extractor: FullPageExtractor):
    html_content = "<html><head><title>Title Tag Is King</title></head><body><h1>H1 Is Secondary</h1><p>Content.</p></body></html>"
    url = "http://example.com/fullpage_title_pref"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Title Tag Is King"
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_no_title_or_h1(extractor: FullPageExtractor):
    html_content = "<html><head></head><body><p>Just a paragraph.</p><div>Some divs</div></body></html>"
    url = "http://example.com/fullpage_no_title"
    result = await extractor.extract(html_content, url)

    assert result["title"] == ""
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_empty_html(extractor: FullPageExtractor):
    html_content = ""
    url = "http://example.com/fullpage_empty"
    result = await extractor.extract(html_content, url)

    assert result["title"] == ""
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_with_preparsed_soup(extractor: FullPageExtractor):
    html_content = "<html><head><title>Soup Test Title</title></head><body><h1>Soup H1</h1></body></html>"
    url = "http://example.com/fullpage_soup"
    soup = BeautifulSoup(html_content, "html.parser")
    result = await extractor.extract(html_content, url, soup=soup)

    assert result["title"] == "Soup Test Title"
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_title_tag_with_whitespace(extractor: FullPageExtractor):
    html_content = "<html><head><title>  Spaced Out Title   </title></head><body></body></html>"
    url = "http://example.com/fullpage_whitespace_title"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Spaced Out Title"
    assert result["body"] == html_content

@pytest.mark.asyncio
async def test_extract_full_page_h1_tag_with_whitespace(extractor: FullPageExtractor):
    html_content = "<html><head></head><body><h1>  Spaced Out H1   </h1></body></html>"
    url = "http://example.com/fullpage_whitespace_h1"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Spaced Out H1"
    assert result["body"] == html_content

@pytest.mark.asyncio
async def test_extract_full_page_empty_title_and_h1_tags(extractor: FullPageExtractor):
    html_content = "<html><head><title></title></head><body><h1></h1><p>Content</p></body></html>"
    url = "http://example.com/fullpage_empty_tags"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "" # Empty string from title tag is preferred over empty h1
    assert result["body"] == html_content
    assert result["extraction_method"] == "full_page"

@pytest.mark.asyncio
async def test_extract_full_page_config_param_is_optional_and_not_used(extractor: FullPageExtractor):
    # The constructor takes an optional config, but it's not used by FullPageExtractor
    # This test is more about ensuring it can be instantiated with/without it if the design changes.
    # For now, the fixture provides it as None implicitly by not passing it.
    html_content = "<html><head><title>Config Test</title></head><body>Content</body></html>"
    url = "http://example.com/config_test"
    extractor_with_config = FullPageExtractor(config=MagicMock()) # Pass a mock config
    result_with_config = await extractor_with_config.extract(html_content, url)
    
    extractor_no_config = FullPageExtractor() # Default constructor
    result_no_config = await extractor_no_config.extract(html_content, url)

    assert result_with_config["title"] == "Config Test"
    assert result_with_config["body"] == html_content
    assert result_no_config["title"] == "Config Test"
    assert result_no_config["body"] == html_content
