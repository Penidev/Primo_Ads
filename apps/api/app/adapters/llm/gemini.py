"""Gemini LLM adapter (via the Generative Language REST API).

Uses httpx directly so the backend has no hard dependency on a vendor SDK, which
keeps the adapter easy to swap (see ARCHITECTURE.md adapter pattern).
"""

import asyncio

import httpx

from app.adapters.llm.base import LLMAdapter
from app.config import settings

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
UPLOAD_ROOT = "https://generativelanguage.googleapis.com/upload/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"
# Video deconstruction benefits from the stronger model.
VISION_MODEL = "gemini-2.5-pro"
EMBEDDING_MODEL = "text-embedding-004"
REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
UPLOAD_TIMEOUT = httpx.Timeout(600.0, connect=15.0)
FILE_POLL_ATTEMPTS = 30
FILE_POLL_SECONDS = 3.0


class LLMConfigurationError(Exception):
    """Raised when the provider credentials are absent."""


class LLMRequestError(Exception):
    """Raised when the provider call fails. Message is safe to log."""


class GeminiAdapter(LLMAdapter):
    def __init__(self, model: str = DEFAULT_MODEL, vision_model: str = VISION_MODEL):
        if not settings.gemini_api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not configured.")
        self.api_key = settings.gemini_api_key
        self.model = model
        self.vision_model = vision_model

    async def generate_json(
        self,
        system_instruction: str,
        user_content: str,
        *,
        temperature: float = 0.8,
        max_output_tokens: int = 8192,
    ) -> str:
        payload = {
            # System instruction is a separate field, never concatenated with
            # untrusted user content.
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        url = f"{API_ROOT}/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key},
            )
        if response.status_code >= 400:
            raise LLMRequestError(
                f"Gemini request failed with status {response.status_code}."
            )
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError("Gemini returned an unexpected response shape.") from exc

    async def _upload_video(self, video_bytes: bytes, mime_type: str) -> str:
        """Upload to the Files API and wait until the file is ACTIVE.

        Returns the file URI to reference in a generateContent call.
        """
        start_headers = {
            "x-goog-api-key": self.api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(video_bytes)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as client:
            start = await client.post(
                f"{UPLOAD_ROOT}/files",
                headers=start_headers,
                json={"file": {"display_name": "reference-ad"}},
            )
            if start.status_code >= 400:
                raise LLMRequestError(f"Video upload could not start ({start.status_code}).")

            upload_url = start.headers.get("x-goog-upload-url")
            if not upload_url:
                raise LLMRequestError("Video upload URL was not returned.")

            finalize = await client.post(
                upload_url,
                headers={
                    "Content-Length": str(len(video_bytes)),
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Command": "upload, finalize",
                },
                content=video_bytes,
            )
            if finalize.status_code >= 400:
                raise LLMRequestError(f"Video upload failed ({finalize.status_code}).")

            file_info = (finalize.json() or {}).get("file") or {}
            file_uri = file_info.get("uri")
            file_name = file_info.get("name")
            if not file_uri or not file_name:
                raise LLMRequestError("Video upload response was incomplete.")

            # Video files are processed asynchronously; poll until usable.
            for _ in range(FILE_POLL_ATTEMPTS):
                if file_info.get("state") == "ACTIVE":
                    return str(file_uri)
                if file_info.get("state") == "FAILED":
                    raise LLMRequestError("The provider could not process this video.")
                await asyncio.sleep(FILE_POLL_SECONDS)
                probe = await client.get(
                    f"{API_ROOT}/{file_name}",
                    headers={"x-goog-api-key": self.api_key},
                )
                if probe.status_code >= 400:
                    raise LLMRequestError("Could not check video processing state.")
                file_info = probe.json() or {}

        raise LLMRequestError("Video processing timed out.")

    async def analyze_video_json(
        self,
        system_instruction: str,
        user_content: str,
        video_bytes: bytes,
        mime_type: str,
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 8192,
    ) -> str:
        file_uri = await self._upload_video(video_bytes, mime_type)

        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"fileData": {"fileUri": file_uri, "mimeType": mime_type}},
                        {"text": user_content},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        url = f"{API_ROOT}/models/{self.vision_model}:generateContent"
        async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as client:
            response = await client.post(
                url, json=payload, headers={"x-goog-api-key": self.api_key}
            )
        if response.status_code >= 400:
            raise LLMRequestError(f"Video analysis failed ({response.status_code}).")

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError("Video analysis returned an unexpected shape.") from exc

    async def embed(self, text: str) -> list[float]:
        url = f"{API_ROOT}/models/{EMBEDDING_MODEL}:embedContent"
        payload = {
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text}]},
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key},
            )
        if response.status_code >= 400:
            raise LLMRequestError(
                f"Gemini embedding failed with status {response.status_code}."
            )
        data = response.json()
        try:
            return list(data["embedding"]["values"])
        except (KeyError, TypeError) as exc:
            raise LLMRequestError("Gemini embedding response was malformed.") from exc
