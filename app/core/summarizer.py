from http import client
from google import genai
from google.genai import types

import logging
import app.util as util

log = logging.getLogger("app.core.summarizer")
config = util.get_config()

GOOGLE_API_KEY=userdata.get('GOOGLE_API_KEY')
client = genai.Client(api_key=GOOGLE_API_KEY)
def summarize_text(text: str) -> str:
    """
    Summarizes the given text.
    """
    MODEL_ID = "gemini-2.5-flash" # @param ["gemini-1.5-flash-latest","gemini-2.5-flash-lite-preview-06-17","gemini-2.5-flash","gemini-2.5-pro"] {"allow-input":true}
    prompt = "Generate a 10 paragraph fantasy story. Include at least 2 named characters and 2 named locations. Give as much detail in the story as possible."
    response = client.models.generate_content(
    model=MODEL_ID,
    contents=prompt
    )
story = response.text

    client = genai.Client(
        model=config["GENAI_MODEL"],
        api_key=config["GENAI_API_KEY"],
        project_id=config["GENAI_PROJECT_ID"],
    )
    log.info("Summarizing text...")
    prompt = config["MARKDOWN_SUMMARY_PROMPT"]
    response = client.models.generate_content(
        model = "gemini-2.5-flash",
        contents=[
            
        ]
    )
    summary = f"This is a placeholder summary of the text: '{text[:50]}...'"
    return summaryhttps://ai.google.dev/gemini-api/docs/document-processing#python_2
