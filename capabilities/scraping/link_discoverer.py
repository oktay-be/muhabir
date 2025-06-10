"""
Link discovery for web scraping.
"""

import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import aiohttp

# Assuming ScrapingConfig might be used for things like user-agent, timeouts, or link patterns
from .config import ScrapingConfig
from .network_utils import fetch_html

logger = logging.getLogger(__name__)


class LinkDiscoverer:
    """Discovers relevant links from web pages based on keywords and site-specific patterns."""
    
    def __init__(self, config: ScrapingConfig, max_concurrent_tasks: int = 5):
        """
        Initialize the link discoverer.
        
        Args:
            config: ScrapingConfig instance for settings like user-agent, request timeouts.
            max_concurrent_tasks: Maximum concurrent discovery tasks (not directly used in this class yet,
                                  but could be for managing internal task queues if discovering from multiple
                                  seed URLs simultaneously within this class).
        """
        self.config = config
        self.max_concurrent_tasks = max_concurrent_tasks # Placeholder for now
        logger.info(f"LinkDiscoverer initialized. Max concurrent tasks (placeholder): {max_concurrent_tasks}")

    async def discover_links(
        self, 
        site_url: str, # Renamed from page_url for clarity, this is the entry point for a site
        keywords: List[str], 
        session: aiohttp.ClientSession,
        search_depth: int = 1, # How many levels of links to follow from the initial page
        visited_urls: Optional[set] = None # To avoid re-processing and loops
    ) -> List[Dict[str, str]]: # Return type is a list of dicts with link info
        """
        Discover relevant links starting from a given site URL, potentially following links.
        
        Args:
            site_url: The initial URL of the site/page to start discovery from.
            keywords: Keywords to filter links (case-insensitive).
            session: Active aiohttp.ClientSession for making HTTP requests.
            search_depth: How many levels deep to discover links. 0 means only the initial page.
            visited_urls: A set of already visited URLs to prevent re-fetching and loops.
            
        Returns:
            A list of unique, relevant link information dictionaries.
            Each dictionary contains: {'url': str, 'title_anchor': str, 'source_page_url': str}
        """
        if visited_urls is None:
            visited_urls = set()

        if site_url in visited_urls or search_depth < 0:
            return []

        visited_urls.add(site_url)
        discovered_links_map: Dict[str, Dict[str, str]] = {} # Use a map to store unique links by URL
        
        logger.info(f"Discovering links from {site_url} (depth: {search_depth}, keywords: {keywords})")

        try:
            html_content = await self._fetch_html(site_url, session)
            if not html_content:
                logger.warning(f"No HTML content fetched from {site_url}, cannot discover links.")
                return []
            
            soup = BeautifulSoup(html_content, "html.parser")
            base_domain = urlparse(site_url).netloc
            
            links_on_this_page = []

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                anchor_text = a_tag.get_text(strip=True)
                
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                
                absolute_url = urljoin(site_url, href)
                link_domain = urlparse(absolute_url).netloc

                # Basic filter: only consider links within the same domain or subdomains for now
                # More advanced logic could come from self.config (e.g., allowed_domains)
                if not link_domain.endswith(base_domain):
                    # logger.debug(f"Skipping external link: {absolute_url} (base: {base_domain})")
                    continue

                # Check if keywords match URL or anchor text
                if self._matches_keywords(absolute_url, anchor_text, keywords):
                    if absolute_url not in discovered_links_map: # Ensure uniqueness
                        link_info = {
                            "url": absolute_url,
                            "title_anchor": anchor_text,
                            "source_page_url": site_url
                        }
                        discovered_links_map[absolute_url] = link_info
                        links_on_this_page.append(absolute_url)
            
            logger.info(f"Found {len(discovered_links_map)} relevant links on page {site_url}.")

            # Recursive discovery if depth allows
            if search_depth > 0:
                for link_url in links_on_this_page: # Iterate over links found on *this* page
                    if link_url not in visited_urls: # Check before recursive call
                        # logger.debug(f"Recursively discovering from {link_url} (depth left: {search_depth - 1})")
                        recursive_links = await self.discover_links(
                            link_url, keywords, session, search_depth - 1, visited_urls
                        )
                        for r_link_info in recursive_links:
                            if r_link_info['url'] not in discovered_links_map:
                                discovered_links_map[r_link_info['url']] = r_link_info
            
        except Exception as e:
            logger.error(f"Error discovering links from {site_url}: {e}", exc_info=True)
        
        final_links = list(discovered_links_map.values())
        logger.info(f"Total {len(final_links)} unique links discovered starting from {site_url} after depth {search_depth}.")
        return final_links
    
    def _matches_keywords(self, url: str, anchor_text: str, keywords: List[str]) -> bool:
        """
        Check if URL or anchor text matches keywords.
        
        Args:
            url: URL to check
            anchor_text: Anchor text to check
            keywords: Keywords to match against
            
        Returns:
            True if matches, False otherwise
        """
        if not keywords:
            return True
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if (keyword_lower in url.lower() or 
                keyword_lower in anchor_text.lower()):
                return True
        
        return False
    
    async def _fetch_html(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Fetch HTML content from URL using shared network utility.
        
        Args:
            url: URL to fetch
            session: HTTP session to use
              
        Returns:
            HTML content or None if fetch fails
        """
        return await fetch_html(url, session, self.config)
