#!/usr/bin/env python3

import json
from capabilities.scraping.extractors.ldjson_extractor import LdJsonExtractor

extractor = LdJsonExtractor()

# Test the exact JSON from the failing test
json_content = '''
{
    "@context": "http://schema.org",
    "@type": "NewsArticle",
    "headline": "Title with\\\\nnewline and \\\\"quotes\\\\"",
    "articleBody": "Body with\\\\ttab and backslash\\\\\\\\."
}
'''

print('Raw JSON content:')
print(repr(json_content))
print()

cleaned = extractor._clean_json_string(json_content)
print('Cleaned JSON:')
print(repr(cleaned))
print()

try:
    parsed = json.loads(cleaned)
    print('Parsed successfully:')
    print('headline:', repr(parsed['headline']))
    print('articleBody:', repr(parsed['articleBody']))
except Exception as e:
    print('Parse error:', e)

print()
print("Testing with corrected JSON (fewer backslashes):")

# Corrected JSON that should work
corrected_json_content = '''
{
    "@context": "http://schema.org",
    "@type": "NewsArticle",
    "headline": "Title with\\nnewline and \\"quotes\\"",
    "articleBody": "Body with\\ttab and backslash\\\\."
}
'''

print('Corrected JSON content:')
print(repr(corrected_json_content))
print()

cleaned2 = extractor._clean_json_string(corrected_json_content)
print('Cleaned corrected JSON:')
print(repr(cleaned2))
print()

try:
    parsed2 = json.loads(cleaned2)
    print('Parsed successfully:')
    print('headline:', repr(parsed2['headline']))
    print('articleBody:', repr(parsed2['articleBody']))
except Exception as e:
    print('Parse error:', e)
