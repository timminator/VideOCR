# Compilation instructions
# nuitka-project: --standalone
# nuitka-project: --include-windows-runtime-dlls=yes
# nuitka-project-if: {OS} == "Windows":
#     nuitka-project: --output-filename=videocr-cli
# nuitka-project-if: {OS} == "Linux":
#     nuitka-project: --output-filename=videocr-cli.bin

# Windows-specific metadata for the executable
# nuitka-project-if: {OS} == "Windows":
#     nuitka-project-set: APP_VERSION = (__import__("sys").path.insert(0, "..") or __import__("_version").__version__)
#     nuitka-project: --file-description="VideOCR CLI"
#     nuitka-project: --file-version={APP_VERSION}
#     nuitka-project: --product-name="VideOCR-CLI"
#     nuitka-project: --product-version={APP_VERSION}
#     nuitka-project: --copyright="timminator"

import argparse
import os
import sys
from contextlib import nullcontext

from wakepy import keep

from videocr import save_subtitles_to_file, utils
from videocr.lang_dictionaries import (
    ARABIC_LANGS,
    CYRILLIC_LANGS,
    DEVANAGARI_LANGS,
    ESLAV_LANGS,
    LATIN_LANGS,
    SPECIFIC_LANGS,
)

SUPPORTED_LANGUAGES = (
    SPECIFIC_LANGS
    | LATIN_LANGS
    | ARABIC_LANGS
    | ESLAV_LANGS
    | CYRILLIC_LANGS
    | DEVANAGARI_LANGS
)


# custom validators for argparse
def valid_video_path(arg):
    if not os.path.isfile(arg):
        raise argparse.ArgumentTypeError(f"Video file does not exist or is not a valid file: '{arg}'")
    return arg


def valid_output_path(arg):
    dir_name = os.path.dirname(arg) or '.'
    if not os.path.isdir(dir_name):
        raise argparse.ArgumentTypeError(f"Output directory does not exist: '{dir_name}'")
    if not os.access(dir_name, os.W_OK):
        raise argparse.ArgumentTypeError(f"Output directory is not writable: '{dir_name}'")
    return arg


def valid_language(arg):
    lang = arg.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise argparse.ArgumentTypeError(f"Unsupported OCR language code: '{arg}'")
    return lang


def restricted_int(min_val=None, max_val=None):
    def validator(arg):
        try:
            value = int(arg)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Must be an integer. Got '{arg}'") from None

        if min_val is not None and value < min_val:
            raise argparse.ArgumentTypeError(f"Value must be >= {min_val}")
        if max_val is not None and value > max_val:
            raise argparse.ArgumentTypeError(f"Value must be <= {max_val}")
        return value
    return validator


def restricted_float(min_val=None, max_val=None):
    def validator(arg):
        try:
            value = float(arg)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Must be a decimal number. Got '{arg}'") from None

        if min_val is not None and value < min_val:
            raise argparse.ArgumentTypeError(f"Value must be >= {min_val}")
        if max_val is not None and value > max_val:
            raise argparse.ArgumentTypeError(f"Value must be <= {max_val}")
        return value
    return validator


def valid_time_string(arg):
    if not arg:
        return ""
    try:
        utils.get_ms_from_time_str(arg)
        return arg
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid time format '{arg}'. Use MM:SS or HH:MM:SS.") from None


ALIGNMENT_MAP = {
    'bottom-left': 'an1', 'bottom-center': 'an2', 'bottom-right': 'an3',
    'middle-left': 'an4', 'middle-center': 'an5', 'middle-right': 'an6',
    'top-left': 'an7', 'top-center': 'an8', 'top-right': 'an9',
}
VALID_ALIGNMENT_NAMES = set(ALIGNMENT_MAP.keys())


def valid_alignment_name(arg):
    if not arg:
        return None
    if arg in VALID_ALIGNMENT_NAMES:
        return ALIGNMENT_MAP[arg]
    allowed_values = ", ".join(sorted(list(VALID_ALIGNMENT_NAMES)))
    raise argparse.ArgumentTypeError(f"Invalid alignment '{arg}'. Allowed values are: {allowed_values}")


def main():
    parser = argparse.ArgumentParser(description='Extract subtitles from video using PaddleOCR.')

    parser.add_argument('--video_path', type=valid_video_path, required=True, help='Path to the video file')
    parser.add_argument('--output', type=valid_output_path, default='subtitle.srt', help='Output SRT file path (default: subtitle.srt)')
    parser.add_argument('--lang', type=valid_language, default='ch', help='OCR language (default: ch)')
    parser.add_argument('--time_start', type=valid_time_string, default='0:00', help='Start time (MM:SS or HH:MM:SS)')
    parser.add_argument('--time_end', type=valid_time_string, default='', help='End time (MM:SS or HH:MM:SS)')
    parser.add_argument('--conf_threshold', type=restricted_int(0, 100), default=75, help='Confidence threshold (default: 75)')
    parser.add_argument('--sim_threshold', type=restricted_int(0, 100), default=80, help='Similarity threshold (default: 80)')
    parser.add_argument('--max_merge_gap', type=restricted_float(min_val=0.0), default=0.09, help='Maximum time gap in seconds to merge similar subtitles (default: 0.09)')
    parser.add_argument('--use_fullframe', type=lambda x: x.lower() == 'true', default=False, help='Use full frame for OCR (default: false)')
    parser.add_argument('--use_gpu', type=lambda x: x.lower() == 'true', default=False, help='Enable GPU usage (default: false)')
    parser.add_argument('--use_angle_cls', type=lambda x: x.lower() == 'true', default=False, help='Enable Classification (default: false)')
    parser.add_argument('--use_server_model', type=lambda x: x.lower() == 'true', default=False, help='Enable usage of server model (default: false)')
    parser.add_argument('--brightness_threshold', type=restricted_int(0, 255), default=None, help='Brightness threshold')
    parser.add_argument('--ssim_threshold', type=restricted_int(0, 100), default=92, help='SSIM similarity threshold (default: 92)')
    parser.add_argument('--subtitle_position', type=str, default='center', help='Subtitle position alignment (center (default), left, right, any)')
    parser.add_argument('--frames_to_skip', type=restricted_int(min_val=0), default=1, help='Frames to skip (default: 1)')
    parser.add_argument('--normalize_to_simplified_chinese', type=lambda x: x.lower() == 'true', default=True, help='Normalize Traditional Chinese characters to Simplified Chinese for ch (default: true)')
    parser.add_argument('--post_processing', type=lambda x: x.lower() == 'true', default=False, help='Enable post processing of subtitles (default: false)')
    parser.add_argument('--min_subtitle_duration', type=restricted_float(min_val=0.0), default=0.2, help='Minimum subtitle duration in seconds (default: 0.2)')
    parser.add_argument('--ocr_image_max_width', type=restricted_int(min_val=1), default=960, help='Maximum image width used for OCR (default: 960)')
    parser.add_argument('--use_dual_zone', type=lambda x: x.lower() == 'true', default=False, help='Enable dual zone OCR processing (default: false)')
    parser.add_argument('--crop_x', type=int, default=None, help='(Zone 1) Crop start X')
    parser.add_argument('--crop_y', type=int, default=None, help='(Zone 1) Crop start Y')
    parser.add_argument('--crop_width', type=int, default=None, help='(Zone 1) Crop width')
    parser.add_argument('--crop_height', type=int, default=None, help='(Zone 1) Crop height')
    parser.add_argument('--crop_x2', type=int, default=None, help='(Zone 2) Crop start X')
    parser.add_argument('--crop_y2', type=int, default=None, help='(Zone 2) Crop start Y')
    parser.add_argument('--crop_width2', type=int, default=None, help='(Zone 2) Crop width')
    parser.add_argument('--crop_height2', type=int, default=None, help='(Zone 2) Crop height')
    parser.add_argument('--subtitle_alignment', type=valid_alignment_name, default=None, help='(Zone 1) Subtitle alignment. Allowed: bottom-left, bottom-center, bottom-right, middle-left, middle-center, middle-right, top-left, top-center, top-right')
    parser.add_argument('--subtitle_alignment2', type=valid_alignment_name, default=None, help='(Zone 2) Subtitle alignment. See --subtitle_alignment for allowed values.')
    parser.add_argument('--allow_system_sleep', type=lambda x: x.lower() == 'true', default=False, help='Allow the system to sleep during processing (default: false)')

    args = parser.parse_args()

    try:
        if args.time_start and args.time_end:
            start_ms = utils.get_ms_from_time_str(args.time_start)
            end_ms = utils.get_ms_from_time_str(args.time_end)
            if start_ms > end_ms:
                raise ValueError(f"Start Time ({args.time_start}) cannot be after End Time ({args.time_end}).")

        crop_zones = []
        if not args.use_fullframe:
            zone1_vars = [args.crop_x, args.crop_y, args.crop_width, args.crop_height]

            is_zone1_full = all(v is not None for v in zone1_vars)
            is_zone1_empty = all(v is None for v in zone1_vars)

            if is_zone1_full:
                crop_zones.append({
                    'x': args.crop_x, 'y': args.crop_y,
                    'width': args.crop_width, 'height': args.crop_height
                })
            elif not is_zone1_empty:
                raise ValueError("Partial crop coordinates detected for Zone 1. You must provide ALL four: --crop_x, --crop_y, --crop_width, and --crop_height.")

            if args.use_dual_zone:
                zone2_vars = [args.crop_x2, args.crop_y2, args.crop_width2, args.crop_height2]

                is_zone2_full = all(v is not None for v in zone2_vars)
                is_zone2_empty = all(v is None for v in zone2_vars)

                if is_zone2_full:
                    crop_zones.append({
                        'x': args.crop_x2, 'y': args.crop_y2,
                        'width': args.crop_width2, 'height': args.crop_height2
                    })
                elif not is_zone2_empty:
                    raise ValueError("Partial crop coordinates detected for Zone 2. You must provide ALL four: --crop_x2, --crop_y2, --crop_width2, and --crop_height2.")
                else:
                    if is_zone1_full:
                        raise ValueError("Dual zone OCR was requested, but coordinates for the second zone were not provided.")

        keep_awake_manager = nullcontext() if args.allow_system_sleep else keep.running()

        with keep_awake_manager:
            save_subtitles_to_file(
                video_path=args.video_path,
                file_path=args.output,
                lang=args.lang,
                time_start=args.time_start,
                time_end=args.time_end,
                conf_threshold=args.conf_threshold,
                sim_threshold=args.sim_threshold,
                max_merge_gap_sec=args.max_merge_gap,
                use_fullframe=args.use_fullframe,
                use_gpu=args.use_gpu,
                use_angle_cls=args.use_angle_cls,
                use_server_model=args.use_server_model,
                brightness_threshold=args.brightness_threshold,
                ssim_threshold=args.ssim_threshold,
                subtitle_position=args.subtitle_position,
                frames_to_skip=args.frames_to_skip,
                crop_zones=crop_zones,
                normalize_to_simplified_chinese=args.normalize_to_simplified_chinese,
                post_processing=args.post_processing,
                min_subtitle_duration_sec=args.min_subtitle_duration,
                ocr_image_max_width=args.ocr_image_max_width,
                subtitle_alignments=[args.subtitle_alignment, args.subtitle_alignment2]
            )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
