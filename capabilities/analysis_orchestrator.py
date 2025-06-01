
import asyncio
import logging
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename # For consistent filename sanitization

from capabilities.trends_analyzer import TrendsAnalyzer
from capabilities.web_scraper import WebScraper
from capabilities.news_aggregator import NewsAggregator
from capabilities.ai_summarizer import AISummarizer # Assuming this path is correct

logger = logging.getLogger(__name__)

class AnalysisOrchestrator:
    def __init__(self, session_id: str, base_workspace_path: str, config: dict):
        """
        Initializes the AnalysisOrchestrator.

        Args:
            session_id (str): The unique ID for this analysis session.
            base_workspace_path (str): The root directory for all workspace data (e.g., 'workspace').
            config (dict): Application configuration, expected to contain API keys, cache_dir, etc.
        """
        self.session_id = session_id
        self.base_workspace_path = base_workspace_path
        self.session_path = os.path.join(self.base_workspace_path, self.session_id)
        self.raw_articles_path = os.path.join(self.session_path, "raw_articles") # For NewsAggregator
        self.scraped_articles_path = self.session_path # WebScraper saves directly to session_path
        self.summaries_path = os.path.join(self.session_path, "summaries")
        self.status_markers_path = os.path.join(self.session_path, "status_markers")
        self.config = config

        # Ensure all necessary directories exist
        os.makedirs(self.session_path, exist_ok=True)
        os.makedirs(self.raw_articles_path, exist_ok=True)
        os.makedirs(self.summaries_path, exist_ok=True)
        os.makedirs(self.status_markers_path, exist_ok=True)

    def _create_status_marker(self, marker_name: str, content: dict = None):
        """Creates a status marker file."""
        try:
            with open(os.path.join(self.status_markers_path, marker_name), 'w') as f:
                if content:
                    json.dump(content, f, indent=2)
                else:
                    f.write(datetime.now().isoformat())
            logger.info(f"Session [{self.session_id}]: Created status marker - {marker_name}")
        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Failed to create status marker {marker_name} - {e}")

    async def run_full_pipeline(self, initial_keywords: list = None, initial_scrape_urls: list = None, use_default_urls_keywords: bool = True):
        """Runs the full analysis pipeline.
        Args:
            initial_keywords (list, optional): Keywords from the initial request.
            initial_scrape_urls (list, optional): URLs to scrape from the initial request.
            use_default_urls_keywords (bool): Whether to use default keywords/URLs if initial ones are not provided.
        """
        self._create_status_marker("_JOB_STARTED")
        logger.info(f"Session [{self.session_id}]: Pipeline started.")

        try:
            # Step 1: Gather Trends
            trending_keywords = await self._gather_trends(initial_keywords or [])
            self._create_status_marker("_TRENDS_COMPLETE")

            # Step 2: Fetch and Scrape News (Parallel Execution)
            all_keywords = list(set((initial_keywords or []) + trending_keywords))
            if not all_keywords and use_default_urls_keywords:
                # Define your default keywords if needed, or rely on capability defaults
                all_keywords = self.config.get("DEFAULT_KEYWORDS", ["Fenerbahçe", "Galatasaray", "Beşiktaş", "Trabzonspor", "football", "transfer"])
            
            urls_to_scrape = initial_scrape_urls or []
            if not urls_to_scrape and use_default_urls_keywords:
                urls_to_scrape = self.config.get("DEFAULT_SCRAPE_URLS", [
                    "https://www.fanatik.com.tr/son-dakika-haberleri",
                    "https://www.hurriyet.com.tr/spor/",
                    "https://www.fotomac.com.tr/son-dakika-haberleri"
                ])

            await self._fetch_and_scrape_news(all_keywords, urls_to_scrape)
            self._create_status_marker("_DATA_COLLECTION_COMPLETE")

            # Step 3: AI Summarization
            await self._summarize_articles()
            self._create_status_marker("_SUMMARIZATION_COMPLETE")

            self._create_status_marker("_JOB_SUCCESS")
            logger.info(f"Session [{self.session_id}]: Pipeline completed successfully.")

        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Pipeline failed - {e}", exc_info=True)
            self._create_status_marker("_JOB_FAILED", content={"error": str(e), "details": "Check logs for more info."})

    async def _gather_trends(self, base_keywords: list) -> list:
        logger.info(f"Session [{self.session_id}]: Gathering trends.")
        try:
            trends_analyzer = TrendsAnalyzer(
                twitter_api_key=self.config.get('TWITTER_API_KEY'),
                twitter_api_secret=self.config.get('TWITTER_API_SECRET'),
                twitter_access_token=self.config.get('TWITTER_ACCESS_TOKEN'),
                twitter_access_secret=self.config.get('TWITTER_ACCESS_SECRET')
            )
            # Location can be made configurable
            trending_topics_objects = trends_analyzer.get_trending_topics(keywords=base_keywords, location="Turkey", count=10)
            trending_keywords = [topic.name for topic in trending_topics_objects]
            
            with open(os.path.join(self.session_path, "trending_keywords.json"), 'w', encoding='utf-8') as f:
                json.dump(trending_keywords, f, ensure_ascii=False, indent=2)
            logger.info(f"Session [{self.session_id}]: Found trending keywords: {trending_keywords}")
            return trending_keywords
        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Error gathering trends - {e}", exc_info=True)
            return [] # Return empty list on error but don't fail the whole pipeline yet

    async def _fetch_and_scrape_news(self, keywords: list, urls_to_scrape: list):
        logger.info(f"Session [{self.session_id}]: Fetching and scraping news.")
        
        # Task A: WebScraper
        scraper_task = None
        if urls_to_scrape:
            web_scraper = WebScraper(cache_dir=self.config.get('CACHE_DIR'))
            # Assuming execute_scraping_for_session is the new refactored method
            scraper_task = web_scraper.execute_scraping_for_session(
                session_id=self.session_id,
                base_workspace_path=self.base_workspace_path,
                urls=urls_to_scrape,
                keywords=keywords
            )
        else:
            logger.info(f"Session [{self.session_id}]: No URLs provided for scraping, skipping WebScraper task.")

        # Task B: NewsAggregator
        aggregator_task = None
        if keywords: # Only run aggregator if there are keywords
            news_aggregator = NewsAggregator(
                newsapi_key=self.config.get('NEWSAPI_KEY'),
                worldnewsapi_key=self.config.get('WORLDNEWSAPI_KEY'),
                gnews_api_key=self.config.get('GNEWS_API_KEY'),
                cache_dir=self.config.get('CACHE_DIR'),
                cache_expiration_hours=self.config.get('CACHE_EXPIRATION', 1)
            )
            # Assuming fetch_news_for_session is the new refactored method
            # Sources can be made configurable
            aggregator_task = news_aggregator.fetch_news_for_session(
                session_id=self.session_id,
                base_workspace_path=self.base_workspace_path,
                query=keywords,
                sources=self.config.get("AGGREGATOR_SOURCES", ["newsapi", "gnews"]), # Example default
                limit=self.config.get("AGGREGATOR_LIMIT_PER_SOURCE", 10)
            )
        else:
            logger.info(f"Session [{self.session_id}]: No keywords provided for aggregation, skipping NewsAggregator task.")

        tasks_to_run = []
        if scraper_task: tasks_to_run.append(scraper_task)
        if aggregator_task: tasks_to_run.append(aggregator_task)

        if tasks_to_run:
            results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_name = "WebScraper" if tasks_to_run[i] == scraper_task else "NewsAggregator"
                    logger.error(f"Session [{self.session_id}]: Error in {task_name} task - {result}", exc_info=result)
                    # Decide if this should fail the whole pipeline or just log and continue
        else:
            logger.info(f"Session [{self.session_id}]: No data collection tasks were run.")
        logger.info(f"Session [{self.session_id}]: Data collection phase complete.")

    async def _summarize_articles(self):
        logger.info(f"Session [{self.session_id}]: Starting article summarization.")
        ai_summarizer = AISummarizer(llm_config=self.config.get("LLM_CONFIG")) # Pass LLM config from main app config

        article_files_to_process = []
        # Collect from WebScraper output (directly in session_path)
        for filename in os.listdir(self.scraped_articles_path):
            if filename.endswith(".json") and not filename.startswith(("trending_keywords", "summary_")):
                 # Avoid summarizing already summarized files or keyword files
                if not os.path.isdir(os.path.join(self.scraped_articles_path, filename)):
                    article_files_to_process.append(os.path.join(self.scraped_articles_path, filename))
        
        # Collect from NewsAggregator output (in raw_articles_path)
        for filename in os.listdir(self.raw_articles_path):
            if filename.endswith(".json"):
                article_files_to_process.append(os.path.join(self.raw_articles_path, filename))
        
        unique_article_files = list(set(article_files_to_process)) # Deduplicate if any overlap (shouldn't be)
        logger.info(f"Session [{self.session_id}]: Found {len(unique_article_files)} unique articles to summarize.")

        if not unique_article_files:
            logger.info(f"Session [{self.session_id}]: No articles found to summarize.")
            return

        for article_filepath in unique_article_files:
            try:
                with open(article_filepath, 'r', encoding='utf-8') as f:
                    article_data = json.load(f)
                
                title = article_data.get("title")
                body = article_data.get("body") or article_data.get("content") # Check for 'content' too
                url = article_data.get("url")

                if not title or not body:
                    logger.warning(f"Session [{self.session_id}]: Skipping summarization for {article_filepath} due to missing title or body.")
                    continue

                # Per-article summarization call
                summary_data = await ai_summarizer.summarize_article(title, body, url)
                
                # Save the summary
                original_filename_base = os.path.splitext(os.path.basename(article_filepath))[0]
                summary_filename = f"{original_filename_base}_summary.json"
                summary_output_path = os.path.join(self.summaries_path, summary_filename)
                
                with open(summary_output_path, 'w', encoding='utf-8') as f_sum:
                    json.dump(summary_data, f_sum, ensure_ascii=False, indent=2)
                logger.info(f"Session [{self.session_id}]: Saved summary for {original_filename_base} to {summary_output_path}")

            except Exception as e:
                logger.error(f"Session [{self.session_id}]: Failed to process or summarize article {article_filepath} - {e}", exc_info=True)
                # Optionally, save an error summary for this article
                error_summary_filename = f"{os.path.splitext(os.path.basename(article_filepath))[0]}_summary_error.json"
                with open(os.path.join(self.summaries_path, error_summary_filename), 'w', encoding='utf-8') as f_err:
                    json.dump({"original_filepath": article_filepath, "error": str(e)}, f_err, indent=2)
        
        logger.info(f"Session [{self.session_id}]: Article summarization phase complete.")

# Example of how this might be called (for testing, not part of the class itself)
async def main_orchestrator_test():
    # This is a mock config. In your app, this would come from Flask's current_app.config
    mock_config = {
        "NEWSAPI_KEY": os.getenv("NEWSAPI_KEY"),
        "WORLDNEWSAPI_KEY": os.getenv("WORLDNEWSAPI_KEY"),
        "GNEWS_API_KEY": os.getenv("GNEWS_API_KEY"),
        "TWITTER_API_KEY": os.getenv("TWITTER_API_KEY"),
        "TWITTER_API_SECRET": os.getenv("TWITTER_API_SECRET"),
        "TWITTER_ACCESS_TOKEN": os.getenv("TWITTER_ACCESS_TOKEN"),
        "TWITTER_ACCESS_SECRET": os.getenv("TWITTER_ACCESS_SECRET"),
        "CACHE_DIR": "./cache",
        "CACHE_EXPIRATION": 1,
        "WORKSPACE_DIR": "./workspace", # Orchestrator will use this as base_workspace_path
        "DEFAULT_KEYWORDS": ["Fenerbahçe", "transfer"],
        "DEFAULT_SCRAPE_URLS": ["https://www.fanatik.com.tr/fenerbahce"],
        "AGGREGATOR_SOURCES": ["newsapi"], # Keep it minimal for testing
        "AGGREGATOR_LIMIT_PER_SOURCE": 2,
        "LLM_CONFIG": { # LLM config for AISummarizer
            "config_list": [
                {
                    "base_url": os.getenv("AZURE_OPENAI_ENDPOINT"),
                    "model": os.getenv("MODEL_NAME"), # Your Azure OpenAI deployment name
                    "api_key": os.getenv("AZURE_OPENAI_KEY"),
                    "api_type": "azure",
                    "api_version": "2024-02-15-preview",
                }
            ],
            "temperature": 0.2,
            "timeout": 120,
            "cache_seed": None
        }
    }

    # Ensure environment variables are loaded if using .env for local testing
    # from dotenv import load_dotenv, find_dotenv
    # load_dotenv(find_dotenv())

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    test_session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # The base_workspace_path for the orchestrator is where 'session_id' folders will be created.
    # So, if WORKSPACE_DIR from config is './workspace', orchestrator gets './workspace'.
    orchestrator = AnalysisOrchestrator(session_id=test_session_id, 
                                        base_workspace_path=mock_config["WORKSPACE_DIR"],
                                        config=mock_config)
    
    # Check if LLM is configured for summarizer, otherwise skip test if it would fail
    if not mock_config.get("LLM_CONFIG") or not mock_config["LLM_CONFIG"].get("config_list") or \
       not mock_config["LLM_CONFIG"]["config_list"][0].get("api_key"):
        logger.warning("Azure OpenAI API key or endpoint for summarization is not configured in mock_config. Pipeline test might not fully run summarization.")
        # You might choose to exit or run a limited test

    await orchestrator.run_full_pipeline(
        initial_keywords=["Galatasaray"],
        initial_scrape_urls=["https://www.fotomac.com.tr/galatasaray"],
        use_default_urls_keywords=False
    )

if __name__ == "__main__":
    # This test requires various API keys and Azure OpenAI details to be set as environment variables.
    # Ensure you have a .env file in your project root with these variables for local testing,
    # and uncomment dotenv loading lines if needed.
    asyncio.run(main_orchestrator_test())
