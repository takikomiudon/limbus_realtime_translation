"""client.audio_stream

Resumable PyAudio microphone stream used by Google Speech streaming.
"""

from __future__ import annotations

import queue
import time

import pyaudio

from client.config import STREAMING_LIMIT


def get_current_time() -> int:
    """Return the current time in milliseconds."""
    return int(round(time.time() * 1000))


class ResumableMicrophoneStream:
    """Open a recording stream as a generator yielding audio chunks."""

    def __init__(self, rate: int, chunk_size: int) -> None:
        """Create a resumable microphone stream."""
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
            stream_callback=self._fill_buffer,
        )

    def __enter__(self) -> ResumableMicrophoneStream:
        """Open the stream context."""
        self.closed = False
        return self

    def __exit__(self, type_, value, traceback) -> None:
        """Close the stream and release resources."""
        del type_, value, traceback
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, *args, **kwargs):
        """Collect data from the audio stream into the buffer."""
        del args, kwargs
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """Stream audio from microphone to API and to a local buffer."""
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

            chunk = self._buff.get()
            self.audio_input.append(chunk)

            if chunk is None:
                return
            data.append(chunk)

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
