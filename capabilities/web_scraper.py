"""
Web scraper capability for the Turkish Sports News API.

This module handles scraping news from various Turkish sports websites by first
discovering relevant links and then scraping their content.
"""

import os
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from readability import Document # Added for readability
from urllib.parse import urlparse, urljoin
from werkzeug.utils import secure_filename # Added for filename sanitization

logger = logging.getLogger(__name__)


class WebScraper:
    """Web scraper for Turkish sports news websites"""

    def __init__(self, cache_dir: str, cache_expiration_hours: int = 1):
        """Initialize the web scraper"""
        self.cache_dir = cache_dir
        self.cache_expiration_hours = cache_expiration_hours
        self.session: Optional[aiohttp.ClientSession] = None
        self.discover_semaphore = asyncio.Semaphore(3) # Limit concurrent discovery tasks
        self.scrape_semaphore = asyncio.Semaphore(5)   # Limit concurrent scraping tasks

        os.makedirs(self.cache_dir, exist_ok=True)

        self.site_specific_selectors = {
            "hurriyet.com.tr": {
                "article_selector": "div.news-item, div.col-md-12.col-sm-12.col-xs-12", # Used for detail scraping if needed, less for general content
                "title_selector": "h1.rhd-article-title, h1.page-title, .article-title h1", # More specific for article pages
                "link_selector": "a.news-item__link", # Primarily for discovery if used on a listing page
                "date_selector": "span.rhd-time-box-text, .article-date time, .news-item__date",
                "content_selector": "div.rhd-all-article-detail, div.article-content, .news-item__spot", # Main content area
                "image_selector": "img.rhd-article-spot-img, .article-image img, img.news-item__image",
                "author_selector": "span.rhd-author-name, .article-author, span.news-item__author"
            },
            "fanatik.com.tr": {
                "title_selector": "h1.news-detail__title, h3.title",
                "content_selector": "div.news-detail__body, div.spot",
                "date_selector": "span.news-detail__date, span.date",
                "image_selector": "figure.news-detail__media img, img.lazy",
                "author_selector": ".news-detail__author-name, span.author"
            },
            "sabah.com.tr": {
                "title_selector": "h1.detayH1, h1.pageTitle, h3, h4",
                "content_selector": "div.detayText, div.newsBox, div.spot",
                "date_selector": "span.tarih, .date",
                "image_selector": "figure.newsPicture img, img",
                "author_selector": "a.author, .author"
            },
            "fotomac.com.tr": {
                "title_selector": "h1.news-title, h3.card-title",
                "content_selector": "div.news-text, p.card-text",
                "date_selector": "div.news-date, span.date",
                "image_selector": "div.news-image img, img.card-img-top",
                "author_selector": "div.news-author, span.author"
            },
            "sporx.com": {
                "title_selector": "h1.detail-title, h3.title",
                "content_selector": "div.detail-text, .summary",
                "date_selector": "span.detail-date, .date",
                "image_selector": "div.detail-image img, img",
                "author_selector": "span.author-name, .author-name" # Corrected, was .author-name twice
            },
            "mackolik.com": {
                "title_selector": "h1.page-title, h3", # More specific for article pages
                "content_selector": "div.article-body, .news-summary", # Main content area
                "date_selector": "div.article-info .date, .news-date",
                "image_selector": "div.article-image img, .news-image img",
                "author_selector": "div.article-info .author, .news-author"
            },
            "ntvspor.net": {
                "title_selector": "h1.news-title, h2, h3",
                "content_selector": "div.news-content, .card-text, .summary",
                "date_selector": "div.meta-data time, .date, time",
                "image_selector": "figure.news-image img, img.card-img-top, .news-image img",
                "author_selector": "div.meta-data .author, .author"
            }
        }
        self.generic_selectors = {
            "title_selector": "h1, h2, .article-title, .content-title, .news_title, [itemprop='headline']",
            "content_selector": "article, .article-body, .article-content, .content-text, .news_body, [itemprop='articleBody']",
            "date_selector": ".date, .time, .published, .pubdate, time, [itemprop='datePublished']",
            "image_selector": "img, .image, .thumbnail, [itemprop='image']", # More specific for main image needed
            "author_selector": ".author, .writer, .reporter, [itemprop='author']"
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
            async with session.get(url, headers=headers, timeout=25) as response: # Increased timeout to 25
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}", exc_info=True)
        return None

    async def _discover_links_from_page(self, page_url: str, keywords: List[str], session: aiohttp.ClientSession) -> List[Dict[str, str]]:
        """Fetches a page and discovers links relevant to keywords."""
        discovered_links = []
        html_content = await self._fetch_html(page_url, session)
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        page_domain = urlparse(page_url).netloc

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            anchor_text = a_tag.get_text(strip=True)
            
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            absolute_url = urljoin(page_url, href)

            # Check if keywords are in URL or anchor text
            url_matches = any(keyword.lower() in absolute_url.lower() for keyword in keywords)
            text_matches = any(keyword.lower() in anchor_text.lower() for keyword in keywords)

            if url_matches or text_matches:
                discovered_links.append({
                    "title_anchor": anchor_text,  # Preliminary title from anchor text
                    "url": absolute_url,
                    "source_page_domain": page_domain # Domain of the page where link was found
                })
        logger.info(f"Discovered {len(discovered_links)} potential links from {page_url} matching keywords.")
        return discovered_links

    async def _scrape_article_details(self, link_info: Dict[str, str], keywords: List[str], session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Scrapes detailed content from a given article URL."""
        article_url = link_info["url"]
        
        # Cache key based on URL and keywords (as keywords influence if we store it)
        cache_key_str = f"{article_url}-{'-'.join(sorted(keywords))}"
        cache_key = hashlib.md5(cache_key_str.encode()).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"article_{cache_key}.json")

        cached_article = self._read_from_cache(cache_file)
        if cached_article:
            logger.info(f"Returning article details from cache for {article_url}")
            return cached_article

        html_content = await self._fetch_html(article_url, session)
        if not html_content:
            return None

        soup = BeautifulSoup(html_content, "html.parser")
        article_domain = urlparse(article_url).netloc.lower()

        extracted_title = link_info.get("title_anchor", "Untitled") # Default title
        extracted_body = ""
        extraction_method_log = [] # To log which methods were tried

        # Strategy 1: Try to parse application/ld+json
        try:
            ld_json_scripts = soup.find_all("script", type="application/ld+json")
            for script_tag in ld_json_scripts:
                if script_tag.string:
                    try:
                        ld_data_content = script_tag.string
                        # Remove potential leading/trailing non-JSON content if any (e.g. comments)
                        # A simple heuristic: find first '{' or '[' and last '}' or ']'
                        first_brace = ld_data_content.find('{')
                        first_bracket = ld_data_content.find('[')
                        last_brace = ld_data_content.rfind('}')
                        last_bracket = ld_data_content.rfind(']')

                        start_index = -1
                        if first_brace != -1 and first_bracket != -1:
                            start_index = min(first_brace, first_bracket)
                        elif first_brace != -1:
                            start_index = first_brace
                        elif first_bracket != -1:
                            start_index = first_bracket
                        
                        end_index = -1
                        if last_brace != -1 and last_bracket != -1:
                            end_index = max(last_brace, last_bracket)
                        elif last_brace != -1:
                            end_index = last_brace
                        elif last_bracket != -1:
                            end_index = last_bracket
                        
                        if start_index != -1 and end_index != -1 and end_index > start_index:
                            ld_data_content = ld_data_content[start_index : end_index+1]
                        
                        ld_data = json.loads(ld_data_content)
                        
                        items_to_check = []
                        if isinstance(ld_data, list):
                            items_to_check.extend(ld_data)
                        elif isinstance(ld_data, dict):
                            items_to_check.append(ld_data)
                            # Sometimes the main object is nested, e.g., inside "@graph"
                            if isinstance(ld_data.get("@graph"), list):
                                items_to_check.extend(ld_data["@graph"])

                        for item in items_to_check:
                            if isinstance(item, dict):
                                item_type = item.get("@type", "")
                                if isinstance(item_type, list): # @type can be a list
                                    item_type_str = " ".join(item_type).lower()
                                else:
                                    item_type_str = str(item_type).lower()

                                if any(t in item_type_str for t in ["newsarticle", "article", "webpage", "reportage", "blogposting"]):
                                    current_item_body = item.get("articleBody") or item.get("text") or item.get("description")
                                    current_item_title = item.get("headline") or item.get("name")

                                    if current_item_body and isinstance(current_item_body, str) and (not extracted_body or len(current_item_body) > len(extracted_body)):
                                        extracted_body = current_item_body
                                        extraction_method_log.append(f"ld+json:body_from_type_{item_type_str.split()[0] if item_type_str else 'unknown'}")
                                    
                                    if current_item_title and isinstance(current_item_title, str) and ((not extracted_title or extracted_title == "Untitled") or len(current_item_title) > len(extracted_title)):
                                        extracted_title = current_item_title
                                        extraction_method_log.append(f"ld+json:title_from_type_{item_type_str.split()[0] if item_type_str else 'unknown'}")
                        
                        if extracted_body and isinstance(extracted_body, list): # Ensure body is string
                            extracted_body = "\\\\n\\\\n".join(filter(None, [str(p) for p in extracted_body]))
                        if extracted_title and isinstance(extracted_title, list): # Ensure title is string
                            extracted_title = " ".join(filter(None, [str(t) for t in extracted_title]))

                        if extracted_body and len(extracted_body) > 100 and extracted_title and extracted_title != "Untitled":
                            logger.info(f"Extracted content via ld+json for {article_url}")
                            break 
                    except json.JSONDecodeError as e_json:
                        logger.debug(f"Failed to parse ld+json content for {article_url}: {e_json}. Content: {script_tag.string[:200]}...")
                    except Exception as e_ld:
                        logger.warning(f"Error processing ld+json for {article_url}: {e_ld}")
            if extraction_method_log and "ld+json" in " ".join(extraction_method_log):
                 logger.info(f"Used ld+json for {article_url}. Body len: {len(extracted_body)}, Title: '{extracted_title[:50]}...'")

        except Exception as e:
            logger.warning(f"Outer error during ld+json processing for {article_url}: {e}")
        
        # Strategy 2: Use readability-lxml if ld+json didn't yield enough or failed
        if not extracted_body or len(extracted_body) < 200: 
            if extracted_body: # Log if there was some ld+json body but it was too short
                 logger.info(f"ld+json body for {article_url} is short (len: {len(extracted_body)}). Trying readability.")
            else: # Log if ld+json found no body at all
                 logger.info(f"ld+json found no body for {article_url}. Trying readability.")
            try:
                doc = Document(html_content)
                readability_title = doc.title()
                content_html = doc.summary(html_partial=True)
                content_soup = BeautifulSoup(content_html, "html.parser")
                
                body_paragraphs = [p.get_text(strip=True) for p in content_soup.find_all(['p', 'div'])] # Consider divs too
                readability_body = "\\\\n\\\\n".join(filter(None, body_paragraphs))

                if len(readability_body) > len(extracted_body): # Prioritize if readability gives more
                    extracted_body = readability_body
                    extraction_method_log.append("readability:body")
                
                if readability_title and ((not extracted_title or extracted_title == "Untitled" or len(extracted_title) < 10) or len(readability_title) > len(extracted_title)):
                    extracted_title = readability_title
                    extraction_method_log.append("readability:title")
                logger.info(f"Used readability for {article_url}. Body len: {len(extracted_body)}, Title: '{extracted_title[:50]}...'")
            except Exception as e_read:
                logger.warning(f"Error using readability-lxml for {article_url}: {e_read}")

        # Strategy 3: Fallback to BeautifulSoup selector logic if readability also failed or content is short
        if not extracted_body or len(extracted_body) < 200:
            logger.warning(f"Readability/ld+json extracted little content for {article_url} (body len: {len(extracted_body)}). Falling back to BS4 selectors.")
            
            current_bs4_selectors = self.generic_selectors
            site_specific_applied = False
            for site_domain_key, site_specific_selects in self.site_specific_selectors.items():
                if site_domain_key in article_domain:
                    current_bs4_selectors = site_specific_selects
                    site_specific_applied = True
                    logger.debug(f"Using site-specific selectors for {article_domain} (BS4 fallback)")
                    break
            if not site_specific_applied:
                logger.debug(f"Using generic selectors for {article_domain} (BS4 fallback)")

            # BS4 Title extraction
            if (not extracted_title or extracted_title == "Untitled" or len(extracted_title) < 10):
                title_selector_str = current_bs4_selectors.get("title_selector", self.generic_selectors["title_selector"])
                title_tag = soup.select_one(title_selector_str)
                bs_title = title_tag.get_text(strip=True) if title_tag else link_info.get("title_anchor", "Untitled")
                if len(bs_title) > len(extracted_title) or extracted_title == "Untitled":
                    extracted_title = bs_title
                    extraction_method_log.append("bs4:title")
                    logger.debug(f"Used BS4 title for {article_url}: '{extracted_title}'")

            # BS4 Body extraction
            body_selector_str = current_bs4_selectors.get("content_selector", self.generic_selectors["content_selector"])
            content_tag = soup.select_one(body_selector_str)
            bs_extracted_body_parts = []
            if content_tag:
                # Prefer direct children text nodes or specific tags like <p> to avoid over-grabbing
                # Also handle cases where content is in sibling divs/ps rather than direct children
                for element in content_tag.find_all(['p', 'div'], recursive=True): # Recursive true, but filter later if needed
                    # Avoid known junk like nav, header, footer, script, style if they are children of content_tag
                    if element.name in ['nav', 'header', 'footer', 'script', 'style', 'aside', 'form']:
                        continue
                    is_nested_content = False
                    for known_selector_key in ["content_selector", "article_selector"]: # check if this element itself is a sub-article
                         if current_bs4_selectors.get(known_selector_key) and element.matches(current_bs4_selectors[known_selector_key]):
                              is_nested_content = True; break
                         if self.generic_selectors.get(known_selector_key) and element.matches(self.generic_selectors[known_selector_key]):
                              is_nested_content = True; break
                    if is_nested_content and element != content_tag : # if it's a nested article like structure, and not the main one we are on
                         continue

                    text_part = element.get_text(separator='\\n', strip=True)
                    if text_part and len(text_part) > 20: # Heuristic: ignore very short text parts
                        bs_extracted_body_parts.append(text_part)
                
                if not bs_extracted_body_parts: # If no p/divs with substantial text, get all text from the content_tag
                    full_content_tag_text = content_tag.get_text(separator='\\n', strip=True)
                    if full_content_tag_text:
                         bs_extracted_body_parts.append(full_content_tag_text)
            
            bs_body = "\\\\n\\\\n".join(bs_extracted_body_parts)
            if len(bs_body) > len(extracted_body): 
                 extracted_body = bs_body
                 extraction_method_log.append("bs4:body_primary_selector")


            # Further BS4 fallback for body if still too short
            if (not extracted_body or len(extracted_body) < 200) and body_selector_str:
                logger.debug(f"Primary BS4 content selector ('{body_selector_str}') found little/no body for {article_url} (length: {len(extracted_body)}). Trying general main content area BS4 fallback.")
                main_content_selectors_list = [
                    "article", ".article", ".story-content", ".entry-content", 
                    "div[role='main']", "div.article-body", "div.article-content", 
                    "div.news-text", "main", "section.content", "div.content"
                ]
                best_main_content_text = ""
                for general_selector_str in main_content_selectors_list:
                    area = soup.select_one(general_selector_str)
                    if area:
                        # Clean out common non-content elements before getting text
                        for junk_tag in area.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style', 'form', '.related-articles', '.comments']):
                            junk_tag.decompose()
                        area_text = area.get_text(separator='\\n', strip=True)
                        if len(area_text) > len(best_main_content_text):
                            best_main_content_text = area_text
                
                if len(best_main_content_text) > len(extracted_body):
                    extracted_body = best_main_content_text
                    extraction_method_log.append("bs4:body_general_main_content")
                    logger.debug(f"Used general BS4 main content area fallback for body on {article_url}, new length: {len(extracted_body)}")
            if "bs4" in " ".join(extraction_method_log):
                logger.info(f"Used BS4 selectors for {article_url}. Body len: {len(extracted_body)}, Title: '{extracted_title[:50]}...'")


        # Strategy 4: Last resort - use cleaned full page text if body is still too short
        MIN_BODY_LENGTH_BEFORE_FULL_PAGE_TEXT = 150 # If body is shorter than this, consider full page
        MIN_BODY_LENGTH_FOR_ACCEPTANCE = 50 # If extracted_body is less than this, full page text is more likely to be better
        
        if not extracted_body or len(extracted_body) < MIN_BODY_LENGTH_BEFORE_FULL_PAGE_TEXT:
            logger.warning(f"All structured extraction methods yielded short body for {article_url} (len: {len(extracted_body)}). Resorting to cleaned full page text.")
            
            temp_soup = BeautifulSoup(html_content, "html.parser") # Re-parse to ensure we have a clean soup
            for tag in temp_soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', '.sidebar', '#sidebar']):
                tag.decompose() # Remove common non-content elements

            all_text_parts = [p.strip() for p in temp_soup.get_text(separator='\\n').split('\\n') if p.strip() and len(p.strip()) > 10] # Only non-empty, reasonably long lines
            full_page_text = "\\\\n\\\\n".join(all_text_parts)
            
            if len(full_page_text) > len(extracted_body) and (len(extracted_body) < MIN_BODY_LENGTH_FOR_ACCEPTANCE or not extracted_body) :
                extracted_body = full_page_text
                extraction_method_log.append("full_page_text_heuristic")
                logger.info(f"Used full_page_text (heuristic) for {article_url}. New body length: {len(extracted_body)}")
            elif not extracted_body and full_page_text: # If body is completely empty, take it
                 extracted_body = full_page_text
                 extraction_method_log.append("full_page_text_empty_fallback")
                 logger.info(f"Used full_page_text (empty fallback) for {article_url}. New body length: {len(extracted_body)}")


        # Final cleanup for title if it's still the default anchor or very short
        if not extracted_title or extracted_title == link_info.get("title_anchor", "Untitled") or len(extracted_title) < 15:
            # Try to get title from <title> tag as a last resort for title
            html_title_tag = soup.find('title')
            if html_title_tag and html_title_tag.string:
                html_doc_title = html_title_tag.string.strip()
                # Often the site name is appended, try to remove it if it looks like "Article Title - Site Name"
                common_separators = [" - ", " | ", " – ", " — "]
                for sep in common_separators:
                    if sep in html_doc_title:
                        parts = html_doc_title.split(sep)
                        # Take the longest part, assuming it's the title, or the first part if lengths are similar
                        potential_title = parts[0]
                        if len(potential_title) > 10: # Basic sanity check
                             html_doc_title = potential_title
                             break
                if (not extracted_title or extracted_title == link_info.get("title_anchor", "Untitled") or len(html_doc_title) > len(extracted_title)) and len(html_doc_title) > 10 :
                    extracted_title = html_doc_title
                    extraction_method_log.append("html_title_tag")
        
        logger.info(f"Extraction methods tried for {article_url}: {', '.join(list(set(extraction_method_log)))}. Final body length: {len(extracted_body)}. Final title: '{extracted_title[:60]}...'")

        # Date, Image, Author extraction (using current_selectors logic)
        # This part remains largely the same, but ensure selectors are correctly chosen
        final_content_selectors = self.generic_selectors # Default to generic
        for site_domain_key, site_specific_selects in self.site_specific_selectors.items():
            if site_domain_key in article_domain:
                final_content_selectors = site_specific_selects
                break
        
        date_tag = soup.select_one(final_content_selectors.get("date_selector", self.generic_selectors["date_selector"]))
        extracted_date = None
        if date_tag:
            try:
                date_str = date_tag.get("datetime") or date_tag.get_text(strip=True)
                # Attempt to parse common date formats if direct fromisoformat fails
                # This is a placeholder for more robust date parsing if needed
                try:
                    extracted_date = datetime.fromisoformat(date_str)
                except ValueError:
                    # Add more parsing attempts here if common non-ISO formats are encountered
                    logger.warning(f"Could not parse date string '{date_str}' as ISO format for {article_url}. Further parsing logic may be needed.")
                    extracted_date = None # Explicitly set to None if parsing fails
            except Exception as e:
                logger.warning(f"Error processing date for {article_url}: {e}")

        image_url = None
        image_tag = soup.select_one(final_content_selectors.get("image_selector", self.generic_selectors["image_selector"]))
        if image_tag and image_tag.get("src"):
            image_url = urljoin(article_url, image_tag["src"])

        author_tag = soup.select_one(final_content_selectors.get("author_selector", self.generic_selectors["author_selector"]))
        extracted_author = author_tag.get_text(strip=True) if author_tag else None
        
        # Add source_page_domain to the article data
        source_page_domain_val = link_info.get("source_page_domain", article_domain)

        # Final keyword check on URL, extracted title, and extracted body
        url_matches = any(keyword.lower() in article_url.lower() for keyword in keywords)
        title_matches = any(keyword.lower() in extracted_title.lower() for keyword in keywords)
        body_matches = any(keyword.lower() in extracted_body.lower() for keyword in keywords)

        if url_matches or title_matches or body_matches:
            article_data = {
                "title": extracted_title.strip() if extracted_title else "Untitled", # Ensure title is stripped
                "url": article_url,
                "body": extracted_body.strip() if extracted_body else "", # Ensure body is stripped
                "source": article_domain,
                "source_page_domain": source_page_domain_val, 
                "published_at": extracted_date.isoformat() if extracted_date else None,
                "image_url": image_url,
                "author": extracted_author, # Added author
                "html_content": html_content 
            }
            self._write_to_cache(cache_file, article_data)
            logger.info(f"Successfully scraped and processed article: {article_url}")
            return article_data
        else:
            logger.info(f"Article {article_url} did not match keywords in final content/title check.")
            return None

    async def scrape_urls(self, initial_urls: List[str], keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrapes news articles from a list of initial URLs.
        1. Discovers relevant links on these pages based on keywords.
        2. Scrapes the content of these discovered links.
        """
        await self._ensure_session()
        if not self.session: # Should not happen if _ensure_session works
            logger.error("Failed to initialize HTTP session.")
            return []

        all_discovered_links_info: List[Dict[str, str]] = []
        
        discovery_tasks = []
        for url in initial_urls:
            async def discover_with_semaphore(u_inner): # Renamed to avoid outer scope capture issues in loop
                async with self.discover_semaphore:
                    logger.debug(f"Discovery semaphore acquired for {u_inner}")
                    result = await self._discover_links_from_page(u_inner, keywords, self.session)
                    logger.debug(f"Discovery semaphore released for {u_inner}")
                    return result
            discovery_tasks.append(discover_with_semaphore(url))
        
        page_link_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)

        for i, result in enumerate(page_link_results):
            if isinstance(result, Exception):
                logger.error(f"Error discovering links from {initial_urls[i]}: {result}", exc_info=True)
            elif result:
                all_discovered_links_info.extend(result)
        
        # Deduplicate discovered links based on URL to avoid scraping the same article multiple times
        unique_links_to_scrape_map: Dict[str, Dict[str,str]] = {}
        for link_info in all_discovered_links_info:
            if link_info["url"] not in unique_links_to_scrape_map:
                 unique_links_to_scrape_map[link_info["url"]] = link_info
        
        unique_links_list = list(unique_links_to_scrape_map.values())
        logger.info(f"Total unique relevant links to scrape: {len(unique_links_list)}")

        if not unique_links_list:
            return []

        scraping_tasks = []
        for link_info in unique_links_list:
            async def scrape_with_semaphore(li_inner): # Renamed to avoid outer scope capture issues in loop
                async with self.scrape_semaphore:
                    logger.debug(f"Scrape semaphore acquired for scraping {li_inner['url']}")
                    result = await self._scrape_article_details(li_inner, keywords, self.session)
                    logger.debug(f"Scrape semaphore released for scraping {li_inner['url']}")
                    return result
            scraping_tasks.append(scrape_with_semaphore(link_info))
        
        final_article_results = await asyncio.gather(*scraping_tasks, return_exceptions=True)

        processed_articles: List[Dict[str, Any]] = []
        for i, result in enumerate(final_article_results):
            original_link_url = unique_links_list[i]['url'] # For logging
            if isinstance(result, Exception):
                logger.error(f"Error scraping article details for {original_link_url}: {result}", exc_info=True)
            elif result:
                # Ensure it matches the simplified format: title, body, source
                # The _scrape_article_details already returns more, which is fine.
                # The API route will select the fields.
                # For consistency with previous simplified format, let's ensure these are primary.
                simplified_article = {
                    "title": result.get("title"),
                    "body": result.get("body"),
                    "source": result.get("source"),
                    # Optionally include other fields if needed by client, like "url"
                    "url": result.get("url"), 
                    "published_at": result.get("published_at"), # Will be string or None
                    "image_url": result.get("image_url"),
                    "html_content": result.get("html_content") # Propagate html_content
                }
                processed_articles.append(simplified_article)
        
        logger.info(f"Successfully scraped {len(processed_articles)} articles in total.")
        # The source_page_domain should already be in each article dict from _scrape_article_details
        # No need for the loop here to add it again.

        return processed_articles

    def _write_to_cache(self, cache_file: str, data: Dict[str, Any]) -> None: # Changed data type
        """Write data to cache file with expiration timestamp"""
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cached data to {cache_file}")
        except Exception as e:
            logger.error(f"Error writing to cache {cache_file}: {str(e)}")

    def _read_from_cache(self, cache_file: str) -> Optional[Dict[str, Any]]: # Changed return type
        """Read data from cache if it exists and is not expired"""
        try:
            if not os.path.exists(cache_file):
                return None
                
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            expiration_delta = timedelta(hours=self.cache_expiration_hours)
            
            if datetime.now() > (cache_time + expiration_delta):
                logger.debug(f"Cache expired for {cache_file}")
                os.remove(cache_file) # Remove expired cache file
                return None
                
            return cache_data["data"]
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from cache file {cache_file}: {str(e)}")
            return None # Or delete the corrupt file: os.remove(cache_file)
        except Exception as e:
            logger.error(f"Error reading from cache {cache_file}: {str(e)}")
            return None

    async def execute_scraping_for_session(self, session_id: str, base_workspace_path: str, urls: List[str], keywords: List[str]) -> None:
        """
        Discovers links from initial URLs based on keywords, scrapes them, 
        and saves each scraped article to the session-specific directory.

        Args:
            session_id (str): The unique ID for this analysis session.
            base_workspace_path (str): The root directory for all workspace data.
            urls (List[str]): List of initial URLs to start discovery from.
            keywords (List[str]): List of keywords to filter discovered links and content.
        """
        logger.info(f"Session [{session_id}]: Starting web scraping. Initial URLs: {urls}, Keywords: {keywords}")
        await self._ensure_session()
        if not self.session:
            logger.error(f"Session [{session_id}]: Failed to initialize HTTP session for web scraping.")
            return

        session_scraped_articles_path = os.path.join(base_workspace_path, session_id) # Per spec, directly in session_path
        os.makedirs(session_scraped_articles_path, exist_ok=True)

        # Step 1: Discover links from the initial set of URLs
        all_discovered_links_info: List[Dict[str, str]] = []
        discovery_tasks = []
        for url_to_discover_from in urls:
            async def discover_with_semaphore(u_inner):
                async with self.discover_semaphore:
                    logger.debug(f"Session [{session_id}]: Discovery semaphore acquired for {u_inner}")
                    # Pass session_id for logging within _discover_links_from_page if it were to be refactored for it
                    result = await self._discover_links_from_page(u_inner, keywords, self.session)
                    logger.debug(f"Session [{session_id}]: Discovery semaphore released for {u_inner}")
                    return result
            discovery_tasks.append(discover_with_semaphore(url_to_discover_from))
        
        page_link_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)

        for i, result in enumerate(page_link_results):
            if isinstance(result, Exception):
                logger.error(f"Session [{session_id}]: Error discovering links from {urls[i]} - {result}", exc_info=True)
            elif result:
                all_discovered_links_info.extend(result)
        
        unique_links_to_scrape_map: Dict[str, Dict[str,str]] = {}
        for link_info in all_discovered_links_info:
            if link_info["url"] not in unique_links_to_scrape_map:
                 unique_links_to_scrape_map[link_info["url"]] = link_info
        
        unique_links_list = list(unique_links_to_scrape_map.values())
        logger.info(f"Session [{session_id}]: Total unique relevant links to scrape: {len(unique_links_list)}")

        if not unique_links_list:
            logger.info(f"Session [{session_id}]: No relevant links found to scrape after discovery.")
            await self.close_session() # Close session if no more work
            return

        # Step 2: Scrape the discovered links
        scraping_tasks = []
        for link_info in unique_links_list:
            async def scrape_with_semaphore(li_inner):
                async with self.scrape_semaphore:
                    logger.debug(f"Session [{session_id}]: Scrape semaphore acquired for scraping {li_inner['url']}")
                    # Pass session_id for logging within _scrape_article_details if it were to be refactored for it
                    result = await self._scrape_article_details(li_inner, keywords, self.session)
                    logger.debug(f"Session [{session_id}]: Scrape semaphore released for scraping {li_inner['url']}")
                    return result
            scraping_tasks.append(scrape_with_semaphore(link_info))
        
        scraped_article_results = await asyncio.gather(*scraping_tasks, return_exceptions=True)

        articles_saved_count = 0
        for i, article_data in enumerate(scraped_article_results):
            original_link_url = unique_links_list[i]['url'] # For logging
            if isinstance(article_data, Exception):
                logger.error(f"Session [{session_id}]: Error scraping article details for {original_link_url} - {article_data}", exc_info=True)
                continue
            
            if article_data and article_data.get("body"): # Ensure there's content
                # Generate filename based on domain and path part
                parsed_url = urlparse(article_data["url"])
                domain = parsed_url.netloc
                path_part = parsed_url.path.strip("/").replace("/", "_")
                
                # Sanitize domain and path_part for filename
                sane_domain = secure_filename(domain)
                sane_path_part = secure_filename(path_part if path_part else "index")
                
                # Limit length of path part to avoid overly long filenames
                max_path_len = 100 
                sane_path_part = sane_path_part[:max_path_len]

                filename_base = f"{sane_domain}__{sane_path_part}"
                
                # To ensure uniqueness if multiple articles somehow resolve to the same base filename (e.g. query params differ but path is same)
                # we can append a short hash of the full URL.
                url_hash_suffix = hashlib.md5(article_data["url"].encode()).hexdigest()[:6]
                filename = f"{filename_base}_{url_hash_suffix}.json"
                filepath = os.path.join(session_scraped_articles_path, filename)
                
                try:
                    # Remove html_content before saving if it's not meant to be persisted in the session files
                    # For now, let's assume it's useful for later stages or debugging, so keep it.
                    # If not, add: article_data.pop('html_content', None)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(article_data, f, ensure_ascii=False, indent=2)
                    articles_saved_count += 1
                    logger.debug(f"Session [{session_id}]: Saved scraped article to {filepath}")
                except Exception as e:
                    logger.error(f"Session [{session_id}]: Failed to save scraped article {article_data.get('title')} to {filepath} - {e}")
            elif article_data: # Article data exists but no body, or body is empty
                 logger.warning(f"Session [{session_id}]: Scraped article {original_link_url} but it has no body content. Skipping save.")
            # If article_data is None, _scrape_article_details already logged it.

        logger.info(f"Session [{session_id}]: Web scraping complete. Saved {articles_saved_count} articles to {session_scraped_articles_path}.")
        await self.close_session()


# Example usage (for testing purposes, typically called from elsewhere)
async def main_test():
    scraper = WebScraper(cache_dir="./scraper_cache", cache_expiration_hours=1)
    # Test URLs and keywords
    test_urls = [
        "https://www.hurriyet.com.tr/spor/",
        "https://www.fanatik.com.tr/son-dakika-haberleri"
    ]
    test_keywords = ["Fenerbahçe", "transfer"]

    try:
        scraped_articles = await scraper.scrape_urls(test_urls, test_keywords)
        print(f"Found {len(scraped_articles)} articles:")
        for article in scraped_articles:
            print(f"  Title: {article['title']}")
            print(f"  Source: {article['source']}")
            print(f"  URL: {article.get('url')}") # URL is good to have
            # print(f"  Body: {article['body'][:100]}...")
            print("-" * 20)
    finally:
        await scraper.close_session()

if __name__ == "__main__":
    # Setup basic logging for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # asyncio.run(main_test()) # Python 3.7+
    # For older versions or specific event loop policies:
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_test())
    finally:
        loop.close()
