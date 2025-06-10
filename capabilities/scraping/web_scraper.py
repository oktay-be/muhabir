"""
Modular web scraper orchestrator that coordinates all scraping components.
"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import urlparse

from .config import ScrapingConfig
from .session_manager import SessionManager
from .cache_manager import CacheManager
from .link_discoverer import LinkDiscoverer
from .content_extractor import ContentExtractor
from .file_manager import FileManager
from .network_utils import normalize_url, is_valid_url # Added

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Modular web scraper that orchestrates all scraping components
    """
    
    def __init__(self, cache_dir: str, cache_expiration_hours: int = 1):
        """
        Initialize the modular web scraper
        
        Args:
            cache_dir: Directory for caching scraped content
            cache_expiration_hours: Hours before cached content expires
        """
        self.cache_dir = cache_dir
        self.cache_expiration_hours = cache_expiration_hours        # Initialize components
        self.config = ScrapingConfig()
        self.session_manager = SessionManager(self.config)
        self.cache_manager = CacheManager(cache_dir, cache_expiration_hours)
        self.link_discoverer = LinkDiscoverer(config=self.config, max_concurrent_tasks=3) # Pass config
        self.content_extractor = ContentExtractor(self.config)
        self.file_manager = FileManager(cache_dir)
        
        # Semaphores for concurrency control
        self.discover_semaphore = asyncio.Semaphore(3)
        self.scrape_semaphore = asyncio.Semaphore(5)
        
        logger.info("Modular web scraper initialized")
    
    async def execute_scraping_for_session(self, session_id: str, keywords: List[str], 
                                         sites: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute complete scraping session with link discovery and content extraction
        
        Args:
            session_id: Unique identifier for this scraping session
            keywords: Keywords to search for
            sites: Optional list of specific sites to scrape
            
        Returns:
            Dict containing scraped articles and session metadata
        """
        session_start = datetime.now()
        logger.info(f"Starting scraping session {session_id} with keywords: {keywords}")
        
        try:
            # Check if session results are cached
            cached_session = self.file_manager.load_session_data(session_id)
            if cached_session:
                logger.info(f"Returning cached session data for {session_id}")
                return cached_session
            
            # Get sites to scrape
            target_sites = sites or list(self.config.site_specific_selectors.keys())
            
            # Discover links
            all_links_raw = [] # Renamed to indicate raw links before processing
            async with self.session_manager: # SessionManager handles session start/stop
                # tasks = [self._discover_links_for_site(site, keywords) for site in target_sites]
                # results = await asyncio.gather(*tasks, return_exceptions=True)
                # for i, result in enumerate(results):
                #     if isinstance(result, list):
                #         all_links_raw.extend(result)
                #         logger.info(f"Found {len(result)} raw links from {target_sites[i]}")
                #     elif isinstance(result, Exception):
                #         logger.error(f"Failed to discover links from {target_sites[i]}: {result}")
                for site in target_sites: # Sequential discovery per site for now
                    try:
                        site_links = await self._discover_links_for_site(site, keywords)
                        all_links_raw.extend(site_links)
                        logger.info(f"Discovered {len(site_links)} links from {site}")
                    except Exception as e:
                        logger.error(f"Failed to discover links from {site}: {e}")

            if not all_links_raw:
                logger.warning(f"No raw links discovered for session {session_id}")
                return {'articles': [], 'session_metadata': self._create_session_metadata(session_id, session_start, 0, 0)}
            
            logger.info(f"Total {len(all_links_raw)} raw links discovered across all sites")
            
            # Normalize and filter discovered links
            processed_links = []
            for link_info in all_links_raw: # Assuming _discover_links_for_site now returns list of dicts
                url = link_info.get('url')
                if not url:
                    logger.warning(f"Link info missing 'url': {link_info}")
                    continue
                
                normalized = normalize_url(url)
                if is_valid_url(normalized):
                    if normalized not in processed_links: # Ensure uniqueness after normalization
                        processed_links.append(normalized)
                else:
                    logger.warning(f"Skipping invalid or non-normalizable URL: {url} (normalized: {normalized})")

            if not processed_links:
                logger.warning(f"No valid links remaining after normalization and filtering for session {session_id}")
                return {'articles': [], 'session_metadata': self._create_session_metadata(session_id, session_start, 0, 0)}

            logger.info(f"Normalized and filtered to {len(processed_links)} unique, valid links.")
            
            # Scrape content from discovered links
            scraped_articles = []
            # Session is already managed by the outer context manager
            tasks = [self._scrape_single_article(link, keywords) for link in processed_links]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict) and result:
                    scraped_articles.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Scraping task failed: {result}")
            
            logger.info(f"Successfully scraped {len(scraped_articles)} articles out of {len(processed_links)} links")
            
            # Prepare session results
            session_data = {
                'articles': scraped_articles,
                'session_metadata': self._create_session_metadata(
                    session_id, session_start, len(processed_links), len(scraped_articles)
                )
            }
            
            # Save session data
            self.file_manager.save_session_data(session_id, session_data)
            
            return session_data
            
        except Exception as e:
            logger.error(f"Scraping session {session_id} failed: {e}")
            return {
                'articles': [],
                'session_metadata': self._create_session_metadata(session_id, session_start, 0, 0),
                'error': str(e)
            }
    
    async def _discover_links_for_site(self, site: str, keywords: List[str]) -> List[Dict[str, Any]]: # Return list of dicts
        """Discover links for a specific site using the LinkDiscoverer module."""
        async with self.discover_semaphore:
            session = await self.session_manager.get_session() # Explicitly get session
            if not session or session.closed:
                logger.error("Session not active or closed in SessionManager, cannot discover links.")
                return []

            search_depth = self.config.link_discovery_depth if hasattr(self.config, 'link_discovery_depth') else 0
            
            # LinkDiscoverer.discover_links returns List[Dict[str, Any]]
            discovered_link_infos = await self.link_discoverer.discover_links(
                site_url=site,
                keywords=keywords,
                session=session, 
                search_depth=search_depth 
            )
            
            # No need to extract just URLs here, return the full info
            # Normalization and validation will happen in execute_scraping_for_session
            return discovered_link_infos 
    
    async def _scrape_single_article(self, url: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Scrape content from a single article URL"""
        
        original_url = url # Keep original for logging if needed
        normalized_url = normalize_url(url)

        if not is_valid_url(normalized_url):
            logger.warning(f"Skipping scraping for invalid or non-normalizable URL: {original_url} (normalized: {normalized_url})")
            return None

        async with self.scrape_semaphore:
            try:
                # Check cache first
                cache_key_params = {"keywords": keywords}
                # Use normalized_url for cache key generation
                cache_key = self.cache_manager.generate_cache_key(normalized_url, params=cache_key_params)
                cached_content = self.cache_manager.get_cached_content(cache_key)
                
                if cached_content:
                    logger.debug(f"Using cached content for {normalized_url} (key: {cache_key})")
                    return cached_content
                
                # Fetch content using normalized_url
                html_content = await self.session_manager.fetch_content(normalized_url)
                if not html_content:
                    logger.warning(f"Failed to fetch HTML content from {normalized_url}")
                    return None
                
                # Extract content using orchestrator, pass normalized_url
                extracted_content = await self.content_extractor.extract_content(normalized_url, html_content)
                if not extracted_content:
                    logger.warning(f"Failed to extract quality content from {normalized_url}")
                    return None
                
                # Prepare article data
                article_data = {
                    'url': normalized_url, # Store normalized URL
                    'original_url': original_url, # Optionally store original URL
                    'scraped_at': datetime.now().isoformat(),
                    'keywords_used': keywords,
                    'title': extracted_content.get('title', ''),
                    'content': extracted_content.get('body', ''),
                    'extraction_method': extracted_content.get('extraction_method', 'unknown'),
                    'site': urlparse(normalized_url).netloc
                }
                
                # Cache the result
                self.cache_manager.cache_content(cache_key, article_data)
                
                # Save individual article
                article_id = cache_key
                self.file_manager.save_article(article_id, article_data)
                
                return article_data
                
            except Exception as e:
                logger.error(f"Failed to scrape article {normalized_url} (original: {original_url}): {e}")
                return None
    
    def _create_session_metadata(self, session_id: str, start_time: datetime, 
                               links_found: int, articles_scraped: int) -> Dict[str, Any]:
        """Create session metadata"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            'session_id': session_id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'links_discovered': links_found,
            'articles_scraped': articles_scraped,
            'success_rate': articles_scraped / links_found if links_found > 0 else 0,
            'scraper_version': 'modular-v1.0'
        }
    
    def get_scraper_info(self) -> Dict[str, Any]:
        """Get information about the scraper configuration"""
        return {
            'cache_dir': self.cache_dir,
            'cache_expiration_hours': self.cache_expiration_hours,
            'supported_sites': list(self.config.site_specific_selectors.keys()),
            'extraction_strategies': self.content_extractor.get_extractor_info(),
            'http_timeout': self.config.http_timeout,
            'max_retries': self.config.max_retries
        }
    
    def cleanup_old_data(self, session_days: int = 7, article_days: int = 30) -> Dict[str, int]:
        """Clean up old cached data"""
        session_cleaned = self.file_manager.cleanup_old_sessions(session_days)
        article_cleaned = self.file_manager.cleanup_old_articles(article_days)
        # Use the new cleanup_expired_cache method name
        cache_cleaned = self.cache_manager.cleanup_expired_cache()
        
        return {
            'sessions_removed': session_cleaned,
            'articles_removed': article_cleaned,
            'cache_files_removed': cache_cleaned
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.session_manager.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)