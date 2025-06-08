from capabilities.scraping.extractors.ldjson_extractor import LdJsonExtractor

extractor = LdJsonExtractor()
ld_data = {'@type': 'Article', 'headline': 'Title', 'articleBody': ['Para1.', 'Para2.']}
title, body = extractor._extract_from_ld_data(ld_data)

print(f'Body: {repr(body)}')
print(f'Expected: {repr("Para1.\\n\\nPara2.")}')
print(f'Are they equal? {body == "Para1.\\n\\nPara2."}')
