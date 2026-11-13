"""Small server-side Gemini REST adapter; keeps the API key out of the browser."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GeminiError(Exception):
    """A safe-to-report upstream failure without exposing key or response body."""


def configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def model_name() -> str:
    # Keep the adapter pinned to the Gemini model currently listed on the free tier.
    return "gemini-3.8-flash"


def generate(system_instruction: str, prompt: str, *, max_output_tokens: int = 700) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiError("Gemini is not configured")
    model = quote(model_name(), safe="-_.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": max_output_tokens},
    }
    request = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    })
    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Do not include provider response text; it may contain request details.
        if exc.code == 429:
            raise GeminiError("Gemini free-tier quota or rate limit reached") from None
        if exc.code in (401, 403):
            raise GeminiError("Gemini rejected the configured API key") from None
        raise GeminiError(f"Gemini request failed with status {exc.code}") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise GeminiError("Gemini could not be reached") from None

    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
    text = "\n".join(part.get("text", "") for part in parts if isinstance(part.get("text"), str)).strip()
    if not text:
        raise GeminiError("Gemini returned no text, possibly due to a safety filter")
    return text
