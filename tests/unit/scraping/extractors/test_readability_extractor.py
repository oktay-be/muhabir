\
# filepath: c:\\\\Users\\\\oktay\\\\Documents\\\\aisports\\\\tests\\\\unit\\\\scraping\\\\extractors\\\\test_readability_extractor.py
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

# Target for mocking if readability is not installed or to simulate its behavior
READABILITY_DOCUMENT_PATH = "readability.Document" # Correct path: where Document is looked up

# Mock the Document class from the readability library before importing the extractor
# This allows testing the ImportError case and controlling Document behavior.
mock_document_class = MagicMock()

# Apply the patch to the module where Document is imported
# We need to ensure this patch is active *before* LdJsonExtractor is imported if it also had such a dependency,
# but here it's specific to ReadabilityExtractor's import of Document.
# For safety and clarity, it's often good to patch where the object is *looked up*.
# In readability_extractor.py, it's `from readability import Document`.

@patch(READABILITY_DOCUMENT_PATH, new_callable=MagicMock)
def import_extractor_with_mocked_document(mock_doc_class_ignored_for_signature):
    from capabilities.scraping.extractors.readability_extractor import ReadabilityExtractor
    return ReadabilityExtractor

# The actual ReadabilityExtractor class will be dynamically imported by fixtures/tests
# that need it, allowing the mock to be set up correctly.

@pytest.fixture
def extractor():
    # This fixture will provide an extractor instance where 'readability.Document' is potentially mocked
    # by test-specific patches if needed, or uses the real one if not.
    # For most tests, we want to simulate a successful import and operation of readability.
    # So, we ensure the mock_document_class (if active from a test-level patch) behaves.
    from capabilities.scraping.extractors.readability_extractor import ReadabilityExtractor
    return ReadabilityExtractor()

def test_get_extraction_priority(extractor):
    assert extractor.get_extraction_priority() == 20

@pytest.mark.asyncio
@patch(READABILITY_DOCUMENT_PATH)
async def test_extract_successful(mock_document_constructor, extractor):
    mock_doc_instance = MagicMock()
    mock_doc_instance.title.return_value = "Test Readability Title"
    mock_doc_instance.summary.return_value = "<p>This is the main content that is long enough to pass the filter.</p><div>Another paragraph that is definitely long enough to be included.</div><p>Short text fragment</p>"
    mock_document_constructor.return_value = mock_doc_instance

    html_content = "<html><body><article><h1>Test Readability Title</h1><p>This is the main content that is long enough to pass the filter.</p><div>Another paragraph that is definitely long enough to be included.</div><p>Short text fragment</p></article></body></html>"
    url = "http://example.com/readability_success"
    
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Test Readability Title"
    assert "This is the main content that is long enough to pass the filter." in result["body"]
    assert "Another paragraph that is definitely long enough to be included." in result["body"]
    assert "Short text fragment" not in result["body"] # Filtered out due to length
    assert result["body"] == "This is the main content that is long enough to pass the filter.\n\nAnother paragraph that is definitely long enough to be included."
    assert result["extraction_method"] == "readability"
    mock_document_constructor.assert_called_once_with(html_content)
    mock_doc_instance.summary.assert_called_once_with(html_partial=True)

@pytest.mark.asyncio
@patch(READABILITY_DOCUMENT_PATH)
async def test_extract_no_content(mock_document_constructor, extractor):
    mock_doc_instance = MagicMock()
    mock_doc_instance.title.return_value = "Empty Page"
    mock_doc_instance.summary.return_value = "" # Readability found no main content
    mock_document_constructor.return_value = mock_doc_instance

    html_content = "<html><body><p>Just some random text, nothing article-like.</p></body></html>"
    url = "http://example.com/no_content"
    
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Empty Page"
    assert result["body"] == ""
    assert result["extraction_method"] == "readability"

@pytest.mark.asyncio
@patch(READABILITY_DOCUMENT_PATH)
async def test_extract_readability_exception(mock_document_constructor, extractor, caplog):
    mock_document_constructor.side_effect = Exception("Readability crashed")

    html_content = "<html><body><p>Content</p></body></html>"
    url = "http://example.com/readability_crash"
    
    result = await extractor.extract(html_content, url)

    assert result["title"] == ""
    assert result["body"] == ""
    assert result["extraction_method"] == "readability"
    assert "Error using readability for http://example.com/readability_crash: Readability crashed" in caplog.text

@pytest.mark.asyncio
async def test_extract_import_error(caplog):
    # To test ImportError, we need to ensure 'readability.Document' is not found
    # when ReadabilityExtractor tries to import it *within the extract method*.
    with patch.dict('sys.modules', {'readability': None}): # Simulate module not found at import time
        # Dynamically import here to ensure the patched sys.modules is in effect
        from capabilities.scraping.extractors.readability_extractor import ReadabilityExtractor
        extractor_instance = ReadabilityExtractor()
        
        html_content = "<html><body><p>Content</p></body></html>"
        url = "http://example.com/import_error"
        
        result = await extractor_instance.extract(html_content, url)

        assert result["title"] == ""
        assert result["body"] == ""
        assert result["extraction_method"] == "readability"
        assert "readability-lxml library not installed." in caplog.text

@pytest.mark.asyncio
@patch(READABILITY_DOCUMENT_PATH)
async def test_extract_with_preparsed_soup(mock_document_constructor, extractor):
    # The ReadabilityExtractor's extract method doesn't directly use the soup
    # for the readability library call, it passes the raw html_content.
    # The soup parameter is more for other extractors or a common interface.
    # This test mainly ensures it runs without error if soup is passed.
    mock_doc_instance = MagicMock()
    mock_doc_instance.title.return_value = "Soup Test Title"
    mock_doc_instance.summary.return_value = "<p>Content from soup test.</p>"
    mock_document_constructor.return_value = mock_doc_instance

    html_content = "<html><body><p>Content from soup test.</p></body></html>"
    url = "http://example.com/soup_test"
    soup = BeautifulSoup(html_content, "html.parser")
    
    result = await extractor.extract(html_content, url, soup=soup)

    assert result["title"] == "Soup Test Title"
    assert result["body"] == "Content from soup test."
    assert result["extraction_method"] == "readability"
    mock_document_constructor.assert_called_once_with(html_content) # Still called with html_content

@pytest.mark.asyncio
@patch(READABILITY_DOCUMENT_PATH)
async def test_extract_title_is_none(mock_document_constructor, extractor):
    mock_doc_instance = MagicMock()
    mock_doc_instance.title.return_value = None # Simulate readability returning None for title
    mock_doc_instance.summary.return_value = "<p>Some body content that is definitely long enough to pass the filter test.</p>"
    mock_document_constructor.return_value = mock_doc_instance

    html_content = "<html><body><p>Some body content that is definitely long enough to pass the filter test.</p></body></html>"
    url = "http://example.com/no_title"
    
    result = await extractor.extract(html_content, url)

    assert result["title"] == "" # Should default to empty string
    assert result["body"] == "Some body content that is definitely long enough to pass the filter test."
    assert result["extraction_method"] == "readability"

@pytest.mark.asyncio
@patch(READABILITY_DOCUMENT_PATH)
async def test_extract_body_with_various_tags_and_stripping(mock_document_constructor, extractor):
    mock_doc_instance = MagicMock()
    mock_doc_instance.title.return_value = "Complex Body"
    mock_doc_instance.summary.return_value = """
            <p>   First paragraph with leading and trailing spaces that is definitely long enough to pass the filter.   </p>
            <div>Second paragraph as a div that is also definitely long enough to pass the filter successfully.</div>
            <p>A very short one.</p> <!-- Should be filtered -->
            <p></p> <!-- Empty paragraph -->
            <div><script>alert('xss')</script><span>Visible text in div that is definitely long enough to be included in the final result</span></div>
            <p>Another one that is definitely long enough to be included in the output.</p>
    """
    mock_document_constructor.return_value = mock_doc_instance

    html_content = "<html><body>...</body></html>"
    url = "http://example.com/complex_body"
    
    result = await extractor.extract(html_content, url)

    assert result["title"] == "Complex Body"
    expected_body_parts = [
        "First paragraph with leading and trailing spaces that is definitely long enough to pass the filter.",
        "Second paragraph as a div that is also definitely long enough to pass the filter successfully.",
        "Visible text in div that is definitely long enough to be included in the final result", # Script content is stripped by get_text
        "Another one that is definitely long enough to be included in the output."
    ]
    actual_body_parts = result["body"].split("\n\n")
    
    # Check that all expected parts are present in the actual body parts
    for expected_part in expected_body_parts:
        assert expected_part in actual_body_parts, f"Expected part '{expected_part}' not found in actual body parts: {actual_body_parts}"
    
    assert "A very short one." not in result["body"]
    assert "<script>" not in result["body"]
    assert result["extraction_method"] == "readability"

