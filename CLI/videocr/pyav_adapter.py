from __future__ import annotations

from collections.abc import Iterator
from types import TracebackType
from typing import TypedDict

import av


class VideoProperties(TypedDict):
    height: int
    width: int
    duration_ms: int
    start_time_offset_ms: float


def get_video_properties(path: str) -> VideoProperties:
    properties: VideoProperties = {
        'height': 0,
        'width': 0,
        'duration_ms': 0,
        'start_time_offset_ms': 0.0,
    }

    with av.open(path) as container:
        stream = container.streams.video[0]
        properties['height'] = int(stream.height)
        properties['width'] = int(stream.width)

        if container.duration is not None:
            properties['duration_ms'] = int(container.duration / 1000.0)
        elif stream.duration is not None and stream.time_base is not None:
            properties['duration_ms'] = int(stream.duration * float(stream.time_base) * 1000.0)

        if container.start_time is not None:
            properties['start_time_offset_ms'] = container.start_time / 1000.0

    return properties


class Capture:
    def __init__(self, video_path: str) -> None:
        self.path: str = video_path
        self.container: av.container.InputContainer | None = None
        self.stream: av.video.stream.VideoStream | None = None
        self.frame_iterator: Iterator[av.VideoFrame] | None = None

    def __enter__(self) -> Capture:
        try:
            self.container = av.open(self.path)
            self.stream = self.container.streams.video[0]
            self.stream.thread_type = 'FRAME'
            self.frame_iterator = self.container.decode(self.stream)
            return self
        except av.error.FFmpegError as e:
            raise OSError(f'Can not open video {self.path}.') from e

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        if self.container:
            self.container.close()

    def read(self) -> tuple[bool, av.VideoFrame | None, float]:
        try:
            if self.frame_iterator is None or self.stream is None or self.stream.time_base is None:
                return False, None, 0.0

            frame = next(self.frame_iterator)
            timestamp = float(frame.pts * self.stream.time_base * 1000) if frame.pts is not None else 0.0
            return True, frame, timestamp

        except StopIteration:
            return False, None, 0.0
