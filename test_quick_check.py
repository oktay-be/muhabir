from capabilities.scraping.network_utils import normalize_url, is_valid_url

# Test the specific failing cases
test_cases = [
    ('HTTPS://Example.com:8080/Path?c=3&b=2&a=1&a=0', 'https://example.com:8080/Path?a=0&a=1&b=2&c=3'),
    ('http://example.com/path?listParam=b&listParam=a', 'http://example.com/path?listParam=a&listParam=b'),
    ('http://example.com/path?z=2&y=1&listParam=b&listParam=a&x=0', 'http://example.com/path?listParam=a&listParam=b&x=0&y=1&z=2'),
    ('http://example.com/!@$^*()_+', 'http://example.com/!@$^*()_+'),
    ('http://[::1]:namedport', 'http://[::1]:namedport'),  # Error case should return original
]

print("Testing normalize_url failing cases:")
for input_url, expected in test_cases:
    result = normalize_url(input_url)
    status = "✓" if result == expected else "✗"
    print(f"{status} {input_url!r} -> {result!r}")
    if result != expected:
        print(f"    Expected: {expected!r}")

print("\nTesting is_valid_url:")
validity_tests = [
    ('//protocol-relative.com/path', True),
    ('http://[::1]:namedport', False),
]

for input_url, expected in validity_tests:
    result = is_valid_url(input_url)
    status = "✓" if result == expected else "✗"
    print(f"{status} {input_url!r} -> {result} (expected: {expected})")
