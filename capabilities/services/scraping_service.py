"""
ScrapingService - Modern scraping service using journ4list library.
Replaces all custom scraping infrastructure.
"""

import asyncio
import os
import json
import logging
from typing import List, Dict, Any, Optional
from journalist import Journalist

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
            logger.info(f"Starting scraping with journ4list: {len(urls)} URLs, keywords: {keywords}")
            
            journalist = Journalist(persist=persist, scrape_depth=scrape_depth)
            
            result = await journalist.read(urls=urls, keywords=keywords)
            
            logger.info(f"Scraping completed. Session: {result['session_id']}, "
                       f"Articles: {len(result['articles'])}")
            
            return result
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}", exc_info=True)
            return {
                "session_id": None,
                "articles": [],
                "extraction_summary": {
                    "error": str(e),
                    "urls_processed": 0,
                    "articles_extracted": 0,
                    "extraction_time_seconds": 0.0
                }
            }
    
    async def scrape_simple(self, urls: List[str], persist: bool = True, 
                          scrape_depth: int = 1) -> Dict[str, Any]:
        """
        Simple scraping without keyword filtering.
        
        Args:
            urls: List of URLs to scrape
            persist: Whether to save session data to files
            scrape_depth: Depth level for link discovery
            
        Returns:
            Dict with articles and session metadata
        """
        try:
            logger.info(f"Starting simple scraping with journ4list: {len(urls)} URLs")
            
            journalist = Journalist(persist=persist, scrape_depth=scrape_depth)
            
            result = await journalist.read(urls=urls)
            
            logger.info(f"Simple scraping completed. Session: {result['session_id']}, "
                       f"Articles: {len(result['articles'])}")
            
            return result
            
        except Exception as e:
            logger.error(f"Simple scraping failed: {e}", exc_info=True)
            return {
                "session_id": None,
                "articles": [],
                "extraction_summary": {
                    "error": str(e),
                    "urls_processed": 0,
                    "articles_extracted": 0,
                    "extraction_time_seconds": 0.0
                }
            }
    
    def find_latest_session(self) -> Optional[str]:
        """Find the latest journ4list session file."""
        try:
            if not os.path.exists(self.workspace_dir):
                logger.warning(f"Workspace directory not found: {self.workspace_dir}")
                return None
                
            sessions = []
            for item in os.listdir(self.workspace_dir):
                item_path = os.path.join(self.workspace_dir, item)
                if os.path.isdir(item_path) and item.startswith("202"):
                    sessions.append(item)
            
            if not sessions:
                logger.warning(f"No session directories found in {self.workspace_dir}")
                return None
                
            sessions.sort(reverse=True)
            latest_session_dir = sessions[0]
            
            session_path = os.path.join(self.workspace_dir, latest_session_dir)
            session_files = []
            
            for file in os.listdir(session_path):
                if file.startswith("session_data") and file.endswith(".json"):
                    session_files.append(file)
            
            if not session_files:
                logger.warning(f"No session_data files found in {session_path}")
                return None
                
            session_files.sort(reverse=True)
            latest_file = session_files[0]
            
            full_path = os.path.join(session_path, latest_file)
            logger.info(f"Found latest session file: {full_path}")
            return full_path
                    
        except Exception as e:
            logger.error(f"Error finding latest session: {e}")
            return None
    
    def list_all_sessions(self) -> List[str]:
        """List all available session files."""
        try:
            if not os.path.exists(self.workspace_dir):
                return []
                
            session_files = []
            for session_dir in os.listdir(self.workspace_dir):
                session_path = os.path.join(self.workspace_dir, session_dir)
                if os.path.isdir(session_path) and session_dir.startswith("202"):
                    for file in os.listdir(session_path):
                        if file.startswith("session_data") and file.endswith(".json"):
                            session_files.append(os.path.join(session_path, file))
            
            session_files.sort(reverse=True)
            return session_files
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    def load_session_data(self, session_file_path: str) -> Optional[Dict[str, Any]]:
        """Load session data from file."""
        try:
            logger.info(f"Loading session data from: {session_file_path}")
            with open(session_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Successfully loaded session data with {len(data.get('articles', []))} articles")
            return data
        except Exception as e:
            logger.error(f"Error loading session data from {session_file_path}: {e}")
            return None
    
    def get_session_info(self, session_file_path: str) -> Dict[str, Any]:
        """Get basic information about a session without loading full data."""
        try:
            data = self.load_session_data(session_file_path)
            if not data:
                return {"error": "Failed to load session data"}
                
            return {
                "session_file": session_file_path,
                "session_id": data.get("session_metadata", {}).get("session_id"),
                "articles_count": len(data.get("articles", [])),
                "start_time": data.get("session_metadata", {}).get("start_time"),
                "end_time": data.get("session_metadata", {}).get("end_time"),
                "duration_seconds": data.get("session_metadata", {}).get("duration_seconds"),
                "success_rate": data.get("session_metadata", {}).get("success_rate", 0.0)
            }
            
        except Exception as e:
            return {"error": f"Error getting session info: {str(e)}"}
    
    def cleanup_old_sessions(self, keep_last_n: int = 5) -> Dict[str, Any]:
        """Clean up old session files, keeping only the most recent ones."""
        try:
            all_sessions = self.list_all_sessions()
            
            if len(all_sessions) <= keep_last_n:
                return {
                    "cleaned": False,
                    "reason": f"Only {len(all_sessions)} sessions found, keeping all",
                    "sessions_removed": 0
                }
            
            sessions_to_remove = all_sessions[keep_last_n:]
            removed_count = 0
            
            for session_file in sessions_to_remove:
                try:
                    # Remove the session file
                    os.remove(session_file)
                    removed_count += 1
                    
                    # Try to remove empty session directory
                    session_dir = os.path.dirname(session_file)
                    if os.path.exists(session_dir) and not os.listdir(session_dir):
                        os.rmdir(session_dir)
                        
                except Exception as e:
                    logger.warning(f"Failed to remove session file {session_file}: {e}")
            
            return {
                "cleaned": True,
                "sessions_removed": removed_count,
                "sessions_kept": keep_last_n,
                "total_sessions_before": len(all_sessions)
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {"error": f"Cleanup failed: {str(e)}"}
