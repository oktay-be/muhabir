#!/usr/bin/env python3
"""
Debug script to test different NewsAPI parameter combinations
to identify why server params fail while client params work.
"""

import requests
import json
from datetime import datetime, timedelta

API_KEY = '7d518cdcc9ca4ccba0040eaf1e6334af'
BASE_URL = "https://newsapi.org/v2/everything"

def test_newsapi_params(params, description):
    """Test NewsAPI with given parameters"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"{'='*60}")
    
    # Add API key to params
    test_params = params.copy()
    test_params['apiKey'] = API_KEY
    
    # Print parameters
    print("Parameters:")
    for key, value in test_params.items():
        print(f"  {key}: {value}")
    
    try:
        response = requests.get(BASE_URL, params=test_params)
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total Results: {data.get('totalResults', 0)}")
            print(f"Articles Returned: {len(data.get('articles', []))}")
            
            # Show first article title if available
            articles = data.get('articles', [])
            if articles:
                print(f"First Article: {articles[0].get('title', 'No title')}")
                print(f"Source: {articles[0].get('source', {}).get('name', 'Unknown')}")
            else:
                print("No articles returned")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {str(e)}")

def main():
    # Generate date range (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    from_date = start_date.isoformat()
    to_date = end_date.isoformat()
    
    # Working client params
    client_params = {
        'q': 'fenerbahce OR Mourinho',
        'language': 'en',
        'from': from_date,
        'to': to_date,
        'pageSize': 10,
        'sortBy': 'publishedAt',
        'searchIn': 'title,description'
    }
    
    # Non-working server params
    server_params = {
        'q': 'Fenerbahce OR Mourinho OR Galatasaray',
        'language': 'en,tr',
        'from': from_date,
        'to': to_date,
        'pageSize': 100
    }
    
    # Test original configurations
    test_newsapi_params(client_params, "Original Client Params (Working)")
    test_newsapi_params(server_params, "Original Server Params (Not Working)")
    
    # Test individual differences
    print("\n" + "="*80)
    print("TESTING INDIVIDUAL DIFFERENCES")
    print("="*80)
    
    # Test 1: Server params with single language
    server_single_lang = server_params.copy()
    server_single_lang['language'] = 'en'
    test_newsapi_params(server_single_lang, "Server Params + Single Language")
    
    # Test 2: Server params with added sortBy
    server_with_sort = server_params.copy()
    server_with_sort['sortBy'] = 'publishedAt'
    test_newsapi_params(server_with_sort, "Server Params + sortBy")
    
    # Test 3: Server params with added searchIn
    server_with_search = server_params.copy()
    server_with_search['searchIn'] = 'title,description'
    test_newsapi_params(server_with_search, "Server Params + searchIn")
    
    # Test 4: Server params with smaller pageSize
    server_small_page = server_params.copy()
    server_small_page['pageSize'] = 10
    test_newsapi_params(server_small_page, "Server Params + Small pageSize")
    
    # Test 5: Server params with client query
    server_client_query = server_params.copy()
    server_client_query['q'] = 'fenerbahce OR Mourinho'
    test_newsapi_params(server_client_query, "Server Params + Client Query")
    
    # Test 6: Server params with all client additions
    server_fixed = {
        'q': 'Fenerbahce OR Mourinho OR Galatasaray',
        'language': 'en',  # Single language
        'from': from_date,
        'to': to_date,
        'pageSize': 10,  # Smaller page size
        'sortBy': 'publishedAt',  # Added sortBy
        'searchIn': 'title,description'  # Added searchIn
    }
    test_newsapi_params(server_fixed, "Server Params with All Client Additions")

if __name__ == "__main__":
    main()
