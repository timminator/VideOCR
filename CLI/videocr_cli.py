# Compilation instructions
# nuitka-project: --standalone
# nuitka-project: --output-filename=videocr-cli
# nuitka-project: --include-module=uuid

# Windows-specific metadata for the executable
# nuitka-project-if: {OS} == "Windows":
#     nuitka-project: --file-description="VideOCR CLI"
#     nuitka-project: --file-version="1.3.0"
#     nuitka-project: --product-name="VideOCR-CLI"
#     nuitka-project: --product-version="1.3.0"
#     nuitka-project: --copyright="timminator"

import argparse

from videocr import save_subtitles_to_file


def main():
    parser = argparse.ArgumentParser(description='Extract subtitles from video using PaddleOCR.')

    parser.add_argument('--video_path', type=str, required=True, help='Path to the video file')
    parser.add_argument('--output', type=str, default='subtitle.srt', help='Output SRT file path (default: subtitle.srt)')
    parser.add_argument('--lang', type=str, default='ch', help='OCR language (default: ch)')
    parser.add_argument('--time_start', type=str, default='0:00', help='Start time (default: 0:00)')
    parser.add_argument('--time_end', type=str, default='', help='End time')
    parser.add_argument('--conf_threshold', type=int, default=75, help='Confidence threshold (default: 75)')
    parser.add_argument('--sim_threshold', type=int, default=80, help='Similarity threshold (default: 80)')
    parser.add_argument('--max_merge_gap', type=float, default=0.09, help='Maximum time gap in seconds to merge similar subtitles (default: 0.09)')
    parser.add_argument('--use_fullframe', type=lambda x: x.lower() == 'true', default=False, help='Use full frame for OCR (true/false)')
    parser.add_argument('--use_gpu', type=lambda x: x.lower() == 'true', default=False, help='Enable GPU usage (true/false)')
    parser.add_argument('--use_angle_cls', type=lambda x: x.lower() == 'true', default=False, help='Enable Classification (true/false)')
    parser.add_argument('--use_server_model', type=lambda x: x.lower() == 'true', default=False, help='Enable usage of server model (true/false)')
    parser.add_argument('--brightness_threshold', type=int, default=None, help='Brightness threshold')
    parser.add_argument('--ssim_threshold', type=int, default=92, help='SSIM similarity threshold (default: 92)')
    parser.add_argument('--subtitle_position', type=str, default='center', help='Subtitle position alignment (center (default), left, right, any)')
    parser.add_argument('--frames_to_skip', type=int, default=1, help='Frames to skip (default: 1)')
    parser.add_argument('--post_processing', type=lambda x: x.lower() == 'true', default=False, help='Enable post processing of subtitles (true/false)')
    parser.add_argument('--min_subtitle_duration', type=float, default=0.2, help='Minimum subtitle duration in seconds (default: 0.2)')
    parser.add_argument('--use_dual_zone', type=lambda x: x.lower() == 'true', default=False, help='Enable dual zone OCR processing (true/false)')
    parser.add_argument('--crop_x', type=int, default=None, help='(Zone 1) Crop start X')
    parser.add_argument('--crop_y', type=int, default=None, help='(Zone 1) Crop start Y')
    parser.add_argument('--crop_width', type=int, default=None, help='(Zone 1) Crop width')
    parser.add_argument('--crop_height', type=int, default=None, help='(Zone 1) Crop height')
    parser.add_argument('--crop_x2', type=int, default=None, help='(Zone 2) Crop start X')
    parser.add_argument('--crop_y2', type=int, default=None, help='(Zone 2) Crop start Y')
    parser.add_argument('--crop_width2', type=int, default=None, help='(Zone 2) Crop width')
    parser.add_argument('--crop_height2', type=int, default=None, help='(Zone 2) Crop height')

    args = parser.parse_args()

    crop_zones = []
    if not args.use_fullframe:
        zone1_defined = all(v is not None for v in [args.crop_x, args.crop_y, args.crop_width, args.crop_height])
        if zone1_defined:
            crop_zones.append({
                'x': args.crop_x, 'y': args.crop_y,
                'width': args.crop_width, 'height': args.crop_height
            })

        if args.use_dual_zone:
            zone2_defined = all(v is not None for v in [args.crop_x2, args.crop_y2, args.crop_width2, args.crop_height2])
            if zone2_defined:
                crop_zones.append({
                    'x': args.crop_x2, 'y': args.crop_y2,
                    'width': args.crop_width2, 'height': args.crop_height2
                })
            else:
                if zone1_defined:
                    raise ValueError("Dual zone OCR was requested, but coordinates for the second zone were not provided.")

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
        post_processing=args.post_processing,
        min_subtitle_duration_sec=args.min_subtitle_duration,
    )


if __name__ == '__main__':
    main()
