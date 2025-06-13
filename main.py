import os
import queue
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pyaudio
import requests
from dotenv import load_dotenv
from google import genai
from google.cloud import speech

load_dotenv()

# API設定
API_BASE_URL = os.environ.get("API_BASE_URL")
API_KEY = os.environ.get("API_KEY")

# Audio recording parameters
STREAMING_LIMIT = 240000  # 4 minutes
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE / 10)  # 100ms

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"

# 翻訳用のスレッドプール
translator_pool = ThreadPoolExecutor(max_workers=2)

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def get_current_time() -> int:
    """Return Current Time in MS.

    Returns:
        int: Current Time in MS.
    """
    return int(round(time.time() * 1000))


class ResumableMicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(
        self: object,
        rate: int,
        chunk_size: int,
    ) -> None:
        """Creates a resumable microphone stream.

        Args:
        self: The class instance.
        rate: The audio file's sampling rate.
        chunk_size: The audio file's chunk size.

        returns: None
        """
        self._rate = rate
        self.chunk_size = chunk_size
        self._num_channels = 1
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()
        self.restart_counter = 0
        self.audio_input = []
        self.last_audio_input = []
        self.result_end_time = 0
        self.is_final_end_time = 0
        self.final_request_end_time = 0
        self.bridging_offset = 0
        self.last_transcript_was_final = False
        self.new_stream = True
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=self._num_channels,
            rate=self._rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

    def __enter__(self: object) -> object:
        """Opens the stream.

        Args:
        self: The class instance.

        returns: None
        """
        self.closed = False
        return self

    def __exit__(
        self: object,
        type: object,
        value: object,
        traceback: object,
    ) -> object:
        """Closes the stream and releases resources.

        Args:
        self: The class instance.
        type: The exception type.
        value: The exception value.
        traceback: The exception traceback.

        returns: None
        """
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(
        self: object,
        in_data: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Continuously collect data from the audio stream, into the buffer.

        Args:
        self: The class instance.
        in_data: The audio data as a bytes object.
        args: Additional arguments.
        kwargs: Additional arguments.

        returns: None
        """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self: object) -> object:
        """Stream Audio from microphone to API and to local buffer

        Args:
            self: The class instance.

        returns:
            The data from the audio stream.
        """
        while not self.closed:
            data = []

            if self.new_stream and self.last_audio_input:
                chunk_time = STREAMING_LIMIT / len(self.last_audio_input)

                if chunk_time != 0:
                    if self.bridging_offset < 0:
                        self.bridging_offset = 0

                    if self.bridging_offset > self.final_request_end_time:
                        self.bridging_offset = self.final_request_end_time

                    chunks_from_ms = round(
                        (self.final_request_end_time - self.bridging_offset)
                        / chunk_time
                    )

                    self.bridging_offset = round(
                        (len(self.last_audio_input) - chunks_from_ms) * chunk_time
                    )

                    for i in range(chunks_from_ms, len(self.last_audio_input)):
                        data.append(self.last_audio_input[i])

                self.new_stream = False

            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            self.audio_input.append(chunk)

            if chunk is None:
                return
            data.append(chunk)
            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)

                    if chunk is None:
                        return
                    data.append(chunk)
                    self.audio_input.append(chunk)

                except queue.Empty:
                    break

            yield b"".join(data)


def translate_text(text: str) -> str:
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[
                """
                あなたには韓国のソシャゲ、Limbus Companyのシーズン6のロードマップ説明放送の内容を日本語に翻訳してもらいます。
                用語としては以下のようなものがあります。
                림버스 컴퍼니: Limbus Company
                이상: イサン
                파우스트: ファウスト
                돈 키호테: ドンキホーテ
                료슈: 良秀
                뫼르소: ムルソー
                홍루: ホンル
                히스클리프: ヒースクリフ
                이스마엘: イシュメール
                로디온: ロージャ
                싱클레어: シンクレア
                아웃티스: ウーティス
                그레고르: グレゴール
                수감자: 囚人
                인격: 人格
                EGO: EGO
                거울 던전: 鏡ダンジョン
                거울 굴절 철도: 鏡屈折鉄道
                발푸르기스의 밤: ヴァルプルギスの夜
                흑수: 黒獣
                가주 후보: 家主候補
                레이혼: レイホン
                지아·초우: ジア・チォウ
                로보토미 코퍼레이션: Lobotomy Corporation
                라이브러리 오브 루이나: Library of Ruina(ラオル)
                티페리트: ティファレト
                증오의 여왕: 憎しみの女王
                절망의 기사: 絶望の騎士
                탐욕의 왕: 貪欲の王
                분노의 시종: 憤怒の従者
                마법소녀: 魔法少女
                명일방주: アークナイツ
                これらの用語集を参考に以下の韓国語の文章を日本語に翻訳してください。
                翻訳結果以外は何も出力しないでください。
                """ + text
            ],
        )

        return response.text
    except Exception as e:
        return f"翻訳エラー: {e}"


def print_translation(translated_text: str, korean_text: str, timestamp: int) -> None:
    """翻訳結果を表示し、Webサーバーに送信する関数"""
    # 現在時刻のタイムスタンプを取得（ミリ秒単位）
    current_timestamp = int(time.time() * 1000)
    
    # コンソールに表示
    sys.stdout.write(YELLOW)
    sys.stdout.write(f"{timestamp}: 韓国語: {korean_text}\n")
    sys.stdout.write(f"{timestamp}: 翻訳: {translated_text}\n")

    # Webサーバーに送信
    if API_BASE_URL:
        try:
            headers = {}
            if API_KEY:
                headers["X-API-Key"] = API_KEY

            payload = {
                "timestamp": current_timestamp,
                "translation": translated_text,
                "korean_text": korean_text
            }

            response = requests.post(
                API_BASE_URL,
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                sys.stdout.write(RED)
                sys.stdout.write(
                    f"エラー: 送信失敗（ステータスコード: {response.status_code}）\n"
                )

        except Exception as e:
            sys.stdout.write(RED)
            sys.stdout.write(f"エラー: 送信中に例外が発生: {str(e)}\n")


def listen_print_loop(responses: object, stream: object) -> None:
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.

    Arg:
        responses: The responses returned from the API.
        stream: The audio stream to be processed.
    """
    for response in responses:
        if get_current_time() - stream.start_time > STREAMING_LIMIT:
            stream.start_time = get_current_time()
            break

        if not response.results:
            continue

        result = response.results[0]

        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript

        result_seconds = 0
        result_micros = 0

        if result.result_end_time.seconds:
            result_seconds = result.result_end_time.seconds

        if result.result_end_time.microseconds:
            result_micros = result.result_end_time.microseconds

        stream.result_end_time = int((result_seconds * 1000) + (result_micros / 1000))

        corrected_time = (
            stream.result_end_time
            - stream.bridging_offset
            + (STREAMING_LIMIT * stream.restart_counter)
        )

        if result.is_final:
            sys.stdout.write(GREEN)
            sys.stdout.write("\033[K")
            sys.stdout.write(str(corrected_time) + ": " + transcript + "\n")

            # 翻訳を非同期で実行
            translator_pool.submit(
                lambda t=transcript, ts=corrected_time: print_translation(
                    translate_text(t), t, ts
                )
            )

            stream.is_final_end_time = stream.result_end_time
            stream.last_transcript_was_final = True

            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                sys.stdout.write(YELLOW)
                sys.stdout.write("Exiting...\n")
                stream.closed = True
                break
        else:
            sys.stdout.write(RED)
            sys.stdout.write("\033[K")
            sys.stdout.write(str(corrected_time) + ": " + transcript + "\r")

            stream.last_transcript_was_final = False


def main() -> None:
    """start bidirectional streaming from microphone input to speech API"""
    client = speech.SpeechClient()

    # Create speech adaptation configuration
    phrase_set = speech.PhraseSet(
        phrases=[
            {"value": "림버스 컴퍼니", "boost": 20},  # limbus company
            {"value": "이상", "boost": 15},  # イサン
            {"value": "파우스트", "boost": 15},  # ファウスト
            {"value": "돈 키호테", "boost": 15},  # ドンキホーテ
            {"value": "료슈", "boost": 15},  # 良秀
            {"value": "뫼르소", "boost": 15},  # ムルソー
            {"value": "홍루", "boost": 15},  # ホンル
            {"value": "히스클리프", "boost": 15},  # ヒースクリフ
            {"value": "이스마엘", "boost": 15},  # イシュメール
            {"value": "로디온", "boost": 15},  # ロージャ
            {"value": "싱클레어", "boost": 15},  # シンクレア
            {"value": "아웃티스", "boost": 15},  # ウーティス
            {"value": "그레고르", "boost": 15},  # グレゴール
            {"value": "티페리트", "boost": 15},  # 囚人
            {"value": "인격", "boost": 15},  # 人格
            {"value": "EGO", "boost": 15},  # EGO
            {"value": "거울 던전", "boost": 15},  # 鏡ダンジョン
            {"value": "거울 굴절 철도", "boost": 15},  # 鏡屈折鉄道
            {"value": "발푸르기스의 밤", "boost": 15},  # ヴァルプルギスの夜
            {"value": "흑수", "boost": 15},  # 黒獣
            {"value": "가주 후보", "boost": 15},  # 家主候補
            {"value": "레이혼", "boost": 15},  # レイホン
            {"value": "지아·초우", "boost": 15},  # ジア・チォウ
            {"value": "로보토미 코퍼레이션", "boost": 15},  # Lobotomy Corporation
            {"value": "라이브러리 오브 루이나", "boost": 15},  # Library of Ruina(ラオル)
            {"value": "티페리트", "boost": 15},  # ティファレト
            {"value": "증오의 여왕", "boost": 15},  # 憎しみの女王
            {"value": "절망의 기사", "boost": 15},  # 絶望の騎士
            {"value": "탐욕의 왕", "boost": 15},  # 貪欲の王
            {"value": "분노의 시종", "boost": 15},  # 憤怒の従者
            {"value": "마법소녀", "boost": 15},  # 魔法少女
            {"value": "명일방주", "boost": 15},  # アークナイツ
        ]
    )

    speech_adaptation = speech.SpeechAdaptation(
        phrase_sets=[phrase_set]
    )

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code="ko-KR",
        max_alternatives=1,
        adaptation=speech_adaptation,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    mic_manager = ResumableMicrophoneStream(SAMPLE_RATE, CHUNK_SIZE)
    print(mic_manager.chunk_size)
    sys.stdout.write(YELLOW)
    sys.stdout.write('\nListening, say "Quit" or "Exit" to stop.\n\n')
    sys.stdout.write("End (ms)       Transcript Results/Status\n")
    sys.stdout.write("=====================================================\n")

    with mic_manager as stream:
        while not stream.closed:
            sys.stdout.write(YELLOW)
            sys.stdout.write(
                "\n" + str(STREAMING_LIMIT * stream.restart_counter) + ": NEW REQUEST\n"
            )

            stream.audio_input = []
            audio_generator = stream.generator()

            requests = (
                speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator
            )

            responses = client.streaming_recognize(streaming_config, requests)

            # Now, put the transcription responses to use.
            listen_print_loop(responses, stream)

            if stream.result_end_time > 0:
                stream.final_request_end_time = stream.is_final_end_time
            stream.result_end_time = 0
            stream.last_audio_input = []
            stream.last_audio_input = stream.audio_input
            stream.audio_input = []
            stream.restart_counter = stream.restart_counter + 1

            if not stream.last_transcript_was_final:
                sys.stdout.write("\n")
            stream.new_stream = True


if __name__ == "__main__":
    main()
