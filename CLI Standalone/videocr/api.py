import os
import sys
import platform
from .video import Video


def get_subtitles(
        video_path: str, paddleocr_path: str, lang='ch', time_start='0:00', time_end='',
        conf_threshold=75, sim_threshold=80, max_merge_gap_sec=0.09, use_fullframe=False,
        det_model_dir=None, rec_model_dir=None, cls_model_dir=None, use_gpu=False, use_angle_cls=False,
        brightness_threshold=None, similar_image_threshold=100, similar_pixel_threshold=25, frames_to_skip=1,
        crop_x=None, crop_y=None, crop_width=None, crop_height=None) -> str:

    v = Video(video_path, paddleocr_path, det_model_dir, rec_model_dir, cls_model_dir)
    v.run_ocr(use_gpu, lang, use_angle_cls, time_start, time_end, conf_threshold, use_fullframe, brightness_threshold, similar_image_threshold, similar_pixel_threshold, frames_to_skip, crop_x, crop_y, crop_width, crop_height)
    return v.get_subtitles(sim_threshold, max_merge_gap_sec)


def save_subtitles_to_file(
        video_path: str, paddleocr_path: str = None, file_path='subtitle.srt', lang='ch',
        time_start='0:00', time_end='', conf_threshold=75, sim_threshold=80, max_merge_gap_sec=0.09,
        use_fullframe=False, det_model_dir=None, rec_model_dir=None, cls_model_dir=None, use_gpu=False, use_angle_cls=False,
        brightness_threshold=None, similar_image_threshold=100, similar_pixel_threshold=25, frames_to_skip=1,
        crop_x=None, crop_y=None, crop_width=None, crop_height=None) -> None:
    # Standalone version uses included PaddleOCR
    paddleocr_path = find_paddleocr()
    # If not manually provided, resolve model dirs
    if not all([det_model_dir, rec_model_dir, cls_model_dir]):
        program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        base_model_path = os.path.join(program_dir, "PaddleOCR.PP-OCRv4.support.files")
        det_model_dir, rec_model_dir, cls_model_dir = resolve_model_dirs(base_model_path, lang)

    with open(file_path, 'w+', encoding='utf-8') as f:
        f.write(get_subtitles(
            video_path, paddleocr_path, lang, time_start, time_end, conf_threshold,
            sim_threshold, max_merge_gap_sec, use_fullframe, det_model_dir, rec_model_dir, cls_model_dir, use_gpu, use_angle_cls, brightness_threshold, similar_image_threshold, similar_pixel_threshold, frames_to_skip, crop_x, crop_y, crop_width, crop_height))


def find_paddleocr() -> str:
    program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    possible_folders = [
        "PaddleOCR-CPU-v1.0.0",
        "PaddleOCR-GPU-v1.0.0-CUDA-11.8"
    ]
    program_name = "paddleocr"

    if platform.system() == "Windows":
        ext = ".exe"
    else:
        ext = ".bin"

    executable_name = f"{program_name}{ext}"

    for folder in possible_folders:
        path = os.path.join(program_dir, folder, executable_name)
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(f"Could not find {executable_name} in expected folders: {possible_folders}")

LATIN_LANGS = {
    "af",
    "az",
    "bs",
    "cs",
    "cy",
    "da",
    "de",
    "es",
    "et",
    "fr",
    "ga",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "ku",
    "la",
    "lt",
    "lv",
    "mi",
    "ms",
    "mt",
    "nl",
    "no",
    "oc",
    "pi",
    "pl",
    "pt",
    "ro",
    "rs_latin",
    "sk",
    "sl",
    "sq",
    "sv",
    "sw",
    "tl",
    "tr",
    "uz",
    "vi",
    "french",
    "german"
}
ARABIC_LANGS = { "ar", "fa", "ug", "ur" }
CYRILLIC_LANGS = {
    "ru",
    "rs_cyrillic",
    "be",
    "bg",
    "uk",
    "mn",
    "abq",
    "ady",
    "kbd",
    "ava",
    "dar",
    "inh",
    "che",
    "lbe",
    "lez",
    "tab"
}
DEVANAGARI_LANGS = {
    "hi",
    "mr",
    "ne",
    "bh",
    "mai",
    "ang",
    "bho",
    "mah",
    "sck",
    "new",
    "gom",
    "bgc",
    "sa"
}

def resolve_model_dirs(base_path: str, lang: str):
    det_path = os.path.join(base_path, "det")
    rec_path = os.path.join(base_path, "rec")
    cls_path = os.path.join(base_path, "cls", "ch_ppocr_mobile_v2.0_cls_infer")

    # DET
    if lang == "ch":
        det_sub = os.path.join(lang, f"{lang}_PP-OCRv4_det_infer")
    elif lang in LATIN_LANGS:
        det_sub = os.path.join("en", "en_PP-OCRv3_det_infer")
    elif lang != "en":
        det_sub = os.path.join("ml", "Multilingual_PP-OCRv3_det_infer")
    else:
        det_sub = os.path.join(lang, f"{lang}_PP-OCRv3_det_infer")

    # REC
    if lang in LATIN_LANGS:
        rec_sub = os.path.join("latin", "latin_PP-OCRv3_rec_infer")
    elif lang in ARABIC_LANGS:
        rec_sub = os.path.join("arabic", "arabic_PP-OCRv4_rec_infer")
    elif lang in CYRILLIC_LANGS:
        rec_sub = os.path.join("cyrillic", "cyrillic_PP-OCRv3_rec_infer")
    elif lang in DEVANAGARI_LANGS:
        rec_sub = os.path.join("devanagari", "devanagari_PP-OCRv4_rec_infer")
    elif lang == "chinese_cht":
        rec_sub = os.path.join(lang, f"{lang}_PP-OCRv3_rec_infer")
    else:
        rec_sub = os.path.join(lang, f"{lang}_PP-OCRv4_rec_infer")

    return (
        os.path.join(det_path, det_sub),
        os.path.join(rec_path, rec_sub),
        cls_path
    )
