import asyncio
import json
import aiohttp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
SERVER_BASE_URL = "http://localhost:5000/api"
ANALYSIS_START_JOB_ENDPOINT = f"{SERVER_BASE_URL}/analysis/start_job"
ANALYSIS_JOB_STATUS_ENDPOINT = f"{SERVER_BASE_URL}/analysis/job_status" # Base for status checks
PARAMETERS_FILE = "search_parameters.json" # Assuming this might contain initial params

async def start_analysis_job(session, payload):
    """Helper function to make a POST request to start an analysis job."""
    try:
        logging.info(f"Attempting to start analysis job with payload: {payload}")
        async with session.post(ANALYSIS_START_JOB_ENDPOINT, json=payload) as response:
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = await response.json()
            logging.info(f"Successfully started analysis job: {data}")
            return data
    except aiohttp.ClientResponseError as e:
        logging.error(f"HTTP error starting analysis job: {e.status} {e.message} - Server response: {await response.text()}")
    except aiohttp.ClientConnectionError as e:
        logging.error(f"Connection error starting analysis job: {e}")
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON response from {ANALYSIS_START_JOB_ENDPOINT}")
    except Exception as e:
        logging.error(f"An unexpected error occurred starting analysis job: {e}")
    return None

async def get_job_status(session, session_id):
    """Helper function to get the status of an analysis job."""
    status_url = f"{ANALYSIS_JOB_STATUS_ENDPOINT}/{session_id}"
    try:
        logging.info(f"Checking status for job ID: {session_id} at {status_url}")
        async with session.get(status_url) as response:
            response.raise_for_status()
            data = await response.json()
            logging.info(f"Job status for {session_id}: {data}")
            return data
    except aiohttp.ClientResponseError as e:
        logging.error(f"HTTP error checking job status {session_id}: {e.status} {e.message} - Server response: {await response.text()}")
    except aiohttp.ClientConnectionError as e:
        logging.error(f"Connection error checking job status {session_id}: {e}")
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON response from {status_url}")
    except Exception as e:
        logging.error(f"An unexpected error occurred checking job status {session_id}: {e}")
    return None

async def main():
    """Main function to load parameters, call the analysis API, and monitor status."""
    try:
        with open(PARAMETERS_FILE, 'r', encoding='utf-8') as f:
            params = json.load(f)
    except FileNotFoundError:
        logging.warning(f"{PARAMETERS_FILE} not found. Using default/empty payload for analysis job.")
        params = {} # Allow running without params file, using defaults in API
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {PARAMETERS_FILE}. Using default/empty payload.")
        params = {}


    # Prepare payload for /analysis/start_job
    # These can be overridden by search_parameters.json
    analysis_payload = {
        "initial_keywords": params.get("initial_keywords_for_analysis", ["Fenerbahçe", "Beşiktaş", "Galatasaray", "Trabzonspor", "Süper Lig", "transfer"]),
        "initial_scrape_urls": params.get("initial_scrape_urls_for_analysis", [
            "https://www.fanatik.com.tr",
            "https://www.fotomac.com.tr",
            "https://www.sabah.com.tr/spor",
            "https://www.hurriyet.com.tr/spor"
        ]),
        "use_default_urls_keywords": params.get("use_default_urls_keywords_for_analysis", True)
    }

    async with aiohttp.ClientSession() as session:
        start_response = await start_analysis_job(session, analysis_payload)

        if start_response and start_response.get("session_id"):
            session_id = start_response["session_id"]
            logging.info(f"Analysis job started with session_id: {session_id}. Polling status...")

            # Polling for job status
            max_retries = 20  # Max number of status checks
            retry_delay = 30  # Seconds to wait between checks (e.g., 30 seconds)
            
            for i in range(max_retries):
                await asyncio.sleep(retry_delay)
                status_response = await get_job_status(session, session_id)

                if status_response:
                    current_status = status_response.get("status", "UNKNOWN").upper()
                    logging.info(f"Poll {i+1}/{max_retries} - Job {session_id} status: {current_status} - Details: {status_response.get('details')}")
                    
                    if current_status == "SUCCESS":
                        logging.info(f"Job {session_id} completed successfully.")
                        # Optionally, fetch and display results if an endpoint is available
                        break
                    elif current_status == "FAILED":
                        logging.error(f"Job {session_id} failed. Details: {status_response.get('error_info', 'No error details provided')}")
                        break
                    elif current_status == "UNKNOWN":
                        logging.warning(f"Job {session_id} status is UNKNOWN. This might indicate an issue.")
                else:
                    logging.warning(f"Could not retrieve status for job {session_id} on attempt {i+1}.")
                
                if i == max_retries - 1:
                    logging.warning(f"Max retries reached for job {session_id}. Last known status: {current_status if 'current_status' in locals() else 'N/A'}")
        else:
            logging.error("Failed to start analysis job or did not receive a session_id.")

if __name__ == "__main__":
    asyncio.run(main())
