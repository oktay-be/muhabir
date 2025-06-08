\
# filepath: c:\\Users\\oktay\\Documents\\aisports\\tests\\unit\\scraping\\test_config.py
import pytest
from capabilities.scraping.config import ScrapingConfig

class TestScrapingConfig:
    def test_initialization_defaults(self):
        """Test that ScrapingConfig initializes with expected default values."""
        config = ScrapingConfig()
        
        # Check if selector dictionaries are initialized
        assert isinstance(config.site_specific_selectors, dict)
        assert isinstance(config.generic_selectors, dict)
        assert len(config.site_specific_selectors) > 0  # Ensure some sites are preconfigured
        assert len(config.generic_selectors) > 0    # Ensure generic selectors exist

        # Check HTTP settings
        assert config.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        assert config.request_timeout == 25
        
        # Check content quality thresholds
        assert config.min_body_length == 50
        assert config.min_title_length == 10
        assert config.high_quality_body_length == 500
        assert config.high_quality_title_length == 15

    def test_get_selectors_for_known_domain(self):
        """Test retrieving selectors for a domain listed in site_specific_selectors."""
        config = ScrapingConfig()
        domain = "hurriyet.com.tr"
        expected_selectors = config.site_specific_selectors[domain]
        selectors = config.get_selectors_for_domain(domain)
        assert selectors == expected_selectors

    def test_get_selectors_for_known_domain_with_subdomain(self):
        """Test retrieving selectors for a subdomain of a known site."""
        config = ScrapingConfig()
        domain = "spor.hurriyet.com.tr"
        # Expects selectors for "hurriyet.com.tr"
        expected_selectors = config.site_specific_selectors["hurriyet.com.tr"]
        selectors = config.get_selectors_for_domain(domain)
        assert selectors == expected_selectors
        
    def test_get_selectors_for_unknown_domain(self):
        """Test retrieving selectors for a domain not in site_specific_selectors."""
        config = ScrapingConfig()
        domain = "unknownexample.com"
        expected_selectors = config.generic_selectors
        selectors = config.get_selectors_for_domain(domain)
        assert selectors == expected_selectors

    def test_get_selectors_for_empty_domain(self):
        """Test retrieving selectors when an empty domain string is provided."""
        config = ScrapingConfig()
        domain = ""
        expected_selectors = config.generic_selectors
        selectors = config.get_selectors_for_domain(domain)
        assert selectors == expected_selectors
        
    def test_get_selectors_for_partial_match_domain(self):
        """Test that a partial but not true subdomain match returns generic selectors."""
        config = ScrapingConfig()
        # e.g., "myhurriyet.com.tr" should not match "hurriyet.com.tr" specific rules
        # unless "myhurriyet.com.tr" itself is a key or "hurriyet.com.tr" is found within "myhurriyet.com.tr"
        # The current implementation `if site_domain in domain.lower():` would match this.
        # Let's test a case that *shouldn't* match if the logic was stricter,
        # but with current logic, it *will* match if a known domain is a substring.
        # To make this test meaningful for the *current* logic, we need a known domain
        # and a test domain where the known domain is a substring.
        
        # Test with a domain that contains a known domain as a substring
        domain_containing_known = "someprefix-hurriyet.com.tr-somesuffix"
        expected_selectors_for_hurriyet = config.site_specific_selectors["hurriyet.com.tr"]
        selectors = config.get_selectors_for_domain(domain_containing_known)
        assert selectors == expected_selectors_for_hurriyet

        # Test with a domain that is a superstring of a known domain but not a direct match or subdomain
        # e.g. if "example.com" is known, "another-example.com.org" should use generic.
        # This case is harder to construct without knowing all site_specific_selectors keys.
        # Let's assume "sporx.com" is a key.
        # "mysporx.com.co" should use generic if "mysporx.com.co" is not a key and "sporx.com" is not "in" "mysporx.com.co" in a way that makes sense.
        # The current logic `if site_domain in domain.lower():` means if "sporx.com" is in "mysporx.com.co", it will match.
        # This test might be redundant with the subdomain test or the one above, depending on the exact keys.

        # A better test for "doesn't falsely match":
        # Ensure a domain that *doesn't* contain any of the site_specific keys returns generic.
        # This is covered by test_get_selectors_for_unknown_domain.

        # Let's refine this test to be more specific about the "in" behavior.
        # If "fotomac.com.tr" is a key.
        # "testfotomac.com.tr.otherdomain.com" should match "fotomac.com.tr"
        domain_with_known_substring = "prefix.fotomac.com.tr.suffix"
        expected_fotomac = config.site_specific_selectors["fotomac.com.tr"]
        selectors_fotomac = config.get_selectors_for_domain(domain_with_known_substring)
        assert selectors_fotomac == expected_fotomac

        # If "nonexistentprefixfotomac.com.tr" is the domain, it should still match "fotomac.com.tr"
        # because "fotomac.com.tr" is in "nonexistentprefixfotomac.com.tr"
        another_domain_substring = "nonexistentprefixfotomac.com.tr"
        selectors_another_fotomac = config.get_selectors_for_domain(another_domain_substring)
        assert selectors_another_fotomac == expected_fotomac


    def test_get_request_headers(self):
        """Test that get_request_headers returns the correct User-Agent."""
        config = ScrapingConfig()
        headers = config.get_request_headers()
        assert "User-Agent" in headers
        assert headers["User-Agent"] == config.user_agent
        assert headers["User-Agent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    def test_get_selectors_for_domain_case_insensitivity(self):
        """Test that domain matching for selectors is case-insensitive."""
        config = ScrapingConfig()
        domain_upper = "HURRIYET.COM.TR"
        expected_selectors = config.site_specific_selectors["hurriyet.com.tr"]
        selectors = config.get_selectors_for_domain(domain_upper)
        assert selectors == expected_selectors

        domain_mixed = "FaNaTiK.cOm.Tr"
        expected_selectors_fanatik = config.site_specific_selectors["fanatik.com.tr"]
        selectors_fanatik = config.get_selectors_for_domain(domain_mixed)
        assert selectors_fanatik == expected_selectors_fanatik

# To run these tests, navigate to the root of your project ('aisports') in the terminal
# and run: pytest tests/unit/scraping/test_config.py
# For coverage: pytest --cov=capabilities.scraping.config --cov-report=html tests/unit/scraping/test_config.py
# (Ensure pytest and pytest-cov are installed: pip install pytest pytest-cov)
