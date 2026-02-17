"""Groq LLM client."""

from groq import Groq


class GroqClient:
    """Groq API client for LLM operations."""

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def chat_completion(self, model: str, messages: list) -> str:
        """Get chat completion from Groq."""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
