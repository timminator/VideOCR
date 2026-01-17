import av
import cv2

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

        if container.start_time is not None:
            properties['start_time_offset_ms'] = container.start_time / 1000.0

        if is_vfr:
            print("Variable frame rate detected. Building timestamp map...", flush=True)
            stop_at_ms = None
            if time_end:
                relative_end_ms = utils.get_ms_from_time_str(time_end)
                absolute_target_ms = relative_end_ms + properties['start_time_offset_ms']
                stop_at_ms = absolute_target_ms + VFR_TIMESTAMP_BUFFER_MS

            frame_iter = container.decode(stream)
            num_frames_to_map = properties['num_frames']
            stopped_early = False

            if num_frames_to_map > 0:
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
                        properties['num_frames'] = i
                        break
            else:
                print("Frame count not found. Estimating progress based on duration...", flush=True)

                duration_sec = float(container.duration / av.time_base) if container.duration is not None else 0.0
                estimated_frames = int(duration_sec * properties['fps']) if duration_sec > 0 and properties['fps'] > 0 else 0
                progress_total = f"~{estimated_frames}" if estimated_frames > 0 else "unknown"

                i = 0
                while True:
                    print(f"\rMapping frame {i + 1} of {progress_total}", end="", flush=True)
                    try:
                        frame = next(frame_iter)
                        timestamp_ms = float(frame.pts * stream.time_base * 1000)
                        properties['frame_timestamps'][i] = timestamp_ms

                        if stop_at_ms and timestamp_ms > stop_at_ms:
                            print(f"\nReached target time. Stopped map generation after frame {i + 1}.", flush=True)
                            stopped_early = True
                            properties['num_frames'] = i + 1
                            break
                        i += 1
                    except StopIteration:
                        properties['num_frames'] = i
                        break

            if not stopped_early:
                print()

    return properties


class Capture:
    def __init__(self, video_path):
        self.path = video_path

    def __enter__(self):
        self.cap = cv2.VideoCapture(self.path)
        if not self.cap.isOpened():
            raise OSError(f'Can not open video {self.path}.')
        return self.cap

    def __exit__(self, exc_type, exc_value, traceback):
        self.cap.release()
