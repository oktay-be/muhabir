import google.generativeai as genai
import os
import logging

logger = logging.getLogger(__name__)

class AISummarizer:
    """
    Uses Google Generative AI to summarize articles.
    """
    def __init__(self, api_key: str = None, model_name: str = "models/gemini-1.5-flash-latest"):
        """
        Initializes the AISummarizer with Google Generative AI.

        Args:
            api_key (str, optional): The Google API key. 
                                     If None, tries to fetch from GOOGLE_API_KEY environment variable.
            model_name (str, optional): The name of the Gemini model to use. 
                                        Defaults to "models/gemini-1.5-flash-latest".
        """
        resolved_api_key = api_key or os.getenv("GOOGLE_API_KEY")

        if not resolved_api_key:
            logger.error("Google API key (GOOGLE_API_KEY) is not set. Summarizer will not function.")
            self.model = None
            return

        try:
            genai.configure(api_key=resolved_api_key)
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"AISummarizer initialized with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Google Generative AI model: {e}", exc_info=True)
            self.model = None

    def summarize_articles_from_text(self, articles_text: str) -> str | None:
        """
        Summarizes a batch of articles provided as a single formatted string into a single consolidated summary.

        The orchestrator is expected to format the input `articles_text` like:
        Article 1:
        <Title1>
        <Body1>
        --------------
        Article 2:
        <Title2>
        <Body2>
        --------------
        ...

        Args:
            articles_text (str): A single string containing all articles formatted as specified.

        Returns:
            str | None: A string containing a single consolidated summary of all articles,
                        or None if summarization fails or the model is not initialized.
        """
        if not self.model:
            logger.error("Summarizer model not initialized. Cannot summarize.")
            return None

        prompt = f"""You will be provided with a series of news articles, each with a title and a body, separated by '--------------'.
These articles represent key news items from the last 24 hours.
Your task is to:
1. Read and understand all the provided articles.
2. Synthesize the information from all articles to create a single, concise, and comprehensive summary.
3. This summary should highlight the most important events, trends, and key takeaways from the collective news.
4. The goal is to provide a lean overview of what happened in the last 24 hours, as if for a news digest.
Do not summarize each article individually. Instead, provide one overarching summary.

Focus on accuracy, conciseness, and clarity.

The input articles are:
{articles_text}

Consolidated Summary of the Last 24 Hours:
"""
        try:
            response = self.model.generate_content(prompt)
            if response.parts:
                return response.text
            else:
                # Handle cases where the response might be blocked or empty
                logger.warning("Received an empty or blocked response from the AI model.")
                # Check for safety ratings or finish reasons if available and relevant
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                    logger.warning(f"Prompt blocked due to: {response.prompt_feedback.block_reason_message}")
                return "Error: Could not generate summary. The content might have been blocked or the response was empty."
        except Exception as e:
            logger.error(f"Error during summarization with Google AI: {e}", exc_info=True)
            return None

# Example Usage (for testing purposes, typically called by an orchestrator)
if __name__ == '__main__':
    # Configure basic logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # This example assumes GOOGLE_API_KEY is set in your environment
    # For local testing, you might provide it directly:
    # summarizer = AISummarizer(api_key="YOUR_GOOGLE_API_KEY_HERE")
    summarizer = AISummarizer()

    if summarizer.model:
        sample_articles_input = """Article 1:
Planetary Discovery
Scientists have discovered a new exoplanet orbiting a distant star. It is believed to be rocky and within the habitable zone.
--------------
Article 2:
Tech Conference Highlights
The annual tech conference showcased advancements in AI and quantum computing, promising transformative changes.
--------------
Article 3:
Economic Outlook
Experts predict steady economic growth for the next quarter, citing strong consumer spending and low unemployment rates.
"""
        
        summary_output = summarizer.summarize_articles_from_text(sample_articles_input)
        
        if summary_output:
            print("\n--- Generated Summary ---")
            print(summary_output)
        else:
            print("Failed to generate summary.")
    else:
        print("AISummarizer could not be initialized. Check API key and logs.")
