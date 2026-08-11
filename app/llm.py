import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()


def get_llm(api_key: str | None = None) -> ChatGoogleGenerativeAI:
    resolved_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_key:
        raise ValueError("GEMINI_API_KEY not found. Add it to your account keys or .env.")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=resolved_key,
        temperature=0,
    )
