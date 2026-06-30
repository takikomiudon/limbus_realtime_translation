"""client.speech_loop

Google Speech-to-Text streaming loop and final transcript handling.
"""

from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor

from google.cloud import speech

from client.audio_stream import ResumableMicrophoneStream, get_current_time
from client.config import CHUNK_SIZE, SAMPLE_RATE, STREAMING_LIMIT
from client.glossary import speech_phrases
from client.publisher import TranslationPublisher
from client.translator import GeminiTranslator

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"


def build_streaming_config() -> speech.StreamingRecognitionConfig:
    """Create the Speech-to-Text streaming configuration."""
    phrase_set = speech.PhraseSet(phrases=speech_phrases())
    speech_adaptation = speech.SpeechAdaptation(phrase_sets=[phrase_set])
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code="ko-KR",
        max_alternatives=1,
        adaptation=speech_adaptation,
    )
    return speech.StreamingRecognitionConfig(config=config, interim_results=True)


def listen_print_loop(
    responses: object,
    stream: ResumableMicrophoneStream,
    translator: GeminiTranslator,
    publisher: TranslationPublisher,
    translator_pool: ThreadPoolExecutor,
) -> None:
    """Read recognition responses and publish final translations."""
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
        result_seconds = result.result_end_time.seconds or 0
        result_micros = result.result_end_time.microseconds or 0
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
            translator_pool.submit(
                lambda text=transcript, timestamp=corrected_time: publisher.publish(
                    translator.translate_text(text),
                    text,
                    timestamp,
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


def run_speech_loop(
    translator: GeminiTranslator,
    publisher: TranslationPublisher,
) -> None:
    """Start bidirectional streaming from microphone input to Speech API."""
    client = speech.SpeechClient()
    streaming_config = build_streaming_config()
    mic_manager = ResumableMicrophoneStream(SAMPLE_RATE, CHUNK_SIZE)
    translator_pool = ThreadPoolExecutor(max_workers=2)

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
            listen_print_loop(
                responses,
                stream,
                translator,
                publisher,
                translator_pool,
            )

            if stream.result_end_time > 0:
                stream.final_request_end_time = stream.is_final_end_time
            stream.result_end_time = 0
            stream.last_audio_input = stream.audio_input
            stream.audio_input = []
            stream.restart_counter += 1

            if not stream.last_transcript_was_final:
                sys.stdout.write("\n")
            stream.new_stream = True
