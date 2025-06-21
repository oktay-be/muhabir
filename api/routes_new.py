"""
API routes for the refactored AISports API.
Simplified architecture with separated scraping and analysis services.
"""

import logging
from flask import Blueprint, jsonify, current_app
from api.endpoints.scraping_endpoints import scraping_blueprint
from api.endpoints.analysis_endpoints import analysis_blueprint

logger = logging.getLogger(__name__)

# Create main API blueprint
api_blueprint = Blueprint('api', __name__)

# Register sub-blueprints with URL prefixes
api_blueprint.register_blueprint(scraping_blueprint, url_prefix='/scraping')
api_blueprint.register_blueprint(analysis_blueprint, url_prefix='/analysis')

@api_blueprint.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the refactored API."""
    return jsonify({
        "status": "healthy",
        "version": "2.0.0-refactored",
        "architecture": "service-oriented",
        "services": {
            "scraping": "journ4list",
            "analysis": "google_genai + claude4"
        },
        "endpoints": {
            "scraping": "/api/scraping/*",
            "analysis": "/api/analysis/*"
        }
    }), 200

@api_blueprint.route('/status', methods=['GET'])
def get_overall_status():
    """Get overall system status for all services."""
    try:
        from capabilities.services.scraping_service import ScrapingService
        from capabilities.ai_summarizer import AISummarizer
        
        # Check scraping service
        scraping_service = ScrapingService()
        latest_session = scraping_service.find_latest_session()
        scraping_status = {
            "available": True,
            "latest_session_available": latest_session is not None,
            "workspace_dir": scraping_service.workspace_dir,
            "total_sessions": len(scraping_service.list_all_sessions())
        }
        
        # Check AI service
        google_api_key = current_app.config.get('GOOGLE_API_KEY')
        ai_status = {
            "google_api_configured": bool(google_api_key),
            "model_available": False
        }
        
        if google_api_key:
            try:
                ai_summarizer = AISummarizer(google_api_key=google_api_key)
                ai_status["model_available"] = bool(ai_summarizer.model)
            except Exception as e:
                ai_status["error"] = str(e)
        
        return jsonify({
            "overall_status": "healthy",
            "timestamp": "2025-06-21T00:00:00Z",
            "services": {
                "scraping": scraping_status,
                "analysis": ai_status
            },
            "architecture_info": {
                "pipeline_removed": True,
                "orchestrator_removed": True,
                "service_separation": "complete"
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({
            "overall_status": "error",
            "error": str(e)
        }), 500

@api_blueprint.route('/migration_info', methods=['GET'])
def get_migration_info():
    """Get information about the migration from old to new architecture."""
    return jsonify({
        "migration": {
            "status": "completed",
            "from": "custom scraping + pipeline orchestration",
            "to": "journ4list + service-oriented architecture",
            "breaking_changes": False,
            "deprecated_endpoints": [
                "/api/analysis/start_job (use /api/scraping/start + /api/analysis/process_scraped_data)",
                "/api/analysis/get_job_status (use /api/scraping/status + /api/analysis/status)"
            ]
        },
        "new_workflow": {
            "step_1": "POST /api/scraping/start - Start scraping with journ4list",
            "step_2": "GET /api/scraping/latest - Check scraping results", 
            "step_3": "POST /api/analysis/process_scraped_data - Analyze scraped data",
            "alternative": "POST /api/analysis/auto_process - One-step auto analysis"
        },
        "benefits": [
            "Separated concerns (scraping vs analysis)",
            "No blocking pipeline operations", 
            "Battle-tested journ4list library",
            "Independent service scaling",
            "Better error handling",
            "Simplified codebase"
        ]
    }), 200

# Remove all complex pipeline orchestration code
# Remove threading logic  
# Remove AnalysisOrchestrator usage
# Remove start_analysis_job endpoint (replaced by separated endpoints)

# Legacy endpoint for backward compatibility (optional)
@api_blueprint.route('/legacy/analysis/start_job', methods=['POST'])
def legacy_start_analysis_job():
    """
    Legacy endpoint for backward compatibility.
    Redirects to new separated workflow.
    """
    return jsonify({
        "message": "This endpoint has been deprecated in the refactored architecture",
        "migration_guide": {
            "old_workflow": "POST /api/analysis/start_job (single complex call)",
            "new_workflow": [
                "1. POST /api/scraping/start (start scraping)",
                "2. POST /api/analysis/process_scraped_data (analyze results)"
            ],
            "or_use": "POST /api/analysis/auto_process (convenience method)"
        },
        "redirect_to": "/api/migration_info"
    }), 301
