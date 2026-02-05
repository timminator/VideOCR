from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

import cv2
import fast_ssim
import wordninja_enhanced as wordninja
from pymediainfo import MediaInfo

from . import utils
from .lang_dictionaries import ARABIC_LANGS
from .models import PredictedFrames, PredictedSubtitle
from .pyav_adapter import Capture, get_video_properties


class Video:
    path: str
    lang: str
    use_fullframe: bool
    paddleocr_path: str
    post_processing: bool
    det_model_dir: str
    rec_model_dir: str
    cls_model_dir: str
    num_frames: int
    fps: float
    height: int
    width: int
    pred_frames_zone1: list[PredictedFrames]
    pred_frames_zone2: list[PredictedFrames]
    pred_subs: list[PredictedSubtitle]
    validated_zones: list[dict[str, int | float]]
    is_vfr: bool
    frame_timestamps: dict[int, float]
    start_time_offset_ms: float

    def __init__(self, path: str, paddleocr_path: str, det_model_dir: str, rec_model_dir: str, cls_model_dir: str, time_end: str | None = None):
        self.path = path
        self.paddleocr_path = paddleocr_path
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self.cls_model_dir = cls_model_dir
        self.frame_timestamps = {}
        self.start_time_offset_ms = 0.0

        media_info = MediaInfo.parse(path)
        video_track = [t for t in media_info.tracks if t.track_type == 'Video'][0]

        initial_fps = float(video_track.frame_rate) if video_track.frame_rate else 0.0
        initial_num_frames = int(video_track.frame_count) if video_track.frame_count else 0

        self.is_vfr = (
            video_track.frame_rate_mode == 'VFR'
            or video_track.framerate_mode_original == 'VFR'
        )

        props = get_video_properties(self.path, self.is_vfr, time_end, initial_fps, initial_num_frames)
        self.height = props['height']
        self.width = props['width']
        self.fps = props['fps']
        self.num_frames = props['num_frames']
        self.start_time_offset_ms = props['start_time_offset_ms']
        self.frame_timestamps = props['frame_timestamps']

    def run_ocr(self, use_gpu: bool, lang: str, use_angle_cls: bool, time_start: str, time_end: str, conf_threshold: int, use_fullframe: bool,
                brightness_threshold: int, ssim_threshold: int, subtitle_position: str, frames_to_skip: int, crop_zones: list[dict], ocr_image_max_width: int) -> None:
        conf_threshold = float(conf_threshold / 100)
        ssim_threshold = float(ssim_threshold / 100)
        self.lang = lang
        self.use_fullframe = use_fullframe
        self.validated_zones = []
        self.pred_frames_zone1 = []
        self.pred_frames_zone2 = []

        if self.is_vfr:
            if time_start:
                start_target_ms = utils.get_ms_from_time_str(time_start) + self.start_time_offset_ms
                ocr_start = utils.get_frame_index_from_ms(self.frame_timestamps, start_target_ms)
            else:
                ocr_start = 0

            if time_end:
                end_target_ms = utils.get_ms_from_time_str(time_end) + self.start_time_offset_ms
                ocr_end = utils.get_frame_index_from_ms(self.frame_timestamps, end_target_ms)
            else:
                ocr_end = self.num_frames
        else:
            ocr_start = utils.get_frame_index(time_start, self.fps) if time_start else 0
            ocr_end = utils.get_frame_index(time_end, self.fps) if time_end else self.num_frames

        if ocr_end < ocr_start:
            raise ValueError('time_start is later than time_end')
        num_ocr_frames = ocr_end - ocr_start

        for zone in crop_zones:
            if zone['y'] >= self.height:
                print(self.height)
                raise ValueError(f"Crop Y position ({zone['y']}) is outside video height ({self.height}).")
            if zone['x'] >= self.width:
                raise ValueError(f"Crop X position ({zone['x']}) is outside video width ({self.width}).")

            if zone['y'] + zone['height'] > self.height:
                print(f"Warning: Crop area extends out of bounds (crop_y + crop_height > video height ({self.height})). The crop area will be clipped.", flush=True)
            if zone['x'] + zone['width'] > self.width:
                print(f"Warning: Crop area extends out of bounds (crop_x + crop_width > video width ({self.width})). The crop area will be clipped.", flush=True)

            self.validated_zones.append({
                'x_start': zone['x'],
                'y_start': zone['y'],
                'x_end': zone['x'] + zone['width'],
                'y_end': zone['y'] + zone['height'],
                'midpoint_y': zone['y'] + (zone['height'] / 2)
            })

        TEMP_PREFIX = f"videocr_temp_{os.getpid()}_"
        base_temp = tempfile.gettempdir()
        current_pid = os.getpid()

        for name in os.listdir(base_temp):
            if name.startswith("videocr_temp_"):
                temp_path = os.path.join(base_temp, name)
                try:
                    match = re.match(r"videocr_temp_(\d+)_", name)
                    if match:
                        dir_pid = int(match.group(1))

                        if dir_pid == current_pid:
                            continue

                        if os.path.isdir(temp_path):
                            if not utils.is_process_running(dir_pid):
                                shutil.rmtree(temp_path, ignore_errors=True)
                except Exception as e:
                    print(f"Could not remove leftover temp dir '{name}': {e}", flush=True)

        temp_dir = tempfile.mkdtemp(prefix=TEMP_PREFIX)

        # get frames from ocr_start to ocr_end
        frame_paths = []
        with Capture(self.path) as v:
            # PyAV does not support accurate seeking and this was also error prone with OpenCV before
            if ocr_start > 0:
                for i in range(ocr_start):
                    v.grab()
                    print(f"\rAdvancing to frame {i + 1}/{ocr_start}", end="", flush=True)
                print()

            prev_samples = [None] * len(self.validated_zones) if self.validated_zones else [None]
            modulo = frames_to_skip + 1
            padding = len(str(num_ocr_frames))
            for i in range(num_ocr_frames):
                print(f"\rStep 1: Processing image {i + 1} of {num_ocr_frames}", end="", flush=True)
                if i % modulo == 0:
                    read_success, frame = v.read()
                    if not read_success:
                        continue

                    # Determine regions to process
                    images_to_process = []
                    if use_fullframe:
                        images_to_process.append({'image': frame, 'zone_idx': 0})
                    elif self.validated_zones:
                        for idx, zone in enumerate(self.validated_zones):
                            images_to_process.append({
                                'image': frame[zone['y_start']:zone['y_end'], zone['x_start']:zone['x_end']],
                                'zone_idx': idx
                            })
                    else:
                        # Default to bottom third if no zones are specified
                        images_to_process.append({'image': frame[2 * self.height // 3:, :], 'zone_idx': 0})

                    for item in images_to_process:
                        img = item['image']
                        zone_idx = item['zone_idx']

                        if ocr_image_max_width and img.shape[1] > ocr_image_max_width:
                            original_height, original_width = img.shape[:2]
                            scale_ratio = ocr_image_max_width / original_width
                            new_height = int(original_height * scale_ratio)
                            img = cv2.resize(img, (ocr_image_max_width, new_height), interpolation=cv2.INTER_AREA)

                        if brightness_threshold:
                            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                            _, mask = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)
                            img = cv2.bitwise_and(img, img, mask=mask)

                        if ssim_threshold < 1:
                            w = img.shape[1]
                            if subtitle_position == "center":
                                w_margin = int(w * 0.35)
                                sample = img[:, w_margin:w - w_margin]
                            elif subtitle_position == "left":
                                sample = img[:, :int(w * 0.3)]
                            elif subtitle_position == "right":
                                sample = img[:, int(w * 0.7):]
                            elif subtitle_position == "any":
                                sample = img
                            else:
                                raise ValueError(f"Invalid subtitle_position: {subtitle_position}")

                            if prev_samples[zone_idx] is not None:
                                score = fast_ssim.ssim(prev_samples[zone_idx], sample, data_range=255)
                                if score > ssim_threshold:
                                    prev_samples[zone_idx] = sample
                                    continue
                            prev_samples[zone_idx] = sample

                        frame_index = i + ocr_start
                        frame_filename = f"frame_{frame_index:0{padding}d}_zone{zone_idx}.jpg"
                        frame_path = os.path.join(temp_dir, frame_filename)

                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        cv2.imwrite(frame_path, img)
                        frame_paths.append(frame_path)
                else:
                    v.grab()

        print()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        args = [
            self.paddleocr_path,
            "ocr",
            "--input", temp_dir,
            "--device", "gpu" if use_gpu else "cpu",
            "--use_textline_orientation", "true" if use_angle_cls else "false",
            "--use_doc_orientation_classify", "False",
            "--use_doc_unwarping", "False",
            "--lang", self.lang,
        ]

        # Conditionally add model dirs
        if self.det_model_dir:
            args += ["--text_detection_model_dir", self.det_model_dir]
            args += ["--text_detection_model_name", os.path.basename(self.det_model_dir)]
        if self.rec_model_dir:
            args += ["--text_recognition_model_dir", self.rec_model_dir]
            args += ["--text_recognition_model_name", os.path.basename(self.rec_model_dir)]
        if self.cls_model_dir and use_angle_cls:
            args += ["--textline_orientation_model_dir", self.cls_model_dir]
            args += ["--textline_orientation_model_name", os.path.basename(self.cls_model_dir)]

        print("Starting PaddleOCR... This can take a while...", flush=True)

        if not os.path.isfile(self.paddleocr_path):
            raise OSError(f"PaddleOCR executable not found at: {self.paddleocr_path}")

        # Run PaddleOCR
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, bufsize=1)

        stdout_lines = []
        stderr_lines = []

        stderr_thread = threading.Thread(target=utils.read_pipe, args=(process.stderr, stderr_lines))
        stderr_thread.start()

        ocr_outputs = {}
        current_image = None
        total_images = len(frame_paths)
        ocr_image_index = 0
        try:
            for line in iter(process.stdout.readline, ''):
                stdout_lines.append(line)
                line = line.strip()

                if "ppocr INFO: **********" in line:
                    match = re.search(r"\*+(.+?)\*+$", line)
                    if match:
                        current_image = os.path.basename(match.group(1)).strip()
                        ocr_outputs[current_image] = []
                        ocr_image_index += 1
                        print(f"\rStep 2: Performing OCR on image {ocr_image_index} of {total_images}", end="", flush=True)
                elif current_image and '[[' in line:
                    try:
                        match = re.search(r"ppocr INFO:\s*(\[.+\])", line)
                        if match:
                            ocr_data_raw = ast.literal_eval(match.group(1))
                            if self.lang in ARABIC_LANGS:
                                box, (text, score) = ocr_data_raw
                                corrected_data = [box, (utils.convert_visual_to_logical(text), score)]
                                ocr_outputs[current_image].append(corrected_data)
                            else:
                                ocr_outputs[current_image].append(ocr_data_raw)
                    except Exception as e:
                        print(f"Error parsing OCR for {current_image}: {e}", flush=True)
        finally:
            process.stdout.close()

        exit_code = process.wait()
        stderr_thread.join()
        print()

        if exit_code != 0:
            full_stdout = "".join(stdout_lines)
            full_stderr = "".join(stderr_lines)

            command_str = ' '.join(args)
            log_message = (
                f"PaddleOCR process failed with exit code {exit_code}.\n"
                f"Command: {command_str}\n\n"
                f"--- STDOUT ---\n{full_stdout}\n\n"
                f"--- STDERR ---\n{full_stderr}\n"
            )
            log_file_path = utils.log_error(log_message, log_name="paddleocr_error.log")
            print(f"Error: PaddleOCR failed. See the log file for technical details:\n{log_file_path}", flush=True)
            sys.exit(1)

        # Map to predicted_frames for each zone
        frame_predictions_by_zone = {0: {}, 1: {}}

        for path in frame_paths:
            frame_filename = os.path.basename(path)
            match = re.search(r"frame_(\d+)_zone(\d)\.jpg", frame_filename)
            if not match:
                continue
            frame_index, zone_index = int(match.group(1)), int(match.group(2))
            ocr_result = ocr_outputs.get(frame_filename, [])
            pred_data = [ocr_result] if ocr_result else [[]]

            predicted_frame = PredictedFrames(frame_index, pred_data, conf_threshold, zone_index)
            frame_predictions_by_zone[zone_index][frame_index] = predicted_frame

        for zone_idx in frame_predictions_by_zone:
            frames = sorted(frame_predictions_by_zone[zone_idx].values(), key=lambda f: f.start_index)

            if not frames:
                continue

            for i in range(len(frames) - 1):
                current_pred = frames[i]
                next_pred = frames[i + 1]

                current_pred.end_index = next_pred.start_index - 1

            if frames:
                frames[-1].end_index = ocr_end - 1

            frame_predictions_by_zone[zone_idx] = frames

        self.pred_frames_zone1 = frame_predictions_by_zone.get(0, [])
        self.pred_frames_zone2 = frame_predictions_by_zone.get(1, [])

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def get_subtitles(self, sim_threshold: int, max_merge_gap_sec: float, lang: str, post_processing: bool, min_subtitle_duration_sec: float) -> str:
        self._generate_subtitles(sim_threshold, max_merge_gap_sec, lang, post_processing, min_subtitle_duration_sec)

        srt_lines = []
        for i, sub in enumerate(self.pred_subs, 1):
            start_time, end_time = self._get_srt_timestamps(sub)
            srt_lines.append(f'{i}\n{start_time} --> {end_time}\n{sub.text}\n\n')

        return ''.join(srt_lines)

    def _generate_subtitles(self, sim_threshold: int, max_merge_gap_sec: float, lang: str, post_processing: bool, min_subtitle_duration_sec: float) -> None:
        print("Generating subtitles...", flush=True)

        subs_zone1 = self._process_single_zone(self.pred_frames_zone1, sim_threshold, max_merge_gap_sec, lang, post_processing, min_subtitle_duration_sec)
        subs_zone2 = self._process_single_zone(self.pred_frames_zone2, sim_threshold, max_merge_gap_sec, lang, post_processing, min_subtitle_duration_sec)

        if subs_zone1 and not subs_zone2:
            self.pred_subs = subs_zone1
        elif not subs_zone1 and subs_zone2:
            self.pred_subs = subs_zone2
        elif subs_zone1 and subs_zone2:
            self.pred_subs = self._merge_dual_zone_subtitles(subs_zone1, subs_zone2)
        else:
            self.pred_subs = []

    def _process_single_zone(self, pred_frames: list[PredictedFrames], sim_threshold: int, max_merge_gap_sec: float, lang: str,
                             post_processing: bool, min_subtitle_duration_sec: float) -> list[PredictedSubtitle]:
        if not pred_frames:
            return []

        language_mapping = {
            "en": "en",
            "fr": "fr",
            "german": "de",
            "it": "it",
            "es": "es",
            "pt": "pt"
        }

        language_model = None
        if post_processing:
            if lang in language_mapping:
                language_model = wordninja.LanguageModel(language=language_mapping[lang])

        subs = []
        for frame in sorted(pred_frames, key=lambda f: f.start_index):
            new_sub = PredictedSubtitle([frame], frame.zone_index, sim_threshold, lang, language_model)
            if not new_sub.text:
                continue

            if subs:
                last_sub = subs[-1]
                if self._is_gap_mergeable(last_sub, new_sub, max_merge_gap_sec) and last_sub.is_similar_to(new_sub):
                    last_sub.frames.extend(new_sub.frames)
                    last_sub.frames.sort(key=lambda f: f.start_index)
                else:
                    subs.append(new_sub)
            else:
                subs.append(new_sub)

        for sub in subs:
            sub.finalize_text(post_processing)

        # Filter out subs that are too short
        filtered_subs = [
            sub for sub in subs if self._get_subtitle_duration_sec(sub) >= min_subtitle_duration_sec
        ]

        if not filtered_subs:
            return []

        # Re-merge the cleaned-up list of subtitles if applicable
        cleaned_subs = [filtered_subs[0]]
        for next_sub in filtered_subs[1:]:
            last_sub = cleaned_subs[-1]
            if self._is_gap_mergeable(last_sub, next_sub, max_merge_gap_sec) and last_sub.is_similar_to(next_sub):
                last_sub.frames.extend(next_sub.frames)
                last_sub.frames.sort(key=lambda f: f.start_index)
                last_sub.finalize_text(post_processing)
            else:
                cleaned_subs.append(next_sub)

        return cleaned_subs

    def _merge_dual_zone_subtitles(self, subs1: list[PredictedSubtitle], subs2: list[PredictedSubtitle]) -> list[PredictedSubtitle]:
        all_subs = sorted(subs1 + subs2, key=lambda s: s.index_start)

        if not all_subs:
            return []

        merged_subs = [all_subs[0]]
        for current_sub in all_subs[1:]:
            last_sub = merged_subs[-1]

            if current_sub.index_start <= last_sub.index_end:
                last_zone_info = self.validated_zones[last_sub.zone_index]
                current_zone_info = self.validated_zones[current_sub.zone_index]

                if current_zone_info['midpoint_y'] < last_zone_info['midpoint_y']:
                    last_sub.text = f"{current_sub.text}\n{last_sub.text}"
                else:
                    last_sub.text = f"{last_sub.text}\n{current_sub.text}"

                last_sub.frames.extend(current_sub.frames)
                last_sub.frames.sort(key=lambda f: f.start_index)
            else:
                merged_subs.append(current_sub)

        return merged_subs

    def _get_srt_timestamps(self, sub: PredictedSubtitle) -> tuple[str, str]:
        if self.is_vfr:
            start_ms, end_ms = self._get_subtitle_ms_times(sub)
            start_time = utils.get_srt_timestamp_from_ms(start_ms)
            end_time = utils.get_srt_timestamp_from_ms(end_ms)
            return start_time, end_time
        else:
            start_time = utils.get_srt_timestamp(sub.index_start, self.fps, self.start_time_offset_ms)
            end_time = utils.get_srt_timestamp(sub.index_end + 1, self.fps, self.start_time_offset_ms)
            return start_time, end_time

    def _get_subtitle_ms_times(self, sub: PredictedSubtitle) -> tuple[float, float]:
        first_frame_ms = self.frame_timestamps.get(0, 0)
        correction_delta = first_frame_ms - self.start_time_offset_ms

        start_time_ms = self.frame_timestamps.get(sub.index_start, 0)
        end_time_ms = self.frame_timestamps.get(sub.index_end + 1)

        # For the end time, we try to get the timestamp of the next frame, if it doesn't exist, we fall back to estimating duration of last frame
        if end_time_ms is None:
            end_time_ms = self.frame_timestamps.get(sub.index_end, 0) + (1000 / self.fps)

        # Apply the correction to align with the container's start time
        corrected_start_time_ms = start_time_ms - correction_delta
        corrected_end_time_ms = end_time_ms - correction_delta

        return corrected_start_time_ms, corrected_end_time_ms

    def _get_subtitle_duration_sec(self, sub: PredictedSubtitle) -> float:
        if self.is_vfr:
            start_ms, end_ms = self._get_subtitle_ms_times(sub)
            return (end_ms - start_ms) / 1000
        else:
            return (sub.index_end + 1 - sub.index_start) / self.fps

    def _is_gap_mergeable(self, last_sub: PredictedSubtitle, next_sub: PredictedSubtitle, max_merge_gap_sec: float) -> bool:
        if self.is_vfr:
            _, last_end_ms = self._get_subtitle_ms_times(last_sub)
            next_start_ms, _ = self._get_subtitle_ms_times(next_sub)
            gap_ms = next_start_ms - last_end_ms
            return gap_ms <= (max_merge_gap_sec * 1000)
        else:
            max_frame_merge_diff = int(max_merge_gap_sec * self.fps) + 1
            gap_frames = next_sub.index_start - last_sub.index_end
            return gap_frames <= max_frame_merge_diff
