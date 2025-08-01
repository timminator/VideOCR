import datetime
import os
import platform
import sys

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


# finds the available PaddleOCR executable and returns its path
def find_paddleocr() -> str:
    program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    possible_folders = [
        "PaddleOCR-CPU-v1.3.0",
        "PaddleOCR-GPU-v1.3.0-CUDA-11.8"
    ]
    program_name = "paddleocr"

    ext = ".exe" if platform.system() == "Windows" else ".bin"

    executable_name = f"{program_name}{ext}"

    for folder in possible_folders:
        path = os.path.join(program_dir, folder, executable_name)
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(f"Could not find {executable_name} in expected folders: {possible_folders}")


# resolves the model directory for the specified language and mode
def resolve_model_dirs(lang: str, use_server_model: bool) -> tuple[str, str, str]:
    program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    base_path = os.path.join(program_dir, "PaddleOCR.PP-OCRv5.support.files")

    det_path = os.path.join(base_path, "det")
    rec_path = os.path.join(base_path, "rec")
    cls_path = os.path.join(base_path, "cls", "PP-LCNet_x1_0_textline_ori")

    mode = "server" if use_server_model else "mobile"

    # DET
    if lang in {"ch", "chinese_cht", "en", "japan", "korean"} | LATIN_LANGS | ESLAV_LANGS:
        det_sub = f"PP-OCRv5_{mode}_det"
    else:
        det_sub = "PP-OCRv3_mobile_det"

    # REC
    if lang in ("ch", "chinese_cht", "en", "japan"):
        rec_sub = f"PP-OCRv5_{mode}_rec"
    elif lang in LATIN_LANGS:
        rec_sub = "latin_PP-OCRv5_mobile_rec"
    elif lang in ARABIC_LANGS:
        rec_sub = "arabic_PP-OCRv3_mobile_rec"
    elif lang in ESLAV_LANGS:
        rec_sub = "eslav_PP-OCRv5_mobile_rec"
    elif lang in CYRILLIC_LANGS:
        rec_sub = "cyrillic_PP-OCRv3_mobile_rec"
    elif lang in DEVANAGARI_LANGS:
        rec_sub = "devanagari_PP-OCRv3_mobile_rec"
    elif lang == "korean":
        rec_sub = "korean_PP-OCRv5_mobile_rec"

    return (
        os.path.join(det_path, det_sub),
        os.path.join(rec_path, rec_sub),
        cls_path
    )
