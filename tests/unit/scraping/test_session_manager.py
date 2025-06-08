\
# filepath: c:\\\\Users\\\\oktay\\\\Documents\\\\aisports\\\\tests\\\\unit\\\\scraping\\\\test_session_manager.py
import pytest
import asyncio
import aiohttp
import pytest_asyncio # Added import
from unittest.mock import MagicMock, AsyncMock, patch

from capabilities.scraping.config import ScrapingConfig
from capabilities.scraping.session_manager import SessionManager

@pytest.fixture
def mock_scraping_config():
    """Fixture for a mock ScrapingConfig."""
    config = MagicMock(spec=ScrapingConfig)
    config.get_request_headers = MagicMock(return_value={"User-Agent": "TestAgent/1.0"})
    config.request_timeout = 10 # seconds
    return config

@pytest_asyncio.fixture  # Changed from @pytest.fixture
async def session_manager(mock_scraping_config):
    """Fixture for SessionManager instance, ensuring cleanup."""
    manager = SessionManager(config=mock_scraping_config)
    yield manager
    # Ensure session is closed after tests that might leave it open
    if manager._session and not manager._session.closed:
        await manager.close_session()

@pytest.mark.asyncio
class TestSessionManager:

    async def test_initialization(self, mock_scraping_config):
        manager = SessionManager(config=mock_scraping_config)
        assert manager.config == mock_scraping_config
        assert manager._session is None

    async def test_get_session_creates_new_session(self, session_manager, mock_scraping_config):
        assert session_manager._session is None
        session = await session_manager.get_session()
        assert isinstance(session, aiohttp.ClientSession)
        assert not session.closed
        assert session_manager._session == session
        # Check if config values were used
        assert session.headers["User-Agent"] == "TestAgent/1.0"
        assert session.timeout.total == mock_scraping_config.request_timeout

    async def test_get_session_returns_existing_session(self, session_manager):
        session1 = await session_manager.get_session()
        session2 = await session_manager.get_session()
        assert session1 == session2
        assert not session1.closed

    async def test_get_session_recreates_closed_session(self, session_manager):
        session1 = await session_manager.get_session()
        await session1.close() # Manually close it
        assert session1.closed

        session2 = await session_manager.get_session()
        assert session2 is not None
        assert not session2.closed
        assert session1 != session2 # Should be a new session instance

    async def test_close_session_closes_active_session(self, session_manager):
        session = await session_manager.get_session()
        assert not session.closed
        await session_manager.close_session()
        assert session.closed

    async def test_close_session_no_active_session(self, session_manager, caplog):
        # Ensure no session exists initially
        session_manager._session = None 
        await session_manager.close_session()
        assert "No active HTTP session to close" in caplog.text

    async def test_close_session_already_closed(self, session_manager, caplog):
        session = await session_manager.get_session()
        await session.close() # Manually close
        await session_manager.close_session()
        assert "session already closed" in caplog.text.lower() or "No active HTTP session to close" in caplog.text

    async def test_context_manager_usage(self, mock_scraping_config):
        async with SessionManager(config=mock_scraping_config) as manager:
            assert manager._session is not None
            assert not manager._session.closed
            original_session = manager._session
        assert original_session.closed

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_content_success(self, mock_get, session_manager):
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Success</html>")
        mock_response.raise_for_status = MagicMock() # Does nothing if status is 2xx
        # mock_get.return_value = mock_response # This doesn't work directly for async with
        mock_get.return_value.__aenter__.return_value = mock_response # Correct for async with context

        url = "http://example.com/success"
        content = await session_manager.fetch_content(url)
        
        assert content == "<html>Success</html>"
        mock_get.assert_called_once_with(url)

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_content_http_error_404_no_retry(self, mock_get, session_manager, caplog):
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 404
        mock_response.message = "Not Found"
        mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            MagicMock(), (), status=404, message="Not Found"
        ))
        mock_get.return_value.__aenter__.return_value = mock_response

        url = "http://example.com/notfound"
        content = await session_manager.fetch_content(url, retries=2, retry_delay=0.01)
        
        assert content is None
        mock_get.assert_called_once_with(url) # Should only be called once
        assert f"Client error 404 for {url}. Not retrying." in caplog.text

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_content_server_error_with_retries(self, mock_get, session_manager, caplog):
        mock_response_fail = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response_fail.status = 500
        mock_response_fail.message = "Server Error"
        mock_response_fail.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            MagicMock(), (), status=500, message="Server Error"
        ))

        mock_response_success = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response_success.status = 200
        mock_response_success.text = AsyncMock(return_value="Success after retry")
        mock_response_success.raise_for_status = MagicMock()

        # Fail twice, then succeed
        mock_get.side_effect = [
            AsyncMock(__aenter__=AsyncMock(return_value=mock_response_fail)),
            AsyncMock(__aenter__=AsyncMock(return_value=mock_response_fail)),
            AsyncMock(__aenter__=AsyncMock(return_value=mock_response_success))
        ]

        url = "http://example.com/servererror"
        content = await session_manager.fetch_content(url, retries=2, retry_delay=0.01)
        
        assert content == "Success after retry"
        assert mock_get.call_count == 3
        assert f"HTTP error fetching {url} (attempt 1/3): 500 Server Error" in caplog.text
        assert f"HTTP error fetching {url} (attempt 2/3): 500 Server Error" in caplog.text
        assert f"Successfully fetched content from {url}" in caplog.text

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_content_client_connection_error_with_retries(self, mock_get, session_manager, caplog):
        # Simulate aiohttp.ClientConnectorError
        mock_get.side_effect = [
            aiohttp.ClientConnectorError(MagicMock(), OSError("Connection failed")),
            aiohttp.ClientConnectorError(MagicMock(), OSError("Connection failed")),
            AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
                status=200, text=AsyncMock(return_value="Success"), raise_for_status=MagicMock()
            )))
        ]

        url = "http://example.com/connection_error"
        content = await session_manager.fetch_content(url, retries=2, retry_delay=0.01)

        assert content == "Success"
        assert mock_get.call_count == 3
        assert f"Client error fetching {url} (attempt 1/3)" in caplog.text
        assert f"Client error fetching {url} (attempt 2/3)" in caplog.text

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_content_timeout_error_with_retries(self, mock_get, session_manager, caplog):
        mock_response_success = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response_success.status = 200
        mock_response_success.text = AsyncMock(return_value="Success after timeout retry")
        mock_response_success.raise_for_status = MagicMock()

        mock_get.side_effect = [
            asyncio.TimeoutError("Request timed out"),
            asyncio.TimeoutError("Request timed out"),
            AsyncMock(__aenter__=AsyncMock(return_value=mock_response_success))
        ]

        url = "http://example.com/timeout"
        content = await session_manager.fetch_content(url, retries=2, retry_delay=0.01)

        assert content == "Success after timeout retry"
        assert mock_get.call_count == 3
        assert f"Timeout error fetching {url} (attempt 1/3)" in caplog.text
        assert f"Timeout error fetching {url} (attempt 2/3)" in caplog.text

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_content_all_retries_fail(self, mock_get, session_manager, caplog):
        mock_response_fail = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response_fail.status = 503
        mock_response_fail.message = "Service Unavailable"
        mock_response_fail.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
            MagicMock(), (), status=503, message="Service Unavailable"
        ))
        
        # All attempts fail
        mock_get.return_value.__aenter__.return_value = mock_response_fail

        url = "http://example.com/allfail"
        retries = 2
        content = await session_manager.fetch_content(url, retries=retries, retry_delay=0.01)
        
        assert content is None
        assert mock_get.call_count == retries + 1
        assert f"Failed to fetch {url} after {retries + 1} attempts" in caplog.text

# To run these tests:
# pytest tests/unit/scraping/test_session_manager.py
# For coverage:
# pytest --cov=capabilities.scraping.session_manager --cov-report=html tests/unit/scraping/test_session_manager.py
