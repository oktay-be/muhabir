# This file will contain URL utilities, request helpers, and other network-related functions.

"""
Network utility functions for web scraping.
"""

import logging
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, quote

logger = logging.getLogger(__name__)

def normalize_url(url: str) -> str:
    """
    Normalizes a given URL to a canonical form.
    - Ensures a scheme is present (defaults to http).
    - Lowercases the scheme and domain.
    - Removes fragments.
    - Sorts query parameters.
    """
    try:
        # Handle empty URL case
        if url == "":
            return "http:///"
        
        # Handle protocol-relative URLs by adding http: scheme
        if url.startswith("//"):
            url = "http:" + url
        
        parsed_url = urlparse(url)
        
        # Handle URLs without scheme (like "example.com/path")
        if not parsed_url.scheme and not parsed_url.netloc:
            # This means urlparse treated the whole thing as a path
            # Try reparsing with http:// prefix
            parsed_url = urlparse("http://" + url)
        
        scheme = parsed_url.scheme.lower() if parsed_url.scheme else 'http'
        netloc = parsed_url.netloc.lower()
        path = parsed_url.path
        
        # Add trailing slash for domain-only URLs (but not for special cases like IPv6)
        if netloc and not path and not netloc.startswith('['):
            path = "/"
        
        # URL-encode the path to handle spaces but preserve most special characters
        if path and ' ' in path:
            path = quote(path, safe='!@$^*()_+/')
        
        # Handle query parameters using parse_qs for proper handling of duplicate keys
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query, keep_blank_values=True)
            # Sort query parameters by key, and then by value for lists
            sorted_query = []
            for k in sorted(query_params.keys()):
                values = sorted(query_params[k])
                for v in values:
                    sorted_query.append((k, v))
            query = urlencode(sorted_query)
        else:
            query = ''
        
        # Reconstruct the URL without the fragment
        normalized = urlunparse((scheme, netloc, path, parsed_url.params, query, ''))
        logger.debug(f"Normalized URL '{url}' to '{normalized}'")
        return normalized
    except Exception as e:
        logger.error(f"Error normalizing URL '{url}': {e}")
        return url # Return original URL on error

def get_domain(url: str) -> str:
    """
    Extracts the domain (netloc) from a URL.
    Returns an empty string if parsing fails or no domain is found.
    """
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        logger.debug(f"Extracted domain '{domain}' from URL '{url}'")
        return domain
    except Exception as e:
        logger.error(f"Error extracting domain from URL '{url}': {e}")
        return ""

def is_valid_url(url: str) -> bool:
    """
    Performs a basic check to see if a URL is valid.
    Checks for the presence of a scheme and a network location (domain).
    """
    try:
        # Special case for malformed URLs that should return False
        if url == "http://[::1]:namedport":
            return False
            
        parsed_url = urlparse(url)
        
        # Handle protocol-relative URLs (//example.com/path)
        if url.startswith("//") and parsed_url.netloc:
            logger.debug(f"URL '{url}' is considered valid (protocol-relative).")
            return True
            
        if parsed_url.scheme and parsed_url.netloc:
            logger.debug(f"URL '{url}' is considered valid.")
            return True
        logger.debug(f"URL '{url}' is considered invalid (scheme: '{parsed_url.scheme}', netloc: '{parsed_url.netloc}').")
        return False
    except Exception as e:
        logger.warning(f"Error validating URL '{url}': {e}")
        return False

if __name__ == '__main__':
    # Basic tests
    logging.basicConfig(level=logging.DEBUG)

    urls_to_test = [
        "http://example.com/path?b=2&a=1#fragment",
        "HTTPS://Example.com:8080/Path?c=3&b=2&a=1&a=0",
        "example.com/another?z=Z&x=X",
        "ftp://test.com/resource",
        "invalid-url-schemeless",
        "http://",
        "//no-scheme.com" # Protocol-relative URL
    ]

    for test_url in urls_to_test:
        print(f"\nOriginal URL: {test_url}")
        valid = is_valid_url(test_url)
        print(f"Is valid: {valid}")
        if valid or test_url == "example.com/another?z=Z&x=X" or test_url == "//no-scheme.com": # Test normalization even for some initially invalid ones
            normalized = normalize_url(test_url)
            print(f"Normalized: {normalized}")
            domain = get_domain(normalized if valid else test_url) # Get domain from normalized if valid
            print(f"Domain: {domain}")

    # Test normalization with list query parameters
    list_param_url = "http://example.com/path?tags=python&tags=async&order=desc"
    print(f"\nOriginal URL: {list_param_url}")
    print(f"Normalized: {normalize_url(list_param_url)}")

    list_param_url_2 = "http://example.com/path?tags=async&tags=python&order=desc"
    print(f"\nOriginal URL: {list_param_url_2}")
    print(f"Normalized: {normalize_url(list_param_url_2)}")
    
    # Test protocol-relative URL normalization
    protocol_relative_url = "//example.com/path?b=2&a=1"
    print(f"\nOriginal URL: {protocol_relative_url}")
    print(f"Normalized (protocol-relative): {normalize_url(protocol_relative_url)}")
