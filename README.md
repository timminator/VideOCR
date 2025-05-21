<p align="center">
<img src="https://github.com/timminator/VideOCR/blob/master/Pictures/VideOCR.png" alt="VideOCR Icon" width="128">
  <h1 align="center">VideOCR</h1>
  <p align="center">
    Extract hardcoded subtitles from videos!
    <br />
  </p>
</p>

<br>

## ℹ About

Extract hardcoded (burned-in) subtitles from videos via a simple to use GUI by utilizing the [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) OCR engine. Everything can be easily configured via a few clicks.

This repository also provides a version of VideOCR that can be used from the command line in combination with PaddleOCR.

## Setup

### Windows:
You can either install it with the setup installer or you can just download a folder with all the required files including the executable and unzip it to your desired location.

### Linux:
Download the tarball archive from the releases page and unzip it to your desired location.
Optionally you can add VideOCR to your App menus if you want to.
For this step open a terminal where you unpacked the archive and run

```
./install_videocr.sh
```
This will create a shortcut for VideOCR. You can remove it via:  

```
./uninstall_videocr.sh
```

## Usage

Import a video and seek through the video via the timeline. You can also use the right and left arrow keys. Then you can just draw a crop box over the right part of the video. Use click+drag to select. Afterwards you can start the subtitle extraction process via the "Run" Button.

Further options can be configured in the "Advanced Settings" Tab. You can find more info about them in the parameters section available in the CLI version.
![image](https://github.com/timminator/VideOCR/blob/master/Pictures/GUI.png)

## Usage (CLI version)
  
There are two CLI versions available, the CLI Standalone version is recommended. Unzip the archive to your desired location and open a terminal in there. Afterwards you can run the following command:

### Windows:
```
.\videocr-cli-sa.exe -h
```

### Linux:

```
./videocr-cli-sa.bin -h
```

### Example usage (Standalone version, Windows):
```
.\videocr-cli-sa.exe --video_path "Path\to\your\video\example.mp4" --output "Path\to\your\desired\subtitle\location\example.srt" --lang en --time_start "18:40" --use_gpu true --use_angle_cls true
```
More info about the arguments can be found in the parameters section further down.

## Performance

The OCR process can be very slow on the CPU. Using this in combination with a GPU is highly recommended.

## Tips

When cropping, leave a bit of buffer space above and below the text to ensure accurate readings.

### Quick Configuration Cheatsheet

|| More Speed | More Accuracy | Notes
-|------------|---------------|--------
Input Video Quality       | Use lower quality           | Use higher quality  | Performance impact of using higher resolution video can be reduced with cropping
`frames_to_skip`          | Higher number               | Lower number        |
`brightness_threshold`    | Higher threshold            | N/A                 | A brightness threshold can help speed up the OCR process by filtering out dark frames. In certain circumstances such as when subtitles are white and against a bright background, it may also help with accuracy.


### Command Line Parameters (CLI version)

- `video_path`

  Path for the video where subtitles should be extracted from.

- `output`

  Path for the desired location where the .srt file should be stored.

- `lang`

  The language of the subtitles. See [PaddleOCR docs](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.10/docs/ppocr/blog/multi_languages.en.md#5-support-languages-and-abbreviations) for list of supported languages and their abbreviations

- `conf_threshold`

  Confidence threshold for word predictions. Words with lower confidence than this value will be discarded. The default value `75` is fine for most cases. 

  Make it closer to 0 if you get too few words in each line, or make it closer to 100 if there are too many excess words in each line.

- `sim_threshold`

  Similarity threshold for subtitle lines. Subtitle lines with larger [Levenshtein](https://en.wikipedia.org/wiki/Levenshtein_distance) ratios than this threshold will be merged together. The default value `80` is fine for most cases.

  Make it closer to 0 if you get too many duplicated subtitle lines, or make it closer to 100 if you get too few subtitle lines.

- `max_merge_gap`

  Maximum allowed time gap (in seconds) between two subtitles to be considered for merging if they are similar. The default value 0.09 (i.e., 90 milliseconds) works well in most scenarios.

  Increase this value if you notice that the output SRT file contains several subtitles with the same text that should be merged into a single one and are wrongly split into multiple ones. This can happen if the PaddleOCR OCR engine is not able to detect any text for a short amount of time while the subtitle is displayed in the selected video.

- `time_start` and `time_end`

  Extract subtitles from only a clip of the video. The subtitle timestamps are still calculated according to the full video length.

- `use_fullframe`

  By default, the specified cropped area is used for OCR or if a crop is not specified, then the bottom third of the frame will be used. By setting this value to `True` the entire frame will be used.

- `crop_x`, `crop_y`, `crop_width`, `crop_height`

  Specifies the bounding area in pixels for the portion of the frame that will be used for OCR. See image below for example:
  ![image](https://github.com/timminator/VideOCR/blob/master/Pictures/crop_example.png)

- `det_model_dir`

  The text detection inference model folder. Already configured by default when using the standalone version.

- `rec_model_dir`
  
  The text recognition inference model folder. Already configured by default when using the standalone version.

- `cls_model_dir`
  
  The classification inference model folder. Already configured by default when using the standalone version.

- `use_gpu`

  Set to `True` if performing OCR with GPU.

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

  Only available when using VideOCR CLI version. This specifies the path to the PaddleOCR executable. If installed via python it should be available in path, so it should be enough to just specify "paddleocr.exe". You can also download the standalone version used by the GUI version, that does not require Python, from [here](https://github.com/timminator/PaddleOCR-Standalone/releases/tag/v.1.0.0).
  
The CLI version also requires to specify the correct detection/recognition/classification model directory for each language. The model files can be downloaded from [here](https://github.com/timminator/PaddleOCR-Standalone/releases/download/v.1.0.0/PaddleOCR.PP-OCRv4.support.files.7z).
  
  
