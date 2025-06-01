\
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import logging
import json # Keep for main's output
from typing import List, Dict, Optional, Any

# Configure basic logging for the standalone script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StandaloneFotomacScraper:
    """A standalone scraper for a single Fotomac article, using project's logic."""

    def __init__(self): # Removed cache_dir and cache_expiration_hours
        self.session: Optional[aiohttp.ClientSession] = None
        # Removed os.makedirs(self.cache_dir, exist_ok=True)

        # Selectors for fotomac.com.tr (from the project)
        self.selectors = {
            "title_selector": "h1.news-title, h3.card-title",
            "content_selector": "div.news-text, p.card-text", # Main content area
            "date_selector": "div.news-date, span.date",
            "image_selector": "div.news-image img, img.card-img-top",
            "author_selector": "div.news-author, span.author" # Though author is not in the final output dict
        }

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _fetch_html(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            # Increased timeout as per recent project changes
            async with session.get(url, headers=headers, timeout=25) as response:
                response.raise_for_status()
                logger.info(f"Successfully fetched HTML from {url}")
                return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}", exc_info=True)
        return None

    async def scrape_article_details(self, article_url: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Scrapes detailed content from the given article URL."""
        await self._ensure_session()
        if not self.session:
            logger.error("Failed to initialize HTTP session for scraping details.")
            return None

        html_content = await self._fetch_html(article_url, self.session)
        if not html_content:
            return None

        soup = BeautifulSoup(html_content, "html.parser")
        article_domain = urlparse(article_url).netloc.lower() # Should be 'fotomac.com.tr'

        # Use the predefined selectors for Fotomac
        selectors = self.selectors
        
        title_tag = soup.select_one(selectors["title_selector"])
        # For a direct article, title_anchor is not available, so use a placeholder or rely on extraction
        extracted_title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        content_tag = soup.select_one(selectors["content_selector"])
        extracted_body_parts = []
        if content_tag:
            for p_tag in content_tag.find_all(['p', 'div'], recursive=False):
                 text_part = p_tag.get_text(separator='\\n', strip=True)
                 if text_part:
                    extracted_body_parts.append(text_part)
            if not extracted_body_parts:
                extracted_body_parts.append(content_tag.get_text(separator='\\n', strip=True))
        extracted_body = "\\n\\n".join(extracted_body_parts)
        if not extracted_body: # Fallback if specific content extraction fails
             # Try to get text from common main content tags if specific selector fails
            main_content_areas = soup.select("article, .article, .story-content, .entry-content, div[role='main']")
            if main_content_areas:
                extracted_body = main_content_areas[0].get_text(separator='\\n', strip=True)
            else: # Last resort
                extracted_body = soup.get_text(separator='\\n', strip=True)


        date_tag = soup.select_one(selectors["date_selector"])
        published_date = ""
        if date_tag:
            published_date = date_tag.get_text(strip=True)
            if not published_date and date_tag.has_attr('datetime'):
                 published_date = date_tag['datetime']
        
        image_tag = soup.select_one(selectors["image_selector"])
        image_url = None
        if image_tag:
            img_src = image_tag.get("src") or image_tag.get("data-src")
            if img_src:
                image_url = urljoin(article_url, img_src)
        
        # Final keyword check (as in project)
        # For a direct scrape, this confirms the content is relevant to expected keywords.
        url_matches = any(keyword.lower() in article_url.lower() for keyword in keywords)
        title_matches = any(keyword.lower() in extracted_title.lower() for keyword in keywords)
        body_matches = any(keyword.lower() in extracted_body.lower() for keyword in keywords)

        if keywords and not (url_matches or title_matches or body_matches):
            logger.info(f"Article {article_url} did not match provided keywords in final content/title check.")
            return None # Or decide to return it anyway if keywords are just for filtering discovered links

        article_data = {
            "title": extracted_title,
            "url": article_url,
            "body": extracted_body[:2000] + ('...' if len(extracted_body) > 2000 else ''), # Longer body for standalone
            "source": article_domain,
            "published_at": published_date,
            "image_url": image_url
        }
        logger.info(f"Successfully scraped and processed article: {article_url}")
        return article_data

async def main():
    target_url = "https://www.fotomac.com.tr/fenerbahce/2025/05/30/fenerbahce-haberleri-jose-mourinho-icin-karar-verildi-iste-o-tarih?paging=4"
    # Keywords relevant to the article, for the final content check (as per project's WebScraper logic)
    relevant_keywords = ["fenerbahce", "mourinho", "karar", "tarih"]

    scraper = StandaloneFotomacScraper()
    
    scraped_article_data = None
    try:
        scraped_article_data = await scraper.scrape_article_details(target_url, relevant_keywords)
    finally:
        await scraper.close_session()

    if scraped_article_data:
        logger.info("--- Scraped Article Details ---")
        logger.info(f"Title: {scraped_article_data.get('title')}")
        logger.info(f"URL: {scraped_article_data.get('url')}")
        logger.info(f"Source: {scraped_article_data.get('source')}")
        logger.info(f"Published At: {scraped_article_data.get('published_at')}")
        logger.info(f"Image URL: {scraped_article_data.get('image_url')}")
        logger.info(f"Body (first 200 chars): {scraped_article_data.get('body', '')[:200]}...")
        
        # Optionally, save to a file
        with open("single_fotomac_article.json", "w", encoding="utf-8") as f:
            json.dump(scraped_article_data, f, ensure_ascii=False, indent=2)
        logger.info("Scraped data also saved to single_fotomac_article.json")
    else:
        logger.warning(f"Could not scrape article details from {target_url}")

if __name__ == "__main__":
    asyncio.run(main())
