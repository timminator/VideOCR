import argparse
from videocr import save_subtitles_to_file

def main():
    parser = argparse.ArgumentParser(description='Extract subtitles from video using PaddleOCR.')

    parser.add_argument('--video_path', type=str, required=True, help='Path to the video file')
    parser.add_argument('--paddleocr_path', type=str, required=True, help='Path to the PaddleOCR executable')
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
    parser.add_argument('--det_model_dir', type=str, default=None, help='Detection model directory')
    parser.add_argument('--rec_model_dir', type=str, default=None, help='Recognition model directory')
    parser.add_argument('--cls_model_dir', type=str, default=None, help='Classification model directory')
    parser.add_argument('--brightness_threshold', type=int, default=None, help='Brightness threshold')
    parser.add_argument('--similar_image_threshold', type=int, default=100, help='Similar image threshold (default: 100)')
    parser.add_argument('--similar_pixel_threshold', type=int, default=25, help='Similar pixel threshold (default: 25)')
    parser.add_argument('--frames_to_skip', type=int, default=1, help='Frames to skip (default: 1)')
    parser.add_argument('--crop_x', type=int, default=None, help='Crop start X')
    parser.add_argument('--crop_y', type=int, default=None, help='Crop start Y')
    parser.add_argument('--crop_width', type=int, default=None, help='Crop width')
    parser.add_argument('--crop_height', type=int, default=None, help='Crop height')

    args = parser.parse_args()

    save_subtitles_to_file(
        video_path=args.video_path,
        paddleocr_path=args.paddleocr_path,
        file_path=args.output,
        lang=args.lang,
        time_start=args.time_start,
        time_end=args.time_end,
        conf_threshold=args.conf_threshold,
        sim_threshold=args.sim_threshold,
        max_merge_gap_sec=args.max_merge_gap,
        use_fullframe=args.use_fullframe,
        det_model_dir=args.det_model_dir,
        rec_model_dir=args.rec_model_dir,
        cls_model_dir=args.cls_model_dir,
        use_gpu=args.use_gpu,
        use_angle_cls=args.use_angle_cls,
        brightness_threshold=args.brightness_threshold,
        similar_image_threshold=args.similar_image_threshold,
        similar_pixel_threshold=args.similar_pixel_threshold,
        frames_to_skip=args.frames_to_skip,
        crop_x=args.crop_x,
        crop_y=args.crop_y,
        crop_width=args.crop_width,
        crop_height=args.crop_height
    )

if __name__ == '__main__':
    main()
