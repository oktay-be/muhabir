"""
API routes for the Turkish Sports News API.
"""

import logging
import time
import asyncio # Added for Quart compatibility if needed, and for running sync in executor
import os # Add this import
import json # Add this import
from datetime import datetime # Add this import
from flask import Blueprint, jsonify, request, current_app, url_for
from werkzeug.utils import secure_filename # Add this import
from api.models import (
    NewsRequest, NewsResponse, ErrorResponse, TrendingRequest, TrendingTopic, NewsArticle, 
    TimeRangeEnum, NewsSourceEnum, AnalysisRequest # Added AnalysisRequest
)
from capabilities.news_aggregator import NewsAggregator
from capabilities.trends_analyzer import TrendsAnalyzer
from capabilities.scraping.web_scraper import WebScraper # New import
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
def run_orchestrator_in_thread(app_config, session_id, base_workspace_path, aggregated_config):
    # The AnalysisOrchestrator is instantiated here, within the thread
    orchestrator = AnalysisOrchestrator(
        session_id=session_id,
        base_workspace_path=base_workspace_path,
        config=app_config # Pass the main app config
    )
    try:
        # The orchestrator's run_full_pipeline is an async method
        asyncio.run(orchestrator.run_full_pipeline(aggregated_config))
    except Exception as e:
        logger.error(f"Exception in orchestrator thread for session {session_id}: {e}", exc_info=True)
        # Orchestrator handles creating _JOB_FAILED marker.

@api_blueprint.route('/analysis/start_job', methods=['POST'])
def start_analysis_job():
    """
    Starts a new analysis job.
    Creates a unique session and triggers the analysis pipeline in a background thread.
    Returns a 202 Accepted response immediately.
    
    POST Body (optional):
    {
        "client_keywords": ["Fenerbahçe", "transfer"],
        "client_scrape_urls": ["https://www.fanatik.com.tr/fenerbahce"],
        "use_default_urls_keywords": true,
        "time_range": "last_week", // e.g., "last_24_hours", "last_week"
        "custom_start_date": "YYYY-MM-DD", // Optional
        "custom_end_date": "YYYY-MM-DD"   // Optional
    }
    """
    try:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        base_workspace_path = current_app.config.get('WORKSPACE_DIR', os.path.join(current_app.root_path, 'workspace'))
        os.makedirs(base_workspace_path, exist_ok=True)

        request_data_raw = request.get_json(silent=True) or {}
        
        # Validate incoming data using Pydantic model if it makes sense here
        # For now, directly extracting with .get for flexibility
        client_config_payload = {
            'keywords': request_data_raw.get("client_keywords"),
            'scrape_urls': request_data_raw.get("client_scrape_urls"),
            'use_default_urls_keywords': request_data_raw.get("use_default_urls_keywords", True),
            'time_range': request_data_raw.get("time_range"), # Expects a string like "last_week"
            'custom_start_date': request_data_raw.get("custom_start_date"),
            'custom_end_date': request_data_raw.get("custom_end_date")
        }
        logger.info(f"Received client_config_payload: {client_config_payload}")        # Load search_parameters.json
        search_params_data = {}
        search_params_path = current_app.config.get('SEARCH_PARAMETERS_PATH', os.path.join(current_app.root_path, 'search_parameters.json'))
        if os.path.exists(search_params_path):
            try:
                with open(search_params_path, 'r', encoding='utf-8') as f:
                    search_params_data = json.load(f)
                logger.info(f"Loaded search_parameters.json: {search_params_data}")
            except Exception as e:
                logger.error(f"Error loading or parsing search_parameters.json: {e}")
        else:
            logger.warning(f"search_parameters.json not found at {search_params_path}")

        # Aggregate parameters according to priority rules:
        # 1. Client keywords extend search_parameters.json keywords
        # 2. Client URLs extend search_parameters.json URLs  
        # 3. Client time info overwrites search_parameters.json time info
        # 4. Max results comes only from search_parameters.json
        aggregated_config = {}
        
        # Keywords: extend (client + search_parameters)
        search_keywords = search_params_data.get('keywords', [])
        client_keywords = client_config_payload.get('keywords') or []
        aggregated_config['keywords'] = search_keywords + client_keywords
        
        # URLs: extend (client + search_parameters)
        search_urls = search_params_data.get('scrape_urls', [])
        client_urls = client_config_payload.get('scrape_urls') or []
        aggregated_config['scrape_urls'] = search_urls + client_urls
        
        # Time info: client overwrites search_parameters
        if client_config_payload.get('time_range'):
            aggregated_config['time_range'] = client_config_payload['time_range']
        else:
            aggregated_config['time_range'] = search_params_data.get('default_time_range', 'last_24_hours')
            
        # Custom dates: client overwrites
        if client_config_payload.get('custom_start_date'):
            aggregated_config['custom_start_date'] = client_config_payload['custom_start_date']
        if client_config_payload.get('custom_end_date'):
            aggregated_config['custom_end_date'] = client_config_payload['custom_end_date']
            
        # Max results: only from search_parameters.json (mandatory)
        aggregated_config['max_results'] = search_params_data.get('max_results_news', 10)  # Default to 10 if not in search_parameters
        
        # News sources: from search_parameters.json
        aggregated_config['news_sources'] = search_params_data.get('news_sources', ['newsapi'])
        
        # Use default URLs/keywords flag
        aggregated_config['use_default_urls_keywords'] = client_config_payload.get('use_default_urls_keywords', True)
        
        logger.info(f"Aggregated configuration: {aggregated_config}")

        app_config_copy = current_app.config.copy()

        # Store job initial info
        if not hasattr(current_app, 'jobs'):
            current_app.jobs = {}
        
        status_endpoint = url_for('api.get_analysis_job_status', session_id=session_id, _external=True)
        results_endpoint = url_for('api.get_job_results', session_id=session_id, _external=True)

        current_app.jobs[session_id] = {
            "status": "pending", 
            "session_id": session_id,
            "start_time": datetime.now().isoformat(),
            "status_endpoint": status_endpoint,
            "results_endpoint": results_endpoint,
            "client_config_received": client_config_payload,
            "search_params_loaded": search_params_data,
            "aggregated_config": aggregated_config
        }

        # Start the background task using threading
        thread = threading.Thread(target=run_orchestrator_in_thread, args=(
            app_config_copy, 
            session_id, 
            base_workspace_path, 
            aggregated_config
        ))
        thread.start()

        logger.info(f"Job {session_id} started. Status endpoint: {status_endpoint}")
        return jsonify({
            "message": "Analysis job initiated successfully",
            "session_id": session_id,
            "status_endpoint": status_endpoint,
            "results_endpoint": results_endpoint
        }), 202

    except Exception as e:
        logger.error(f"Error starting analysis job: {str(e)}", exc_info=True)
        # Ensure ErrorResponse is serializable if it's a Pydantic model by calling .dict()
        # Assuming ErrorResponse is already defined and imported
        return jsonify(ErrorResponse(
            error="Job Start Error", 
            code=500, 
            details=str(e)
        ).model_dump()), 500 # Use .model_dump() for Pydantic v2+ or .dict() for v1

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

@api_blueprint.route('/analysis/job_results/<session_id>', methods=['GET'])
def get_job_results(session_id: str):
    """
    Gets the results of a completed analysis job.
    (Placeholder implementation)
    """
    logger.info(f"Attempting to retrieve results for session_id: {session_id}")
    base_workspace_path = current_app.config.get('WORKSPACE_DIR', os.path.join(current_app.root_path, 'workspace'))
    session_path = os.path.join(base_workspace_path, secure_filename(session_id))
    # Example: Define a path where results might be stored, e.g., a summary file
    summary_file_path = os.path.join(session_path, "summary", "final_summary.txt") # Adjust as per your orchestrator

    if not os.path.exists(session_path):
        return jsonify(ErrorResponse(
            error="Not Found", 
            code=404, 
            details=f"Session ID {session_id} not found."
        ).model_dump()), 404 # Use .model_dump() for Pydantic v2+

    # Check if the specific result file exists (e.g., summary)
    if os.path.exists(summary_file_path):
        try:
            # Example: return content of a summary file
            with open(summary_file_path, 'r', encoding='utf-8') as f:
                summary_content = f.read()
            return jsonify({
                "session_id": session_id,
                "status": "COMPLETED", # Assuming if results file exists, job is completed
                "results": {
                    "summary": summary_content
                    # You can add more structured results here
                }
            }), 200
        except Exception as e:
            logger.error(f"Error reading results file {summary_file_path} for session {session_id}: {e}", exc_info=True)
            return jsonify(ErrorResponse(
                error="Result Retrieval Error", 
                code=500, 
                details=f"Could not read results for session {session_id}."
            ).model_dump()), 500
    else:
        # If the specific result file doesn't exist, check the job's overall status
        job_info = current_app.jobs.get(session_id)
        if job_info:
            job_status = job_info.get("status", "UNKNOWN")
            if job_status in ["pending", "RUNNING", "INITIALIZED"]: # Check against actual statuses used
                return jsonify({
                    "session_id": session_id,
                    "status": job_status,
                    "message": "Job is still processing or has not yet produced results. Results are not yet available."
                }), 202 # Accepted, but not ready
            else: # e.g., FAILED, or COMPLETED but specific file missing
                return jsonify(ErrorResponse(
                    error="Results Not Found", 
                    code=404, 
                    details=f"Results for session ID {session_id} are not available. Job status: {job_status}."
                ).model_dump()), 404
        else:
            # This case might be redundant if the initial session_path check handles it,
            # but good for robustness if current_app.jobs might not have the session for some reason.
            return jsonify(ErrorResponse(
                error="Not Found", 
                code=404, 
                details=f"Session ID {session_id} not found, cannot determine job status for results."
            ).model_dump()), 404

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

