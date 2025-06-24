"""
Scraping endpoints - Separated scraping logic using journ4list.
These endpoints handle only scraping operations, completely separated from analysis.
"""

import asyncio
import logging
from quart import Blueprint, request, jsonify, current_app
from typing import List, Dict, Any

# Import the new scraping service
from capabilities.services.scraping_service import ScrapingService

logger = logging.getLogger(__name__)
scraping_blueprint = Blueprint('scraping', __name__)

@scraping_blueprint.route('/start', methods=['POST'])
async def start_scraping():
    """
    Start a scraping job using journ4list.
    Completely separated from other API calls and analysis.
    
    POST Body:
    {
        "urls": ["https://www.fanatik.com.tr", "https://www.fotomac.com.tr"],
        "keywords": ["Fenerbahçe", "transfer", "futbol"],  // optional
        "persist": true,  // optional, default true
        "scrape_depth": 1  // optional, default 1
    }
    """
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        urls = data.get('urls', [])
        if not urls:
            return jsonify({"error": "URLs are required"}), 400
        
        if not isinstance(urls, list):
            return jsonify({"error": "URLs must be a list"}), 400
            
        keywords = data.get('keywords', [])
        persist = data.get('persist', True)
        scrape_depth = data.get('scrape_depth', 1)
        
        logger.info(f"Starting scraping job: {len(urls)} URLs, keywords: {keywords}")
        
        # Initialize scraping service
        scraping_service = ScrapingService()
        
        # Run scraping asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if keywords:
                result = loop.run_until_complete(
                    scraping_service.scrape_with_keywords(
                        urls=urls,
                        keywords=keywords,
                        persist=persist,
                        scrape_depth=scrape_depth
                    )
                )
            else:
                result = loop.run_until_complete(
                    scraping_service.scrape_simple(
                        urls=urls,
                        persist=persist,
                        scrape_depth=scrape_depth
                    )
                )
        finally:
            loop.close()
        
        # Return standardized response
        response = {
            "session_id": result.get("session_id"),
            "status": "completed" if result.get("session_id") else "failed",
            "articles_found": len(result.get("articles", [])),
            "extraction_summary": result.get("extraction_summary", {}),
            "persist_enabled": persist,
            "scrape_depth": scrape_depth,
            "keywords_used": keywords if keywords else None
        }
        
        if result.get("session_id"):
            logger.info(f"Scraping completed successfully. Session: {result['session_id']}")
            return jsonify(response), 200
        else:
            logger.error(f"Scraping failed: {result.get('extraction_summary', {}).get('error', 'Unknown error')}")
            return jsonify(response), 500
            
    except Exception as e:
        logger.error(f"Error in scraping endpoint: {e}", exc_info=True)
        return jsonify({"error": f"Scraping endpoint error: {str(e)}"}), 500

@scraping_blueprint.route('/latest', methods=['GET'])
async def get_latest_session():
    """Get the latest scraping session data."""
    try:
        scraping_service = ScrapingService()
        latest_session_path = scraping_service.find_latest_session()
        
        if not latest_session_path:
            return jsonify({"error": "No sessions found"}), 404
            
        session_info = scraping_service.get_session_info(latest_session_path)
        
        if "error" in session_info:
            return jsonify(session_info), 500
            
        return jsonify({
            "latest_session": session_info,
            "message": "Use /load endpoint with session_file to get full data"
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting latest session: {e}")
        return jsonify({"error": str(e)}), 500

@scraping_blueprint.route('/sessions', methods=['GET'])
async def list_sessions():
    """List all available scraping sessions."""
    try:
        scraping_service = ScrapingService()
        session_files = scraping_service.list_all_sessions()
        
        sessions_info = []
        for session_file in session_files[:10]:  # Limit to 10 most recent
            info = scraping_service.get_session_info(session_file)
            if "error" not in info:
                sessions_info.append(info)
        
        return jsonify({
            "total_sessions": len(session_files),
            "sessions_shown": len(sessions_info),
            "sessions": sessions_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500

@scraping_blueprint.route('/load', methods=['POST'])
async def load_session_data():
    """
    Load full session data from a specific session file.
    
    POST Body:
    {
        "session_file_path": "/path/to/session_data.json"
    }
    """
    try:
        data = request.get_json() or {}
        session_file_path = data.get('session_file_path')
        
        if not session_file_path:
            return jsonify({"error": "session_file_path is required"}), 400
        
        scraping_service = ScrapingService()
        session_data = scraping_service.load_session_data(session_file_path)
        
        if not session_data:
            return jsonify({"error": "Failed to load session data"}), 500
            
        return jsonify({
            "session_file": session_file_path,
            "session_data": session_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error loading session data: {e}")
        return jsonify({"error": str(e)}), 500

@scraping_blueprint.route('/cleanup', methods=['POST'])
async def cleanup_sessions():
    """
    Clean up old session files.
    
    POST Body:
    {
        "keep_last_n": 5  // optional, default 5
    }
    """
    try:
        data = request.get_json() or {}
        keep_last_n = data.get('keep_last_n', 5)
        
        scraping_service = ScrapingService()
        cleanup_result = scraping_service.cleanup_old_sessions(keep_last_n)
        
        return jsonify(cleanup_result), 200
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return jsonify({"error": str(e)}), 500

@scraping_blueprint.route('/status', methods=['GET'])
async def get_scraping_status():
    """Get scraping service status and configuration."""
    try:
        scraping_service = ScrapingService()
        
        # Check if workspace exists
        workspace_exists = os.path.exists(scraping_service.workspace_dir)
        
        # Get session count
        session_count = len(scraping_service.list_all_sessions())
        
        # Get latest session info
        latest_session_path = scraping_service.find_latest_session()
        latest_session_info = None
        if latest_session_path:
            latest_session_info = scraping_service.get_session_info(latest_session_path)
        
        return jsonify({
            "service": "ScrapingService with journ4list",
            "status": "available",
            "workspace_directory": scraping_service.workspace_dir,
            "workspace_exists": workspace_exists,
            "total_sessions": session_count,
            "latest_session": latest_session_info,
            "journ4list_version": ">=0.1.0"
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {e}")
        return jsonify({
            "service": "ScrapingService", 
            "status": "error",
            "error": str(e)
        }), 500
