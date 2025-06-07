import asyncio
import aiohttp
from datetime import datetime, timedelta

# Test the exact parameters that are now used in the fixed NewsAggregator
async def test_fixed_params():
    api_key = "7d518cdcc9ca4ccba0040eaf1e6334af"
    
    # These are the NEW parameters from the fixed NewsAggregator
    now = datetime.now()
    from_date = (now - timedelta(days=1)).isoformat()
    
    params = {
        "q": "Fenerbahce OR Mourinho", 
        "language": "en",  # Single language instead of "en,tr"
        "from": from_date,
        "to": now.isoformat(),
        "apiKey": api_key,
        "pageSize": 10,  # min(max_results, 10) - smaller pageSize
        "sortBy": "publishedAt",  # Added sortBy parameter
        "searchIn": "title,description"  # Added searchIn parameter
    }
    
    print("Testing FIXED NewsAPI parameters:")
    print(f"Query: {params['q']}")
    print(f"Language: {params['language']}")
    print(f"Page Size: {params['pageSize']}")
    print(f"Sort By: {params['sortBy']}")
    print(f"Search In: {params['searchIn']}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://newsapi.org/v2/everything", params=params) as response:
                print(f"\nResponse Status: {response.status}")
                data = await response.json()
                
                total = data.get("totalResults", 0)
                articles = data.get("articles", [])
                
                print(f"Total Results: {total}")
                print(f"Articles Returned: {len(articles)}")
                
                if articles:
                    print(f"\n✅ SUCCESS! First article:")
                    print(f"   Title: {articles[0].get('title')}")
                    print(f"   Source: {articles[0].get('source', {}).get('name')}")
                    return True
                else:
                    print("\n❌ No articles returned")
                    return False
                    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_fixed_params())
    if success:
        print("\n🎉 The NewsAPI parameter fix is working!")
    else:
        print("\n😞 The fix still has issues.")
