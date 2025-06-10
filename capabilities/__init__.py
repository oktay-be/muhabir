"""
Init file for the capabilities package.
"""

from capabilities.news_aggregator import NewsAggregator
from capabilities.trends_analyzer import TrendsAnalyzer
from capabilities.scraping.web_scraper import WebScraper

__all__ = ['NewsAggregator', 'TrendsAnalyzer', 'WebScraper']
