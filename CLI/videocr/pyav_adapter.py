import av

from . import utils

VFR_TIMESTAMP_BUFFER_MS = 500.0


def get_video_properties(path: str, is_vfr: bool, time_end: str | None, initial_fps: float, initial_num_frames: int) -> dict:
    properties = {
        'height': 0,
        'fps': initial_fps,
        'num_frames': initial_num_frames,
        'start_time_offset_ms': 0.0,
        'frame_timestamps': {}
    }

    with av.open(path) as container:
        stream = container.streams.video[0]
        properties['height'] = stream.height

        if not properties['fps'] or properties['fps'] <= 0:
            properties['fps'] = float(stream.average_rate)

        if not properties['num_frames'] or properties['num_frames'] <= 0:
            if stream.frames > 0:
                properties['num_frames'] = stream.frames
            elif stream.duration is not None and properties['fps'] > 0:
                duration_sec = float(stream.duration * stream.time_base)
                properties['num_frames'] = int(duration_sec * properties['fps'])

        if container.start_time is not None:
            properties['start_time_offset_ms'] = container.start_time / 1000.0

        if is_vfr:
            print("Variable frame rate detected. Building timestamp map...", flush=True)
            stop_at_ms = None
            if time_end:
                relative_end_ms = utils.get_ms_from_time_str(time_end)
                absolute_target_ms = relative_end_ms + properties['start_time_offset_ms']
                stop_at_ms = absolute_target_ms + VFR_TIMESTAMP_BUFFER_MS

            num_frames_to_map = properties['num_frames']
            stopped_early = False
            frame_iter = container.decode(stream)
            for i in range(num_frames_to_map):
                print(f"\rMapping frame {i + 1} of {num_frames_to_map}", end="", flush=True)

                try:
                    frame = next(frame_iter)
                    timestamp_ms = float(frame.pts * stream.time_base * 1000)
                    properties['frame_timestamps'][i] = timestamp_ms

                    if stop_at_ms and timestamp_ms > stop_at_ms:
                        print(f"\nReached target time. Stopped map generation after frame {i + 1}.", flush=True)
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
