"""
API routes for the Turkish Sports News API.
"""

import logging
import time
import asyncio # Added for Quart compatibility if needed, and for running sync in executor
import os # Add this import
import json # Add this import
from datetime import datetime # Add this import
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename # Add this import
from api.models import (
    NewsRequest, NewsResponse, ErrorResponse, NewsArticle, TrendingTopic,
    TrendingRequest, TrendingResponse, NewsSourceEnum # Removed SimpleNewsRequest
)
from capabilities.news_aggregator import NewsAggregator
from capabilities.trends_analyzer import TrendsAnalyzer
from capabilities.web_scraper import WebScraper
from utils.constants import DEFAULT_TEAM_IDS, DEFAULT_DOMAINS
from utils.validators import validate_request_data
from pydantic import ValidationError
from capabilities.analysis_orchestrator import AnalysisOrchestrator # Added
import uuid # Added for session IDs

logger = logging.getLogger(__name__)

# Create API blueprint
api_blueprint = Blueprint('api', __name__)


@api_blueprint.route('/news', methods=['POST'])
async def get_news(): # Changed to async
    """
    Get news articles based on specified parameters
    
    Expected POST body:
    {
        "keywords": ["Fenerbahçe", "Mourinho"], # Can be a list of keywords
        "team_ids": [8650], 
        "languages": ["tr", "en"],
        "domains": ["hurriyet.com.tr"],
        "max_results": 50,
        "time_range": "last_24_hours",
        "sources": ["all"], # or specific like ["newsapi", "fotmob"]
        "include_trends": true,
        "scrape_urls": ["https://www.hurriyet.com.tr/spor/futbol/"]
    }
    """
    start_time = time.time()
      # Get NewsAPI key from app config
    newsapi_key = current_app.config.get('NEWSAPI_KEY')
    if not newsapi_key:
        logger.error("NEWSAPI_KEY is not configured")
        return jsonify(ErrorResponse(
            error="Configuration Error", 
            code=500, 
            details="NewsAPI key is not configured"
        ).dict()), 500
    
    # Parse and validate the request data
    try:
        request_data = request.get_json() or {}
        news_request = NewsRequest(**request_data)
    except ValidationError as e:
        logger.error(f"Invalid request data: {str(e)}")
        return jsonify(ErrorResponse(
            error="Invalid Request", 
            code=400, 
            details=str(e)
        ).dict()), 400
        
    try:
        # Initialize the news aggregator
        news_aggregator = NewsAggregator(
            newsapi_key=newsapi_key,
            worldnewsapi_key=current_app.config.get('WORLDNEWSAPI_KEY'),
            gnews_api_key=current_app.config.get('GNEWS_API_KEY'),
            cache_dir=current_app.config.get('CACHE_DIR'),
            cache_expiration_hours=current_app.config.get('CACHE_EXPIRATION', 1)
        )
        
        # Analyze trends if requested
        trending_topics = []
        if news_request.include_trends:
            trends_analyzer = TrendsAnalyzer(
                twitter_api_key=current_app.config.get('TWITTER_API_KEY'),
                twitter_api_secret=current_app.config.get('TWITTER_API_SECRET'),
                twitter_access_token=current_app.config.get('TWITTER_ACCESS_TOKEN'),
                twitter_access_secret=current_app.config.get('TWITTER_ACCESS_SECRET')
            )
            # Assuming trends_analyzer.get_trending_topics is synchronous
            # If it were async, it would need to be awaited and run in executor if blocking
            trending_topics = trends_analyzer.get_trending_topics(
                keywords=news_request.keywords, 
                location="Turkey"
            )
        
        # Apply trending topics to the keywords if available
        # The news_aggregator.update_keywords is synchronous and fine as is.
        if trending_topics:
            trending_keywords = [topic.name for topic in trending_topics[:5]]
            news_aggregator.update_keywords(trending_keywords)
        
        # Configure news aggregator with request parameters
        # The news_aggregator.configure is synchronous and fine as is.
        news_aggregator.configure(
            default_keywords=news_request.keywords,
            team_ids=news_request.team_ids,
            languages=news_request.languages,
            domains=news_request.domains,
            max_results=news_request.max_results,
            time_range=news_request.time_range,
            custom_start_date=news_request.custom_start_date,
            custom_end_date=news_request.custom_end_date
        )
        
        # Determine sources to use
        sources_to_fetch = news_request.sources
        if NewsSourceEnum.ALL in news_request.sources:
            sources_to_fetch = news_aggregator.get_available_sources()
            # Remove web_scraping if no scrape_urls are provided, as get_news doesn't handle it directly
            if not news_request.scrape_urls and NewsSourceEnum.WEB_SCRAPING in sources_to_fetch:
                sources_to_fetch.remove(NewsSourceEnum.WEB_SCRAPING)
        
        # Get news from specified sources using the main get_news method
        # The `news_request.keywords` are already set as default_keywords in `configure`
        # and `update_keywords` handles additional ones (like from trends).
        # The `get_news` method itself takes a `query` param which can be a list.
        # For the `/news` endpoint, we rely on the configured keywords.
        articles = await news_aggregator.get_news( # await async call
            query=news_request.keywords, # Pass keywords as the query
            sources=[source.value for source in sources_to_fetch if source != NewsSourceEnum.WEB_SCRAPING], # Pass string list
            limit=news_request.max_results
        )
        sources_used = [source.value for source in sources_to_fetch if source != NewsSourceEnum.WEB_SCRAPING]

        # Scrape web sources if requested - this part remains separate as it uses a different capability
        if (NewsSourceEnum.ALL in news_request.sources or NewsSourceEnum.WEB_SCRAPING in news_request.sources) and news_request.scrape_urls:
            web_scraper = WebScraper(cache_dir=current_app.config.get('CACHE_DIR'))
            try: # Added try-finally for session management
                # Assuming web_scraper.scrape_urls is synchronous
                # If it were async, it would need to be awaited and run in executor if blocking
                # scraped_articles = web_scraper.scrape_urls( # Modified to await async call
                #     urls=news_request.scrape_urls,
                #     keywords=news_request.keywords
                # ) # Modified to await async call
                scraped_articles = await web_scraper.scrape_urls( # Modified to await async call
                    urls=news_request.scrape_urls, # Modified to await async call
                    keywords=news_request.keywords # Modified to await async call
                ) # Modified to await async call
                articles.extend(scraped_articles)
                if NewsSourceEnum.WEB_SCRAPING.value not in sources_used:
                    sources_used.append(NewsSourceEnum.WEB_SCRAPING.value)
            finally: # Added try-finally for session management
                await web_scraper.close_session() # Added session close
        
        # Deduplicate and sort articles - these are synchronous methods
        unique_articles = news_aggregator.deduplicate_articles(articles)
        sorted_articles = news_aggregator.sort_articles(unique_articles)
        
        # Prepare response
        # response = NewsResponse(
        #     articles=[NewsArticle(**article) for article in sorted_articles],
        #     trending_topics=trending_topics,
        #     total_count=len(sorted_articles),
        #     sources_used=sources_used,
        #     query_time=time.time() - start_time
        # )
        
        # logger.info(f"Served news request with {len(sorted_articles)} articles from {len(sources_used)} sources")
        # return jsonify(response.dict())
        
        # Simplified response for client
        client_response = []
        for article_data in sorted_articles:
            article = NewsArticle(**article_data) # Ensure it's a Pydantic model for consistent access
            client_response.append({
                "title": article.title,
                "body": article.content, # Using content as body
                "source": article.source # Using source field (e.g., newsapi, gnews, domain)
            })
        
        logger.info(f"Served news request with {len(client_response)} articles from {len(sources_used)} sources")
        return jsonify(client_response)
        
    except Exception as e:
        logger.error(f"Error processing news request: {str(e)}", exc_info=True)
        return jsonify(ErrorResponse(
            error="Processing Error", 
            code=500, 
            details=str(e)
        ).dict()), 500


@api_blueprint.route('/trending', methods=['POST'])
def get_trending():
    """
    Get trending topics related to Turkish sports
    
    POST Body:
    {
        "keywords": ["Turkey", "Fenerbahçe", "football"],
        "location": "Turkey",
        "limit": 10
    }
    """
    try:
        # Parse request data
        data = request.get_json() or {}
        
        # Validate request with Pydantic model
        try:
            trending_request = TrendingRequest(**data)
        except ValidationError as e:
            return jsonify(ErrorResponse(
                error="Validation Error",
                code=400,
                details=str(e)
            ).dict()), 400
        
        trends_analyzer = TrendsAnalyzer(
            twitter_api_key=current_app.config.get('TWITTER_API_KEY'),
            twitter_api_secret=current_app.config.get('TWITTER_API_SECRET'),
            twitter_access_token=current_app.config.get('TWITTER_ACCESS_TOKEN'),
            twitter_access_secret=current_app.config.get('TWITTER_ACCESS_SECRET')
        )
        
        trending_topics = trends_analyzer.get_trending_topics(
            keywords=trending_request.keywords,
            location=trending_request.location,
            count=trending_request.limit
        )
        
        logger.info(f"Served trending topics request with {len(trending_topics)} topics")
        response = TrendingResponse(
            topics=trending_topics,
            count=len(trending_topics),
            location=trending_request.location
        )
        return jsonify(response.dict())
        
    except Exception as e:
        logger.error(f"Error processing trending topics request: {str(e)}", exc_info=True)
        return jsonify(ErrorResponse(
            error="Processing Error", 
            code=500, 
            details=str(e)
        ).dict()), 500


@api_blueprint.route('/scrape', methods=['POST'])
async def scrape_website(): # Changed to async
    """
    Scrape news articles from specified URLs based on keywords
    POST Body:
    {
        "urls": ["https://www.example.com/sports"],
        "keywords": ["Fenerbahçe"]
    }
    """
    try:
        data = request.get_json()
        if not data or 'urls' not in data or 'keywords' not in data:
            return jsonify(ErrorResponse(
                error="Invalid Request", 
                code=400, 
                details="Missing 'urls' or 'keywords' in request body"
            ).dict()), 400
        
        urls = data.get('urls')
        keywords = data.get('keywords')
        
        if not isinstance(urls, list) or not isinstance(keywords, list):
            return jsonify(ErrorResponse(
                error="Invalid Request", 
                code=400, 
                details="'urls' and 'keywords' must be lists"
            ).dict()), 400

        web_scraper = WebScraper(cache_dir=current_app.config.get('CACHE_DIR'))
        scraped_data_list = [] # Initialize list to hold all scraped data
        try: # Added try-finally for session management
            # scraped_articles = web_scraper.scrape_urls(urls, keywords) # Modified to await async call
            scraped_data_list = await web_scraper.scrape_urls(urls, keywords) # Modified to await async call
        finally: # Added try-finally for session management
            await web_scraper.close_session() # Added session close
        
        # Create workspace and save scraped_data
        workspace_dir = os.path.join(current_app.root_path, 'workspace')
        os.makedirs(workspace_dir, exist_ok=True)
        
        timestamp_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        request_specific_dir = os.path.join(workspace_dir, timestamp_id)
        os.makedirs(request_specific_dir, exist_ok=True)
        
        # Prepare data for JSON serialization and save each article to its own file
        serializable_data_list = []
        for item_index, item in enumerate(scraped_data_list):
            s_item = item.copy()
            if isinstance(s_item.get('published_at'), datetime):
                s_item['published_at'] = s_item['published_at'].isoformat()
            serializable_data_list.append(s_item) # Keep this for the client response preparation

            # Create a safe filename from the URL
            article_url = s_item.get("url")
            if article_url:
                # Custom pre-processing: Remove protocol and replace slashes
                processed_url = article_url.replace("https://", "").replace("http://", "")
                processed_url = processed_url.replace("/", "__")
                
                # Secure the filename and add .json extension
                base_filename = secure_filename(processed_url)
                # secure_filename might return an empty string if the input is really bad,
                # or it might be too short. Add a fallback or ensure it's meaningful.
                if not base_filename: # Fallback if secure_filename results in empty
                    base_filename = f"article_{item_index}"
                
                # Ensure filename is not too long (optional, but good practice)
                # secure_filename itself doesn't truncate, so manual truncation might still be desired.
                # However, the previous truncation was arbitrary. Let's rely on secure_filename's safety
                # and typical filesystem limits. If very long URLs are common, truncation might be re-added.
                output_file_path = os.path.join(request_specific_dir, f"{base_filename}.json")
            else:
                # Fallback filename if URL is missing (should ideally not happen)
                output_file_path = os.path.join(request_specific_dir, f"article_{item_index}.json")

            try:
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(s_item, f, ensure_ascii=False, indent=2)
                logger.info(f"Saved article data to {output_file_path}")
            except Exception as e:
                logger.error(f"Error saving article to {output_file_path}: {e}")

        # Simplified response for client (without html_content for brevity in HTTP response)
        client_response = []
        if serializable_data_list: # Ensure scraped_data is not None
            for article_data in serializable_data_list:
                client_response.append({
                    "title": article_data.get("title"),
                    "body": article_data.get("body"), 
                    "source": article_data.get("source"),
                    "url": article_data.get("url"),
                    "published_at": article_data.get("published_at"),
                    "image_url": article_data.get("image_url")
                })
        return jsonify(client_response)
        
    except Exception as e:
        logger.error(f"Error scraping website: {str(e)}", exc_info=True)
        return jsonify(ErrorResponse(
            error="Scraping Error", 
            code=500, 
            details=str(e)
        ).dict()), 500


@api_blueprint.route('/analysis/start_job', methods=['POST'])
async def start_analysis_job():
    """
    Starts a new analysis job.
    Creates a unique session and triggers the analysis pipeline asynchronously.
    
    POST Body (optional):
    {
        "initial_keywords": ["Fenerbahçe", "transfer"],
        "initial_scrape_urls": ["https://www.fanatik.com.tr/fenerbahce"],
        "use_default_urls_keywords": true 
    }
    """
    try:
        session_id = str(uuid.uuid4())
        base_workspace_path = current_app.config.get('WORKSPACE_DIR', os.path.join(current_app.root_path, 'workspace'))
        
        # Ensure base_workspace_path exists
        os.makedirs(base_workspace_path, exist_ok=True)

        request_data = request.get_json(silent=True) or {}
        initial_keywords = request_data.get("initial_keywords")
        initial_scrape_urls = request_data.get("initial_scrape_urls")
        use_default_urls_keywords = request_data.get("use_default_urls_keywords", True)

        # The orchestrator needs the full app config to pass to capabilities
        app_config = current_app.config

        orchestrator = AnalysisOrchestrator(
            session_id=session_id,
            base_workspace_path=base_workspace_path,
            config=app_config # Pass the whole app config
        )

        # Run the pipeline in the background (fire and forget from API perspective)
        # For a more robust solution with task queues (Celery, RQ), this would be different.
        # For now, we use asyncio.create_task for non-blocking execution.
        asyncio.create_task(orchestrator.run_full_pipeline(
            initial_keywords=initial_keywords,
            initial_scrape_urls=initial_scrape_urls,
            use_default_urls_keywords=use_default_urls_keywords
        ))
        
        logger.info(f"Started analysis job with session_id: {session_id}")
        return jsonify({
            "message": "Analysis job started.",
            "session_id": session_id,
            "status_endpoint": f"/api/analysis/job_status/{session_id}"
        }), 202 # Accepted

    except Exception as e:
        logger.error(f"Error starting analysis job: {str(e)}", exc_info=True)
        return jsonify(ErrorResponse(
            error="Job Start Error", 
            code=500, 
            details=str(e)
        ).dict()), 500

@api_blueprint.route('/analysis/job_status/<session_id>', methods=['GET'])
def get_analysis_job_status(session_id: str):
    """
    Gets the status of an analysis job.
    Checks for status marker files in the session directory.
    """
    try:
        base_workspace_path = current_app.config.get('WORKSPACE_DIR', os.path.join(current_app.root_path, 'workspace'))
        session_path = os.path.join(base_workspace_path, secure_filename(session_id)) # Sanitize session_id for path
        status_markers_path = os.path.join(session_path, "status_markers")

        if not os.path.exists(session_path) or not os.path.isdir(session_path):
            return jsonify(ErrorResponse(
                error="Not Found", 
                code=404, 
                details=f"Session ID {session_id} not found."
            ).dict()), 404

        status_info = {
            "session_id": session_id,
            "status": "UNKNOWN",
            "details": "Status markers not found or job not started.",
            "last_update": None,
            "stages_completed": [],
            "error_info": None
        }
        
        # Define the order of markers to determine current status
        # These should match the marker names created by AnalysisOrchestrator
        ordered_markers = [
            "_JOB_STARTED",
            "_TRENDS_COMPLETE",
            "_DATA_COLLECTION_COMPLETE",
            "_SUMMARIZATION_COMPLETE",
            "_JOB_SUCCESS" # Terminal success state
        ]
        
        # Check for failure marker first
        failure_marker_path = os.path.join(status_markers_path, "_JOB_FAILED")
        if os.path.exists(failure_marker_path):
            status_info["status"] = "FAILED"
            try:
                with open(failure_marker_path, 'r') as f:
                    error_content = json.load(f)
                status_info["details"] = "Job failed. See error_info."
                status_info["error_info"] = error_content.get("error", "Unknown error")
                status_info["last_update"] = error_content.get("timestamp", datetime.fromtimestamp(os.path.getmtime(failure_marker_path)).isoformat())
            except Exception as e_read:
                status_info["details"] = f"Job failed. Could not read error details: {e_read}"
                status_info["last_update"] = datetime.fromtimestamp(os.path.getmtime(failure_marker_path)).isoformat()
            return jsonify(status_info)

        # Check for success and other stage markers
        last_found_marker_time = None
        current_stage_index = -1

        for idx, marker_name in enumerate(ordered_markers):
            marker_file = os.path.join(status_markers_path, marker_name)
            if os.path.exists(marker_file):
                status_info["stages_completed"].append(marker_name.replace("_", " ").strip())
                marker_time = datetime.fromtimestamp(os.path.getmtime(marker_file)).isoformat()
                if last_found_marker_time is None or marker_time > last_found_marker_time:
                    last_found_marker_time = marker_time
                    current_stage_index = idx
            else:
                # If a marker is missing, the job is at the stage before it (or the last found one)
                break 
        
        status_info["last_update"] = last_found_marker_time

        if current_stage_index == -1 and not status_info["stages_completed"]: # No markers found at all, but session dir exists
             status_info["status"] = "INITIALIZED"
             status_info["details"] = "Session initialized, job pending start."
             # Check if session_path itself has a creation time we can use
             if os.path.exists(session_path):
                 status_info["last_update"] = datetime.fromtimestamp(os.path.getctime(session_path)).isoformat()

        elif current_stage_index == (len(ordered_markers) - 1): # _JOB_SUCCESS is the last one
            status_info["status"] = "SUCCESS"
            status_info["details"] = "Job completed successfully."
        elif current_stage_index >= 0:
            status_info["status"] = "RUNNING"
            # Details about the current or last completed stage
            last_completed_stage_name = ordered_markers[current_stage_index].replace("_", " ").lower().replace(" complete", "")
            if "job started" in last_completed_stage_name:
                 status_info["details"] = f"Job has started."
            else:
                 status_info["details"] = f"Processing. Last completed stage: {last_completed_stage_name.title()}."
        else: # Should be covered by INITIALIZED or UNKNOWN if no markers found
            pass


        return jsonify(status_info)

    except Exception as e:
        logger.error(f"Error getting job status for session {session_id}: {str(e)}", exc_info=True)
        return jsonify(ErrorResponse(
            error="Status Check Error", 
            code=500, 
            details=str(e)
        ).dict()), 500


@api_blueprint.route('/docs')
def api_docs():
    """API documentation endpoint"""
    return jsonify({
        "name": "Turkish Sports News API Documentation",
        "version": "1.0.0",
        "endpoints": [
            {
                "path": "/api/news",
                "method": "POST",
                "description": "Get news articles based on specified parameters",
                "request_body": NewsRequest().dict(),
                "response": {
                    "articles": [{"title": "Example article", "url": "https://example.com", "source": "Example Source"}],
                    "trending_topics": [{"name": "Example Topic", "tweet_volume": 5000}],
                    "total_count": 1,
                    "sources_used": ["NewsAPI", "FotMob", "WebScraping"],
                    "query_time": 0.5
                }
            },            {
                "path": "/api/trending",
                "method": "POST",
                "description": "Get trending topics related to Turkish sports",
                "request_body": {
                    "keywords": ["Turkey", "Fenerbahçe", "football"],
                    "location": "Turkey",
                    "limit": 10
                }
            },            {
                "path": "/api/scrape",
                "method": "POST",
                "description": "Scrape specified URLs for sports news",
                "request_body": {
                    "urls": ["https://example.com/sports"],
                    "keywords": ["Turkey", "Fenerbahçe"]
                }
            }
        ]
    })

