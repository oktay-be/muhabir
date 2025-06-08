from capabilities.scraping.extractors.ldjson_extractor import LdJsonExtractor

extractor = LdJsonExtractor()
print('Test 1:', repr(extractor._clean_json_string(' { "key" : "value" ')))
print('Test 2:', repr(extractor._clean_json_string(' "key" : "value" } ')))
print('Test 3:', repr(extractor._clean_json_string('invalid json')))
print('Test 4:', repr(extractor._clean_json_string('{"key": "value"}')))
