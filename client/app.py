"""client.app

Client application entrypoint wiring settings, translator, publisher, and audio.
"""

from client.config import load_client_settings
from client.publisher import TranslationPublisher
from client.speech_loop import run_speech_loop
from client.translator import GeminiTranslator


def main() -> None:
    """Run the realtime translation client."""
    settings = load_client_settings()
    translator = GeminiTranslator(api_key=settings.google_api_key)
    publisher = TranslationPublisher(
        api_base_url=settings.api_base_url,
        api_key=settings.api_key,
    )
    run_speech_loop(translator=translator, publisher=publisher)
