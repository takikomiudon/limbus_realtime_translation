"""client.publisher

Console output and optional POST publishing for completed translations.
"""

import sys
import time

import requests

RED = "\033[0;31m"
YELLOW = "\033[0;33m"


class TranslationPublisher:
    """Print translations locally and optionally send them to the server."""

    def __init__(self, api_base_url: str | None, api_key: str | None) -> None:
        self._api_base_url = api_base_url
        self._api_key = api_key

    def publish(self, translated_text: str, korean_text: str, timestamp: int) -> None:
        """Print and send a completed translation."""
        current_timestamp = int(time.time() * 1000)

        sys.stdout.write(YELLOW)
        sys.stdout.write(f"{timestamp}: 韓国語: {korean_text}\n")
        sys.stdout.write(f"{timestamp}: 翻訳: {translated_text}\n")

        if not self._api_base_url:
            return

        try:
            headers = {}
            if self._api_key:
                headers["X-API-Key"] = self._api_key

            response = requests.post(
                self._api_base_url,
                json={
                    "timestamp": current_timestamp,
                    "translation": translated_text,
                    "korean_text": korean_text,
                },
                headers=headers,
                timeout=10,
            )

            if response.status_code != 200:
                sys.stdout.write(RED)
                sys.stdout.write(
                    f"エラー: 送信失敗（ステータスコード: {response.status_code}）\n"
                )
        except Exception as exc:
            sys.stdout.write(RED)
            sys.stdout.write(f"エラー: 送信中に例外が発生: {exc}\n")
