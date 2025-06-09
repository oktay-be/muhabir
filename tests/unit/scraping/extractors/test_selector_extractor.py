\
# filepath: c:\\\\Users\\\\oktay\\\\Documents\\\\aisports\\\\tests\\\\unit\\\\scraping\\\\extractors\\\\test_selector_extractor.py
import pytest
import asyncio
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

from capabilities.scraping.extractors.selector_extractor import SelectorExtractor
from capabilities.scraping.config import ScrapingConfig # Assuming ScrapingConfig is importable

@pytest.fixture
def mock_config():
    config = MagicMock(spec=ScrapingConfig)
    config.site_specific_selectors = {
        "specific.com": {
            "title_selector": ".specific-title",
            "content_selector": ".specific-content"
        }
    }
    config.generic_selectors = {
        "title_selector": "h1.generic-title",
        "content_selector": "div.generic-content"
    }
    
    # Make get_selectors_for_domain a simple MagicMock that can be overridden easily
    config.get_selectors_for_domain = MagicMock()
    
    # Set a default side_effect, but allow return_value to override it
    def default_get_selectors_for_domain(domain):
        if "specific.com" in domain:
            return config.site_specific_selectors["specific.com"]
        return config.generic_selectors
    
    config.get_selectors_for_domain.side_effect = default_get_selectors_for_domain
    
    # Mock for config.get to handle MIN_PARAGRAPH_LENGTH
    def mock_config_get_method(key, default=None):
        if key == "MIN_PARAGRAPH_LENGTH":
            return 20  # Ensure it returns an integer
        return default # Simpler handling for other keys

    config.get = MagicMock(side_effect=mock_config_get_method)
    
    return config

@pytest.fixture
def extractor(mock_config):
    return SelectorExtractor(config=mock_config)

def test_get_extraction_priority(extractor: SelectorExtractor):
    assert extractor.get_extraction_priority() == 30

@pytest.mark.asyncio
async def test_extract_with_site_specific_selectors(extractor: SelectorExtractor, mock_config):
    html_content = """
    <html><head><title>Fallback Title</title></head>
    <body>
        <h1 class="specific-title">Specific Title</h1>
        <div class="specific-content">
            <p>Specific paragraph 1, long enough.</p>
            <p>Short</p>
            <div>Specific div content, also long enough.</div>
        </div>
        <h1 class="generic-title">Generic Title</h1>
        <div class="generic-content"><p>Generic paragraph.</p></div>
    </body></html>
    """
    url = "http://specific.com/page"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Specific Title"
    assert "Specific paragraph 1, long enough." in result["body"]
    assert "Specific div content, also long enough." in result["body"]
    assert "Short" not in result["body"]
    assert "Generic Title" not in result["title"] # Should not use generic if specific matches
    assert "Generic paragraph." not in result["body"]
    assert result["extraction_method"] == "css_selectors_site_specific"
    mock_config.get_selectors_for_domain.assert_called_with("specific.com")

@pytest.mark.asyncio
async def test_extract_with_generic_selectors(extractor: SelectorExtractor, mock_config):
    html_content = """
    <html><head><title>Fallback Title</title></head>
    <body>
        <h1 class="generic-title">Generic Page Title</h1>
        <div class="generic-content">
            <p>Generic paragraph 1, which is sufficiently long.</p>
            <p>Too short.</p>
            <div>Generic div content, also sufficiently long.</div>
        </div>
        <article><p>Fallback article content.</p></article>
    </body></html>
    """
    url = "http://otherdomain.com/page"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Generic Page Title"
    assert "Generic paragraph 1, which is sufficiently long." in result["body"]
    assert "Generic div content, also sufficiently long." in result["body"]
    assert "Too short." not in result["body"]
    assert "Fallback article content." not in result["body"] # Generic should be preferred over structural fallback
    assert result["extraction_method"] == "css_selectors_generic"
    mock_config.get_selectors_for_domain.assert_called_with("otherdomain.com")

@pytest.mark.asyncio
async def test_extract_title_fallback_to_html_title_tag(extractor: SelectorExtractor, mock_config):
    # No specific or generic title selectors match, but content selector might
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {"content_selector": ".some-content"}
    html_content = """
    <html><head><title>HTML Title Tag - Site Name</title></head>
    <body>
        <div class="some-content"><p>Some body content here.</p></div>
    </body></html>
    """
    url = "http://anothersite.com/page"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "HTML Title Tag" # Site name should be stripped
    assert result["body"] == "Some body content here."
    assert result["extraction_method"] == "css_selectors_generic" # or site_specific if domain matched

@pytest.mark.asyncio
async def test_extract_title_fallback_no_site_name_in_html_title(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {"content_selector": ".some-content"}
    html_content = '''
    <html><head><title>Just The Title</title></head>
    <body>
        <div class="some-content"><p>Body here.</p></div>
    </body></html>
    '''
    url = "http://simpletitle.com/page"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Just The Title"

@pytest.mark.asyncio
async def test_extract_body_fallback_to_structural_tags(extractor: SelectorExtractor, mock_config):
    # No specific or generic content selectors match
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {"title_selector": "h1.page-title"}
    html_content = """
    <html><head><title>Some Title</title></head>
    <body>
        <h1 class="page-title">Page Title From Selector</h1>
        <article>
            <header>Article Header - ignore</header>
            <p>This is the primary article content and it is long enough.</p>
            <p>Another paragraph in the article.</p>
            <aside>Sidebar - ignore</aside>
            <script>var x=1;</script>
            <footer>Article Footer - ignore</footer>
        </article>
        <div class="random-div"><p>Not in article.</p></div>
    </body></html>
    """
    url = "http://fallbacksite.com/page"
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Page Title From Selector"
    assert "This is the primary article content and it is long enough." in result["body"]
    assert "Another paragraph in the article." in result["body"]
    assert "Article Header - ignore" not in result["body"]
    assert "Sidebar - ignore" not in result["body"]
    assert "Article Footer - ignore" not in result["body"]
    assert "var x=1;" not in result["body"]
    assert "Not in article." not in result["body"] # Should only get from <article>
    assert result["extraction_method"] == "css_selectors_generic"


@pytest.mark.asyncio
async def test_extract_body_fallback_to_second_structural_tag(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {} # No selectors defined
    html_content = """
    <html><head><title>Title</title></head>
    <body>
        <div class="story-content">
            <p>Content from .story-content, which is a fallback selector and is long enough.</p>
        </div>
    </body></html>
    """
    url = "http://fallbacksite2.com/page"
    result = await extractor.extract(html_content, url)
    assert "Content from .story-content" in result["body"]

@pytest.mark.asyncio
async def test_extract_no_selectors_match_no_fallbacks_work(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {
        "title_selector": ".non-existent-title",
        "content_selector": ".non-existent-content"
    }
    html_content = "<html><head></head><body><p>Just a lonely paragraph, too short for fallback.</p></body></html>"
    url = "http://emptysite.com/page"
    result = await extractor.extract(html_content, url)

    assert result["title"] == ""
    assert result["body"] == ""
    assert result["extraction_method"] == "css_selectors_generic"

@pytest.mark.asyncio
async def test_extract_with_preparsed_soup(extractor: SelectorExtractor, mock_config):
    html_content = """
    <html><head><title>Soup Test</title></head>
    <body><h1 class="generic-title">Soup Title</h1><div class="generic-content"><p>Soup body content that is long.</p></div></body></html>
    """
    url = "http://soupsite.com/page"
    soup = BeautifulSoup(html_content, "html.parser")
    result = await extractor.extract(html_content, url, soup=soup)

    assert result["title"] == "Soup Title"
    assert "Soup body content that is long." in result["body"]
    assert result["extraction_method"] == "css_selectors_generic"

def test_get_selector_type(extractor: SelectorExtractor, mock_config):
    assert extractor._get_selector_type("specific.com") == "site_specific"
    assert extractor._get_selector_type("www.specific.com.sub") == "site_specific"
    assert extractor._get_selector_type("generic.com") == "generic"
    # Ensure the mock was set up as expected for this part of the test
    assert "specific.com" in extractor.config.site_specific_selectors

@pytest.mark.asyncio
async def test_extract_body_no_substantial_paragraphs_uses_full_text(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {"content_selector": "#main"}
    html_content = """
    <html><body>
        <div id="main">
            <span>Short.</span> <span>Also short.</span> <span>And this.</span>
            This text is not in a p or div but is part of main. And it is long enough.
        </div>
    </body></html>"""
    url = "http://shortparas.com"
    result = await extractor.extract(html_content, url)
    # _extract_text_from_content will find no p/divs > 20 chars, so it takes all text from #main
    assert "Short. Also short. And this.\nThis text is not in a p or div but is part of main. And it is long enough." in result["body"]

@pytest.mark.asyncio
async def test_extract_body_unwanted_elements_cleaned_from_fallback(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {} # Force fallback
    html_content = """
    <html><body>
        <article>
            <nav>Navigation menu</nav>
            <p>Good content here which is long enough.</p>
            <header>A header inside article</header>
            <p>More good content, and this text makes it long enough.</p>
            <footer>A footer inside article</footer>
            <aside>An aside</aside>
            <script>alert('test')</script>
            <style>.hide {display:none;}</style>
        </article>
    </body></html>"""
    url = "http://cleanfallback.com"
    result = await extractor.extract(html_content, url)
    body = result["body"]
    assert "Good content here which is long enough." in body
    assert "More good content, and this text makes it long enough." in body
    assert "Navigation menu" not in body
    assert "A header inside article" not in body # This might be kept if not explicitly removed by get_text of parent
    assert "A footer inside article" not in body # Same as header
    assert "An aside" not in body
    assert "alert('test')" not in body
    assert ".hide {display:none;}" not in body
    # The current fallback logic for _extract_body does decompose nav, header, footer, aside, script, style
    # before calling get_text. So they should be gone.

@pytest.mark.asyncio
async def test_extract_body_from_div_elements(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {"content_selector": ".content-area"}
    html_content = """
    <html><body>
        <div class="content-area">
            <div>This is the first div paragraph, long enough.</div>
            <div>This is the second div paragraph, also long enough.</div>
            <p>A p tag too, for good measure and length.</p>
        </div>
    </body></html>"""
    url = "http://divcontent.com"
    result = await extractor.extract(html_content, url)
    assert "This is the first div paragraph, long enough." in result["body"]
    assert "This is the second div paragraph, also long enough." in result["body"]
    assert "A p tag too, for good measure and length." in result["body"]

@pytest.mark.asyncio
async def test_extract_empty_html(extractor: SelectorExtractor):
    html_content = ""
    url = "http://emptyhtml.com"
    result = await extractor.extract(html_content, url)
    assert result["title"] == ""
    assert result["body"] == ""

@pytest.mark.asyncio
async def test_extract_html_with_only_title_tag(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {} # No specific selectors
    html_content = "<html><head><title>Only Title Here</title></head><body></body></html>"
    url = "http://onlytitlehtml.com"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Only Title Here"
    assert result["body"] == ""

@pytest.mark.asyncio
async def test_extract_title_stripping_various_separators(extractor: SelectorExtractor, mock_config):
    mock_config.get_selectors_for_domain.side_effect = None
    mock_config.get_selectors_for_domain.return_value = {} # No specific selectors
    test_cases = [
        ("Title - Site", "Title"),
        ("Title | Site", "Title"),
        ("Title – Site", "Title"), # en-dash
        ("Title — Site", "Title"), # em-dash
        ("Title - Another - Part", "Title"), # Only first part
        ("Title NoSeparator", "Title NoSeparator")
    ]
    for full_title, expected_title in test_cases:
        html_content = f"<html><head><title>{full_title}</title></head><body></body></html>"
        url = "http://titleseparator.com"
        result = await extractor.extract(html_content, url)
        assert result["title"] == expected_title
