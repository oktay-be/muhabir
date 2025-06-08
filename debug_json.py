import json

# Test what json.loads actually does with escaped sequences
json_string = '''
{
    "@context": "http://schema.org",
    "@type": "NewsArticle",
    "headline": "Title with\\nnewline and \\"quotes\\"",
    "articleBody": "Body with\\ttab and backslash\\\\."
}
'''

print("Original JSON string:")
print(repr(json_string))

parsed = json.loads(json_string)
print("\nParsed data:")
print(repr(parsed))

print("\nHeadline from parsed data:")
print(repr(parsed["headline"]))

print("\nArticleBody from parsed data:")
print(repr(parsed["articleBody"]))
