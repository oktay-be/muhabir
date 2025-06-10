from capabilities.scraping.network_utils import normalize_url, is_valid_url

test_cases = [
    'example.com/another?z=Z&x=X',
    'http://example.com',
    'http://example.com/path with spaces',
    '',
    'http://example.com?c&b&a',
    '//protocol-relative.com/path',
    'http://[::1]:namedport'
]

print("Testing normalize_url function:")
for case in test_cases:
    result = normalize_url(case)
    print(f'{case!r} -> {result!r}')

print("\nTesting is_valid_url function:")
for case in test_cases:
    result = is_valid_url(case)
    print(f'{case!r} -> {result}')
