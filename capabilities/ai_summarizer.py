import asyncio
import logging
import os
import json
from typing import Dict, Any
import google.generativeai as genai
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class AISummarizer:
    """
    Uses Google's Generative AI (Gemini 2.5 Pro) to process European sports news session data.
    Provides a single focused method for summarizing and classifying journalist session data.
    """
    
    def __init__(self, google_api_key: str = None, model_name: str = "models/gemini-2.0-flash-exp"):
        """
        Initializes the AISummarizer with Google Generative AI.

        Args:
            google_api_key (str, optional): Google API key. If None, tries to get from
                                           GOOGLE_API_KEY environment variable.
            model_name (str, optional): The name of the Gemini model to use.
                                        Defaults to "models/gemini-2.0-flash-exp" (Gemini 2.5 Pro).
        """
        self.model = None
        api_key = google_api_key or os.getenv("GOOGLE_API_KEY")

        if not api_key:
            logger.error("Google API key (GOOGLE_API_KEY) is not set. Summarizer will not function.")
            return

        try:
            genai.configure(api_key=api_key)
            # Configuration for JSON output
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,  # Lower temperature for more consistent processing
                max_output_tokens=8192  # Ensure enough space for comprehensive output
            )
            self.model = genai.GenerativeModel(
                model_name,
                generation_config=generation_config
            )
            logger.info(f"AISummarizer initialized with Google GenAI model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI model: {e}", exc_info=True)
            self.model = None

    async def summarize_and_classify_session_data_object(self, session_data_file_path: str) -> Dict[str, Any]:
        """
        Processes a journalist session data file using the PROMPT.md instructions.
        
        Loads the session data file and PROMPT.md, combines them, and sends to Gemini 2.5 Pro
        for comprehensive processing including deduplication, cleaning, summarization, and 
        classification according to European sports news taxonomy.

        Args:
            session_data_file_path (str): Path to the journalist session data JSON file
                                         (e.g., ".journalist_workspace/20250621_235627_808728/session_data_fanatik_com_tr.json")

        Returns:
            Dict[str, Any]: Structured JSON result containing processed articles with summaries,
                           classifications, and processing metadata according to PROMPT.md specifications.
                           Returns error structure if processing fails.
        """
        if not self.model:
            logger.error("Google GenAI model is not initialized. Cannot process session data.")
            return {
                "error": "Summarizer not initialized",
                "processing_summary": {"total_input_articles": 0, "error": "Model not initialized"},
                "processed_articles": []
            }

        try:
            # Load session data file
            session_data_path = Path(session_data_file_path)
            if not session_data_path.exists():
                logger.error(f"Session data file not found: {session_data_file_path}")
                return {
                    "error": f"Session data file not found: {session_data_file_path}",
                    "processing_summary": {"total_input_articles": 0, "error": "File not found"},
                    "processed_articles": []
                }

            with open(session_data_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Load PROMPT.md file
            prompt_md_path = Path(__file__).parent.parent / "PROMPT.md"
            if not prompt_md_path.exists():
                logger.error(f"PROMPT.md file not found: {prompt_md_path}")
                return {
                    "error": f"PROMPT.md file not found: {prompt_md_path}",
                    "processing_summary": {"total_input_articles": 0, "error": "PROMPT.md not found"},
                    "processed_articles": []
                }

            with open(prompt_md_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()

            # Construct the complete prompt
            combined_prompt = f"""{prompt_content}

## SESSION DATA TO PROCESS

Please process the following European sports news session data according to the specifications above:

```json
{json.dumps(session_data, indent=2, ensure_ascii=False)}
```

Respond with the structured JSON result according to the OUTPUT FORMAT specified in the prompt above.
"""

            logger.info(f"Processing session data file: {session_data_file_path}")
            logger.info(f"Session contains {len(session_data.get('articles', []))} articles from {session_data.get('source_domain', 'unknown domain')}")

            # Send to Gemini for processing
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self.model.generate_content, combined_prompt)

            if response.text:
                try:
                    result = json.loads(response.text)
                    
                    # Validate the response structure
                    if "processing_summary" in result and "processed_articles" in result:
                        logger.info(f"Successfully processed session data: {len(result.get('processed_articles', []))} articles processed")
                        return result
                    else:
                        logger.warning(f"Response missing required structure: {list(result.keys())}")
                        return {
                            "error": "Invalid response structure from Gemini",
                            "processing_summary": {"total_input_articles": len(session_data.get('articles', [])), "error": "Invalid response structure"},
                            "processed_articles": [],
                            "raw_response": response.text
                        }
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON response from Gemini: {e}")
                    return {
                        "error": f"JSON decode error: {str(e)}",
                        "processing_summary": {"total_input_articles": len(session_data.get('articles', [])), "error": "JSON decode error"},
                        "processed_articles": [],
                        "raw_response": response.text
                    }
            else:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logger.error(f"Content generation blocked by Google GenAI. Reason: {response.prompt_feedback.block_reason}")
                    return {
                        "error": f"Content blocked: {response.prompt_feedback.block_reason}",
                        "processing_summary": {"total_input_articles": len(session_data.get('articles', [])), "error": "Content blocked"},
                        "processed_articles": []
                    }
                else:
                    logger.error(f"No content received from Google GenAI. Response: {response}")
                    return {
                        "error": "No content received from Gemini",
                        "processing_summary": {"total_input_articles": len(session_data.get('articles', [])), "error": "No content received"},
                        "processed_articles": []
                    }

        except FileNotFoundError as e:
            logger.error(f"File not found error: {e}")
            return {
                "error": f"File not found: {str(e)}",
                "processing_summary": {"total_input_articles": 0, "error": "File not found"},
                "processed_articles": []
            }
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing session data JSON: {e}")
            return {
                "error": f"Session data JSON error: {str(e)}",
                "processing_summary": {"total_input_articles": 0, "error": "Session data JSON error"},
                "processed_articles": []
            }
        except Exception as e:
            logger.error(f"Error during session data processing: {e}", exc_info=True)
            return {
                "error": f"Processing error: {str(e)}",
                "processing_summary": {"total_input_articles": 0, "error": "Processing error"},
                "processed_articles": []
            }


# Example Usage (for testing this module directly)
async def main_test_summarizer():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    summarizer = AISummarizer() 

    if not summarizer.model:
        print("AISummarizer (Google GenAI) could not be initialized. Exiting test.")
        print("Ensure GOOGLE_API_KEY environment variable is set.")
        return

    # Test with an actual session data file if available
    session_data_path = ".journalist_workspace/20250621_235627_808728/session_data_fanatik_com_tr.json"
    
    if Path(session_data_path).exists():
        print(f"\\n--- Testing Session Data Processing ---")
        print(f"Processing: {session_data_path}")
        
        result = await summarizer.summarize_and_classify_session_data_object(session_data_path)
        
        print("\\nProcessing Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Test session data file not found: {session_data_path}")
        print("Please provide a valid session data file path for testing.")


if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY environment variable not set. This test requires it.")
    else:
        asyncio.run(main_test_summarizer())
