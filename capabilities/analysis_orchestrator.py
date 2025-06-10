import asyncio
import logging
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from werkzeug.utils import secure_filename

from capabilities.trends_analyzer import TrendsAnalyzer
from capabilities.scraping.web_scraper import WebScraper
from capabilities.news_aggregator import NewsAggregator
from capabilities.ai_summarizer import AISummarizer

# Default constants
DEFAULT_TEAM_IDS = [8650]  # Fenerbahçe
DEFAULT_DOMAINS = []

logger = logging.getLogger(__name__)

class AnalysisOrchestrator:
    def __init__(self, session_id: str, base_workspace_path: str, config):
        """
        Initializes the AnalysisOrchestrator.

        Args:
            session_id (str): The unique ID for this analysis session.
            base_workspace_path (str): The root directory for all workspace data (e.g., 'workspace').
            config (dict): Application configuration, expected to contain API keys, cache_dir, etc.
        """
        self.session_id = session_id
        self.base_workspace_path = base_workspace_path
        self.config = config
        self.session_path = os.path.join(self.base_workspace_path, self.session_id)
        self.status_markers_path = os.path.join(self.session_path, "status_markers")
        self.raw_articles_path = os.path.join(self.session_path, "raw_articles")
        self.processed_articles_path = os.path.join(self.session_path, "processed_articles")
        self.summary_path = os.path.join(self.session_path, "summary")
        self.trends_path = os.path.join(self.session_path, "trends")

        # Initialize capabilities
        self.news_aggregator = NewsAggregator(
            newsapi_key=config.get('NEWSAPI_KEY'),
            worldnewsapi_key=config.get('WORLDNEWSAPI_KEY'),
            gnews_api_key=config.get('GNEWS_API_KEY'),
            cache_dir=config.get('CACHE_DIR', './cache'),
            cache_expiration_hours=config.get('CACHE_EXPIRATION', 1)
        )
        self.web_scraper = WebScraper(
            cache_dir=config.get('CACHE_DIR', './cache'),
            cache_expiration_hours=config.get('CACHE_EXPIRATION', 1)
        )
        self.trends_analyzer = TrendsAnalyzer(
            twitter_api_key=config.get('TWITTER_API_KEY'),
            twitter_api_secret=config.get('TWITTER_API_SECRET'),
            twitter_access_token=config.get('TWITTER_ACCESS_TOKEN'),
            twitter_access_secret=config.get('TWITTER_ACCESS_SECRET'),
            cache_dir=config.get('CACHE_DIR', './cache'),
            cache_expiration_hours=config.get('CACHE_EXPIRATION', 1)
        )
        self._create_session_directories()

    def _create_session_directories(self):
        os.makedirs(self.session_path, exist_ok=True)
        os.makedirs(self.status_markers_path, exist_ok=True)
        os.makedirs(self.raw_articles_path, exist_ok=True)
        os.makedirs(self.processed_articles_path, exist_ok=True)
        os.makedirs(self.summary_path, exist_ok=True)
        os.makedirs(self.trends_path, exist_ok=True)
        logger.info(f"Session directories created for session {self.session_id} at {self.session_path}")

    def _create_status_marker(self, marker_name: str, data: Optional[Dict] = None):
        """Creates a status marker file, optionally with JSON data."""
        marker_file = os.path.join(self.status_markers_path, marker_name)
        try:
            with open(marker_file, 'w') as f:
                if data:
                    json.dump(data, f, indent=2)
                else:
                    f.write("")
            logger.info(f"Status marker '{marker_name}' created for session {self.session_id}.")
        except IOError as e:
            logger.error(f"Failed to create status marker '{marker_name}' for session {self.session_id}: {e}")

    async def run_full_pipeline(self, aggregated_config: Dict):
        """
        Runs the full analysis pipeline: trends -> news aggregation & scraping -> summarization.
        
        Args:
            aggregated_config (Dict): Dictionary containing aggregated parameters from client and search_parameters.json:
                'keywords': List[str] - Combined keywords from client and search_parameters
                'scrape_urls': List[str] - Combined URLs from client and search_parameters
                'time_range': str - Time range (client overrides search_parameters)
                'custom_start_date': Optional[str] - Custom start date if provided
                'custom_end_date': Optional[str] - Custom end date if provided
                'max_results': int - Max results from search_parameters.json only
                'news_sources': List[str] - News sources from search_parameters.json
                'use_default_urls_keywords': bool - Whether to use defaults
        """
        start_time = time.time()
        self._create_status_marker("_JOB_STARTED", {"timestamp": datetime.now().isoformat()})
        logger.info(f"Session [{self.session_id}]: Starting full analysis pipeline.")
        logger.info(f"Session [{self.session_id}]: Aggregated config: {aggregated_config}")

        try:
            # 1. Fetch and Scrape News using aggregated config
            fetched_article_paths, scraped_article_paths = await self._fetch_and_scrape_news(
                session_id=self.session_id,
                aggregated_config=aggregated_config
            )
            self._create_status_marker("_DATA_COLLECTION_COMPLETE", {"timestamp": datetime.now().isoformat(), "fetched_count": len(fetched_article_paths), "scraped_count": len(scraped_article_paths)})

            # 2. Summarize Articles
            logger.info(f"Session [{self.session_id}]: Placeholder for summarization step. Articles to process: {len(fetched_article_paths) + len(scraped_article_paths)}")
            await asyncio.sleep(2)
            summary_output_file = os.path.join(self.summary_path, "final_summary.txt")
            with open(summary_output_file, "w") as f:
                f.write(f"Summary for session {self.session_id} based on {len(fetched_article_paths) + len(scraped_article_paths)} articles.")
            self._create_status_marker("_SUMMARIZATION_COMPLETE", {"timestamp": datetime.now().isoformat(), "summary_file": summary_output_file})            # 3. Finalize Job
            self._create_status_marker("_JOB_SUCCESS", {"timestamp": datetime.now().isoformat(), "duration_seconds": time.time() - start_time})
            logger.info(f"Session [{self.session_id}]: Full analysis pipeline completed successfully in {time.time() - start_time:.2f} seconds.")
            return {"status": "success", "session_id": self.session_id, "summary_file": summary_output_file}
        
        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Error in analysis pipeline: {e}", exc_info=True)
            self._create_status_marker("_JOB_FAILED", {"timestamp": datetime.now().isoformat(), "error": str(e)})
            return {"status": "error", "session_id": self.session_id, "error": str(e)}

    async def _fetch_and_scrape_news(self, session_id: str, aggregated_config: Dict) -> tuple[List[str], List[str]]:
        """Fetches news using NewsAggregator and scrapes specified URLs using aggregated configuration.
        Uses parallel execution with asyncio.create_task(), append, and gather pattern."""
        logger.info(f"Session [{session_id}]: Starting news fetching and scraping.")
        logger.info(f"Session [{session_id}]: Aggregated config for fetch/scrape: {aggregated_config}")

        keywords_for_session = aggregated_config.get('keywords', [])
        scrape_urls_for_session = aggregated_config.get('scrape_urls', [])

        # Configure NewsAggregator with aggregated parameters
        self.news_aggregator.configure(
            team_ids=self.config.get("TEAM_IDS", DEFAULT_TEAM_IDS),
            languages=self.config.get("NEWS_LANGUAGES", ["en"]),
            domains=self.config.get("NEWS_DOMAINS", DEFAULT_DOMAINS),
            max_results=aggregated_config.get('max_results', 10),
            time_range=aggregated_config.get('time_range', 'last_24_hours'),
            custom_start_date=aggregated_config.get('custom_start_date'),
            custom_end_date=aggregated_config.get('custom_end_date')
        )

        # Create tasks for parallel execution
        tasks = []

        # Task 1: News fetching (if keywords provided)
        if keywords_for_session:
            logger.info(f"Session [{session_id}]: Creating news fetching task with keywords: {keywords_for_session}")
            news_fetch_task = asyncio.create_task(
                self.news_aggregator.fetch_news_for_session(
                    session_id=session_id,
                    base_workspace_path=self.base_workspace_path,
                    query=keywords_for_session,
                    sources=aggregated_config.get('news_sources', ['newsapi']),
                    limit=None
                )
            )
            tasks.append(('news_fetch', news_fetch_task))
        else:
            logger.info(f"Session [{session_id}]: No keywords provided for news aggregation.")        # Task 2: Web scraping (if URLs provided)
        if scrape_urls_for_session:
            logger.info(f"Session [{session_id}]: Creating web scraping task for URLs: {scrape_urls_for_session}")
            web_scrape_task = asyncio.create_task(
                self.web_scraper.execute_scraping_for_session(
                    session_id=session_id,
                    keywords=keywords_for_session,
                    sites=scrape_urls_for_session
                )
            )
            tasks.append(('web_scrape', web_scrape_task))
        else:
            logger.info(f"Session [{session_id}]: No URLs provided for scraping.")

        # Execute tasks in parallel if any exist
        fetched_article_paths = []
        scraped_article_paths = []

        if tasks:
            logger.info(f"Session [{session_id}]: Executing {len(tasks)} tasks in parallel: {[task[0] for task in tasks]}")
            # Extract just the task objects for gather
            task_objects = [task[1] for task in tasks]
            results = await asyncio.gather(*task_objects, return_exceptions=True)
              # Process results based on task type
            for i, (task_type, task_obj) in enumerate(tasks):
                result = results[i]
                
                if isinstance(result, Exception):
                    logger.error(f"Session [{session_id}]: Error in {task_type} task: {result}", exc_info=True)
                else:
                    if task_type == 'news_fetch':
                        fetched_article_paths = result if result else []
                        logger.info(f"Session [{session_id}]: News fetching complete. Found {len(fetched_article_paths)} articles.")
                    elif task_type == 'web_scrape':
                        # New modular WebScraper returns session data with articles and metadata
                        scraped_article_paths = []
                        if result and isinstance(result, dict):
                            # Extract articles from the session data
                            articles = result.get('articles', [])
                            
                            # Save each article to the workspace session directory for analysis
                            session_scraped_path = os.path.join(self.base_workspace_path, session_id)
                            os.makedirs(session_scraped_path, exist_ok=True)
                            
                            for i, article in enumerate(articles):
                                # Create a filename for each article
                                article_filename = f"scraped_article_{i+1:03d}.json"
                                article_path = os.path.join(session_scraped_path, article_filename)
                                
                                try:
                                    with open(article_path, 'w', encoding='utf-8') as f:
                                        json.dump(article, f, indent=2, ensure_ascii=False)
                                    scraped_article_paths.append(article_path)
                                except Exception as e:
                                    logger.error(f"Failed to save scraped article to {article_path}: {e}")
                            
                            # Also save the complete session data
                            session_data_path = os.path.join(session_scraped_path, "scraping_session_data.json")
                            try:
                                with open(session_data_path, 'w', encoding='utf-8') as f:
                                    json.dump(result, f, indent=2, ensure_ascii=False)
                            except Exception as e:
                                logger.error(f"Failed to save session data to {session_data_path}: {e}")
                        
                        logger.info(f"Session [{session_id}]: Web scraping complete. Found {len(scraped_article_paths)} scraped articles.")
        else:
            logger.info(f"Session [{session_id}]: No tasks to execute (no keywords or URLs provided).")

        return fetched_article_paths, scraped_article_paths
