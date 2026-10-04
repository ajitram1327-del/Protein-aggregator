import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv("../.env")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents='Tell me if you are alive.',
    )
    print("gemini-3.8-flash:", response.text)
except Exception as e:
    print("gemini-3.8-flash error:", e)
