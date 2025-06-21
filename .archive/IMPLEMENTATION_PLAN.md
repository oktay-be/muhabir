# AISports Refactoring Implementation Plan

## Immediate Action Items (Next Steps)

### 1. Project Setup and Dependencies

#### Install journ4list
```bash
# Update requirements.txt
echo "journ4list>=0.1.0" >> requirements.txt
pip install journ4list
```

#### Create new directory structure
```bash
mkdir -p capabilities/services
mkdir -p integrations
mkdir -p api/endpoints
mkdir -p config
mkdir -p .archive/deprecated_scraping
```

### 2. Phase 1 Implementation (This Week)

#### Step 1: Move deprecated scraping code to archive
```bash
# Archive the entire scraping infrastructure
mv capabilities/scraping/* .archive/deprecated_scraping/
# Keep the directory but empty it for now
```

#### Step 2: Create ScrapingService with journ4list
```python
# capabilities/services/scraping_service.py
import asyncio
import os
import json
import logging
from typing import List, Dict, Any, Optional
from journ4list import Journalist

logger = logging.getLogger(__name__)

class ScrapingService:
    """
    Modern scraping service using journ4list library.
    Replaces all custom scraping infrastructure.
    """
    
    def __init__(self, workspace_dir: str = ".journalist_workspace"):
        self.workspace_dir = workspace_dir
        
    async def scrape_with_keywords(self, urls: List[str], keywords: List[str], 
                                 persist: bool = True, scrape_depth: int = 1) -> Dict[str, Any]:
        """
        Scrape URLs with keyword filtering using journ4list.
        
        Args:
            urls: List of URLs to scrape
            keywords: Keywords for relevance filtering
            persist: Whether to save session data to files
            scrape_depth: Depth level for link discovery
            
        Returns:
            Dict with articles and session metadata
        """
        try:
            journalist = Journalist(persist=persist, scrape_depth=scrape_depth)
            
            result = await journalist.read(urls=urls, keywords=keywords)
            
            logger.info(f"Scraping completed. Session: {result['session_id']}, "
                       f"Articles: {len(result['articles'])}")
            
            return result
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return {
                "session_id": None,
                "articles": [],
                "extraction_summary": {
                    "error": str(e),
                    "urls_processed": 0,
                    "articles_extracted": 0
                }
            }
    
    def find_latest_session(self) -> Optional[str]:
        """Find the latest journ4list session file."""
        try:
            if not os.path.exists(self.workspace_dir):
                return None
                
            sessions = []
            for item in os.listdir(self.workspace_dir):
                item_path = os.path.join(self.workspace_dir, item)
                if os.path.isdir(item_path) and item.startswith("202"):
                    sessions.append(item)
            
            if not sessions:
                return None
                
            sessions.sort(reverse=True)
            latest_session_dir = sessions[0]
            
            session_path = os.path.join(self.workspace_dir, latest_session_dir)
            for file in os.listdir(session_path):
                if file.startswith("session_data") and file.endswith(".json"):
                    return os.path.join(session_path, file)
                    
            return None
            
        except Exception as e:
            logger.error(f"Error finding latest session: {e}")
            return None
    
    def load_session_data(self, session_file_path: str) -> Optional[Dict[str, Any]]:
        """Load session data from file."""
        try:
            with open(session_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading session data from {session_file_path}: {e}")
            return None
```

#### Step 3: Create separated API endpoints
```python
# api/endpoints/scraping_endpoints.py
import asyncio
import logging
from flask import Blueprint, request, jsonify, current_app
from capabilities.services.scraping_service import ScrapingService
from api.models import ScrapingRequest, ScrapingResponse

logger = logging.getLogger(__name__)
scraping_blueprint = Blueprint('scraping', __name__)

@scraping_blueprint.route('/start', methods=['POST'])
def start_scraping():
    """
    Start a scraping job using journ4list.
    Separated from other API calls completely.
    """
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        urls = data.get('urls', [])
        if not urls:
            return jsonify({"error": "URLs are required"}), 400
            
        keywords = data.get('keywords', [])
        persist = data.get('persist', True)
        scrape_depth = data.get('scrape_depth', 1)
        
        # Initialize scraping service
        scraping_service = ScrapingService()
        
        # Run scraping asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                scraping_service.scrape_with_keywords(
                    urls=urls,
                    keywords=keywords,
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
            "persist_enabled": persist
        }
        
        if result.get("session_id"):
            logger.info(f"Scraping completed successfully. Session: {result['session_id']}")
            return jsonify(response), 200
        else:
            logger.error(f"Scraping failed: {result.get('extraction_summary', {}).get('error', 'Unknown error')}")
            return jsonify(response), 500
            
    except Exception as e:
        logger.error(f"Error in scraping endpoint: {e}")
        return jsonify({"error": f"Scraping endpoint error: {str(e)}"}), 500

@scraping_blueprint.route('/latest', methods=['GET'])
def get_latest_session():
    """Get the latest scraping session data."""
    try:
        scraping_service = ScrapingService()
        latest_session_path = scraping_service.find_latest_session()
        
        if not latest_session_path:
            return jsonify({"error": "No sessions found"}), 404
            
        session_data = scraping_service.load_session_data(latest_session_path)
        if not session_data:
            return jsonify({"error": "Failed to load session data"}), 500
            
        return jsonify({
            "session_file": latest_session_path,
            "session_data": session_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting latest session: {e}")
        return jsonify({"error": str(e)}), 500
```

#### Step 4: Create analysis endpoint separated from scraping
```python
# api/endpoints/analysis_endpoints.py
import asyncio
import logging
from flask import Blueprint, request, jsonify, current_app
from capabilities.ai_summarizer import AISummarizer
from capabilities.services.scraping_service import ScrapingService

logger = logging.getLogger(__name__)
analysis_blueprint = Blueprint('analysis', __name__)

@analysis_blueprint.route('/process_scraped_data', methods=['POST'])
def analyze_scraped_data():
    """
    Analyze scraped data using AI (separated from scraping process).
    Can work with session_id or direct session_data.
    """
    try:
        data = request.get_json() or {}
        
        # Initialize AI summarizer
        google_api_key = current_app.config.get('GOOGLE_API_KEY')
        if not google_api_key:
            return jsonify({"error": "Google API key not configured"}), 500
            
        ai_summarizer = AISummarizer(google_api_key=google_api_key)
        
        session_data = None
        session_source = None
        
        # Option 1: Direct session data (persist=false scenario)
        if 'session_data' in data:
            session_data = data['session_data']
            session_source = "direct_data"
            
        # Option 2: Session file path (persist=true scenario)
        elif 'session_file_path' in data:
            scraping_service = ScrapingService()
            session_data = scraping_service.load_session_data(data['session_file_path'])
            session_source = f"file: {data['session_file_path']}"
            
        # Option 3: Latest session (convenience)
        elif data.get('use_latest_session', False):
            scraping_service = ScrapingService()
            latest_path = scraping_service.find_latest_session()
            if latest_path:
                session_data = scraping_service.load_session_data(latest_path)
                session_source = f"latest: {latest_path}"
        
        if not session_data:
            return jsonify({"error": "No session data provided or found"}), 400
        
        # Run AI analysis
        use_claude4 = data.get('use_claude4', True)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if session_source.startswith("file:"):
                # Use persist=true scenario
                result = loop.run_until_complete(
                    ai_summarizer.process_news_with_claude4_prompt(
                        session_file_path=session_source.replace("file: ", ""),
                        use_claude4=use_claude4
                    )
                )
            else:
                # Use persist=false scenario
                result = loop.run_until_complete(
                    ai_summarizer.process_news_with_claude4_prompt(
                        session_data=session_data,
                        use_claude4=use_claude4
                    )
                )
        finally:
            loop.close()
        
        logger.info(f"AI analysis completed. Source: {session_source}, "
                   f"Articles processed: {len(result.get('processed_articles', []))}")
        
        return jsonify({
            "analysis_result": result,
            "session_source": session_source,
            "use_claude4": use_claude4
        }), 200
        
    except Exception as e:
        logger.error(f"Error in analysis endpoint: {e}")
        return jsonify({"error": f"Analysis error: {str(e)}"}), 500
```

#### Step 5: Update main routes.py to use new endpoints
```python
# api/routes.py - SIMPLIFIED VERSION
import logging
from flask import Blueprint, jsonify, current_app
from api.endpoints.scraping_endpoints import scraping_blueprint
from api.endpoints.analysis_endpoints import analysis_blueprint

logger = logging.getLogger(__name__)

# Create main API blueprint
api_blueprint = Blueprint('api', __name__)

# Register sub-blueprints
api_blueprint.register_blueprint(scraping_blueprint, url_prefix='/scraping')
api_blueprint.register_blueprint(analysis_blueprint, url_prefix='/analysis')

@api_blueprint.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "version": "2.0.0-refactored",
        "services": {
            "scraping": "journ4list",
            "analysis": "google_genai + claude4"
        }
    }), 200

@api_blueprint.route('/status', methods=['GET'])
def get_status():
    """Get overall system status."""
    try:
        from capabilities.services.scraping_service import ScrapingService
        
        scraping_service = ScrapingService()
        latest_session = scraping_service.find_latest_session()
        
        return jsonify({
            "scraping_service": "available",
            "latest_session": latest_session is not None,
            "workspace_dir": scraping_service.workspace_dir,
            "google_api_configured": bool(current_app.config.get('GOOGLE_API_KEY'))
        }), 200
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({"error": str(e)}), 500

# Remove all complex pipeline orchestration
# Remove threading logic
# Remove AnalysisOrchestrator usage
```

### 3. Testing the New Implementation

#### Test 1: Basic journ4list integration
```python
# test_new_architecture.py
import asyncio
import json
from capabilities.services.scraping_service import ScrapingService

async def test_scraping_service():
    """Test the new scraping service with journ4list."""
    
    scraping_service = ScrapingService()
    
    # Test URLs (Turkish sports sites)
    test_urls = [
        "https://www.fanatik.com.tr",
        "https://www.fotomac.com.tr"
    ]
    
    test_keywords = ["Fenerbahçe", "transfer", "futbol"]
    
    print("Testing ScrapingService with journ4list...")
    
    result = await scraping_service.scrape_with_keywords(
        urls=test_urls,
        keywords=test_keywords,
        persist=True,
        scrape_depth=1
    )
    
    print(f"Session ID: {result.get('session_id')}")
    print(f"Articles found: {len(result.get('articles', []))}")
    print(f"Extraction summary: {result.get('extraction_summary')}")
    
    # Test latest session finder
    latest = scraping_service.find_latest_session()
    print(f"Latest session file: {latest}")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_scraping_service())
```

#### Test 2: API endpoint separation
```bash
# Test new endpoints with curl

# 1. Test scraping endpoint
curl -X POST http://localhost:5000/api/scraping/start \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.fanatik.com.tr"],
    "keywords": ["Fenerbahçe", "transfer"],
    "persist": true,
    "scrape_depth": 1
  }'

# 2. Test analysis endpoint with latest session
curl -X POST http://localhost:5000/api/analysis/process_scraped_data \
  -H "Content-Type: application/json" \
  -d '{
    "use_latest_session": true,
    "use_claude4": true
  }'

# 3. Test health check
curl http://localhost:5000/api/health
```

### 4. Configuration Updates

#### Update requirements.txt
```txt
# Add to requirements.txt
journ4list>=0.1.0

# Keep existing
flask>=2.0.0
google-generativeai>=0.3.0
pydantic>=1.8.0
# ... other existing dependencies
```

#### Update .env file
```bash
# .env - Add new variables
JOURN4LIST_WORKSPACE_DIR=.journalist_workspace
JOURN4LIST_DEFAULT_PERSIST=true
JOURN4LIST_DEFAULT_SCRAPE_DEPTH=2

# Keep existing
GOOGLE_API_KEY=your_key
NEWSAPI_KEY=your_key
# ... other existing keys
```

### 5. Immediate Benefits

1. **Simplified Architecture**: No more complex pipeline orchestration
2. **Separated Concerns**: Scraping and analysis are independent
3. **Better Error Handling**: journ4list provides robust error management
4. **Modern Async**: Built-in asyncio support
5. **Easier Testing**: Services can be tested independently

### 6. Next Phase Implementation

After Phase 1 is stable:

1. **Create NewsService** for API-only news fetching
2. **Implement integration adapters** for data transformation
3. **Add comprehensive test suite** for new architecture
4. **Remove deprecated code** completely
5. **Update documentation** and deployment configs

### 7. Success Validation

Phase 1 is successful when:
- ✅ journ4list scraping works with Turkish sports sites
- ✅ AI analysis processes journ4list session data
- ✅ API endpoints respond correctly
- ✅ No breaking changes to existing functionality
- ✅ Performance is equal or better

This implementation plan provides a clear, executable roadmap for the first phase of refactoring while maintaining system stability.
