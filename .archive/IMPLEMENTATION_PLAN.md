# AISports News Collection & Analysis System - Implementation Plan

## Overview

This plan outlines the implementation of a comprehensive news collection and analysis system using MongoDB for data storage, AI for content processing, and a workflow that supports both automated collection and targeted re-scraping based on discovered gaps.

## Use Cases

### UseCase 1: Automated Full Collection
1. **Raw Scraping**: Use journ4list to scrape sources (results stored temporarily in `.journalist_workspace/`)
2. **AI Summarization**: Process each source's raw data → `ai_summarized_www_fanatik_com.json` (per source)
3. **AI Aggregation**: Combine source summaries by region → `ai_summarized_tr.json`, `ai_summarized_eu.json`
4. **EU Extension**: Extend EU data with NewsAPI → `ai_summarized_eu_extended.json`
5. **AI Diff Analysis**: Compare EU extended vs TR → generate diff report
6. **Database Storage**: Store all processed results in MongoDB
7. **Frontend Trigger**: Single button to initiate entire workflow

### UseCase 2: Targeted Re-scraping
1. **Gap Identification**: User identifies missing entities from diff analysis
2. **Targeted Scraping**: Scrape only EU sources with new keywords
3. **AI Processing**: Follow same AI pipeline (summarize → store → display)
4. **Frontend Integration**: Show results organized by source

## Database Design (MongoDB)

### Collections Schema

```javascript
// Collection: collection_runs
{
  "_id": ObjectId,
  "run_id": "run_20250624_153000", // Unique identifier
  "run_type": "full_collection" | "targeted_scraping",
  "status": "running" | "completed" | "failed",
  "triggered_at": ISODate,
  "completed_at": ISODate,
  "parameters": {
    "keywords": ["fenerbahce", "mourinho"],
    "regions": ["TR", "EU"],
    "targeted_keyword": "vlahovic", // For UseCase2 only
    "targeted_region": "EU" // For UseCase2 only
  },
  "statistics": {
    "total_sources_scraped": 11,
    "tr_articles": 45,
    "eu_articles": 67,
    "processing_time_seconds": 245
  }
}

// Collection: ai_summaries_per_source
{
  "_id": ObjectId,
  "run_id": "run_20250624_153000",
  "source_domain": "www_fanatik_com",
  "source_url": "https://www.fanatik.com.tr",
  "region": "TR" | "EU",
  "summary_data": {
    // Complete ai_summarized_www_fanatik_com.json content
    "processing_summary": {...},
    "processed_articles": [...],
    "source_metadata": {...}
  },
  "raw_session_file": "session_data_fanatik_com_tr.json", // Reference only
  "articles_count": 12,
  "processing_time_seconds": 45,
  "created_at": ISODate
}

// Collection: ai_aggregated_results
{
  "_id": ObjectId,
  "run_id": "run_20250624_153000",
  "region": "TR" | "EU",
  "aggregation_type": "scraped_only" | "extended_with_newsapi",
  "aggregated_data": {
    // Complete ai_summarized_tr.json or ai_summarized_eu_extended.json content
    "processing_summary": {...},
    "processed_articles": [...],
    "aggregation_metadata": {...}
  },
  "source_count": 5,
  "total_articles": 67,
  "sources_included": ["www_fanatik_com", "www_fotomac_com"],
  "newsapi_articles_added": 23, // Only for extended type
  "created_at": ISODate
}

// Collection: ai_diff_results
{
  "_id": ObjectId,
  "run_id": "run_20250624_153000",
  "comparison": {
    "eu_file_id": ObjectId, // Reference to ai_aggregated_results
    "tr_file_id": ObjectId
  },
  "diff_analysis": {
    // AI-generated diff analysis
    "entities_in_eu_only": ["vlahovic", "kimmich"],
    "entities_in_tr_only": ["yusuf_yazici"],
    "common_entities": [...],
    "trending_topics_diff": {...},
    "sentiment_analysis": {...}
  },
  "missing_entities_for_targeting": ["vlahovic", "kimmich"], // For UseCase2
  "created_at": ISODate
}

// Collection: newsapi_data
{
  "_id": ObjectId,
  "run_id": "run_20250624_153000",
  "fetch_timestamp": ISODate,
  "keywords_used": ["fenerbahce", "mourinho"],
  "raw_response": {...}, // Original NewsAPI response
  "transformed_articles": [...], // Converted to our schema
  "articles_count": 23,
  "api_quota_used": 100
}
```

## Architecture Components

### 1. Database Layer (`database/`)

#### `mongodb_client.py` (Enhanced)
```python
class MongoDBClient:
    # Connection Management
    async def connect() -> bool
    async def disconnect()
    async def ensure_indexes()
    
    # Collection Runs
    async def create_collection_run(run_data: Dict) -> str
    async def update_run_status(run_id: str, status: str, stats: Dict = None) -> bool
    async def get_run(run_id: str) -> Optional[Dict]
    async def get_latest_run(run_type: str = None) -> Optional[Dict]
    async def list_runs(limit: int = 10) -> List[Dict]
    
    # Source Summaries
    async def save_source_summary(summary_data: Dict) -> str
    async def get_source_summaries(run_id: str, region: str = None) -> List[Dict]
    async def get_source_summary(run_id: str, source_domain: str) -> Optional[Dict]
    
    # Aggregated Results
    async def save_aggregated_result(aggregated_data: Dict) -> str
    async def get_aggregated_result(run_id: str, region: str, type: str) -> Optional[Dict]
    
    # Diff Results
    async def save_diff_result(diff_data: Dict) -> str
    async def get_diff_result(run_id: str) -> Optional[Dict]
    
    # NewsAPI Data
    async def save_newsapi_data(newsapi_data: Dict) -> str
    async def get_newsapi_data(run_id: str) -> Optional[Dict]
    
    # Queries for Frontend
    async def get_articles_by_source(run_id: str, source_domain: str) -> List[Dict]
    async def search_articles(query: str, run_id: str = None) -> List[Dict]
    async def get_missing_entities(run_id: str) -> List[str]
```

### 2. AI Processing Layer (`capabilities/`)

#### `ai_aggregator.py` (New)
```python
class AIAggregator:
    def __init__(self, google_api_key: str, mongodb_client: MongoDBClient)
    
    # Main workflows
    async def aggregate_by_region(run_id: str, region: str) -> Dict
    async def extend_eu_with_newsapi(run_id: str, newsapi_data: Dict) -> Dict
    async def generate_diff_analysis(run_id: str) -> Dict
    
    # AI prompt generation
    def _create_aggregation_prompt(source_summaries: List[Dict], region: str) -> str
    def _create_extension_prompt(eu_data: Dict, newsapi_data: Dict) -> str
    def _create_diff_prompt(eu_extended: Dict, tr_data: Dict) -> str
    
    # AI processing
    async def _run_ai_processing(prompt: str, operation_type: str) -> Dict
```

#### `ai_summarizer.py` (Keep existing)
- Maintain current `summarize_and_classify_session_data_object()` method
- Used by orchestrator for processing individual source session files

### 3. Data Integration Layer (`integrations/`)

#### `newsapi_service.py` (New)
```python
class NewsAPIService:
    def __init__(self, api_key: str)
    
    async def fetch_news(keywords: List[str], sources: List[str] = None) -> Dict
    def transform_to_schema(newsapi_response: Dict) -> Dict
    def validate_quota() -> bool
```

### 4. Orchestration Layer (`capabilities/`)

#### `collection_orchestrator.py` (New)
```python
class CollectionOrchestrator:
    def __init__(self, mongodb_client: MongoDBClient, ai_aggregator: AIAggregator, 
                 newsapi_service: NewsAPIService)
    
    # UseCase 1: Full Collection
    async def run_full_collection(keywords: List[str]) -> str:
        """
        1. Create collection run in MongoDB
        2. Trigger parallel scraping (TR + EU sources)
        3. Process each source with AI → save to MongoDB
        4. Aggregate by region → save to MongoDB  
        5. Extend EU with NewsAPI → save to MongoDB
        6. Generate diff analysis → save to MongoDB
        7. Update run status to completed
        """
    
    # UseCase 2: Targeted Scraping
    async def run_targeted_scraping(target_keywords: List[str], region: str = "EU") -> str:
        """
        1. Create targeted run in MongoDB
        2. Scrape only specified region with new keywords
        3. Process with AI → save to MongoDB
        4. Return results for frontend display
        """
    
    # Helper methods
    async def _scrape_sources(params: Dict, region: str) -> List[str]  # Returns session file paths
    async def _process_session_files(session_files: List[str], run_id: str) -> List[str]  # Returns summary IDs
    async def _cleanup_temp_files(session_files: List[str])
```

### 5. API Layer (`api/endpoints/`)

#### `collection_endpoints.py` (New)
```python
@collection_blueprint.route('/run', methods=['POST'])
async def start_full_collection():
    """
    POST /api/collection/run
    Body: {
        "keywords": ["fenerbahce", "mourinho"]
    }
    Returns: {"run_id": "run_20250624_153000", "status": "started"}
    """

@collection_blueprint.route('/targeted', methods=['POST'])
async def start_targeted_scraping():
    """
    POST /api/collection/targeted  
    Body: {
        "target_keywords": ["vlahovic"],
        "region": "EU",
        "base_keywords": ["fenerbahce"] # Optional
    }
    Returns: {"run_id": "run_20250624_153001", "status": "started"}
    """

@collection_blueprint.route('/status/<run_id>', methods=['GET'])
async def get_collection_status(run_id: str):
    """Get real-time status of collection run"""

@collection_blueprint.route('/runs', methods=['GET'])
async def list_collection_runs():
    """List recent collection runs with summary"""
```

#### `results_endpoints.py` (New)
```python
@results_blueprint.route('/latest', methods=['GET'])
async def get_latest_results():
    """Get latest collection results summary"""

@results_blueprint.route('/run/<run_id>', methods=['GET'])
async def get_run_results(run_id: str):
    """Get complete results for specific run"""

@results_blueprint.route('/diff/<run_id>', methods=['GET'])  
async def get_diff_analysis(run_id: str):
    """Get diff analysis results"""

@results_blueprint.route('/sources/<run_id>', methods=['GET'])
async def get_source_breakdown(run_id: str):
    """Get results broken down by source"""

@results_blueprint.route('/articles/search', methods=['POST'])
async def search_articles():
    """Search articles across runs"""

@results_blueprint.route('/missing-entities/<run_id>', methods=['GET'])
async def get_missing_entities(run_id: str):
    """Get entities for targeted scraping (UseCase2)"""
```

### 6. Configuration (`helpers/config/`)

#### Update `main.py`
```python
# Add MongoDB configuration
app.config['MONGODB_URI'] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
app.config['MONGODB_DATABASE'] = os.getenv('MONGODB_DATABASE', 'aisports')

# Add NewsAPI configuration  
app.config['NEWSAPI_KEY'] = os.getenv('NEWSAPI_KEY')
app.config['NEWSAPI_SOURCES'] = ['bbc-sport', 'espn', 'four-four-two']

# Add collection settings
app.config['MAX_CONCURRENT_SCRAPING'] = int(os.getenv('MAX_CONCURRENT_SCRAPING', '5'))
app.config['CLEANUP_TEMP_FILES'] = os.getenv('CLEANUP_TEMP_FILES', 'true').lower() == 'true'
```

## Data Flow

### Full Collection Workflow
```
Frontend Button Click
    ↓
POST /api/collection/run
    ↓
CollectionOrchestrator.run_full_collection()
    ↓
1. Create run record in MongoDB
2. Parallel scraping (TR + EU sources) 
3. For each session file:
   - AI summarization → save to ai_summaries_per_source
4. AI aggregation by region → save to ai_aggregated_results  
5. Extend EU with NewsAPI → save to ai_aggregated_results
6. AI diff analysis → save to ai_diff_results
7. Update run status → completed
    ↓
Frontend polls /api/collection/status/{run_id}
    ↓
Frontend displays results via /api/results/run/{run_id}
```

### Targeted Scraping Workflow
```
User clicks missing entity from diff
    ↓
POST /api/collection/targeted
    ↓
CollectionOrchestrator.run_targeted_scraping()
    ↓
1. Create targeted run record
2. Scrape EU sources with new keywords
3. AI summarization per source → save to MongoDB
4. Return results for immediate display
    ↓
Frontend shows source-by-source results
```

## File Structure

```
aisports/
├── database/
│   └── mongodb_client.py (enhanced)
├── capabilities/
│   ├── ai_summarizer.py (existing)
│   ├── ai_aggregator.py (new)
│   └── collection_orchestrator.py (new)
├── integrations/
│   └── newsapi_service.py (new)
├── api/endpoints/
│   ├── collection_endpoints.py (new)
│   └── results_endpoints.py (new)
├── helpers/config/
│   └── main.py (updated)
└── .env (updated with MongoDB and NewsAPI config)
```

## Implementation Phases

### Phase 1: Database Foundation
1. Enhance `mongodb_client.py` with all required methods
2. Create database indexes for performance
3. Add connection management and error handling
4. Create test scripts for database operations

### Phase 2: AI Processing Components  
1. Create `ai_aggregator.py` with AI prompt generation
2. Create `newsapi_service.py` for data integration
3. Test AI aggregation with sample data
4. Validate schema transformations

### Phase 3: Orchestration Layer
1. Create `collection_orchestrator.py` 
2. Implement full collection workflow
3. Implement targeted scraping workflow
4. Add comprehensive error handling and logging

### Phase 4: API Endpoints
1. Create collection endpoints
2. Create results endpoints  
3. Add input validation and error responses
4. Create API documentation

### Phase 5: Integration & Testing
1. End-to-end testing of both use cases
2. Performance optimization
3. Error scenarios testing
4. Frontend integration points

## Dependencies

### New Python Packages
```
pymongo>=4.6.0
motor>=3.3.0  # Async MongoDB driver
```

### Environment Variables
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=aisports
NEWSAPI_KEY=your_newsapi_key
MAX_CONCURRENT_SCRAPING=5
CLEANUP_TEMP_FILES=true
```

## Notes

- **No Backward Compatibility**: This is a complete rewrite focused on the new workflow
- **Raw Data**: Journalist session files are temporary and not stored in MongoDB
- **AI-First**: All processing steps use AI for intelligent content handling
- **Scalable**: Designed to handle multiple concurrent collection runs
- **Frontend Ready**: API structure supports real-time status updates and flexible data access
