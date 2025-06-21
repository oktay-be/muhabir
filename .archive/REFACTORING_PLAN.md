# AISports Project Refactoring Plan

## Overview
This document outlines the comprehensive refactoring plan to transition the AISports project from custom scraping logic to the `journ4list` library, separate API calls from scraping logic, and remove pipeline dependencies.

## Current Architecture Analysis

### Current Components to be Deprecated/Removed

#### 1. Custom Scraping Infrastructure (DEPRECATED)
```
capabilities/scraping/
├── web_scraper.py                    # Main web scraper - REMOVE
├── link_discoverer.py               # Link discovery logic - REMOVE  
├── content_extractor.py             # Content extraction - REMOVE
├── session_manager.py               # Session management - REMOVE
├── network_utils.py                 # Network utilities - REMOVE
├── cache_manager.py                 # Cache management - REMOVE
├── file_manager.py                  # File operations - REMOVE
├── config.py                        # Scraping config - REMOVE
├── constants.py                     # Scraping constants - REMOVE
└── extractors/                      # All extractors - REMOVE
    ├── base_extractor.py
    ├── fullpage_extractor.py
    ├── ldjson_extractor.py
    ├── readability_extractor.py
    └── selector_extractor.py
```

#### 2. Pipeline Architecture (DEPRECATED)
- `analysis_orchestrator.py` - Complex pipeline orchestration - SIMPLIFY
- `analysis_orchestrator_fixed.py` - Backup file - REMOVE

#### 3. Test Infrastructure (DEPRECATED)
```
tests/unit/scraping/                 # All scraping tests - REMOVE
tests/unit/test_web_scraper_wrapper.py - REMOVE
```

### Current Components to be Preserved/Refactored

#### 1. Core Capabilities (PRESERVE & ENHANCE)
- `capabilities/ai_summarizer.py` - ✅ Already enhanced with Claude 4 integration
- `capabilities/news_aggregator.py` - News API integration (keep)
- `capabilities/trends_analyzer.py` - Trend analysis (keep)

#### 2. API Layer (REFACTOR)
- `api/routes.py` - Separate scraping from API calls
- `api/models.py` - Update models for new architecture

#### 3. Utilities (PRESERVE)
- `utils/` - General utilities (keep most)
- `helpers/` - Helper functions (keep most)

## New Architecture Design

### 1. Service-Oriented Architecture

```
capabilities/
├── services/
│   ├── __init__.py
│   ├── scraping_service.py          # NEW: journ4list wrapper
│   ├── news_service.py              # NEW: API-based news fetching
│   ├── analysis_service.py          # NEW: AI analysis coordination
│   └── persistence_service.py       # NEW: Data persistence
├── ai_summarizer.py                 # ENHANCED: Already updated
├── news_aggregator.py               # REFACTORED: API calls only
└── trends_analyzer.py               # PRESERVED: Minimal changes
```

### 2. API Layer Separation

```
api/
├── endpoints/
│   ├── __init__.py
│   ├── scraping_endpoints.py        # NEW: Scraping-specific endpoints
│   ├── news_endpoints.py            # NEW: News API endpoints
│   └── analysis_endpoints.py        # NEW: Analysis endpoints
├── routes.py                        # REFACTORED: Main route coordination
└── models.py                        # UPDATED: New request/response models
```

### 3. Integration Layer

```
integrations/
├── __init__.py
├── journ4list_adapter.py           # NEW: journ4list integration
├── newsapi_adapter.py              # NEW: NewsAPI integration wrapper
└── claude_adapter.py               # NEW: Claude API integration
```

## Migration Strategy

### Phase 1: Infrastructure Setup (Week 1)

#### 1.1 Install journ4list
```bash
pip install journ4list
```

#### 1.2 Create new service architecture
- Create `capabilities/services/` directory
- Implement `scraping_service.py` with journ4list integration
- Create adapter layer for journ4list

#### 1.3 Archive old scraping code
```bash
# Move to archive for reference
mkdir .archive/deprecated_scraping
mv capabilities/scraping/* .archive/deprecated_scraping/
```

### Phase 2: Service Implementation (Week 1-2)

#### 2.1 ScrapingService Implementation
```python
# capabilities/services/scraping_service.py
import asyncio
from typing import List, Dict, Any, Optional
from journ4list import Journalist
from integrations.journ4list_adapter import Journ4listAdapter

class ScrapingService:
    """
    Service for handling all scraping operations using journ4list.
    Completely replaces the old scraping infrastructure.
    """
    
    def __init__(self, persist: bool = True, scrape_depth: int = 1):
        self.persist = persist
        self.scrape_depth = scrape_depth
        self.adapter = Journ4listAdapter()
    
    async def scrape_urls(self, urls: List[str], keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        """Scrape URLs using journ4list"""
        
    async def scrape_from_session_file(self, session_file_path: str) -> Dict[str, Any]:
        """Load existing journ4list session data"""
        
    def find_latest_session(self) -> Optional[str]:
        """Find latest journ4list session file"""
```

#### 2.2 NewsService Implementation
```python
# capabilities/services/news_service.py
class NewsService:
    """
    Service for handling API-based news fetching.
    Separates API calls from scraping completely.
    """
    
    def __init__(self, newsapi_key: str, worldnewsapi_key: str = None):
        self.newsapi_key = newsapi_key
        self.worldnewsapi_key = worldnewsapi_key
    
    async def fetch_from_newsapi(self, query_params: Dict) -> Dict[str, Any]:
        """Fetch news from NewsAPI"""
        
    async def fetch_from_worldnews(self, query_params: Dict) -> Dict[str, Any]:
        """Fetch news from WorldNewsAPI"""
```

#### 2.3 AnalysisService Implementation
```python
# capabilities/services/analysis_service.py
class AnalysisService:
    """
    Service coordinating AI analysis operations.
    Works with both scraping and API data.
    """
    
    def __init__(self, ai_summarizer: AISummarizer):
        self.ai_summarizer = ai_summarizer
    
    async def process_scraped_data(self, session_data: Dict) -> Dict[str, Any]:
        """Process journ4list session data"""
        
    async def process_api_data(self, news_data: Dict) -> Dict[str, Any]:
        """Process API-fetched news data"""
```

### Phase 3: API Layer Refactoring (Week 2)

#### 3.1 Separate API Endpoints
```python
# api/endpoints/scraping_endpoints.py
@scraping_blueprint.route('/scrape/start', methods=['POST'])
async def start_scraping():
    """Start scraping job using journ4list"""
    
@scraping_blueprint.route('/scrape/status/<session_id>', methods=['GET'])
async def get_scraping_status(session_id: str):
    """Get scraping job status"""

# api/endpoints/news_endpoints.py
@news_blueprint.route('/news/fetch', methods=['POST'])
async def fetch_news():
    """Fetch news from APIs (NewsAPI, WorldNews)"""

# api/endpoints/analysis_endpoints.py
@analysis_blueprint.route('/analyze/scraping', methods=['POST'])
async def analyze_scraped_data():
    """Analyze scraped data"""
    
@analysis_blueprint.route('/analyze/news', methods=['POST'])
async def analyze_news_data():
    """Analyze API news data"""
```

#### 3.2 Refactor Main Routes
```python
# api/routes.py - SIMPLIFIED
from api.endpoints.scraping_endpoints import scraping_blueprint
from api.endpoints.news_endpoints import news_blueprint
from api.endpoints.analysis_endpoints import analysis_blueprint

def register_blueprints(app):
    app.register_blueprint(scraping_blueprint, url_prefix='/api/scraping')
    app.register_blueprint(news_blueprint, url_prefix='/api/news')
    app.register_blueprint(analysis_blueprint, url_prefix='/api/analysis')

# Remove complex pipeline orchestration
# Each endpoint handles its own business logic
```

### Phase 4: Integration Layer (Week 2-3)

#### 4.1 Journ4list Adapter
```python
# integrations/journ4list_adapter.py
class Journ4listAdapter:
    """
    Adapter for journ4list library.
    Handles configuration, session management, and data transformation.
    """
    
    def __init__(self):
        self.journalist_config = self._load_config()
    
    async def create_session(self, persist: bool = True) -> Journalist:
        """Create journ4list session"""
        
    def transform_to_aisports_format(self, journ4list_data: Dict) -> Dict:
        """Transform journ4list output to AISports format"""
        
    def find_workspace_sessions(self) -> List[str]:
        """Find all journ4list workspace sessions"""
```

#### 4.2 NewsAPI Adapter
```python
# integrations/newsapi_adapter.py
class NewsAPIAdapter:
    """
    Adapter for NewsAPI and other news APIs.
    Standardizes API responses to common format.
    """
    
    def transform_newsapi_response(self, response: Dict) -> Dict:
        """Transform NewsAPI response to standard format"""
        
    def transform_worldnews_response(self, response: Dict) -> Dict:
        """Transform WorldNewsAPI response to standard format"""
```

### Phase 5: Remove Pipeline Dependencies (Week 3)

#### 5.1 Remove AnalysisOrchestrator
- Delete `analysis_orchestrator.py`
- Delete `analysis_orchestrator_fixed.py`
- Remove pipeline-based threading logic
- Implement direct service calls in endpoints

#### 5.2 Update Request/Response Models
```python
# api/models.py - NEW MODELS
class ScrapingRequest(BaseModel):
    urls: List[str]
    keywords: Optional[List[str]] = None
    persist: bool = True
    scrape_depth: int = 1

class ScrapingResponse(BaseModel):
    session_id: str
    status: str
    articles_found: int
    extraction_summary: Dict[str, Any]

class NewsRequest(BaseModel):
    sources: List[str]
    query: str
    time_range: TimeRangeEnum
    max_results: int = 100

class AnalysisRequest(BaseModel):
    data_source: str  # "scraping" or "api"
    session_id: Optional[str] = None
    data: Optional[Dict] = None
    use_claude4: bool = True
```

### Phase 6: Testing & Validation (Week 3-4)

#### 6.1 Create New Test Suite
```
tests/
├── integration/
│   ├── test_journ4list_integration.py   # NEW: Test journ4list
│   ├── test_api_separation.py           # NEW: Test API separation
│   └── test_end_to_end.py               # NEW: Full workflow tests
├── services/
│   ├── test_scraping_service.py         # NEW: Test scraping service
│   ├── test_news_service.py             # NEW: Test news service
│   └── test_analysis_service.py         # NEW: Test analysis service
└── endpoints/
    ├── test_scraping_endpoints.py       # NEW: Test scraping endpoints
    ├── test_news_endpoints.py           # NEW: Test news endpoints
    └── test_analysis_endpoints.py       # NEW: Test analysis endpoints
```

#### 6.2 Remove Old Tests
```bash
# Archive old tests
mv tests/unit/scraping/ .archive/deprecated_tests/
rm tests/unit/test_web_scraper_wrapper.py
```

## Configuration Changes

### 1. Environment Variables
```bash
# .env - NEW VARIABLES
JOURN4LIST_WORKSPACE_DIR=.journalist_workspace
JOURN4LIST_PERSIST=true
JOURN4LIST_SCRAPE_DEPTH=2

# EXISTING VARIABLES (keep)
NEWSAPI_KEY=your_newsapi_key
WORLDNEWSAPI_KEY=your_worldnews_key
GOOGLE_API_KEY=your_google_api_key
```

### 2. Configuration Files
```json
// config/scraping_config.json - NEW
{
  "journ4list": {
    "default_persist": true,
    "default_scrape_depth": 2,
    "workspace_cleanup_hours": 24,
    "max_concurrent_sessions": 5
  },
  "extraction": {
    "timeout_seconds": 30,
    "retry_attempts": 3,
    "user_agent": "AISports-Bot/1.0"
  }
}

// config/analysis_config.json - NEW
{
  "claude4": {
    "model": "claude-3-sonnet-20240229",
    "max_tokens": 4000,
    "temperature": 0.1
  },
  "categories": {
    "confidence_threshold": 0.6,
    "max_categories_per_article": 5
  }
}
```

## Data Flow Changes

### Old Pipeline Flow (DEPRECATED)
```
API Request → Orchestrator → [Scraping + NewsAPI + AI] → Response
```

### New Service Flow (NEW)
```
Scraping Request → ScrapingService → journ4list → Response
News Request → NewsService → APIs → Response  
Analysis Request → AnalysisService → AI → Response
```

### Combined Workflow (NEW)
```
1. Client calls /api/scraping/start → ScrapingService
2. Client calls /api/analysis/scraping → AnalysisService
3. OR Client calls /api/news/fetch → NewsService
4. Client calls /api/analysis/news → AnalysisService
```

## Benefits of New Architecture

### 1. Separation of Concerns
- Scraping isolated from API calls
- Each service has single responsibility
- Independent testing and deployment

### 2. Improved Maintainability
- Remove complex pipeline orchestration
- Use battle-tested journ4list library
- Clearer code organization

### 3. Better Scalability
- Services can be scaled independently
- No blocking pipeline operations
- Async-first architecture

### 4. Enhanced Reliability
- Robust error handling via journ4list
- Better session management
- Standardized data formats

## Migration Timeline

| Week | Phase | Activities | Deliverables |
|------|-------|------------|--------------|
| 1 | Infrastructure | Install journ4list, create services | Service skeletons |
| 2 | Implementation | Build services and adapters | Working services |
| 2-3 | API Refactoring | Separate endpoints, remove pipeline | New API structure |
| 3 | Cleanup | Remove old code, update configs | Clean codebase |
| 3-4 | Testing | Build test suite, validation | Test coverage |

## Rollback Strategy

### 1. Git Branching
```bash
# Create feature branch for refactoring
git checkout -b refactor/journ4list-migration

# Keep main branch stable
# Merge only after complete testing
```

### 2. Archive Strategy
```bash
.archive/
├── deprecated_scraping/     # Old scraping code
├── deprecated_tests/        # Old test files
├── deprecated_pipeline/     # Pipeline orchestration
└── migration_logs/          # Migration progress logs
```

### 3. Rollback Commands
```bash
# If rollback needed
git checkout main
rm -rf capabilities/services/
git checkout HEAD -- capabilities/scraping/
```

## Success Criteria

### 1. Functional Requirements
- ✅ All current API endpoints work with new architecture
- ✅ journ4list integration provides same or better scraping results
- ✅ AI analysis works with both scraping and API data
- ✅ Session management preserved

### 2. Performance Requirements
- ✅ Response times equal or better than current system
- ✅ Memory usage reduced (no complex pipeline)
- ✅ Concurrent request handling improved

### 3. Quality Requirements
- ✅ Test coverage >90%
- ✅ No breaking changes to existing API contracts
- ✅ Error handling improved
- ✅ Documentation updated

## Risk Mitigation

### 1. Technical Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| journ4list incompatibility | High | Thorough testing, fallback plan |
| Performance degradation | Medium | Benchmarking, optimization |
| Data format changes | Medium | Adapter pattern, transformation |

### 2. Business Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Service downtime | High | Phased migration, rollback plan |
| Feature regression | Medium | Comprehensive testing |
| User experience impact | Low | API compatibility maintained |

## Conclusion

This refactoring plan provides a comprehensive roadmap to modernize the AISports project by:

1. **Replacing custom scraping** with the proven journ4list library
2. **Separating concerns** through service-oriented architecture  
3. **Removing pipeline complexity** in favor of direct service calls
4. **Improving maintainability** with cleaner code organization
5. **Enhancing scalability** with independent services

The migration will be done incrementally with proper testing and rollback strategies to ensure minimal disruption to existing functionality.
