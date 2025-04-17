<p align="center">
  <h1 align="center">VideOCR</h1>
  <p align="center">
    Extract hardcorded subtitles from videos!
    <br />
  </p>
</p>

<br>

## ℹ About

Extract hardcoded (burned-in) subtitles from videos using the [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) OCR engine. This tool can easily be run from the command line without having Python or any other packages installed.
You can decide between installing it via the setup installer or just downloading the folder with all the required files including the executable.
The installer also allows you to add the install location to you path which allows you to use VideOCR from every location.

This repository also provides a version of VideOCR that does not include the standalone version of PaddleOCR out of the box, if you installed PaddleOCR version via Python for example (requires at least version 2.10.0).

## Performance

The OCR process can be very slow on the CPU. Using this in combination with a GPU is highly recommended.

## Tips

To shorten the amount of time it takes to perform OCR on each frame, you can use the `crop_x`, `crop_y`, `crop_width`, `crop_height` params to crop out only the areas of the videos where the subtitles appear. When cropping, leave a bit of buffer space above and below the text to ensure accurate readings.

### Quick Configuration Cheatsheet

|| More Speed | More Accuracy | Notes
-|------------|---------------|--------
Input Video Quality       | Use lower quality           | Use higher quality  | Performance impact of using higher resolution video can be reduced with cropping
`frames_to_skip`          | Higher number               | Lower number        |
`brightness_threshold`    | Higher threshold            | N/A                 | A brightness threshold can help speed up the OCR process by filtering out dark frames. In certain circumstances such as when subtitles are white and against a bright background, it may also help with accuracy.


### Parameters

- `video_path`

  Path for the video where subtitles should be extracted from.
  
- `lang`

  The language of the subtitles. See [PaddleOCR docs](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.6/doc/doc_en/multi_languages_en.md#5-support-languages-and-abbreviations) for list of supported languages and their abbreviations

- `conf_threshold`

  Confidence threshold for word predictions. Words with lower confidence than this value will be discarded. The default value `75` is fine for most cases. 

  Make it closer to 0 if you get too few words in each line, or make it closer to 100 if there are too many excess words in each line.

- `sim_threshold`

  Similarity threshold for subtitle lines. Subtitle lines with larger [Levenshtein](https://en.wikipedia.org/wiki/Levenshtein_distance) ratios than this threshold will be merged together. The default value `80` is fine for most cases.

  Make it closer to 0 if you get too many duplicated subtitle lines, or make it closer to 100 if you get too few subtitle lines.

- `time_start` and `time_end`

  Extract subtitles from only a clip of the video. The subtitle timestamps are still calculated according to the full video length.

- `use_fullframe`

  By default, the specified cropped area is used for OCR or if a crop is not specified, then the bottom third of the frame will be used. By setting this value to `True` the entire frame will be used.

- `crop_x`, `crop_y`, `crop_width`, `crop_height`

  Specifies the bounding area in pixels for the portion of the frame that will be used for OCR. See image below for example:
  ![image](https://user-images.githubusercontent.com/8058852/226201081-f4ec9a23-4cc8-48d4-b15c-6ea2ac29ae93.png)

- `det_model_dir`

  The text detection inference model folder. Already configured by default when using the standalone version.

- `rec_model_dir`
  
  The text recognition inference model folder. Already configured by default when using the standalone version.
  
- `cls_model_dir`
  
  The classification inference model folder. Already configured by default when using the standalone version.

- `use_gpu`

  Set to `True` if performing ocr with gpu.
  
- `use_angle_cls`

  Set to `True` if classification should be enabled.

- `brightness_threshold`
  
  If set, pixels whose brightness are less than the threshold will be blackened out. Valid brightness values range from 0 (black) to 255 (white). This can help improve accuracy when performing OCR on videos with white subtitles.

- `similar_image_threshold`

  The number of non-similar pixels there can be before the program considers 2 consecutive frames to be different. If a frame is not different from the previous frame, then the OCR result from the previous frame will be used (which can save a lot of time depending on how fast each OCR inference takes).

- `similar_pixel_threshold`

  Brightness threshold from 0-255 used with the `similar_image_threshold` to determine if 2 consecutive frames are different. If the difference between 2 pixels exceeds the threshold, then they will be considered non-similar.

- `frames_to_skip`

  The number of frames to skip before sampling a frame for OCR. Keep in mind the fps of the input video before increasing.
  
- `paddleocr_path`

  Only available when using VideOCR without PaddleOCR included. This specifies the path to the paddleocr executable. IF installed via python it should be available in path, so it should be enough to just specify "paddleocr.exe".
  
  
