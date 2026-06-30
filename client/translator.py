"""client.translator

Gemini-backed Korean-to-Japanese translation helpers.
"""

from google import genai

from client.glossary import build_translation_prompt

MODEL_NAME = "gemini-2.5-flash-preview-05-20"


class GeminiTranslator:
    """Translate recognized Korean text with a Gemini model."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def translate_text(self, text: str) -> str:
        """Translate text and return only the model text or an error message."""
        try:
            response = self._client.models.generate_content(
                model=MODEL_NAME,
                contents=[build_translation_prompt(text)],
            )
            return response.text
        except Exception as exc:
            return f"翻訳エラー: {exc}"
