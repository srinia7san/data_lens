import os
from google import genai

def embed_question(text: str, api_key: str | None = None) -> list[float]:
    api_key = api_key or os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    client = genai.Client(api_key=api_key)

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    return response.embeddings[0].values
