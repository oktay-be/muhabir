"""
Turkish Sports News API

A Flask-based REST API that aggregates sports news content from multiple sources
about Turkey and Turkish football, with trend analysis and web scraping capabilities.
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from helpers.config.logging import configure_logging
from api.routes import api_blueprint
from helpers.config.main import configure_app


def create_app(config_name=None):
    """
    Create and configure the Flask application.
    
    Args:
        config_name: Configuration name ('development', 'production', 'testing')
    
    Returns:
        Flask application instance
    """
    # Configure logging
    configure_logging()
    logger = logging.getLogger(__name__)
    
    # Initialize and configure Flask app
    app = configure_app(__name__, config_name)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    # Root endpoint
    @app.route('/')
    def index():
        """API root - returns basic info and status"""
        return jsonify({
            "status": "online",
            "name": "Turkish Sports News API",
            "version": os.getenv("API_VERSION", "1.0.0"),
            "docs": "/api/docs"
        })
    
    # Health check endpoint for K8s
    @app.route('/health')
    def health_check():
        """Health check endpoint for Kubernetes"""
        return jsonify({"status": "healthy"})
    
    return app


# Create the application instance
app = create_app()

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"Starting Turkish Sports News API in {'debug' if debug_mode else 'production'} mode")
    app.run(host=host, port=port, debug=debug_mode)
