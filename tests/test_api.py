"""
Integration tests for the API endpoints.
"""
import json
import sys
import os
import pytest
from unittest.mock import patch

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app


@pytest.fixture
def client():
    """Create a test client for the app."""
    app = create_app('testing')
    with app.test_client() as test_client:
        yield test_client

@patch('capabilities.news_aggregator.NewsAggregator.get_news')
def test_get_news(mock_get_news, client):
    """Test the /api/news endpoint."""
    # Mock the response from the news aggregator
    mock_news = [
        {
            "title": "Fenerbahçe wins important match",
            "url": "https://example.com/news/1",
            "source": "Example News",
            "published_at": "2025-05-24T12:00:00Z",
            "content": "Fenerbahçe won an important match yesterday."
        }
    ]
    mock_get_news.return_value = mock_news
    
    response = client.post('/api/news/simple', 
                               json={"query": "fenerbahçe", "limit": 1})
    
    # Check the response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['news']) == 1
    assert data['news'][0]['title'] == mock_news[0]['title']
    assert data['status'] == 'success'

@patch('capabilities.trends_analyzer.TrendsAnalyzer.get_trending_topics')
def test_get_trending(mock_get_trending, client):
    """Test the /api/trending endpoint."""
    # Mock the response from the trends analyzer
    mock_trending = [
        {"name": "Fenerbahçe", "tweet_volume": 1000, "relevance_score": 1.0, "related_keywords": []},
        {"name": "Galatasaray", "tweet_volume": 800, "relevance_score": 1.0, "related_keywords": []},
        {"name": "Beşiktaş", "tweet_volume": 600, "relevance_score": 1.0, "related_keywords": []}
    ]
    mock_get_trending.return_value = mock_trending
    
    response = client.post('/api/trending', 
                               json={"keywords": ["Turkey", "Football"], "limit": 3})
    
    # Check the response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['topics']) == 3
    assert data['topics'][0]['name'] == mock_trending[0]['name']
    assert data['count'] == 3

@patch('capabilities.web_scraper.WebScraper.scrape_urls')
def test_scrape_news(mock_scrape_urls, client):
    """Test the /api/scrape endpoint."""
    # Mock the response from the web scraper
    mock_scraped = [
        {
            "url": "https://example.com/news/1",
            "content": "Detailed content of Fenerbahçe's win.",
            "title": "Fenerbahçe wins important match",
            "error": None
        }
    ]
    mock_scrape_urls.return_value = mock_scraped
    
    response = client.post('/api/scrape', 
                               json={"urls": ["https://example.com/news/1"]})
    
    # Check the response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['scraped_data']) == 1
    assert data['scraped_data'][0]['url'] == mock_scraped[0]['url']
    assert data['scraped_data'][0]['content'] == mock_scraped[0]['content']
    assert data['status'] == 'success'
