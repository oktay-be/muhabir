# google_genai_connection_test.py
import os
import sys
from dotenv import load_dotenv
# import certifi # certifi may not be needed with google-cloud-aiplatform
# import google.generativeai as genai # Switching to google-cloud-aiplatform

from google.cloud import aiplatform
from google.cloud.aiplatform import gapic as aiplatform_gapic # For specifying API endpoint
# from google.cloud.aiplatform.models import Prediction # For type hinting if needed
import google.generativeai as genai # Keep for now for API_KEY based, will remove if ADC works


# --- Set GOOGLE_APPLICATION_CREDENTIALS to use the real service account key ---
# IMPORTANT: Ensure this key file is kept secure and not committed to public repositories.
REAL_KEY_FILENAME = 'gen-lang-client-0306766464-a6a1f383d725.json'
REAL_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), REAL_KEY_FILENAME)

if os.path.exists(REAL_KEY_PATH):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = REAL_KEY_PATH
    print(f"Attempting to use Service Account Key: {REAL_KEY_PATH}")
else:
    print(f"WARNING: Service account key not found at {REAL_KEY_PATH}. ADC might fail or use other credentials.")


# --- Load environment variables (still needed for API_KEY as a fallback or for other services) ---
project_root = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(project_root, '.env')

if not os.path.exists(dotenv_path):
    print(f"Warning: .env file not found at {dotenv_path}. Trying default load_dotenv().")
    if not load_dotenv(): # load_dotenv() returns True if .env was loaded, False otherwise
        print(f"Still could not load .env. Ensure it's in {project_root} or current directory.")
else:
    load_dotenv(dotenv_path)
    print(f".env file loaded from {dotenv_path}")

API_KEY = os.getenv("GOOGLE_API_KEY")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID") # Expecting this in .env now
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1") # Default location if not in .env

if not API_KEY:
    print("Warning: GOOGLE_API_KEY not found. API key method will fail if Vertex AI method also fails.")
if not PROJECT_ID:
    print("--------------------------------------------------------------------")
    print("ERROR: GOOGLE_CLOUD_PROJECT_ID not found in .env file.")
    print(f"Please add GOOGLE_CLOUD_PROJECT_ID='your-project-id' to {dotenv_path}")
    print("--------------------------------------------------------------------")
    sys.exit(1)

print(f"Using PROJECT_ID: {PROJECT_ID}")
print(f"Using LOCATION: {LOCATION}")
if API_KEY:
    print(f"Successfully loaded GOOGLE_API_KEY: {API_KEY[:4]}...{API_KEY[-4:]}")


# --- Parameters ---
MODEL_NAME_VERTEX = "gemini-1.5-flash-001" # Changed to a broadly available model
CONTENT_PROMPT = "Explain bubble sort to me using Vertex AI."

print(f"\n--- Attempting with Vertex AI (Service Account Method) ---")
print(f"Attempting to connect to Google Vertex AI with model: {MODEL_NAME_VERTEX}")

try:
    # --- Confirm Project ID and Location before init ---
    print(f"Attempting to initialize Vertex AI with effective PROJECT_ID: '{PROJECT_ID}' and LOCATION: '{LOCATION}'")
    # --- Initialize Vertex AI ---
    print(f"Initializing Vertex AI with Project ID: {PROJECT_ID} and Location: {LOCATION}...")
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    print("Vertex AI initialized successfully.")

    # --- Import GenerativeModel from Vertex AI SDK ---
    from vertexai.generative_models import GenerativeModel as VertexGenerativeModel

    print(f"Initializing GenerativeModel (Vertex AI) with model name: '{MODEL_NAME_VERTEX}'...")
    model_vertex = VertexGenerativeModel(MODEL_NAME_VERTEX)
    print("Vertex AI GenerativeModel initialized successfully.")

    # --- Generate content using Vertex AI ---
    print(f"Sending request to Vertex AI model '{MODEL_NAME_VERTEX}' with prompt: '{CONTENT_PROMPT}'...")
    response_vertex = model_vertex.generate_content(CONTENT_PROMPT)
    print("Vertex AI request successful.")

    # --- Print response text from Vertex AI ---
    print("\n--- Vertex AI Model Response ---")
    if response_vertex.candidates and response_vertex.candidates[0].content.parts:
        print(response_vertex.candidates[0].content.parts[0].text)
    else:
        print("Vertex AI response does not have expected structure. Full response:")
        print(response_vertex)
    print("--- End of Vertex AI Response ---")

except Exception as e:
    print("\n--------------------------------------------------------------------")
    print(f"AN ERROR OCCURRED (Vertex AI):")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {e}")
    import traceback
    traceback.print_exc()
    print("--------------------------------------------------------------------")

# --- Fallback or comparative test using google.generativeai with API Key (Original Method) ---
if API_KEY:
    print("\n--- Attempting with google.generativeai (API Key Method) for comparison ---")
    MODEL_NAME_GENAI_LIB = "gemini-1.5-pro-latest" # Using a common model for this library
    print(f"Attempting to connect to Google Gemini with model: {MODEL_NAME_GENAI_LIB} using google.generativeai library")
    try:
        # os.environ['SSL_CERT_FILE'] = certifi.where() # Keep if SSL issues persist with this client
        # print(f"Attempting to use SSL certificates from: {certifi.where()}")
        print("Configuring google.generativeai with API key and transport='rest'...")
        genai.configure(api_key=API_KEY, transport='rest')
        print("Configuration successful.")

        print(f"Initializing GenerativeModel (google.generativeai) with model name: '{MODEL_NAME_GENAI_LIB}'...")
        model_genai_lib = genai.GenerativeModel(MODEL_NAME_GENAI_LIB)
        print("Model (google.generativeai) initialized successfully.")

        print(f"Sending request to model '{MODEL_NAME_GENAI_LIB}' with prompt: '{CONTENT_PROMPT}'...")
        response_genai_lib = model_genai_lib.generate_content(contents=CONTENT_PROMPT)
        print("Request (google.generativeai) successful.")

        print("\n--- google.generativeai Model Response ---")
        if hasattr(response_genai_lib, 'text'):
            print(response_genai_lib.text)
        else:
            print("Response object (google.generativeai) does not have a 'text' attribute. Full response:")
            print(response_genai_lib)
        print("--- End of google.generativeai Response ---")

    except Exception as e:
        print("\n--------------------------------------------------------------------")
        print(f"AN ERROR OCCURRED (google.generativeai API Key Method):")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {e}")
        import traceback
        traceback.print_exc()
        print("--------------------------------------------------------------------")
else:
    print("\nSkipping google.generativeai (API Key Method) test as GOOGLE_API_KEY is not set.")

