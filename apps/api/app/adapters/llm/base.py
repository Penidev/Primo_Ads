"""LLM adapter interface.

Implementations must keep system instructions structurally separate from user
content (never concatenated) so untrusted brief text cannot override platform
instructions (prompt-injection defence, SECURITY.md §4).
"""

from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    @abstractmethod
    async def generate_json(
        self,
        system_instruction: str,
        user_content: str,
        *,
        temperature: float = 0.8,
        max_output_tokens: int = 8192,
    ) -> str:
        """Return the model's raw response text, expected to be JSON."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for semantic retrieval."""

    @abstractmethod
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
        """Analyse a video and return the model's raw JSON response.

        Used to deconstruct reference advertisements into structured blueprints.
        """
