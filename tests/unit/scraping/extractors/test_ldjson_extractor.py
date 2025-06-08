\
# filepath: c:\\Users\\oktay\\Documents\\aisports\\tests\\unit\\scraping\\extractors\\test_ldjson_extractor.py
import pytest
import asyncio
from bs4 import BeautifulSoup
from capabilities.scraping.extractors.ldjson_extractor import LdJsonExtractor

@pytest.fixture
def extractor():
    return LdJsonExtractor()

def test_get_extraction_priority(extractor: LdJsonExtractor):
    assert extractor.get_extraction_priority() == 10

@pytest.mark.asyncio
async def test_extract_no_ldjson(extractor: LdJsonExtractor):
    html_content = "<html><body><p>No JSON-LD here.</p></body></html>"
    url = "http://example.com/no_ldjson"
    result = await extractor.extract(html_content, url)
    assert result["title"] == ""
    assert result["body"] == ""
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_simple_ldjson(extractor: LdJsonExtractor):
    html_content = '''
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "NewsArticle",
                "headline": "Test Article Title",
                "articleBody": "This is the body of the test article."
            }
            </script>
        </head>
        <body></body>
    </html>
    '''
    url = "http://example.com/simple_ldjson"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Test Article Title"
    assert result["body"] == "This is the body of the test article."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_with_list(extractor: LdJsonExtractor):
    html_content = '''
    <html>
        <head>
            <script type="application/ld+json">
            [
                {
                    "@context": "http://schema.org",
                    "@type": "WebPage",
                    "name": "Page Name"
                },
                {
                    "@context": "http://schema.org",
                    "@type": "NewsArticle",
                    "headline": "Main Article Title",
                    "articleBody": "Main article content here."
                }
            ]
            </script>
        </head>
        <body></body>
    </html>
    '''
    url = "http://example.com/list_ldjson"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Main Article Title" # Should pick the NewsArticle
    assert result["body"] == "Main article content here."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_with_graph(extractor: LdJsonExtractor):
    html_content = '''
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@graph": [
                    {
                        "@type": "WebPage",
                        "name": "Some Page"
                    },
                    {
                        "@type": "Article",
                        "headline": "Article in Graph",
                        "description": "Description from graph article."
                    }
                ]
            }
            </script>
        </head>
        <body></body>
    </html>
    '''
    url = "http://example.com/graph_ldjson"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Article in Graph"
    assert result["body"] == "Description from graph article."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_multiple_ldjson_scripts(extractor: LdJsonExtractor):
    html_content = '''
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "BlogPosting",
                "headline": "First Post",
                "articleBody": "Shorter body."
            }
            </script>
            <script type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "NewsArticle",
                "headline": "More Important Article",
                "articleBody": "This is a longer and more important body of text for the article."
            }
            </script>
        </head>
        <body></body>
    </html>
    '''
    url = "http://example.com/multiple_ldjson"
    result = await extractor.extract(html_content, url)
    # Expects the content from the script that provides a longer body
    assert result["title"] == "More Important Article"
    assert result["body"] == "This is a longer and more important body of text for the article."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_various_fields(extractor: LdJsonExtractor):
    # Test with 'name' for title and 'text' for body
    html_content_name_text = '''
    <html><head><script type="application/ld+json">
    { "@type": "Article", "name": "Title from Name", "text": "Body from Text" }
    </script></head><body></body></html>
    '''
    result = await extractor.extract(html_content_name_text, "http://example.com/name_text")
    assert result["title"] == "Title from Name"
    assert result["body"] == "Body from Text"

    # Test with 'description' for body
    html_content_description = '''
    <html><head><script type="application/ld+json">
    { "@type": "WebPage", "headline": "Title from Headline", "description": "Body from Description" }
    </script></head><body></body></html>
    '''
    result = await extractor.extract(html_content_description, "http://example.com/description")
    assert result["title"] == "Title from Headline"
    assert result["body"] == "Body from Description"

@pytest.mark.asyncio
async def test_extract_malformed_ldjson(extractor: LdJsonExtractor):
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "@type": "NewsArticle",
        "headline": "Good Title",
        "articleBody": "Good body, but the JSON is broken after this..."
        THIS IS NOT VALID JSON
    </script></head><body></body></html>
    '''
    # The _clean_json_string should try to recover this
    # However, if json.loads still fails after cleaning, it should return empty
    # Let's test a case where cleaning might not perfectly recover it for json.loads
    result = await extractor.extract(html_content, "http://example.com/malformed")
    # Depending on how robust _clean_json_string is, this might extract or not.
    # Based on current _clean_json_string, it might fail to parse.
    # If it successfully parses the valid part:
    # assert result["title"] == "Good Title"
    # assert result["body"] == "Good body, but the JSON is broken after this..."
    # If it fails to parse:
    assert result["title"] == "" # Or "Good Title" if cleaning is very robust
    assert result["body"] == "" # Or "Good body..." if cleaning is very robust
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_with_preparsed_soup(extractor: LdJsonExtractor):
    html_content = '''
    <html><head><script type="application/ld+json">
    { "@type": "Article", "headline": "Soup Test", "articleBody": "Body from soup." }
    </script></head><body></body></html>
    '''
    url = "http://example.com/soup_test"
    soup = BeautifulSoup(html_content, "html.parser")
    result = await extractor.extract(html_content, url, soup=soup)
    assert result["title"] == "Soup Test"
    assert result["body"] == "Body from soup."

@pytest.mark.asyncio
async def test_extract_empty_script_tag(extractor: LdJsonExtractor):
    html_content = '<html><head><script type="application/ld+json"></script></head><body></body></html>'
    url = "http://example.com/empty_script"
    result = await extractor.extract(html_content, url)
    assert result["title"] == ""
    assert result["body"] == ""

@pytest.mark.asyncio
async def test_extract_script_tag_with_only_whitespace(extractor: LdJsonExtractor):
    html_content = '<html><head><script type="application/ld+json">   \\n\\t   </script></head><body></body></html>'
    url = "http://example.com/whitespace_script"
    result = await extractor.extract(html_content, url)
    assert result["title"] == ""
    assert result["body"] == ""

@pytest.mark.asyncio
async def test_extract_ldjson_body_is_list(extractor: LdJsonExtractor):
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "@type": "Article",
        "headline": "List Body Title",
        "articleBody": ["Paragraph 1.", "Paragraph 2.", "Paragraph 3."]
    }
    </script></head><body></body></html>
    '''
    url = "http://example.com/list_body"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "List Body Title"
    assert result["body"] == "Paragraph 1.\\n\\nParagraph 2.\\n\\nParagraph 3."

@pytest.mark.asyncio
async def test_extract_ldjson_title_is_list(extractor: LdJsonExtractor):
    # While less common for title, the code handles it, so we test it.
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "@type": "Article",
        "headline": ["Main Title", "Subtitle"],
        "articleBody": "Some body content."
    }
    </script></head><body></body></html>
    '''
    url = "http://example.com/list_title"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Main Title Subtitle"
    assert result["body"] == "Some body content."

@pytest.mark.asyncio
async def test_extract_ldjson_chooses_longer_content(extractor: LdJsonExtractor):
    html_content = '''
    <html><head>
        <script type="application/ld+json">
        {
            "@type": "WebPage",
            "name": "Short Title",
            "description": "Short body."
        }
        </script>
        <script type="application/ld+json">
        {
            "@type": "Article",
            "headline": "A Much Longer and More Descriptive Title",
            "articleBody": "This is a significantly longer and more detailed body of text compared to the other script tag."
        }
        </script>
    </head><body></body></html>
    '''
    url = "http://example.com/longer_content"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "A Much Longer and More Descriptive Title"
    assert result["body"] == "This is a significantly longer and more detailed body of text compared to the other script tag."

@pytest.mark.asyncio
async def test_extract_ldjson_stops_if_substantial_content_found(extractor: LdJsonExtractor):
    # This test assumes that if a script tag yields a body > 200 chars and a title, it stops.
    html_content = '''
    <html><head>
        <script type="application/ld+json">
        {
            "@type": "Article",
            "headline": "Sufficiently Long Article",
            "articleBody": "This is the first article body, and it is designed to be long enough to trigger the early exit condition. The length of this text should be well over two hundred characters to ensure that the extractor prioritizes it and does not proceed to parse subsequent LD+JSON blocks if this one is deemed sufficient for content extraction purposes."
        }
        </script>
        <script type="application/ld+json">
        {
            "@type": "NewsArticle",
            "headline": "Another Article - Should Not Be Reached",
            "articleBody": "This content should not be extracted if the previous one was sufficient."
        }
        </script>
    </head><body></body></html>
    '''
    url = "http://example.com/substantial_content"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Sufficiently Long Article"
    assert "This is the first article body" in result["body"]
    assert "Another Article - Should Not Be Reached" not in result["title"]
    assert "This content should not be extracted" not in result["body"]


# Tests for helper methods
def test_clean_json_string(extractor: LdJsonExtractor):
    assert extractor._clean_json_string('{"key": "value"}') == '{"key": "value"}'
    assert extractor._clean_json_string('  leading whitespace {"key": "value"} trailing ') == '{"key": "value"}'
    assert extractor._clean_json_string('non-json prefix {"key": "value"} suffix') == '{"key": "value"}'
    assert extractor._clean_json_string('non-json prefix [{"key": "value"}] suffix') == '[{"key": "value"}]'
    assert extractor._clean_json_string('invalid json') == 'invalid json' # No braces/brackets
    assert extractor._clean_json_string(' { "key" : "value" ') == '{ "key" : "value" ' # Missing closing brace
    assert extractor._clean_json_string(' "key" : "value" } ') == ' "key" : "value" } ' # Missing opening brace
    assert extractor._clean_json_string('prefix { "data": [1,2], "more": "stuff" } suffix') == '{ "data": [1,2], "more": "stuff" }'
    assert extractor._clean_json_string('prefix [ { "item": 1 }, { "item": 2 } ] suffix') == '[ { "item": 1 }, { "item": 2 } ]'
    # Test with mixed brackets and braces where outer is a brace
    assert extractor._clean_json_string('stuff { "a": [1,2], "b": { "c": 3 } } morestuff') == '{ "a": [1,2], "b": { "c": 3 } }'
    # Test with mixed brackets and braces where outer is a bracket
    assert extractor._clean_json_string('stuff [ {"a": 1}, {"b": [2,3]} ] morestuff') == '[ {"a": 1}, {"b": [2,3]} ]'
    assert extractor._clean_json_string('') == ''
    assert extractor._clean_json_string('{}') == '{}'
    assert extractor._clean_json_string('[]') == '[]'
    assert extractor._clean_json_string(' { "unterminatedKey": ') == '{ "unterminatedKey": ' # Corrected expectation

def test_parse_ld_json(extractor: LdJsonExtractor):
    assert extractor._parse_ld_json('{"key": "value"}') == {"key": "value"}
    assert extractor._parse_ld_json('  {"key": "value"}  ') == {"key": "value"} # Relies on _clean_json_string
    assert extractor._parse_ld_json('prefix {"key": "value"} suffix') == {"key": "value"} # Relies on _clean_json_string
    assert extractor._parse_ld_json('{"key": "value", "num": 123}') == {"key": "value", "num": 123}
    assert extractor._parse_ld_json('[1, "two", {"three": 3}]') == [1, "two", {"three": 3}]
    assert extractor._parse_ld_json('invalid json') is None
    assert extractor._parse_ld_json('{"key": "value", "unterminated}') is None # Malformed
    assert extractor._parse_ld_json('/* comment */ {"key": "value"}') == {"key": "value"} # _clean_json_string handles this

def test_extract_from_ld_data_single_dict(extractor: LdJsonExtractor):
    ld_data = {
        "@type": "NewsArticle",
        "headline": "Test Title",
        "articleBody": "Test body content."
    }
    title, body = extractor._extract_from_ld_data(ld_data)
    assert title == "Test Title"
    assert body == "Test body content."

def test_extract_from_ld_data_list_of_dicts(extractor: LdJsonExtractor):
    ld_data = [
        {"@type": "WebPage", "name": "Generic Page"},
        {"@type": "Article", "headline": "Main Article", "text": "Main text."}
    ]
    title, body = extractor._extract_from_ld_data(ld_data)
    assert title == "Main Article"
    assert body == "Main text."

def test_extract_from_ld_data_graph(extractor: LdJsonExtractor):
    ld_data = {
        "@graph": [
            {"@type": "Organization", "name": "Org Name"},
            {"@type": "BlogPosting", "headline": "Blog Post Title", "description": "Blog post description."}
        ]
    }
    title, body = extractor._extract_from_ld_data(ld_data)
    assert title == "Blog Post Title"
    assert body == "Blog post description."

def test_extract_from_ld_data_type_list(extractor: LdJsonExtractor):
    ld_data = {
        "@type": ["Thing", "Article"], # Type is a list
        "name": "Article Name",
        "articleBody": "Body of article."
    }
    title, body = extractor._extract_from_ld_data(ld_data)
    assert title == "Article Name"
    assert body == "Body of article."

def test_extract_from_ld_data_no_relevant_type(extractor: LdJsonExtractor):
    ld_data = {"@type": "Product", "name": "A Product", "description": "Product details."}
    title, body = extractor._extract_from_ld_data(ld_data)
    assert title == "" # Or "A Product" if we decide to be more lenient, current logic is strict
    assert body == ""  # Or "Product details"

def test_extract_from_ld_data_prioritizes_fields(extractor: LdJsonExtractor):
    # headline over name
    ld_data_title = {
        "@type": "Article",
        "headline": "Primary Headline",
        "name": "Secondary Name",
        "articleBody": "Body"
    }
    title, _ = extractor._extract_from_ld_data(ld_data_title)
    assert title == "Primary Headline"

    # articleBody over text over description
    ld_data_body1 = {
        "@type": "Article", "headline": "T",
        "articleBody": "Use ArticleBody", "text": "Ignore Text", "description": "Ignore Description"
    }
    _, body = extractor._extract_from_ld_data(ld_data_body1)
    assert body == "Use ArticleBody"

    ld_data_body2 = {
        "@type": "Article", "headline": "T",
        "text": "Use Text", "description": "Ignore Description"
    }
    _, body = extractor._extract_from_ld_data(ld_data_body2)
    assert body == "Use Text"
    
    ld_data_body3 = {
        "@type": "Article", "headline": "T",
        "description": "Use Description"
    }
    _, body = extractor._extract_from_ld_data(ld_data_body3)
    assert body == "Use Description"

def test_extract_from_ld_data_body_is_list(extractor: LdJsonExtractor):
    ld_data = {
        "@type": "Article", "headline": "Title",
        "articleBody": ["Para1.", "Para2."]
    }
    _, body = extractor._extract_from_ld_data(ld_data)
    assert body == "Para1.\\n\\nPara2."

def test_extract_from_ld_data_title_is_list(extractor: LdJsonExtractor):
    ld_data = {
        "@type": "Article", "headline": ["Main", "Sub"],
        "articleBody": "Body"
    }
    title, _ = extractor._extract_from_ld_data(ld_data)
    assert title == "Main Sub"

def test_extract_from_ld_data_empty_inputs(extractor: LdJsonExtractor):
    title, body = extractor._extract_from_ld_data({})
    assert title == ""
    assert body == ""
    title, body = extractor._extract_from_ld_data([])
    assert title == ""
    assert body == ""
    title, body = extractor._extract_from_ld_data(None) # Should handle gracefully
    assert title == ""
    assert body == ""
    title, body = extractor._extract_from_ld_data([{"@type": "NonArticle"}])
    assert title == ""
    assert body == ""

@pytest.mark.asyncio
async def test_extract_ldjson_with_special_characters_in_script(extractor: LdJsonExtractor):
    # Test for characters like newlines, tabs within the JSON string values
    # which should be handled correctly by json.loads if the JSON is valid.
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "@context": "http://schema.org",
        "@type": "NewsArticle",
        "headline": "Title with\\nnewline and \\"quotes\\"",
        "articleBody": "Body with\\ttab and backslash\\\\."
    }
    </script></head><body></body></html>
    '''
    url = "http://example.com/special_chars"
    result = await extractor.extract(html_content, url)
    # Corrected assertions:
    assert result["title"] == 'Title with\nnewline and "quotes"'
    assert result["body"] == 'Body with\ttab and backslash\\.'
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_complex_nested_structure(extractor: LdJsonExtractor):
    # Test a more complex, nested JSON-LD that might still contain relevant info
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "@context": "http://schema.org",
        "@type": "WebPage",
        "name": "Outer Page",
        "mainEntity": {
            "@type": "Article",
            "headline": "Nested Article Title",
            "articleBody": "Content of the nested article.",
            "author": {
                "@type": "Person",
                "name": "John Doe"
            }
        }
    }
    </script></head><body></body></html>
    '''
    # Current _extract_from_ld_data only looks at top-level items or items in @graph.
    # It does not recursively search nested structures like 'mainEntity' unless 'mainEntity' itself is an Article.
    # This test will check current behavior. If desired, _extract_from_ld_data could be enhanced.
    url = "http://example.com/nested_ldjson"
    result = await extractor.extract(html_content, url)
    
    # Based on current implementation, it will find "Outer Page" as title and no body from WebPage type.
    # If mainEntity was processed, it would be "Nested Article Title".
    # The current logic iterates through `items_to_check`. If `ld_data` is a dict, `items_to_check` gets `ld_data` and `ld_data["@graph"]` if it exists.
    # So, the `WebPage` item is processed. It has `name: "Outer Page"`.
    # The `Article` is nested inside `mainEntity` and won't be directly iterated over unless `_extract_from_ld_data` is made recursive.
    
    # Expected behavior with current non-recursive _extract_from_ld_data:
    assert result["title"] == "Outer Page" # From WebPage
    assert result["body"] == "" # WebPage doesn't provide articleBody directly in this structure for the extractor
    
    # If we wanted to extract from mainEntity, _extract_from_ld_data would need modification.
    # For now, this test confirms the current behavior.

@pytest.mark.asyncio
async def test_extract_ldjson_multiple_types_in_one_object(extractor: LdJsonExtractor):
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "@context": "http://schema.org",
        "@type": ["WebPage", "Article", "NewsArticle"],
        "headline": "Multi-type Article",
        "name": "Multi-type Page Name",
        "articleBody": "Content for multi-type."
    }
    </script></head><body></body></html>
    '''
    url = "http://example.com/multi_type_object"
    result = await extractor.extract(html_content, url)
    # NewsArticle/Article types should be preferred for fields
    assert result["title"] == "Multi-type Article" # headline from Article/NewsArticle
    assert result["body"] == "Content for multi-type."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_with_comments_in_script_tag_outside_json(extractor: LdJsonExtractor):
    html_content = '''
    <html><head><script type="application/ld+json">
    // This is a comment before the JSON
    {
        "@context": "http://schema.org",
        "@type": "Article",
        "headline": "Article with Comments",
        "articleBody": "Body here."
    }
    // This is a comment after the JSON
    </script></head><body></body></html>
    '''
    url = "http://example.com/ldjson_with_comments"
    result = await extractor.extract(html_content, url)
    # _clean_json_string should handle this by finding the first { and last }
    assert result["title"] == "Article with Comments"
    assert result["body"] == "Body here."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_malformed_but_cleanable(extractor: LdJsonExtractor):
    # Test case where _clean_json_string can successfully extract valid JSON
    # from a script tag that has extra non-JSON content.
    html_content = '''
    <html><head><script type="application/ld+json">
    some_javascript_variable = {
        "@context": "http://schema.org",
        "@type": "NewsArticle",
        "headline": "Cleanable JSON Title",
        "articleBody": "This is the body of the cleanable JSON."
    }; // Semicolon and other JS stuff
    </script></head><body></body></html>
    '''
    url = "http://example.com/cleanable_malformed_ldjson"
    result = await extractor.extract(html_content, url)
    assert result["title"] == "Cleanable JSON Title"
    assert result["body"] == "This is the body of the cleanable JSON."
    assert result["extraction_method"] == "ld_json"

@pytest.mark.asyncio
async def test_extract_ldjson_completely_invalid_json_after_cleaning(extractor: LdJsonExtractor):
    # Test case where _clean_json_string might return something that's still not valid JSON
    html_content = '''
    <html><head><script type="application/ld+json">
    {
        "key": "value" // Missing closing brace, and cleaning won't add it
    </script></head><body></body></html>
    '''
    url = "http://example.com/invalid_after_cleaning"
    result = await extractor.extract(html_content, url)
    assert result["title"] == ""
    assert result["body"] == ""
    assert result["extraction_method"] == "ld_json"

