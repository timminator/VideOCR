import datetime
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import IO

import av
import numpy as np
from cpuid import cpuid, xgetbv  # type: ignore

from .lang_dictionaries import (
    ARABIC_LANGS,
    CYRILLIC_LANGS,
    DEVANAGARI_LANGS,
    ESLAV_LANGS,
    LATIN_LANGS,
)
from .models import PredictedText

ALIGNMENT_MAP = {
    'bottom-left': 'an1', 'bottom-center': 'an2', 'bottom-right': 'an3',
    'middle-left': 'an4', 'middle-center': 'an5', 'middle-right': 'an6',
    'top-left': 'an7', 'top-center': 'an8', 'top-right': 'an9',
}
VALID_ALIGNMENT_NAMES = set(ALIGNMENT_MAP.keys())


def get_ms_from_time_str(time_str: str) -> float:
    """Convert time string to milliseconds."""
    t = [float(x) for x in time_str.split(":")]
    if len(t) == 3:
        td = datetime.timedelta(hours=t[0], minutes=t[1], seconds=t[2])
    elif len(t) == 2:
        td = datetime.timedelta(minutes=t[0], seconds=t[1])
    else:
        raise ValueError(f'Time data "{time_str}" does not match format "%H:%M:%S"')
    return td.total_seconds() * 1000


def get_srt_timestamp(frame_index: int, fps: float, offset_ms: float = 0.0) -> str:
    """Convert frame index into SRT timestamp."""
    td = datetime.timedelta(milliseconds=(frame_index / fps * 1000 + offset_ms))
    ms = td.microseconds // 1000
    m, s = divmod(td.seconds, 60)
    h, m = divmod(m, 60)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def get_srt_timestamp_from_ms(ms: float) -> str:
    """Convert milliseconds into SRT timestamp."""
    td = datetime.timedelta(milliseconds=ms)
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    milliseconds = td.microseconds // 1000
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}'


def frame_to_array(frame: av.VideoFrame, fmt: str) -> np.ndarray:
    """Converts a frame to an array, safely falls back if threads arg is unsupported."""
    if not hasattr(frame_to_array, "supports_threads"):
        frame_to_array.supports_threads = True  # type: ignore

    if frame_to_array.supports_threads:  # type: ignore
        try:
            return frame.to_ndarray(format=fmt, threads=1)
        except TypeError:
            frame_to_array.supports_threads = False  # type: ignore

    return frame.to_ndarray(format=fmt)


# checks if two words are on the same line based on vertical overlap
def is_on_same_line(word1: PredictedText, word2: PredictedText) -> bool:
    """Checks if two words are on the same line based on vertical overlap."""
    y_min1 = min(p[1] for p in word1.bounding_box)
    y_max1 = max(p[1] for p in word1.bounding_box)
    y_min2 = min(p[1] for p in word2.bounding_box)
    y_max2 = max(p[1] for p in word2.bounding_box)

    midpoint1 = (y_min1 + y_max1) / 2
    midpoint2 = (y_min2 + y_max2) / 2

    return (y_min1 < midpoint2 < y_max1) or (y_min2 < midpoint1 < y_max2)


def extract_non_chinese_segments(text: str) -> list[tuple[str, str]]:
    """Extracts non chinese segments out of the detected text for post processing."""
    segments: list[tuple[str, str]] = []
    current_segment = ''

    def is_chinese(char: str) -> bool:
        return '\u4e00' <= char <= '\u9fff'

    for char in text:
        if is_chinese(char):
            if current_segment:
                segments.append(('non_chinese', current_segment))
                current_segment = ''
            segments.append(('chinese', char))
        else:
            current_segment += char

    if current_segment:
        segments.append(('non_chinese', current_segment))

    return segments


def find_paddleocr() -> str:
    """Finds the available PaddleOCR executable and returns its path."""
    program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    program_name = "paddleocr"
    ext = ".exe" if platform.system() == "Windows" else ".bin"
    executable_name = f"{program_name}{ext}"

    for entry in os.listdir(program_dir):
        if entry.startswith("PaddleOCR-"):
            path = os.path.join(program_dir, entry, executable_name)
            if os.path.isfile(path):
                return path

    raise FileNotFoundError(f"Could not find {executable_name} in any folder starting with 'PaddleOCR'")


def resolve_model_dirs(lang: str, use_server_model: bool) -> tuple[str, str, str]:
    """Resolves the model directory for the specified language and mode."""
    program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    base_path = os.path.join(program_dir, "PaddleOCR.PP-OCRv5.support.files")

    det_path = os.path.join(base_path, "det")
    rec_path = os.path.join(base_path, "rec")
    cls_path = os.path.join(base_path, "cls", "PP-LCNet_x1_0_textline_ori")

    mode = "server" if use_server_model else "mobile"

    # DET
    if lang == "ka":
        det_sub = "PP-OCRv3_mobile_det"
    else:
        det_sub = f"PP-OCRv5_{mode}_det"

    # REC
    if lang in ("ch", "chinese_cht", "japan"):
        rec_sub = f"PP-OCRv5_{mode}_rec"
    elif lang in LATIN_LANGS:
        rec_sub = "latin_PP-OCRv5_mobile_rec"
    elif lang in ARABIC_LANGS:
        rec_sub = "arabic_PP-OCRv5_mobile_rec"
    elif lang in ESLAV_LANGS:
        rec_sub = "eslav_PP-OCRv5_mobile_rec"
    elif lang in CYRILLIC_LANGS:
        rec_sub = "cyrillic_PP-OCRv5_mobile_rec"
    elif lang in DEVANAGARI_LANGS:
        rec_sub = "devanagari_PP-OCRv5_mobile_rec"
    elif lang in ("en", "korean", "th", "el", "te", "ta"):
        rec_sub = f"{lang}_PP-OCRv5_mobile_rec"
    elif lang == "ka":
        rec_sub = "ka_PP-OCRv3_mobile_rec"

    return (
        os.path.join(det_path, det_sub),
        os.path.join(rec_path, rec_sub),
        cls_path
    )


def perform_hardware_check(paddleocr_path: str, use_gpu: bool) -> None:
    """Checks if the current system supports the hardware requirements."""
    error_prefix = "Unsupported Hardware Error:"
    warning_prefix = "Hardware Check Warning:"

    def has_avx() -> bool:
        # CPUID leaf 1: Check AVX and OSXSAVE flags
        _, _, ecx, _ = cpuid(1)
        osxsave = bool(ecx & (1 << 27))
        avx = bool(ecx & (1 << 28))

        # OS support check: XGETBV for YMM registers
        ymm_supported = False
        if osxsave:
            try:
                xcr0 = xgetbv(0)
                ymm_supported = (xcr0 & 0b110) == 0b110
            except Exception:
                ymm_supported = False

        return avx and ymm_supported

    def check_cpu() -> None:
        try:
            if not has_avx():
                raise SystemExit(f"{error_prefix} CPU or Operating System does not support the AVX instruction set, which is required.")
        except Exception as e:
            print(f"{warning_prefix} Could not determine CPU AVX support due to an error: {e}. Functionality is uncertain.", flush=True)

    CUDA_COMPATIBILITY_MAP = {
        "CUDA-11.8": (6.1, 8.9) if platform.system() == "Windows" else (6.0, 8.9),
        "CUDA-12.9": (7.5, 12.0),
    }

    CUDA_DRIVER_MAP = {
        "CUDA-11.8": "451.22" if platform.system() == "Windows" else "450.36.06",
        "CUDA-12.9": "527.41" if platform.system() == "Windows" else "525.60.13",
    }

    def parse_version(v_str: str) -> tuple[int, ...]:
        return tuple(map(int, v_str.split('.')))

    def check_gpu() -> None:
        try:
            command = ["nvidia-smi", "--query-gpu=driver_version,compute_cap", "--format=csv,noheader"]
            result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')

            first_gpu_info = result.stdout.strip().split('\n')[0]
            if not first_gpu_info:
                raise SystemExit(f"{error_prefix} GPU mode enabled, but 'nvidia-smi' returned no GPU info.")

            driver_version_str, compute_cap_str = [item.strip() for item in first_gpu_info.split(',')]
            compute_capability = float(compute_cap_str)

            detected_cuda_version = next((v for v in CUDA_COMPATIBILITY_MAP if v in paddleocr_path), None)

            if detected_cuda_version:
                # Check Compute Capability
                min_cc, max_cc = CUDA_COMPATIBILITY_MAP[detected_cuda_version]
                if not (min_cc <= compute_capability <= max_cc):
                    raise SystemExit(
                        f"{error_prefix} GPU compute capability is {compute_capability}, but this build "
                        f"({detected_cuda_version}) requires a value between {min_cc} and {max_cc}."
                    )

                # Check NVIDIA Driver Version
                required_driver = CUDA_DRIVER_MAP[detected_cuda_version]
                if parse_version(driver_version_str) < parse_version(required_driver):
                    raise SystemExit(
                        f"{error_prefix} NVIDIA driver version is {driver_version_str}, but this build "
                        f"({detected_cuda_version}) requires version {required_driver} or newer."
                    )

        except Exception as e:
            print(f"{warning_prefix} Could not determine GPU support due to an error: {e}. Functionality is uncertain.", flush=True)

    check_cpu()

    build_folder_name = os.path.basename(os.path.dirname(paddleocr_path))

    if use_gpu and 'GPU' in build_folder_name.upper():
        check_gpu()


def read_pipe(pipe: IO[str], output_list: list[str]) -> None:
    """Reads lines from a pipe and appends them to a list."""
    try:
        for line in iter(pipe.readline, ''):
            output_list.append(line)
    finally:
        pipe.close()


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is still running."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            return str(pid) in result.stdout
        else:
            if os.path.exists(f"/proc/{pid}"):
                return True
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return False


def create_clean_temp_dir() -> str:
    """Cleans up orphaned temporary directories from previous crashed runs and creates a fresh one for the current process."""
    current_pid = os.getpid()
    temp_prefix = f"videocr_temp_{current_pid}_"
    base_temp = tempfile.gettempdir()

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
                        if not is_process_running(dir_pid):
                            shutil.rmtree(temp_path, ignore_errors=True)
            except Exception as e:
                print(f"Could not remove leftover temp dir '{name}': {e}", flush=True)

    return tempfile.mkdtemp(prefix=temp_prefix)


def log_error(message: str, log_name: str = "error_log.txt") -> str:
    """Saves errors to a log file."""
    if platform.system() == "Windows":
        log_dir = os.path.join(os.getenv('LOCALAPPDATA') or os.path.expanduser('~'), "VideOCR")
    else:
        log_dir = os.path.join(os.path.expanduser('~'), ".config", "VideOCR")

    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, log_name)
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")

    return log_path
