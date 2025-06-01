\
import asyncio
import logging
import os
import json
from typing import List, Dict, Any

# Corrected imports based on autogen-agentchat structure
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
# Import from autogen_ext.models.openai
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Configure logging
logger = logging.getLogger(__name__)

class AISummarizer:
    """
    Uses AutoGen to summarize articles into bullet points using OpenAI models.
    """
    def __init__(self, openai_config: Dict[str, Any] = None):
        """
        Initializes the AISummarizer.

        Args:
            openai_config (Dict[str, Any], optional): Configuration for the OpenAI LLM.
                If None, it will try to build a default OpenAI config
                from environment variables (OPENAI_API_KEY, OPENAI_MODEL_NAME).
                Example:
                {
                    "model": "gpt-4o-2024-08-06", # Updated model name
                    "api_key": "sk-yourkey",
                    "temperature": 0.2,
                    "timeout": 180,
                    "response_format": {"type": "json_object"} # Optional, but recommended for JSON mode
                }
        """
        effective_config = {}
        if openai_config:
            effective_config = openai_config.copy()
        
        # Ensure required keys are present, falling back to environment variables
        if "api_key" not in effective_config:
            effective_config["api_key"] = os.getenv("OPENAI_API_KEY")
        if "model" not in effective_config:
            effective_config["model"] = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-2024-08-06") # Default model updated

        # Set defaults for other parameters if not provided
        effective_config.setdefault("temperature", 0.2)
        effective_config.setdefault("timeout", 180)
        effective_config.setdefault("response_format", {"type": "json_object"})


        if not effective_config.get("api_key"):
            logger.error("OpenAI API key (OPENAI_API_KEY) is not set. Summarizer will not function.")
            self.model_client = None
            self.summarizer_agent = None
            self.user_proxy = None
            return
        
        try:
            self.model_client = OpenAIChatCompletionClient(
                model=effective_config["model"],
                api_key=effective_config["api_key"],
                temperature=effective_config["temperature"],
                timeout=effective_config["timeout"],
                response_format=effective_config["response_format"] 
            )
            
            self.summarizer_agent = AssistantAgent(
                name="ArticleSummarizerAgent",
                system_message="""You are an expert news summarizer.
Your task is to read the provided article (title and body) and generate a concise summary consisting of 3 to 5 key bullet points.
The bullet points should capture the main topics and factual information of the article.
You MUST respond with a JSON object containing two keys: "original_url" (if provided, otherwise null) and "summary_bullets" (a list of strings, where each string is a bullet point).
Example for a single article:
{
  "original_url": "http://example.com/article1",
  "summary_bullets": [
    "Bullet point 1 about the article.",
    "Bullet point 2 highlighting a key fact.",
    "Bullet point 3 covering another important aspect."
  ]
}
If you receive a list of articles to summarize, provide a list of such JSON objects.
However, for this interaction, you will be given one article at a time.
Focus on clarity and conciseness.""",
                model_client=self.model_client,
                max_consecutive_auto_reply=1 
            )

            self.user_proxy = UserProxyAgent(
                name="SummaryRequester",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=1,
                code_execution_config=False,
            )
        except Exception as e:
            logger.error(f"Failed to initialize AISummarizer agents: {e}", exc_info=True)
            self.model_client = None
            self.summarizer_agent = None
            self.user_proxy = None

    async def summarize_article(self, article_title: str, article_body: str, article_url: str = None) -> Dict[str, Any]:
        """
        Summarizes a single article.

        Args:
            article_title (str): The title of the article.
            article_body (str): The body/content of the article.
            article_url (str, optional): The original URL of the article for reference.

        Returns:
            Dict[str, Any]: A dictionary containing the original URL and a list of summary bullet points.
                           Returns a default error structure if summarization fails.
        """
        if not self.model_client or not self.summarizer_agent or not self.user_proxy:
            logger.error("AISummarizer is not properly initialized. Cannot summarize.")
            return {"original_url": article_url, "summary_bullets": ["Error: Summarizer not initialized."]}

        prompt = f"""Please summarize the following article:

Title: {article_title}

Body:
{article_body[:15000]}"""  # Truncate body to avoid excessive token usage, adjust as needed

        if article_url:
            prompt += f"\\n\\nOriginal URL (for your reference in the output JSON): {article_url}"
        
        logger.info(f"Requesting summary for article URL: {article_url if article_url else 'N/A'}, Title: {article_title[:50]}...")

        try:
            # Reset agents or clear history before each call to ensure stateless summarization for each article.
            # This is important if the same agent instances are reused.
            self.user_proxy.reset() # Reset user proxy agent
            self.summarizer_agent.reset() # Reset summarizer agent
            
            await self.user_proxy.a_initiate_chat(
                recipient=self.summarizer_agent,
                message=prompt,
            )
            
            # Retrieve the last message from the perspective of the user_proxy, which should be the assistant's reply.
            # The chat messages are stored in `chat_messages`, keyed by the other agent.
            chat_history = self.user_proxy.chat_messages.get(self.summarizer_agent, [])
            if not chat_history:
                 logger.error(f"No chat history found with {self.summarizer_agent.name} for article: {article_title[:50]}...")
                 return {"original_url": article_url, "summary_bullets": ["Error: No chat history from agent."]}

            last_message = chat_history[-1]

            if last_message and last_message.get("content") and last_message.get("role") == "assistant":
                content_str = last_message["content"]
                try:
                    summary_data = json.loads(content_str)
                    if "summary_bullets" in summary_data and isinstance(summary_data["summary_bullets"], list):
                        logger.info(f"Successfully summarized article: {article_title[:50]}...")
                        if "original_url" not in summary_data:
                            summary_data["original_url"] = article_url
                        return summary_data
                    else:
                        logger.warning(f"Summary output for '{article_title[:50]}' not in expected JSON format: {content_str}")
                        return {"original_url": article_url, "summary_bullets": [f"Warning: Unexpected summary format: {content_str}"]}
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON summary for '{article_title[:50]}...': {content_str}")
                    return {"original_url": article_url, "summary_bullets": [f"Error: Could not parse summary JSON: {content_str}"]}
            else:
                logger.error(f"No valid summary message received from agent for article: {article_title[:50]}... Last message: {last_message}")
                return {"original_url": article_url, "summary_bullets": ["Error: No summary received from agent."]}

        except Exception as e:
            logger.error(f"Error during summarization for article '{article_title[:50]}...': {e}", exc_info=True)
            return {"original_url": article_url, "summary_bullets": [f"Error: Exception during summarization - {str(e)}"]}

    async def summarize_articles_in_session(self, articles_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Summarizes a list of articles.

        Args:
            articles_data (List[Dict[str, str]]): A list of dictionaries, where each dictionary
                                                 should have "title", "body", and optionally "url".
                                                 Example: [{"title": "T1", "body": "B1", "url": "U1"}, ...]

        Returns:
            List[Dict[str, Any]]: A list of summary dictionaries.
        """
        if not self.model_client:
            logger.error("LLM client (ModelClient) is not configured. Cannot summarize batch.")
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

    # Set OPENAI_API_KEY and optionally OPENAI_MODEL_NAME in your environment variables
    
    summarizer = AISummarizer() # Uses environment variables by default

    if not summarizer.model_client:
         print("AISummarizer could not be initialized. Exiting test.")
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
        }
    ]

    print("\\n--- Testing Single Article Summarization ---")
    if sample_articles[0]["body"]:
        single_summary = await summarizer.summarize_article(
            sample_articles[0]["title"],
            sample_articles[0]["body"],
            sample_articles[0]["url"]
        )
        print(json.dumps(single_summary, indent=2))
    else:
        print("Skipping single article test due to missing body in sample.")

    print("\\n\\n--- Testing Batch Article Summarization ---")
    batch_summaries = await summarizer.summarize_articles_in_session(sample_articles)
    print(json.dumps(batch_summaries, indent=2))

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
    else:
        asyncio.run(main_test_summarizer())
