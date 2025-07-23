import av

from . import utils

VFR_TIMESTAMP_BUFFER_MS = 500.0


def get_video_properties(path: str, is_vfr: bool, num_frames: int, time_end: str | None) -> dict:
    properties = {
        'height': 0,
        'start_time_offset_ms': 0.0,
        'frame_timestamps': {}
    }

    with av.open(path) as container:
        stream = container.streams.video[0]
        properties['height'] = stream.height
        if stream.start_time is not None:
            properties['start_time_offset_ms'] = float(stream.start_time * stream.time_base * 1000)

        if is_vfr:
            print("Variable frame rate detected. Building timestamp map...")
            stop_at_ms = None
            if time_end:
                stop_at_ms = utils.get_ms_from_time_str(time_end) + VFR_TIMESTAMP_BUFFER_MS

            stopped_early = False
            frame_iter = container.decode(stream)
            for i in range(num_frames):
                print(f"\rMapping frame {i + 1} of {num_frames}", end="", flush=True)

                try:
                    frame = next(frame_iter)
                    timestamp_ms = float(frame.pts * stream.time_base * 1000)
                    properties['frame_timestamps'][i] = timestamp_ms

                    if stop_at_ms and timestamp_ms > stop_at_ms:
                        print(f"\nReached target time. Stopped map generation after frame {i + 1}.")
                        stopped_early = True
                        break
                except StopIteration:
                    pass
            if not stopped_early:
                print()

    return properties


class Capture:
    def __init__(self, video_path):
        self.path = video_path
        self.container = None
        self.stream = None
        self.frame_iterator = None

    def __enter__(self):
        try:
            self.container = av.open(self.path)
            self.stream = self.container.streams.video[0]
            self.frame_iterator = self.container.decode(self.stream)
            return self
        except av.AVError as e:
            raise OSError(f'Can not open video {self.path}.') from e

    def __exit__(self, exc_type, exc_value, traceback):
        if self.container:
            self.container.close()

    def read(self):
        try:
            frame = next(self.frame_iterator)
            return True, frame.to_ndarray(format='rgb24')
        except StopIteration:
            return False, None

    def grab(self):
        try:
            next(self.frame_iterator)
            return True
        except StopIteration:
            return False
