import pytest
from abc import ABC, abstractmethod
from capabilities.scraping.extractors.base_extractor import BaseExtractor

# A concrete implementation for testing purposes
class ConcreteExtractor(BaseExtractor):
    async def extract(self, html_content: str, url: str) -> dict:
        # Simulate extraction
        if "error" in html_content:
            return {"error": "Simulated extraction error"}
        return {"title": "Test Title", "body": html_content, "url": url}

    def get_extraction_priority(self) -> int:
        return 25 # Override default priority

class TestBaseExtractor:

    def test_base_extractor_is_abc(self):
        """Test that BaseExtractor is an Abstract Base Class."""
        assert issubclass(BaseExtractor, ABC)

    def test_abstract_method_defined(self):
        """Test that 'extract' is defined as an abstract method."""
        assert 'extract' in BaseExtractor.__abstractmethods__

    def test_default_priority(self):
        """Test the default extraction priority."""
        # Create a minimal concrete class that doesn't override get_extraction_priority
        class DefaultPriorityExtractor(BaseExtractor):
            async def extract(self, html_content: str, url: str) -> dict:
                return {}
        
        extractor = DefaultPriorityExtractor()
        assert extractor.get_extraction_priority() == 50

    @pytest.mark.asyncio
    async def test_concrete_extractor_implementation(self):
        """Test a concrete implementation of BaseExtractor."""
        extractor = ConcreteExtractor()
        html = "<p>Some content</p>"
        url = "http://example.com/test"
        
        result = await extractor.extract(html, url)
        
        assert isinstance(result, dict)
        assert result["title"] == "Test Title"
        assert result["body"] == html
        assert result["url"] == url
        assert extractor.get_extraction_priority() == 25

    @pytest.mark.asyncio
    async def test_concrete_extractor_error_scenario(self):
        """Test error scenario in a concrete implementation."""
        extractor = ConcreteExtractor()
        html_error = "error content leads to failure"
        url = "http://example.com/error_page"

        result = await extractor.extract(html_error, url)
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "Simulated extraction error"

    def test_cannot_instantiate_base_extractor_directly(self):
        """Test that BaseExtractor cannot be instantiated directly due to abstract methods."""
        with pytest.raises(TypeError) as excinfo:
            BaseExtractor() # type: ignore
        assert "Can't instantiate abstract class BaseExtractor without an implementation for abstract method 'extract'" in str(excinfo.value)

# To run these tests:
# pytest tests/unit/scraping/extractors/test_base_extractor.py
# For coverage:
# pytest --cov=capabilities.scraping.extractors.base_extractor --cov-report=html tests/unit/scraping/extractors/test_base_extractor.py
