import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv("../.env")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Tell me if you are alive.',
    )
    print("gemini-2.5-flash:", response.text)
except Exception as e:
    print("gemini-2.5-flash error:", e)

try:
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='Tell me if you are alive.',
    )
    print("gemini-1.5-flash:", response.text)
except Exception as e:
    print("gemini-1.5-flash error:", e)
