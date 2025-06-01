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
import threading # Added for threading

logger = logging.getLogger(__name__)

# Create API blueprint
api_blueprint = Blueprint('api', __name__)

# Function to run the orchestrator pipeline in a separate thread
def run_orchestrator_in_thread(app_config, session_id, base_workspace_path, initial_keywords, initial_scrape_urls, use_default_urls_keywords, client_keywords, client_scrape_urls):
    orchestrator = AnalysisOrchestrator(
        session_id=session_id,
        base_workspace_path=base_workspace_path,
        config=app_config
    )
    # Since orchestrator.run_full_pipeline is an async method, we need to run it in an event loop.
    # Each thread needs its own event loop if we are using asyncio.run()
    # However, if the Flask app is already running with an async framework like Quart or using app.run(debug=True) 
    # which might use Werkzeug\'s auto-reloader with its own event loop management,
    # directly calling asyncio.run() in a new thread can sometimes lead to "loop is already running" errors
    # or other event loop conflicts.
    # A common pattern for running an async function from a synchronous thread is:
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # loop.run_until_complete(orchestrator.run_full_pipeline(...))
    # loop.close()
    # For simplicity here, we'll use asyncio.run(), assuming it handles loop creation/closing correctly in a new thread.
    # If issues arise, the more explicit loop management above might be needed.
    try:
        asyncio.run(orchestrator.run_full_pipeline(
            initial_keywords=initial_keywords,
            initial_scrape_urls=initial_scrape_urls,
            use_default_urls_keywords=use_default_urls_keywords,
            client_keywords=client_keywords,
            client_scrape_urls=client_scrape_urls
        ))
    except Exception as e:
        logger.error(f"Exception in orchestrator thread for session {session_id}: {e}", exc_info=True)
        # Optionally, update a global status or a specific file to indicate failure from the thread
        # For now, the orchestrator itself handles creating a _JOB_FAILED marker.


@api_blueprint.route('/analysis/start_job', methods=['POST'])
def start_analysis_job(): # Changed to synchronous
    """
    Starts a new analysis job.
    Creates a unique session and triggers the analysis pipeline in a background thread.
    Returns a 202 Accepted response immediately.
    
    POST Body (optional):
    {
        "client_keywords": ["Fenerbahçe", "transfer"], // Renamed from initial_keywords for clarity
        "client_scrape_urls": ["https://www.fanatik.com.tr/fenerbahce"], // Renamed
        "use_default_urls_keywords": true 
    }
    """
    try:
        # Generate a timestamp-based session ID
        timestamp_session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") # YYYYMMDD_HHMMSS_microseconds
        session_id = timestamp_session_id # Use this as the session_id

        base_workspace_path = current_app.config.get('WORKSPACE_DIR', os.path.join(current_app.root_path, 'workspace'))
        
        os.makedirs(base_workspace_path, exist_ok=True)

        request_data = request.get_json(silent=True) or {}
        client_keywords = request_data.get("client_keywords") # Keywords from client
        client_scrape_urls = request_data.get("client_scrape_urls") # URLs from client
        use_default_urls_keywords = request_data.get("use_default_urls_keywords", True)

        # Load initial keywords and URLs from search_parameters.json
        search_params_keywords = []
        search_params_urls = []
        search_params_path = current_app.config.get('SEARCH_PARAMETERS_PATH', os.path.join(current_app.root_path, 'search_parameters.json'))
        if os.path.exists(search_params_path):
            try:
                with open(search_params_path, 'r', encoding='utf-8') as f:
                    params_data = json.load(f)
                search_params_keywords = params_data.get("keywords", [])
                search_params_urls = params_data.get("scrape_urls", [])
                logger.info(f"Loaded {len(search_params_keywords)} keywords and {len(search_params_urls)} URLs from {search_params_path}")
            except Exception as e:
                logger.error(f"Error loading search_parameters.json: {e}")
        else:
            logger.warning(f"search_parameters.json not found at {search_params_path}. Proceeding without them.")


        app_config = current_app.config.copy() # Pass a copy of the config

        # Start the orchestrator pipeline in a new thread
        thread = threading.Thread(
            target=run_orchestrator_in_thread,
            args=(
                app_config, 
                session_id, 
                base_workspace_path,
                search_params_keywords, # Pass keywords from search_parameters.json
                search_params_urls,     # Pass URLs from search_parameters.json
                use_default_urls_keywords,
                client_keywords,        # Pass keywords from client request
                client_scrape_urls      # Pass URLs from client request
            )
        )
        thread.daemon = True # Allow main program to exit even if threads are running
        thread.start()
        
        logger.info(f"Started analysis job in background thread with session_id: {session_id}")
        return jsonify({
            "message": "Analysis job successfully started in the background.",
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

