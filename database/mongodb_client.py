"""
MongoDB client for AISports application.
Handles all database operations for the news collection and AI processing workflow.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import os

# Try to import pymongo, handle gracefully if not installed
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, DuplicateKeyError
    from bson import ObjectId
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    # Define dummy classes for type hints when pymongo is not available
    class MongoClient: pass
    class ConnectionFailure(Exception): pass
    class DuplicateKeyError(Exception): pass
    class ObjectId: pass
    ASCENDING = 1
    DESCENDING = -1

logger = logging.getLogger(__name__)

class MongoDBClient:
    """
    MongoDB client for AISports application.
    Manages connections and operations for all collections.
    """
    
    def __init__(self, connection_string: str = None, database_name: str = "aisports"):
        """
        Initialize MongoDB client.
        
        Args:
            connection_string: MongoDB connection URI
            database_name: Database name to use
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError("pymongo is required but not installed. Install with: pip install pymongo")
            
        self.connection_string = connection_string or os.getenv(
            "MONGODB_URI", 
            "mongodb://localhost:27017"
        )
        self.database_name = database_name
        self.client = None
        self.db = None
        
        # Collection names
        self.COLLECTION_RUNS = "collection_runs"
        self.AI_SUMMARIES_PER_SOURCE = "ai_summaries_per_source"
        self.AI_AGGREGATED_RESULTS = "ai_aggregated_results"
        self.AI_DIFF_RESULTS = "ai_diff_results"
        self.NEWSAPI_DATA = "newsapi_data"
    
    async def connect(self) -> bool:
        """
        Connect to MongoDB and ensure database setup.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = MongoClient(self.connection_string)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            
            # Ensure indexes
            await self.ensure_indexes()
            
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            return True
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def ensure_indexes(self):
        """Create necessary indexes for performance."""
        try:
            # Collection runs indexes
            self.db[self.COLLECTION_RUNS].create_index([
                ("run_id", ASCENDING)
            ], unique=True)
            self.db[self.COLLECTION_RUNS].create_index([
                ("created_at", DESCENDING)
            ])
            self.db[self.COLLECTION_RUNS].create_index([
                ("run_type", ASCENDING),
                ("status", ASCENDING)
            ])
            
            # AI summaries per source indexes
            self.db[self.AI_SUMMARIES_PER_SOURCE].create_index([
                ("run_id", ASCENDING),
                ("source_domain", ASCENDING)
            ])
            self.db[self.AI_SUMMARIES_PER_SOURCE].create_index([
                ("region", ASCENDING),
                ("created_at", DESCENDING)
            ])
            
            # AI aggregated results indexes
            self.db[self.AI_AGGREGATED_RESULTS].create_index([
                ("run_id", ASCENDING),
                ("region", ASCENDING),
                ("aggregation_type", ASCENDING)
            ])
            
            # AI diff results indexes
            self.db[self.AI_DIFF_RESULTS].create_index([
                ("run_id", ASCENDING)
            ])
            
            # NewsAPI data indexes
            self.db[self.NEWSAPI_DATA].create_index([
                ("run_id", ASCENDING)
            ])
            self.db[self.NEWSAPI_DATA].create_index([
                ("fetch_timestamp", DESCENDING)
            ])
            
            logger.info("MongoDB indexes ensured")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    # Collection Runs Operations
    async def save_collection_run(self, run_data: Dict) -> str:
        """
        Save collection run metadata.
        
        Args:
            run_data: Collection run data
            
        Returns:
            str: run_id of saved record
        """
        try:
            run_data["created_at"] = datetime.now(timezone.utc)
            result = self.db[self.COLLECTION_RUNS].insert_one(run_data)
            logger.info(f"Saved collection run: {run_data['run_id']}")
            return run_data['run_id']
            
        except DuplicateKeyError:
            logger.warning(f"Collection run already exists: {run_data['run_id']}")
            return run_data['run_id']
        except Exception as e:
            logger.error(f"Error saving collection run: {e}")
            raise
    
    async def update_collection_run_status(self, run_id: str, status: str, stats: Dict = None) -> bool:
        """
        Update collection run status and stats.
        
        Args:
            run_id: Collection run identifier
            status: New status ("running", "completed", "failed")
            stats: Optional stats to update
            
        Returns:
            bool: True if update successful
        """
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now(timezone.utc)
            }
            
            if status == "completed":
                update_data["completed_at"] = datetime.now(timezone.utc)
            
            if stats:
                update_data["stats"] = stats
            
            result = self.db[self.COLLECTION_RUNS].update_one(
                {"run_id": run_id},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating collection run status: {e}")
            return False
    
    async def get_collection_run(self, run_id: str) -> Optional[Dict]:
        """Get collection run by ID."""
        try:
            return self.db[self.COLLECTION_RUNS].find_one({"run_id": run_id})
        except Exception as e:
            logger.error(f"Error getting collection run: {e}")
            return None
    
    async def get_latest_run(self, run_type: str = None) -> Optional[Dict]:
        """Get latest collection run, optionally filtered by type."""
        try:
            query = {}
            if run_type:
                query["run_type"] = run_type
            
            return self.db[self.COLLECTION_RUNS].find_one(
                query, 
                sort=[("created_at", DESCENDING)]
            )
        except Exception as e:
            logger.error(f"Error getting latest run: {e}")
            return None
    
    # AI Summaries Per Source Operations
    async def save_source_summary(self, summary_data: Dict) -> str:
        """
        Save AI summary for specific source.
        
        Args:
            summary_data: Source summary data
            
        Returns:
            str: ObjectId of saved record
        """
        try:
            summary_data["created_at"] = datetime.now(timezone.utc)
            result = self.db[self.AI_SUMMARIES_PER_SOURCE].insert_one(summary_data)
            logger.info(f"Saved source summary: {summary_data['source_domain']} for run {summary_data['run_id']}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error saving source summary: {e}")
            raise
    
    async def get_run_summaries(self, run_id: str, region: str = None) -> List[Dict]:
        """Get all source summaries for a run, optionally filtered by region."""
        try:
            query = {"run_id": run_id}
            if region:
                query["region"] = region
            
            return list(self.db[self.AI_SUMMARIES_PER_SOURCE].find(query))
        except Exception as e:
            logger.error(f"Error getting run summaries: {e}")
            return []
    
    # AI Aggregated Results Operations
    async def save_aggregated_result(self, aggregated_data: Dict) -> str:
        """
        Save regional aggregation result.
        
        Args:
            aggregated_data: Aggregated data
            
        Returns:
            str: ObjectId of saved record
        """
        try:
            aggregated_data["created_at"] = datetime.now(timezone.utc)
            result = self.db[self.AI_AGGREGATED_RESULTS].insert_one(aggregated_data)
            logger.info(f"Saved aggregated result: {aggregated_data['region']} for run {aggregated_data['run_id']}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error saving aggregated result: {e}")
            raise
    
    async def get_aggregated_result(self, run_id: str, region: str, aggregation_type: str = "scraped_only") -> Optional[Dict]:
        """Get aggregated result for region and type."""
        try:
            return self.db[self.AI_AGGREGATED_RESULTS].find_one({
                "run_id": run_id,
                "region": region,
                "aggregation_type": aggregation_type
            })
        except Exception as e:
            logger.error(f"Error getting aggregated result: {e}")
            return None
    
    # AI Diff Results Operations
    async def save_diff_result(self, diff_data: Dict) -> str:
        """
        Save AI diff analysis result.
        
        Args:
            diff_data: Diff analysis data
            
        Returns:
            str: ObjectId of saved record
        """
        try:
            diff_data["created_at"] = datetime.now(timezone.utc)
            result = self.db[self.AI_DIFF_RESULTS].insert_one(diff_data)
            logger.info(f"Saved diff result for run {diff_data['run_id']}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error saving diff result: {e}")
            raise
    
    async def get_diff_result(self, run_id: str) -> Optional[Dict]:
        """Get diff analysis result for run."""
        try:
            return self.db[self.AI_DIFF_RESULTS].find_one({"run_id": run_id})
        except Exception as e:
            logger.error(f"Error getting diff result: {e}")
            return None
    
    # NewsAPI Data Operations
    async def save_newsapi_data(self, newsapi_data: Dict) -> str:
        """
        Save NewsAPI fetched data.
        
        Args:
            newsapi_data: NewsAPI data
            
        Returns:
            str: ObjectId of saved record
        """
        try:
            newsapi_data["fetch_timestamp"] = datetime.now(timezone.utc)
            result = self.db[self.NEWSAPI_DATA].insert_one(newsapi_data)
            logger.info(f"Saved NewsAPI data for run {newsapi_data['run_id']}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error saving NewsAPI data: {e}")
            raise
    
    async def get_newsapi_data(self, run_id: str) -> Optional[Dict]:
        """Get NewsAPI data for run."""
        try:
            return self.db[self.NEWSAPI_DATA].find_one({"run_id": run_id})
        except Exception as e:
            logger.error(f"Error getting NewsAPI data: {e}")
            return None
    
    # Utility Methods
    async def get_missing_entities(self, run_id: str) -> List[str]:
        """Get entities found in EU but missing in TR for targeting."""
        try:
            diff_result = await self.get_diff_result(run_id)
            if diff_result and "diff_analysis" in diff_result:
                return diff_result["diff_analysis"].get("entities_in_eu_only", [])
            return []
        except Exception as e:
            logger.error(f"Error getting missing entities: {e}")
            return []
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict:
        """
        Clean up old collection data.
        
        Args:
            days_to_keep: Number of days to keep data
            
        Returns:
            Dict: Cleanup statistics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            # Count documents to be deleted
            old_runs = self.db[self.COLLECTION_RUNS].count_documents({
                "created_at": {"$lt": cutoff_date}
            })
            
            # Get run_ids to delete associated data
            old_run_ids = [
                doc["run_id"] for doc in self.db[self.COLLECTION_RUNS].find(
                    {"created_at": {"$lt": cutoff_date}},
                    {"run_id": 1}
                )
            ]
            
            # Delete associated data
            summaries_deleted = self.db[self.AI_SUMMARIES_PER_SOURCE].delete_many({
                "run_id": {"$in": old_run_ids}
            }).deleted_count
            
            aggregated_deleted = self.db[self.AI_AGGREGATED_RESULTS].delete_many({
                "run_id": {"$in": old_run_ids}
            }).deleted_count
            
            diff_deleted = self.db[self.AI_DIFF_RESULTS].delete_many({
                "run_id": {"$in": old_run_ids}
            }).deleted_count
            
            newsapi_deleted = self.db[self.NEWSAPI_DATA].delete_many({
                "run_id": {"$in": old_run_ids}
            }).deleted_count
            
            # Delete old runs
            runs_deleted = self.db[self.COLLECTION_RUNS].delete_many({
                "created_at": {"$lt": cutoff_date}
            }).deleted_count
            
            cleanup_stats = {
                "runs_deleted": runs_deleted,
                "summaries_deleted": summaries_deleted,
                "aggregated_deleted": aggregated_deleted,
                "diff_deleted": diff_deleted,
                "newsapi_deleted": newsapi_deleted,
                "cutoff_date": cutoff_date.isoformat()
            }
            
            logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {"error": str(e)}


# Singleton instance for global use
_mongodb_client = None

async def get_mongodb_client() -> MongoDBClient:
    """Get singleton MongoDB client instance."""
    global _mongodb_client
    
    if _mongodb_client is None:
        _mongodb_client = MongoDBClient()
        if not await _mongodb_client.connect():
            raise ConnectionFailure("Failed to connect to MongoDB")
    
    return _mongodb_client


# Example usage and testing
async def test_mongodb_client():
    """Test MongoDB client functionality."""
    print("🧪 Testing MongoDB Client...")
    
    try:
        # Initialize client
        client = MongoDBClient()
        connected = await client.connect()
        
        if not connected:
            print("❌ Failed to connect to MongoDB")
            return
        
        print("✅ Connected to MongoDB successfully")
        
        # Test collection run operations
        run_data = {
            "run_id": f"test_run_{int(datetime.now().timestamp())}",
            "run_type": "full_collection",
            "status": "running",
            "parameters": {
                "keywords": ["fenerbahce", "test"],
                "regions": ["TR", "EU"]
            }
        }
        
        run_id = await client.save_collection_run(run_data)
        print(f"✅ Saved collection run: {run_id}")
        
        # Test source summary
        summary_data = {
            "run_id": run_id,
            "source_domain": "www_test_com",
            "region": "TR",
            "summary_data": {
                "processing_summary": {"total_articles": 10},
                "processed_articles": []
            }
        }
        
        summary_id = await client.save_source_summary(summary_data)
        print(f"✅ Saved source summary: {summary_id}")
        
        # Test queries
        latest_run = await client.get_latest_run()
        print(f"✅ Latest run: {latest_run['run_id'] if latest_run else 'None'}")
        
        summaries = await client.get_run_summaries(run_id)
        print(f"✅ Run summaries count: {len(summaries)}")
        
        # Update run status
        updated = await client.update_collection_run_status(
            run_id, 
            "completed", 
            {"total_articles": 10}
        )
        print(f"✅ Updated run status: {updated}")
        
        await client.disconnect()
        print("✅ MongoDB client test completed successfully")
        
    except Exception as e:
        print(f"❌ MongoDB client test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mongodb_client())
