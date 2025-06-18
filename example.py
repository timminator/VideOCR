from videocr import save_subtitles_to_file

if __name__ == '__main__':
    save_subtitles_to_file('example_cropped.mp4', 'example.srt', lang='ch', time_start='7:10', time_end='7:34',
     sim_threshold=80, conf_threshold=50, use_fullframe=True,
    # Models different from the default models can be downloaded here: https://huggingface.co/PaddlePaddle
    # det_model_dir='<PADDLEOCR DETECTION MODEL DIR>', rec_model_dir='<PADDLEOCR RECOGNITION MODEL DIR>',
     brightness_threshold=210, similar_image_threshold=1000, frames_to_skip=1)