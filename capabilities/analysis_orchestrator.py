import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List # Add List import
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
            # Ensure content includes a timestamp if provided, or add one
            if content and isinstance(content, dict):
                content.setdefault("timestamp", datetime.now().isoformat())
            elif not content:
                content = {"timestamp": datetime.now().isoformat()}
            
            with open(os.path.join(self.status_markers_path, marker_name), 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            logger.info(f"Session [{self.session_id}]: Created status marker - {marker_name} with content: {content}")
        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Failed to create status marker {marker_name} - {e}")

    async def run_full_pipeline(self, 
                                initial_keywords_from_search_params: List[str] = None, 
                                initial_scrape_urls_from_search_params: List[str] = None, 
                                client_provided_keywords: List[str] = None, 
                                client_provided_scrape_urls: List[str] = None,
                                use_config_defaults_as_fallback: bool = True, # This param is now less directly used
                                client_time_range: str = None, # Added from routes
                                client_custom_start_date: str = None, # Added from routes
                                client_custom_end_date: str = None, # Added from routes
                                news_aggregator_config_from_search_params: dict = None): # Added from routes
        """Runs the full analysis pipeline.
        Args:
            initial_keywords_from_search_params (List[str], optional): Keywords from search_parameters.json.
            initial_scrape_urls_from_search_params (List[str], optional): URLs from search_parameters.json.
            client_provided_keywords (List[str], optional): Keywords from the client's API request.
            client_provided_scrape_urls (List[str], optional): URLs to scrape from the client's API request.
            use_config_defaults_as_fallback (bool): Client flag, its direct utility is reduced.
            client_time_range (str, optional): Time range from client.
            client_custom_start_date (str, optional): Custom start date from client.
            client_custom_end_date (str, optional): Custom end date from client.
            news_aggregator_config_from_search_params (dict, optional): Config for NewsAggregator from search_parameters.json.
        """
        self._create_status_marker("_JOB_STARTED")
        logger.info(f"Session [{self.session_id}]: Pipeline started.")

        try:
            # 1. Consolidate keywords and URLs from search_parameters.json and client request
            aggregated_keywords = set(initial_keywords_from_search_params or [])
            if client_provided_keywords:
                aggregated_keywords.update(client_provided_keywords)
            
            aggregated_scrape_urls = set(initial_scrape_urls_from_search_params or [])
            if client_provided_scrape_urls:
                aggregated_scrape_urls.update(client_provided_scrape_urls)

            logger.info(f"Session [{self.session_id}]: Keywords from (search_params + client_request): {list(aggregated_keywords)}")
            logger.info(f"Session [{self.session_id}]: Scrape URLs from (search_params + client_request): {list(aggregated_scrape_urls)}")

            # 2. Fetch general trending keywords
            logger.info(f"Session [{self.session_id}]: Attempting to gather general trending keywords.")
            # No longer pass aggregated_keywords, _gather_trends is now independent
            trending_keywords_fetched = await self._gather_trends() 
            self._create_status_marker(
                "_TRENDS_COMPLETE", 
                content={
                    "trends_found": trending_keywords_fetched, 
                    "details": "Fetched general trends." if trending_keywords_fetched else "No general trends found or trend gathering skipped/failed."
                }
            )

            # 3. Combine all keyword sources: search_params + client_request + trends
            final_processing_keywords = set(aggregated_keywords)
            final_processing_keywords.update(trending_keywords_fetched)

            # At this point, final_scrape_urls are simply aggregated_scrape_urls
            final_processing_scrape_urls = set(aggregated_scrape_urls)

            logger.info(f"Session [{self.session_id}]: Final keywords for processing (after trends): {list(final_processing_keywords)}")
            logger.info(f"Session [{self.session_id}]: Final scrape URLs for processing: {list(final_processing_scrape_urls)}")

            # 4. CRUCIAL EXIT CONDITION:
            # If both final keywords AND final scrape URLs are empty, log and exit.
            if not final_processing_keywords and not final_processing_scrape_urls:
                message = f"Session [{self.session_id}]: No keywords and no URLs to process after aggregation and trend analysis. Pipeline exiting gracefully."
                logger.warning(message)
                self._create_status_marker("_JOB_HALTED_NO_INPUT", content={"reason": message})
                self._create_status_marker("_JOB_SUCCESS", content={"status": "Completed", "details": "No keywords or URLs to process."})
                return # Exit the pipeline

            logger.info(f"Session [{self.session_id}]: Keywords for data collection (NewsAggregator, WebScraper): {list(final_processing_keywords)}")
            logger.info(f"Session [{self.session_id}]: URLs for WebScraper: {list(final_processing_scrape_urls)}")

            # Define a list to hold tasks for concurrent execution
            pipeline_execution_tasks = []

            # Create a task for data collection
            # This task will execute _fetch_and_scrape_news
            data_collection_task = asyncio.create_task(
                self._fetch_and_scrape_news(
                    keywords=list(final_processing_keywords), 
                    urls_to_scrape=list(final_processing_scrape_urls),
                    client_time_range=client_time_range,
                    client_custom_start_date=client_custom_start_date,
                    client_custom_end_date=client_custom_end_date,
                    news_aggregator_config_from_search_params=news_aggregator_config_from_search_params
                )
            )
            pipeline_execution_tasks.append(data_collection_task)

            # Define a dependent coroutine for summarization that waits for data collection
            async def _dependent_summarization_coro(dc_task_future):
                # Await the result of the data collection task (which is a list of paths)
                collected_articles_paths = await dc_task_future
                
                # Create status marker for data collection completion
                self._create_status_marker(
                    "_DATA_COLLECTION_COMPLETE",
                    content={
                        "collected_files_count": len(collected_articles_paths),
                        "sample_paths": collected_articles_paths[:5] # Safe slice, empty list if no paths
                    }
                )

                # Proceed with bulk summarization using the collected paths
                await self._summarize_collected_articles_bulk(collected_articles_paths)
                
                # Create status marker for summarization completion
                self._create_status_marker("_SUMMARIZATION_COMPLETE")

            # Create a task for the dependent summarization, passing the data_collection_task (future)
            summarization_task = asyncio.create_task(
                _dependent_summarization_coro(data_collection_task)
            )
            pipeline_execution_tasks.append(summarization_task)

            # Run data collection and subsequent summarization tasks concurrently using gather
            # Note: _dependent_summarization_coro will internally wait for data_collection_task
            await asyncio.gather(*pipeline_execution_tasks)

            self._create_status_marker("_JOB_SUCCESS")
            logger.info(f"Session [{self.session_id}]: Pipeline completed successfully.")

        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Pipeline failed - {e}", exc_info=True)
            self._create_status_marker("_JOB_FAILED", content={"error": str(e), "details": "Check logs for more info."})

    async def _gather_trends(self) -> list: # Removed base_keywords parameter
        logger.info(f"Session [{self.session_id}]: Gathering general trends.")
        # Removed: if not base_keywords: block, as it's now fetching general trends

        try:
            # Make location and count configurable
            location = self.config.get("TRENDS_GENERAL_LOCATION", "Turkey")
            count = self.config.get("TRENDS_GENERAL_COUNT", 10)
            
            # Check if essential Twitter API configuration is present
            # If any key is missing, log and return empty list to avoid API errors with partial/dummy keys.
            required_twitter_keys = ['TWITTER_API_KEY', 'TWITTER_API_SECRET', 'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_SECRET']
            if not all(self.config.get(key) for key in required_twitter_keys):
                logger.warning(f"Session [{self.session_id}]: Twitter API configuration is incomplete. Skipping trend gathering.")
                return []

            trends_analyzer = TrendsAnalyzer(
                twitter_api_key=self.config.get('TWITTER_API_KEY'),
                twitter_api_secret=self.config.get('TWITTER_API_SECRET'),
                twitter_access_token=self.config.get('TWITTER_ACCESS_TOKEN'),
                twitter_access_secret=self.config.get('TWITTER_ACCESS_SECRET')
            )
            
            # Call get_trending_topics with an empty list for keywords to fetch general trends for the location.
            # This assumes TrendsAnalyzer handles keywords=[] or keywords=None for general trends.
            logger.info(f"Session [{self.session_id}]: Fetching general trends for location '{location}' with count {count}.")
            trending_topics_objects = trends_analyzer.get_trending_topics(keywords=[], location=location, count=count)
            trending_keywords = [topic.name for topic in trending_topics_objects]
            
            # Save the fetched general trends
            trending_keywords_filepath = os.path.join(self.session_path, "trending_keywords.json")
            with open(trending_keywords_filepath, 'w', encoding='utf-8') as f:
                json.dump(trending_keywords, f, ensure_ascii=False, indent=2)
            logger.info(f"Session [{self.session_id}]: Found general trending keywords: {trending_keywords}. Saved to {trending_keywords_filepath}")
            return trending_keywords
        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Error gathering general trends - {e}", exc_info=True)
            # Ensure an empty list is returned on any error (e.g., API key issue, network error)
            return []

    async def _fetch_and_scrape_news(self, 
                                     keywords: list, 
                                     urls_to_scrape: list,
                                     client_time_range: str = None,
                                     client_custom_start_date: str = None,
                                     client_custom_end_date: str = None,
                                     news_aggregator_config_from_search_params: dict = None):
        logger.info(f"Session [{self.session_id}]: Fetching and scraping news. Keywords: {keywords}, URLs: {urls_to_scrape}")
        
        active_tasks_with_names = [] # Stores tuples of (asyncio.Task, task_name_str)

        # Task A: WebScraper
        if urls_to_scrape:
            web_scraper = WebScraper(cache_dir=self.config.get('CACHE_DIR'))
            scraper_coro = web_scraper.execute_scraping_for_session(
                session_id=self.session_id,
                base_workspace_path=self.base_workspace_path,
                urls=urls_to_scrape,
                keywords=keywords
            )
            scraper_task_obj = asyncio.create_task(scraper_coro)
            active_tasks_with_names.append((scraper_task_obj, "WebScraper"))
        else:
            logger.info(f"Session [{self.session_id}]: No URLs provided for scraping, skipping WebScraper task.")

        # Task B: NewsAggregator
        if keywords: # Only run aggregator if there are keywords
            news_aggregator = NewsAggregator(
                newsapi_key=self.config.get('NEWSAPI_KEY'),
                worldnewsapi_key=self.config.get('WORLDNEWSAPI_KEY'),
                gnews_api_key=self.config.get('GNEWS_API_KEY'),
                cache_dir=self.config.get('CACHE_DIR'),
                cache_expiration_hours=self.config.get('CACHE_EXPIRATION', 1)
            )

            # Configure NewsAggregator with parameters (client > search_params > news_aggregator_default)
            # Time range configuration
            time_range_to_set = client_time_range # Highest priority: client
            custom_start_to_set = client_custom_start_date
            custom_end_to_set = client_custom_end_date

            if not time_range_to_set and news_aggregator_config_from_search_params:
                time_range_to_set = news_aggregator_config_from_search_params.get('time_range') # Second priority: search_parameters.json
            
            # Max results configuration
            max_results_to_set = None
            if news_aggregator_config_from_search_params and news_aggregator_config_from_search_params.get('max_results_news') is not None:
                max_results_to_set = news_aggregator_config_from_search_params.get('max_results_news')
                logger.info(f"Session [{self.session_id}]: Using 'max_results_news' from search_parameters.json: {max_results_to_set}")
            elif self.config.get("AGGREGATOR_LIMIT_PER_SOURCE") is not None:
                max_results_to_set = self.config.get("AGGREGATOR_LIMIT_PER_SOURCE")
                logger.info(f"Session [{self.session_id}]: Using 'AGGREGATOR_LIMIT_PER_SOURCE' from app config: {max_results_to_set}")
            else:
                # Critical: No max_results defined in search_parameters.json or app config.
                error_message = f"Session [{self.session_id}]: NewsAggregator 'max_results_news' is not defined in search_parameters.json and 'AGGREGATOR_LIMIT_PER_SOURCE' is not in app config. Cannot proceed with news aggregation."
                logger.error(error_message)
                # Option 1: Raise an exception to halt this part or the pipeline
                raise ValueError(error_message)
                # Option 2: Skip NewsAggregator task (if preferred, but user asked to fail)
                # logger.warning(f"Session [{self.session_id}]: Skipping NewsAggregator task due to missing max_results configuration.")
                # aggregator_task_obj = None # Ensure it's None so it's not added to tasks

            # Ensure max_results_to_set is an integer if it was found
            if max_results_to_set is not None:
                try:
                    max_results_to_set = int(max_results_to_set)
                except ValueError:
                    error_message = f"Session [{self.session_id}]: Invalid non-integer value for max_results: {max_results_to_set}."
                    logger.error(error_message)
                    raise ValueError(error_message)
            
            # Client-provided max_results (if we add it to AnalysisRequest later) would have higher priority here.

            news_aggregator.configure(
                time_range=time_range_to_set,
                custom_start_date=custom_start_to_set,
                custom_end_date=custom_end_to_set,
                max_results=max_results_to_set # Pass the determined max_results
            )

            aggregator_coro = news_aggregator.fetch_news_for_session(
                session_id=self.session_id,
                base_workspace_path=self.base_workspace_path,
                query=keywords,
                sources=self.config.get("AGGREGATOR_SOURCES", ["newsapi", "gnews"]), 
                limit=self.config.get("AGGREGATOR_LIMIT_PER_SOURCE", 10)
            )
            aggregator_task_obj = asyncio.create_task(aggregator_coro)
            active_tasks_with_names.append((aggregator_task_obj, "NewsAggregator"))
        else:
            logger.info(f"Session [{self.session_id}]: No keywords provided for aggregation, skipping NewsAggregator task.")

        if active_tasks_with_names:
            tasks_for_gather = [t[0] for t in active_tasks_with_names]
            results = await asyncio.gather(*tasks_for_gather, return_exceptions=True)
            
            for i, result in enumerate(results):
                task_name = active_tasks_with_names[i][1] # Get the name corresponding to the result
                if isinstance(result, Exception):
                    logger.error(f"Session [{self.session_id}]: Error in {task_name} task - {result}", exc_info=result)
                    # Decide if this should fail the whole pipeline or just log and continue
        else:
            logger.info(f"Session [{self.session_id}]: No data collection tasks were run.")
        logger.info(f"Session [{self.session_id}]: Data collection phase complete.")
        # Return the paths of all successfully created article files (from both scraper and aggregator)
        all_created_article_files = []
        if isinstance(results, list):
            for res_item in results: # results from gather is a list of return values from tasks
                if isinstance(res_item, list): # If a task returned a list of paths
                    all_created_article_files.extend(res_item)
                elif isinstance(res_item, str) and os.path.isfile(res_item): # If a task returned a single valid path
                    all_created_article_files.append(res_item)
                # Ignore exceptions or other types in results for path collection, they are logged already
        
        # Deduplicate and ensure they are actual files
        valid_files = [f for f in list(set(all_created_article_files)) if isinstance(f, str) and os.path.isfile(f)]
        logger.info(f"Session [{self.session_id}]: Total unique article files collected: {len(valid_files)}")
        return valid_files

    async def _summarize_collected_articles_bulk(self, article_filepaths: List[str]):
        logger.info(f"Session [{self.session_id}]: Starting BULK article summarization for {len(article_filepaths)} articles.")
        if not article_filepaths:
            logger.info(f"Session [{self.session_id}]: No article file paths provided for bulk summarization.")
            return

        ai_summarizer = AISummarizer(google_api_key=self.config.get("GOOGLE_API_KEY"))
        if not ai_summarizer.model: # Check if summarizer initialized correctly
            logger.error(f"Session [{self.session_id}]: AISummarizer could not be initialized. Skipping bulk summarization.")
            return

        articles_content_for_bulk = []
        for article_filepath in article_filepaths:
            try:
                with open(article_filepath, 'r', encoding='utf-8') as f:
                    article_data = json.load(f)
                
                title = article_data.get("title")
                body = article_data.get("body") or article_data.get("content")
                url = article_data.get("url")

                if not title or not body:
                    logger.warning(f"Session [{self.session_id}]: Skipping article {article_filepath} in bulk summarization due to missing title or body.")
                    continue
                articles_content_for_bulk.append({"title": title, "body": body, "url": url})
            except Exception as e:
                logger.error(f"Session [{self.session_id}]: Failed to read or parse article {article_filepath} for bulk summarization - {e}", exc_info=True)
        
        if not articles_content_for_bulk:
            logger.info(f"Session [{self.session_id}]: No valid articles found to include in bulk summary after processing file paths.")
            return

        logger.info(f"Session [{self.session_id}]: Sending {len(articles_content_for_bulk)} articles for bulk summarization.")
        
        try:
            bulk_summary_data = await ai_summarizer.summarize_bulk_articles_content(articles_content_for_bulk, session_id=self.session_id)
            
            summary_filename = f"summary_bulk_{self.session_id}.json"
            summary_output_path = os.path.join(self.summaries_path, summary_filename)
            
            with open(summary_output_path, 'w', encoding='utf-8') as f_sum:
                json.dump(bulk_summary_data, f_sum, ensure_ascii=False, indent=2)
            logger.info(f"Session [{self.session_id}]: Saved bulk summary to {summary_output_path}")

        except Exception as e:
            logger.error(f"Session [{self.session_id}]: Failed to generate or save bulk summary - {e}", exc_info=True)
            error_summary_filename = f"summary_bulk_{self.session_id}_error.json"
            with open(os.path.join(self.summaries_path, error_summary_filename), 'w', encoding='utf-8') as f_err:
                json.dump({"session_id": self.session_id, "error": str(e), "details": "Bulk summarization failed." }, f_err, indent=2)
        
        logger.info(f"Session [{self.session_id}]: Bulk article summarization phase complete.")


    async def _summarize_articles(self):
        logger.info(f"Session [{self.session_id}]: Starting article summarization. [DEPRECATED - Use _summarize_collected_articles_bulk]")
        # Initialize AISummarizer with Google API Key from config
        ai_summarizer = AISummarizer(google_api_key=self.config.get("GOOGLE_API_KEY"))

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
