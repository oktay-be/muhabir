\
import asyncio
import logging
import os
import json
from typing import List, Dict, Any
import google.generativeai as genai

# Configure logging
logger = logging.getLogger(__name__)

class AISummarizer:
    """
    Uses Google's Generative AI (Gemini) to summarize articles into bullet points.
    """
    def __init__(self, google_api_key: str = None, model_name: str = "models/gemini-1.5-flash-latest"):
        """
        Initializes the AISummarizer with Google Generative AI.

        Args:
            google_api_key (str, optional): Google API key. If None, tries to get from
                                           GOOGLE_API_KEY environment variable.
            model_name (str, optional): The name of the Gemini model to use.
                                        Defaults to "models/gemini-1.5-flash-latest".
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
                response_mime_type="application/json" 
            )
            self.model = genai.GenerativeModel(
                model_name,
                generation_config=generation_config
            )
            logger.info(f"AISummarizer initialized with Google GenAI model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI model: {e}", exc_info=True)
            self.model = None

    async def summarize_bulk_articles_content(self, articles_data: List[Dict[str, str]], session_id: str = "default_session") -> Dict[str, Any]:
        """
        Combines content from multiple articles and generates a single summary
        for all of them using Google Generative AI.

        Args:
            articles_data (List[Dict[str, str]]): A list of dictionaries, where each dictionary
                                                 should have "title", "body", and optionally "url".
            session_id (str): An identifier for the summarization session.

        Returns:
            Dict[str, Any]: A dictionary containing the session ID and a list of summary bullet points
                           for the combined content. Returns a default error structure if summarization fails.
        """
        if not self.model:
            logger.error("Google GenAI model is not initialized. Cannot perform bulk summarization.")
            return {"session_id": session_id, "summary_bullets": ["Error: Summarizer not initialized."]}

        if not articles_data:
            logger.warning("No articles provided for bulk summarization.")
            return {"session_id": session_id, "summary_bullets": ["Warning: No articles to summarize."]}

        combined_content = ""
        article_references = []

        for i, article in enumerate(articles_data):
            title = article.get("title", f"Untitled Article {i+1}")
            body = article.get("body", "")
            url = article.get("url")

            if not body: # Skip articles with no body
                logger.info(f"Skipping article '{title}' (URL: {url if url else 'N/A'}) due to empty body in bulk summarization.")
                continue

            combined_content += f"<Title>{title}</Title>\\n<Body>{body}</Body>\\n\\n----------------\\n\\n"
            if url:
                article_references.append(url)
            else:
                article_references.append(f"Reference to article titled: {title}")
        
        if not combined_content.strip():
            logger.warning("All provided articles had empty bodies. Nothing to summarize.")
            return {"session_id": session_id, "summary_bullets": ["Warning: All articles had empty bodies."]}

        # Truncate combined_content if it's too long for the model's context window
        # This limit is an estimate; refer to Gemini model documentation for precise limits.
        # Gemini 1.5 Flash has a large context window, but extremely large inputs can still be an issue.
        # A typical limit might be around 1 million tokens, but for safety and cost, let's use a character limit.
        # Assuming an average of ~4 chars per token, 1M tokens ~ 4M chars. Let's be more conservative.
        # Max input for Gemini 1.5 Flash is 1M tokens. Let's use a character limit like 3,500,000 (generous).
        # The prompt itself also takes space.
        MAX_CHARS_FOR_GEMINI = 3500000 
        if len(combined_content) > MAX_CHARS_FOR_GEMINI:
            logger.warning(f"Combined content length ({len(combined_content)} chars) exceeds limit ({MAX_CHARS_FOR_GEMINI} chars). Truncating for summarization.")
            combined_content = combined_content[:MAX_CHARS_FOR_GEMINI]


        prompt = f"""Your task is to read the provided collection of articles (each with a title and body, separated by '----------------') and generate a single, consolidated summary consisting of 5 to 7 key bullet points.
The summary should synthesize the main themes, topics, and factual information from ALL articles provided.
You MUST respond with a JSON object containing two keys: "session_id" (use the provided session_id: {session_id}) and "summary_bullets" (a list of strings, where each string is a bullet point representing the consolidated summary).

Combined Articles to summarize:
{combined_content}

Session ID (for your reference in the output JSON): {session_id}
Original article URLs/references (for context, not for direct inclusion in summary unless relevant): {', '.join(article_references)}

Respond with ONLY the JSON object.
"""
        
        logger.info(f"Requesting bulk summary from Google GenAI for session_id: {session_id} with {len(articles_data)} articles initially provided.")

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self.model.generate_content, prompt)
            
            if response.text:
                try:
                    summary_data = json.loads(response.text)
                    if "summary_bullets" in summary_data and isinstance(summary_data["summary_bullets"], list) and "session_id" in summary_data:
                        logger.info(f"Successfully generated bulk summary for session_id: {session_id} (Google GenAI).")
                        # Ensure the session_id from the response matches, or use the one we passed.
                        summary_data["session_id"] = session_id 
                        return summary_data
                    else:
                        logger.warning(f"Google GenAI bulk summary output for session_id '{session_id}' not in expected JSON format or missing keys: {response.text}")
                        return {"session_id": session_id, "summary_bullets": [f"Warning: Unexpected bulk summary format from Google GenAI: {response.text}"]}
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON bulk summary from Google GenAI for session_id '{session_id}': {response.text}. Error: {e}")
                    return {"session_id": session_id, "summary_bullets": [f"Error: Could not parse bulk summary JSON from Google GenAI: {response.text}"]}
            else:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logger.error(f"Content generation blocked by Google GenAI for bulk summary (session_id: {session_id}). Reason: {response.prompt_feedback.block_reason}")
                    return {"session_id": session_id, "summary_bullets": [f"Error: Content generation blocked for bulk summary. Reason: {response.prompt_feedback.block_reason}"]}
                else:
                    logger.error(f"No content received from Google GenAI for bulk summary (session_id: {session_id}). Response: {response}")
                    return {"session_id": session_id, "summary_bullets": ["Error: No bulk summary content received from Google GenAI."]}

        except Exception as e:
            logger.error(f"Error during Google GenAI bulk summarization for session_id '{session_id}': {e}", exc_info=True)
            return {"session_id": session_id, "summary_bullets": [f"Error: Exception during Google GenAI bulk summarization - {str(e)}"]}

    async def summarize_article(self, article_title: str, article_body: str, article_url: str = None) -> Dict[str, Any]:
        """
        Summarizes a single article using Google Generative AI.

        Args:
            article_title (str): The title of the article.
            article_body (str): The body/content of the article.
            article_url (str, optional): The original URL of the article for reference.

        Returns:
            Dict[str, Any]: A dictionary containing the original URL and a list of summary bullet points.
                           Returns a default error structure if summarization fails.
        """
        if not self.model:
            logger.error("Google GenAI model is not initialized. Cannot summarize.")
            return {"original_url": article_url, "summary_bullets": ["Error: Summarizer not initialized."]}

        prompt = f"""Your task is to read the provided article (title and body) and generate a concise summary consisting of 3 to 5 key bullet points.
The bullet points should capture the main topics and factual information of the article.
You MUST respond with a JSON object containing two keys: "original_url" (use the provided URL, or null if not provided) and "summary_bullets" (a list of strings, where each string is a bullet point).

Article to summarize:
Title: {article_title}
Body:
{article_body[:15000]} 

Original URL (for your reference in the output JSON): {article_url if article_url else "Not provided"}

Respond with ONLY the JSON object.
"""
        
        logger.info(f"Requesting summary from Google GenAI for article URL: {article_url if article_url else 'N/A'}, Title: {article_title[:50]}...")

        try:
            # For async, we'd typically use an async client if available, or run sync in executor
            # google-generativeai library's generate_content is synchronous.
            # To make this method truly async and non-blocking for an async caller,
            # we should run the blocking call in an executor.
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self.model.generate_content, prompt)
            
            # The response.text should be the JSON string due to response_mime_type="application/json"
            # and the prompt instructions.
            if response.text:
                try:
                    summary_data = json.loads(response.text)
                    # Validate structure
                    if "summary_bullets" in summary_data and isinstance(summary_data["summary_bullets"], list):
                        # Ensure original_url is present, even if it was null in the prompt
                        if "original_url" not in summary_data:
                             summary_data["original_url"] = article_url # Fallback
                        elif summary_data.get("original_url") == "Not provided" and article_url:
                             summary_data["original_url"] = article_url


                        logger.info(f"Successfully summarized article (Google GenAI): {article_title[:50]}...")
                        return summary_data
                    else:
                        logger.warning(f"Google GenAI summary output for '{article_title[:50]}' not in expected JSON format or missing 'summary_bullets': {response.text}")
                        return {"original_url": article_url, "summary_bullets": [f"Warning: Unexpected summary format from Google GenAI: {response.text}"]}
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON summary from Google GenAI for '{article_title[:50]}...': {response.text}. Error: {e}")
                    return {"original_url": article_url, "summary_bullets": [f"Error: Could not parse summary JSON from Google GenAI: {response.text}"]}
            else:
                # Check for safety ratings or other reasons for no text
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logger.error(f"Content generation blocked by Google GenAI for '{article_title[:50]}...'. Reason: {response.prompt_feedback.block_reason}")
                    return {"original_url": article_url, "summary_bullets": [f"Error: Content generation blocked by Google GenAI. Reason: {response.prompt_feedback.block_reason}"]}
                else:
                    logger.error(f"No content received from Google GenAI for article: {article_title[:50]}... Response: {response}")
                    return {"original_url": article_url, "summary_bullets": ["Error: No summary content received from Google GenAI."]}

        except Exception as e:
            logger.error(f"Error during Google GenAI summarization for article '{article_title[:50]}...': {e}", exc_info=True)
            # Check if it's a Google specific API error if possible, e.g. from google.api_core.exceptions
            # For now, a general catch.
            return {"original_url": article_url, "summary_bullets": [f"Error: Exception during Google GenAI summarization - {str(e)}"]}

    async def summarize_articles_in_session(self, articles_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        DEPRECATED: This method summarizes articles individually. 
        Use summarize_bulk_articles_content for a single summary from multiple articles.
        If individual summaries are still needed, this can be kept, but the primary request was for bulk.
        
        Summarizes a list of articles using the Google GenAI summarizer, individually.

        Args:
            articles_data (List[Dict[str, str]]): A list of dictionaries, where each dictionary
                                                 should have "title", "body", and optionally "url".
                                                 Example: [{"title": "T1", "body": "B1", "url": "U1"}, ...]

        Returns:
            List[Dict[str, Any]]: A list of summary dictionaries.
        """
        if not self.model:
            logger.error("Google GenAI model is not configured. Cannot summarize batch.")
            return [{"original_url": article.get("url"), "summary_bullets": ["Error: Summarizer not configured."]} for article in articles_data]

        summaries = []
        for article in articles_data:
            title = article.get("title")
            body = article.get("body")
            url = article.get("url")

            if not title or not body:
                logger.warning(f"Skipping article due to missing title or body. URL: {url if url else 'N/A'}")
                summaries.append({"original_url": url, "summary_bullets": ["Error: Missing title or body for summarization."]})
                continue
            
            summary_result = await self.summarize_article(title, body, url)
            summaries.append(summary_result)
        
        return summaries

# Example Usage (for testing this module directly)
async def main_test_summarizer():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Set GOOGLE_API_KEY in your environment variables
    
    summarizer = AISummarizer() 

    if not summarizer.model:
         print("AISummarizer (Google GenAI) could not be initialized. Exiting test.")
         print("Ensure GOOGLE_API_KEY environment variable is set.")
         return

    sample_articles = [
        {
            "title": "Fenerbahçe signs new star player José Mourinho",
            "body": "Fenerbahçe football club has officially announced the signing of world-renowned coach José Mourinho. The news has sent shockwaves through the Turkish football community. Mourinho, known for his tactical prowess and numerous trophies, is expected to bring a new era of success to the Istanbul-based club. Fans are ecstatic and eagerly awaiting the next season. The contract details reveal a multi-year deal with significant performance bonuses. This move is seen as a major statement of intent from Fenerbahçe's board.",
            "url": "http://example.com/mourinho-signs-fener"
        },
        {
            "title": "Galatasaray prepares for Champions League qualifier",
            "body": "Galatasaray is intensifying its preparations for the upcoming Champions League qualifying rounds. The team has been in a rigorous training camp, focusing on fitness and tactical drills. Coach Okan Buruk expressed confidence in his squad's ability to navigate the challenging qualifiers and reach the group stages. Several new signings are expected to integrate quickly and make an impact. The first qualifying match is scheduled against a tough opponent from Eastern Europe.",
            "url": "http://example.com/galatasaray-cl-prep"
        },
        {
            "title": "Missing Body Test",
            "body": None, # Test missing body
            "url": "http://example.com/missing-body"
        },
        {
            "title": "Very Short Article",
            "body": "This is a very short article. It might be hard to summarize.",
            "url": "http://example.com/short-article"
        }
    ]

    print("\\n--- Testing Single Article Summarization (Google GenAI) ---")
    if sample_articles[0]["body"]:
        single_summary = await summarizer.summarize_article(
            sample_articles[0]["title"],
            sample_articles[0]["body"],
            sample_articles[0]["url"]
        )
        print("Single Article Summary:")
        print(json.dumps(single_summary, indent=2, ensure_ascii=False))
    else:
        print("Skipping single article test due to missing body in sample.")

    print("\\n\\n--- Testing Batch Article Summarization (Individual Summaries - DEPRECATED STYLE) ---")
    # This calls the old method that summarizes one by one.
    # batch_summaries = await summarizer.summarize_articles_in_session(sample_articles) 
    # print("Batch Individual Summaries:")
    # print(json.dumps(batch_summaries, indent=2, ensure_ascii=False))

    print("\\n\\n--- Testing Bulk Content Summarization (Google GenAI) ---")
    # Create a session ID for testing the new bulk summarizer
    test_session_id = "test_bulk_session_123"
    bulk_summary_output = await summarizer.summarize_bulk_articles_content(sample_articles, session_id=test_session_id)
    print(f"Bulk Summary for Session ID: {test_session_id}")
    print(json.dumps(bulk_summary_output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY environment variable not set. This test requires it.")
    else:
        asyncio.run(main_test_summarizer())
