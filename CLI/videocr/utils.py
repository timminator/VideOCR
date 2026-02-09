import datetime
import os
import platform
import re
import subprocess
import sys

from cpuid import cpuid, cpuid_count, xgetbv

from .lang_dictionaries import (
    ARABIC_LANGS,
    CYRILLIC_LANGS,
    DEVANAGARI_LANGS,
    ESLAV_LANGS,
    LATIN_LANGS,
)
from .models import PredictedText


# convert time string to frame index
def get_frame_index(time_str: str, fps: float) -> int:
    t = time_str.split(':')
    t = list(map(float, t))
    if len(t) == 3:
        td = datetime.timedelta(hours=t[0], minutes=t[1], seconds=t[2])
    elif len(t) == 2:
        td = datetime.timedelta(minutes=t[0], seconds=t[1])
    else:
        raise ValueError(
            f'Time data "{time_str}" does not match format "%H:%M:%S"')

    total_seconds = td.total_seconds()
    if total_seconds < 0:
        return 0
    return int(total_seconds * fps)


# convert time string to milliseconds
def get_ms_from_time_str(time_str: str) -> float:
    t = time_str.split(':')
    t = list(map(float, t))
    if len(t) == 3:
        td = datetime.timedelta(hours=t[0], minutes=t[1], seconds=t[2])
    elif len(t) == 2:
        td = datetime.timedelta(minutes=t[0], seconds=t[1])
    else:
        raise ValueError(
            f'Time data "{time_str}" does not match format "%H:%M:%S"')
    return td.total_seconds() * 1000


# finds the frame index closest to the target millisecond timestamp.
def get_frame_index_from_ms(frame_timestamps: dict[int, float], target_ms: float) -> int:
    return min(frame_timestamps.items(), key=lambda item: abs(item[1] - target_ms))[0]


# convert frame index into SRT timestamp
def get_srt_timestamp(frame_index: int, fps: float, offset_ms: float = 0.0) -> str:
    td = datetime.timedelta(milliseconds=(frame_index / fps * 1000 + offset_ms))
    ms = td.microseconds // 1000
    m, s = divmod(td.seconds, 60)
    h, m = divmod(m, 60)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


# convert milliseconds into SRT timestamp
def get_srt_timestamp_from_ms(ms: float) -> str:
    td = datetime.timedelta(milliseconds=ms)
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    milliseconds = td.microseconds // 1000
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}'


# checks if two words are on the same line based on vertical overlap
def is_on_same_line(word1: PredictedText, word2: PredictedText) -> bool:
    y_min1 = min(p[1] for p in word1.bounding_box)
    y_max1 = max(p[1] for p in word1.bounding_box)
    y_min2 = min(p[1] for p in word2.bounding_box)
    y_max2 = max(p[1] for p in word2.bounding_box)

    midpoint1 = (y_min1 + y_max1) / 2
    midpoint2 = (y_min2 + y_max2) / 2

    return (y_min1 < midpoint2 < y_max1) or (y_min2 < midpoint1 < y_max2)


# extracts non chinese segments out of the detected text for post processing
def extract_non_chinese_segments(text) -> list[tuple[str, str]]:
    segments = []
    current_segment = ''

    def is_chinese(char):
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


# Converts sentences from the OCR's non-standard 'reversed visual' order to the correct 'logical' order.
def convert_visual_to_logical(text: str) -> str:

    ARABIC_CHARS = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+')
    ARABIC_TRAILING_PUNCT = re.compile(r'([،؟؛!,.:?()\'"]+)$')

    words = text.split()
    fixed_words = []
    arabic_words = []

    for w in words:
        if ARABIC_CHARS.search(w):
            m = ARABIC_TRAILING_PUNCT.search(w)
            if m:
                punct = m.group(1)
                core_word = w[:-len(punct)]
            else:
                punct = ''
                core_word = w

            reversed_core = core_word[::-1]

            arabic_words.append(reversed_core + punct)
        else:
            if arabic_words:
                fixed_words.extend(arabic_words[::-1])
                arabic_words = []
            fixed_words.append(w)

    if arabic_words:
        fixed_words.extend(arabic_words[::-1])

    return ' '.join(fixed_words)


# finds the available PaddleOCR executable and returns its path
def find_paddleocr() -> str:
    program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    base_folders = [
        "PaddleOCR-CPU-v1.4.0",
        "PaddleOCR-GPU-v1.4.0-CUDA-11.8",
        "PaddleOCR-GPU-v1.4.0-CUDA-12.9"
    ]
    program_name = "paddleocr"

    ext = ".exe" if platform.system() == "Windows" else ".bin"

    executable_name = f"{program_name}{ext}"

    for entry in os.listdir(program_dir):
        for base in base_folders:
            if entry.startswith(base):
                path = os.path.join(program_dir, entry, executable_name)
                if os.path.isfile(path):
                    return path

    raise FileNotFoundError(f"Could not find {executable_name} in any folder matching: {base_folders}")


# resolves the model directory for the specified language and mode
def resolve_model_dirs(lang: str, use_server_model: bool) -> tuple[str, str, str]:
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


# checks if the current system supports the hardware requirements
def perform_hardware_check(paddleocr_path: str, use_gpu: bool) -> None:
    error_prefix = "Unsupported Hardware Error:"
    warning_prefix = "Hardware Check Warning:"

    def has_avx2_and_fma() -> bool:
        # CPUID leaf 1: AVX, OSXSAVE, FMA
        _, _, ecx, _ = cpuid(1)
        osxsave = bool(ecx & (1 << 27))
        avx = bool(ecx & (1 << 28))
        fma = bool(ecx & (1 << 12))

        # OS support check: XGETBV for YMM registers
        ymm_supported = True
        if osxsave:
            try:
                xcr0 = xgetbv(0)
                ymm_supported = (xcr0 & 0b110) == 0b110
            except Exception:
                ymm_supported = False

        # CPUID leaf 7: AVX2
        _, ebx, _, _ = cpuid_count(7, 0)
        avx2 = bool(ebx & (1 << 5))

        return osxsave and avx and avx2 and fma and ymm_supported

    def check_cpu() -> None:
        try:
            if not has_avx2_and_fma():
                raise SystemExit(f"{error_prefix} CPU does not support AVX2 and/or FMA, which is required.")
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


# reads lines from a pipe and appends them to a list
def read_pipe(pipe, output_list: list[str]) -> None:
    try:
        for line in iter(pipe.readline, ''):
            output_list.append(line)
    finally:
        pipe.close()


# Check if a process with given PID is still running (cross-platform)
def is_process_running(pid: int) -> bool:
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


# saves errors to log file
def log_error(message: str, log_name: str = "error_log.txt") -> str:
    if platform.system() == "Windows":
        log_dir = os.path.join(os.getenv('LOCALAPPDATA'), "VideOCR")
    else:
        log_dir = os.path.join(os.path.expanduser('~'), ".config", "VideOCR")

    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, log_name)
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")

    return log_path
