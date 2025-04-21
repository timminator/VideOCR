from __future__ import annotations
from typing import List
import cv2
import numpy as np
import os
import subprocess
import ast
import re
import tempfile
import shutil

from . import utils
from .models import PredictedFrames, PredictedSubtitle
from .opencv_adapter import Capture


class Video:
    path: str
    lang: str
    use_fullframe: bool
    paddleocr_path: str
    det_model_dir: str
    rec_model_dir: str
    cls_model_dir: str
    num_frames: int
    fps: float
    height: int
    pred_frames: List[PredictedFrames]
    pred_subs: List[PredictedSubtitle]

    def __init__(self, path: str, paddleocr_path: str, det_model_dir: str, rec_model_dir: str, cls_model_dir: str):
        self.path = path
        self.paddleocr_path = paddleocr_path
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self.cls_model_dir = cls_model_dir
        with Capture(path) as v:
            self.num_frames = int(v.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = v.get(cv2.CAP_PROP_FPS)
            self.height = int(v.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def run_ocr(self, use_gpu: bool, lang: str, use_angle_cls: bool, time_start: str, time_end: str,
                conf_threshold: int, use_fullframe: bool, brightness_threshold: int, similar_image_threshold: int, similar_pixel_threshold: int, frames_to_skip: int,
                crop_x: int, crop_y: int, crop_width: int, crop_height: int) -> None:
        conf_threshold_percent = float(conf_threshold/100)
        self.lang = lang
        self.use_fullframe = use_fullframe
        self.pred_frames = []

        ocr_start = utils.get_frame_index(time_start, self.fps) if time_start else 0
        ocr_end = utils.get_frame_index(time_end, self.fps) if time_end else self.num_frames

        if ocr_end < ocr_start:
            raise ValueError('time_start is later than time_end')
        num_ocr_frames = ocr_end - ocr_start

        crop_x_end = None
        crop_y_end = None
        if crop_x and crop_y and crop_width and crop_height:
            crop_x_end = crop_x + crop_width
            crop_y_end = crop_y + crop_height

        TEMP_PREFIX = "videocr_temp_"
        base_temp = tempfile.gettempdir()
        for name in os.listdir(base_temp):
            if name.startswith(TEMP_PREFIX):
                try:
                    shutil.rmtree(os.path.join(base_temp, name), ignore_errors=True)
                except Exception as e:
                    print(f"Could not remove leftover temp dir '{name}': {e}")

        temp_dir = tempfile.mkdtemp(prefix=TEMP_PREFIX)

        # get frames from ocr_start to ocr_end
        frame_paths = []
        frame_indices = []
        with Capture(self.path) as v:
            v.set(cv2.CAP_PROP_POS_FRAMES, ocr_start)
            prev_grey = None
            predicted_frames = None
            modulo = frames_to_skip + 1
            for i in range(num_ocr_frames):
                print(f"\rStep 1: Processing image {i+1} of {num_ocr_frames}", end="", flush=True)
                if i % modulo == 0:
                    frame = v.read()[1]
                    if not self.use_fullframe:
                        if crop_x_end and crop_y_end:
                            frame = frame[crop_y:crop_y_end, crop_x:crop_x_end]
                        else:
                            # only use bottom third of the frame by default
                            frame = frame[2 * self.height // 3:, :]

                    if brightness_threshold:
                        frame = cv2.bitwise_and(
                            frame, frame,
                            mask=cv2.inRange(frame,
                                            (brightness_threshold,) * 3,
                                            (255,) * 3)
                        )

                    if similar_image_threshold:
                        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        if prev_grey is not None:
                            _, absdiff = cv2.threshold(
                                cv2.absdiff(prev_grey, grey),
                                similar_pixel_threshold, 255, cv2.THRESH_BINARY)
                            if np.count_nonzero(absdiff) < similar_image_threshold:
                                prev_grey = grey
                                continue
                        prev_grey = grey

                    frame_index = i + ocr_start
                    frame_filename = f"frame_{frame_index}.jpg"
                    frame_path = os.path.join(temp_dir, frame_filename)
                    cv2.imwrite(frame_path, frame)

                    frame_paths.append(frame_path)
                    frame_indices.append(frame_index)
                else:
                    v.read()

        print()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        args = [
            self.paddleocr_path,
            "--image_dir", temp_dir,
            "--use_gpu", "true" if use_gpu else "false",
            "--use_angle_cls", "true" if use_angle_cls else "false",
            "--lang", self.lang,
            "--show_log", "false"
        ]

        # Conditionally add model dirs
        if self.det_model_dir:
            args += ["--det_model_dir", self.det_model_dir]
        if self.rec_model_dir:
            args += ["--rec_model_dir", self.rec_model_dir]
        if self.cls_model_dir:
            args += ["--cls_model_dir", self.cls_model_dir]

        print("Starting PaddleOCR... This can take a while...")

        if not os.path.isfile(self.paddleocr_path):
            raise IOError(f"PaddleOCR executable not found at: {self.paddleocr_path}")

        # Run PaddleOCR
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, bufsize=1) as process:
            # Parse results into {filename: [ocr lines]}
            ocr_outputs = {}
            current_image = None
            total_images = len(frame_paths)
            ocr_image_index = 0
            for line in process.stdout:
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
                        # Extract only the OCR data after 'ppocr INFO:'
                        match = re.search(r"ppocr INFO:\s*(\[.+\])", line)
                        if match:
                            parsed = ast.literal_eval(match.group(1))
                            ocr_outputs[current_image].append(parsed)
                    except Exception as e:
                        print(f"Error parsing OCR for {current_image}: {e}")

        print()

        # Map to predictedframes
        previous_index = None
        previous_pred = None

        for path in frame_paths:
            frame_filename = os.path.basename(path)
            match = re.search(r"frame_(\d+)\.jpg", frame_filename)
            if not match:
                continue

            frame_index = int(match.group(1))
            ocr_result = ocr_outputs.get(frame_filename, [])
            pred_data = [ocr_result] if ocr_result else [[]]
            predicted_frames = PredictedFrames(frame_index, pred_data, conf_threshold_percent)
            self.pred_frames.append(predicted_frames)

            # Handle skipped frames (due to similarity threshold)
            if previous_index is not None and frame_index > previous_index + 1:
                # We assume the skipped frames belong to the previous prediction
                previous_pred.end_index = frame_index - 2

            previous_index = frame_index
            previous_pred = predicted_frames

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def get_subtitles(self, sim_threshold: int) -> str:
        self._generate_subtitles(sim_threshold)
        return ''.join(
            '{}\n{} --> {}\n{}\n\n'.format(
                i,
                utils.get_srt_timestamp(sub.index_start, self.fps),
                utils.get_srt_timestamp(sub.index_end, self.fps),
                sub.text)
            for i, sub in enumerate(self.pred_subs))

    def _generate_subtitles(self, sim_threshold: int) -> None:
        print("Generating subtitles...")
        self.pred_subs = []

        if self.pred_frames is None:
            raise AttributeError(
                'Please call self.run_ocr() first to perform ocr on frames')

        max_frame_merge_diff = int(0.09 * self.fps)
        for frame in self.pred_frames:
            self._append_sub(PredictedSubtitle([frame], sim_threshold), max_frame_merge_diff)
        self.pred_subs = [sub for sub in self.pred_subs if len(sub.frames[0].lines) > 0]

    def _append_sub(self, sub: PredictedSubtitle, max_frame_merge_diff: int) -> None:
        if len(sub.frames) == 0:
            return

        # merge new sub to the last subs if they are not empty, similar and within 0.09 seconds apart
        if self.pred_subs:
            last_sub = self.pred_subs[-1]
            if len(last_sub.frames[0].lines) > 0 and sub.index_start - last_sub.index_end <= max_frame_merge_diff and last_sub.is_similar_to(sub):
                del self.pred_subs[-1]
                sub = PredictedSubtitle(last_sub.frames + sub.frames, sub.sim_threshold)

        self.pred_subs.append(sub)
