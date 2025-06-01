"""
Unit tests for the news aggregator capability.
"""
import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add parent directory to path so we can import capabilities
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from capabilities.news_aggregator import NewsAggregator
from capabilities.trends_analyzer import TrendsAnalyzer
from capabilities.web_scraper import WebScraper


class TestNewsAggregator(unittest.TestCase):
    """Test the news aggregator capability."""

    @patch('requests.get')
    def test_get_news_from_api(self, mock_get):
        """Test fetching news from NewsAPI."""
        # Mock the response from the API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'articles': [
                {
                    'title': 'Test Article',
                    'url': 'https://example.com/test',
                    'source': {'name': 'Test Source'},
                    'publishedAt': '2025-05-24T10:00:00Z',
                    'content': 'This is a test article content.'
                }
            ]
        }
        mock_get.return_value = mock_response

        # Initialize the news aggregator
        aggregator = NewsAggregator(api_key='test_key')
        
        # Get news
        news = aggregator.get_news('test query', limit=1)
        
        # Verify the results
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]['title'], 'Test Article')
        self.assertEqual(news[0]['source'], 'Test Source')

    @patch('requests.get')
    def test_fetch_worldnewsapi_articles(self, mock_get):
        """Test fetching news from WorldNewsAPI."""
        # Mock the response from the API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'news': [
                {
                    'title': 'Test WorldNews Article',
                    'url': 'https://example.com/worldnews',
                    'source_name': 'Test WorldNews Source',
                    'publish_date': '2025-05-25T10:00:00Z',
                    'text': 'This is a test article from WorldNewsAPI.',
                    'image': 'https://example.com/image.jpg',
                    'sentiment': 0.75
                }
            ]
        }
        mock_get.return_value = mock_response

        # Initialize the news aggregator with WorldNewsAPI key
        aggregator = NewsAggregator(api_key='test_key', worldnewsapi_key='test_worldnews_key')
        
        # Get news
        news = aggregator.fetch_worldnewsapi_articles()
        
        # Verify the results
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]['title'], 'Test WorldNews Article')
        self.assertEqual(news[0]['source'], 'Test WorldNews Source')
        self.assertEqual(news[0]['sentiment'], 0.75)  # Check WorldNewsAPI specific field


class TestTrendsAnalyzer(unittest.TestCase):
    """Test the trends analyzer capability."""

    @patch('capabilities.trends_analyzer.TrendsAnalyzer._fetch_twitter_trends')
    def test_get_trending_topics(self, mock_fetch_trends):
        """Test getting trending topics."""
        # Mock the response from the Twitter API (or similar source)
        mock_fetch_trends.return_value = [
            {"name": "Fenerbahçe", "tweet_volume": 10000},
            {"name": "Galatasaray", "tweet_volume": 8000},
            {"name": "Beşiktaş", "tweet_volume": 7000}
        ]

        # Initialize the trends analyzer
        analyzer = TrendsAnalyzer()
        
        # Get trending topics
        topics = analyzer.get_trending_topics(limit=3)
        
        # Verify the results
        self.assertEqual(len(topics), 3)
        self.assertEqual(topics[0]['topic'], 'Fenerbahçe')
        self.assertEqual(topics[0]['count'], 10000)


class TestWebScraper(unittest.TestCase):
    """Test the web scraper capability."""

    @patch('requests.get')
    @patch('bs4.BeautifulSoup')
    def test_scrape_news(self, mock_soup, mock_get):
        """Test scraping news from a website."""
        # Mock the response from the website
        mock_response = MagicMock()
        mock_response.content = "<html><body><h1>Test Title</h1><p>Test Content</p></body></html>"
        mock_get.return_value = mock_response
        
        # Mock BeautifulSoup
        mock_title = MagicMock()
        mock_title.text = "Test Title"
        
        mock_content = MagicMock()
        mock_content.text = "Test Content"
        
        mock_soup_instance = MagicMock()
        mock_soup_instance.select.side_effect = lambda selector: [mock_title] if selector == 'h1' else [mock_content]
        
        mock_soup.return_value = mock_soup_instance

        # Initialize the web scraper
        scraper = WebScraper()
        
        # Scrape news
        news = scraper.scrape_news('https://example.com', {'title': 'h1', 'content': 'p'})
        
        # Verify the results
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]['title'], 'Test Title')
        self.assertEqual(news[0]['content'], 'Test Content')
        self.assertEqual(news[0]['source'], 'example.com')


if __name__ == '__main__':
    unittest.main()
