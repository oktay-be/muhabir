# filepath: c:\Users\oktay\Documents\aisports\api_client_scrape.py
import asyncio
import json
import aiohttp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
SERVER_BASE_URL = "http://localhost:5000/api"
SCRAPE_ENDPOINT = f"{SERVER_BASE_URL}/scrape"
PARAMETERS_FILE = "search_parameters.json"

async def fetch_data(session, url, payload):
    """Helper function to make a POST request and return JSON data."""
    try:
        async with session.post(url, json=payload) as response:
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = await response.json()
            logging.info(f"Successfully fetched data from {url} with payload {payload}")
            return data
    except aiohttp.ClientResponseError as e:
        logging.error(f"HTTP error fetching {url}: {e.status} {e.message} - Server response: {await response.text()}")
    except aiohttp.ClientConnectionError as e:
        logging.error(f"Connection error fetching {url}: {e}")
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON response from {url}")
    except Exception as e:
        logging.error(f"An unexpected error occurred fetching {url}: {e}")
    return None

async def main():
    """Main function to load parameters, call the scrape API endpoint, and print results."""
    try:
        with open(PARAMETERS_FILE, 'r', encoding='utf-8') as f:
            params = json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: {PARAMETERS_FILE} not found.")
        return
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {PARAMETERS_FILE}.")
        return

    scrape_urls = params.get("scrape_urls", [])
    keywords = params.get("keywords", [])

    all_results = []

    async with aiohttp.ClientSession() as session:
        tasks = []

        # Call /api/scrape
        if scrape_urls and keywords:
            scrape_payload = {
                "urls": scrape_urls,
                "keywords": keywords
            }
            logging.info(f"Preparing to call /api/scrape with payload: {scrape_payload}")
            tasks.append(fetch_data(session, SCRAPE_ENDPOINT, scrape_payload))
        elif not scrape_urls:
            logging.warning("No scrape_urls found in parameters file for /api/scrape endpoint.")
        elif not keywords:
            logging.warning("No keywords found in parameters file for /api/scrape endpoint (needed for filtering).")

        if not tasks:
            logging.warning("No tasks to run. Check your parameters file for scrape_urls and keywords.")
            return

        results = await asyncio.gather(*tasks)

        for result_item in results: # Changed variable name for clarity as we expect a single task result
            if result_item and isinstance(result_item, list):
                all_results.extend(result_item)
            elif result_item: # Handles cases where the API might return a single object or error structure
                logging.warning(f"Received non-list result from scrape endpoint: {result_item}")
                # Depending on expected error structure, you might want to append or handle differently
                # For now, if it's a dict (e.g. a single article or an error message), let's add it.
                if isinstance(result_item, dict):
                    all_results.append(result_item)


    if all_results:
        logging.info(f"Total articles/items fetched: {len(all_results)}")
        # Optionally, print all results or a summary
        # for i, item in enumerate(all_results):
        #     print(f"--- Item {i+1} ---")
        #     print(f"  Title: {item.get('title')}")
        #     print(f"  Body: {item.get('body', '')[:100]}...") # Print first 100 chars of body
        #     print(f"  Source: {item.get('source')}")
        
        # Save to a file
        output_filename = "client_output.json"
        with open(output_filename, 'w', encoding='utf-8') as outfile: # Added encoding
            json.dump(all_results, outfile, ensure_ascii=False, indent=2)
        logging.info(f"All results saved to {output_filename}")
    else:
        logging.info("No results fetched from any endpoint.")

if __name__ == "__main__":
    asyncio.run(main())
