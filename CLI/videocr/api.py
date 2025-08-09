from . import utils
from .video import Video


def save_subtitles_to_file(
        video_path: str, file_path='subtitle.srt', lang='ch', time_start='0:00', time_end='',
        conf_threshold=75, sim_threshold=80, max_merge_gap_sec=0.1, use_fullframe=False,
        use_gpu=False, use_angle_cls=False, use_server_model=False, brightness_threshold=None,
        ssim_threshold=92, subtitle_position="center", frames_to_skip=1, crop_zones=None,
        ocr_image_max_width=1280, post_processing=False, min_subtitle_duration_sec=0.2) -> None:

    if crop_zones is None:
        crop_zones = []

    paddleocr_path = utils.find_paddleocr()
    try:
        utils.perform_hardware_check(paddleocr_path)
    except SystemExit as e:
        print(e, flush=True)
        return

    det_model_dir, rec_model_dir, cls_model_dir = utils.resolve_model_dirs(lang, use_server_model)

    v = Video(video_path, paddleocr_path, det_model_dir, rec_model_dir, cls_model_dir, time_end)
    v.run_ocr(
        use_gpu, lang, use_angle_cls, time_start, time_end, conf_threshold,
        use_fullframe, brightness_threshold, ssim_threshold, subtitle_position,
        frames_to_skip, crop_zones, ocr_image_max_width
    )
    subtitles = v.get_subtitles(sim_threshold, max_merge_gap_sec, lang, post_processing, min_subtitle_duration_sec)

    with open(file_path, 'w+', encoding='utf-8') as f:
        f.write(subtitles)
