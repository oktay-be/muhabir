"""
HTTP session management for web scraping.
"""

import asyncio
import logging
import aiohttp  # Added
from typing import Optional, Any, Dict  # Added Dict

# Assuming ScrapingConfig is in a file named config.py in the same directory
from .config import ScrapingConfig  # Added

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages HTTP sessions for web scraping."""

    def __init__(self, config: ScrapingConfig):  # Changed type hint and made config non-optional
        """
        Initializes the SessionManager.

        Args:
            config: ScrapingConfig object for session settings.
        """
        self.config = config  # Store the ScrapingConfig instance
        self._session: Optional[aiohttp.ClientSession] = None  # Changed type hint
        logger.info("SessionManager initialized.")

    async def get_session(self) -> aiohttp.ClientSession:  # Changed return type hint
        """
        Provides an active HTTP session.
        Initializes a new session if one doesn't exist or is closed.
        """
        if self._session is None or self._session.closed:
            logger.info("Creating new HTTP session.")
            headers = self.config.get_request_headers()
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
            logger.info(f"New HTTP session created with timeout {self.config.request_timeout}s.")
        return self._session

    async def close_session(self) -> None:
        """
        Closes the active HTTP session if it exists and is open.
        """
        if self._session is not None and not self._session.closed:
            logger.info("Closing HTTP session.")
            await self._session.close()
            # self._session = None # Session becomes unusable after close, but keep reference to check closed status
            logger.info("HTTP session closed.")
        else:
            logger.info("No active HTTP session to close or session already closed.")

    async def fetch_content(self, url: str, retries: int = 3, retry_delay: int = 1) -> Optional[str]:
        """
        Fetches content from a URL using the managed session.

        Args:
            url: The URL to fetch content from.
            retries: Number of times to retry on failure.
            retry_delay: Delay in seconds between retries.

        Returns:
            The page content as a string if successful, None otherwise.
        """
        session = await self.get_session()
        last_exception = None

        for attempt in range(retries + 1):
            try:
                logger.debug(f"Attempt {attempt + 1} to fetch URL: {url}")
                async with session.get(url) as response:
                    response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
                    content = await response.text()
                    logger.info(f"Successfully fetched content from {url} (status: {response.status}).")
                    return content
            except aiohttp.ClientResponseError as e:  # More specific error for HTTP errors
                logger.warning(f"HTTP error fetching {url} (attempt {attempt + 1}/{retries + 1}): {e.status} {e.message}")
                last_exception = e
                if e.status in [400, 401, 403, 404]:  # Don't retry on these client errors
                    logger.error(f"Client error {e.status} for {url}. Not retrying.")
                    break
            except aiohttp.ClientError as e:  # Catches other client errors like connection issues
                logger.warning(f"Client error fetching {url} (attempt {attempt + 1}/{retries + 1}): {e}")
                last_exception = e
            except asyncio.TimeoutError as e:  # Catch timeout errors specifically
                logger.warning(f"Timeout error fetching {url} (attempt {attempt + 1}/{retries + 1}): {e}")
                last_exception = e

            if attempt < retries:
                logger.info(f"Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to fetch {url} after {retries + 1} attempts. Last error: {last_exception}")

        return None

    async def __aenter__(self):
        await self.get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()


# Example usage (for testing purposes, will be removed or commented out later)
# async def main():
#     # This requires a ScrapingConfig instance
#     from .config import ScrapingConfig
#     config = ScrapingConfig() 
#     manager = SessionManager(config=config)
    
#     async with manager:
#         # Example: Fetching a known site
#         content = await manager.fetch_content("http://example.com")
#         if content:
#             logger.info(f"Fetched content length: {len(content)}")
#         else:
#             logger.error("Failed to fetch content from http://example.com")

#         # Example: Fetching a non-existent site to test retries
#         content_fail = await manager.fetch_content("http://thissitedoesnotexist12345.com", retries=2)
#         if not content_fail:
#             logger.info("Correctly failed to fetch non-existent site.")

# if __name__ == '__main__':
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     # asyncio.run(main()) # Python 3.7+
#     # For older Python versions or specific event loop needs:
#     loop = asyncio.get_event_loop()
#     try:
#         # loop.run_until_complete(main())
#         pass # Commenting out main execution for now
#     finally:
#         # loop.close() # Closing loop can be problematic if other async tasks are running
#         pass