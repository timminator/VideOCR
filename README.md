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

The latest release incorporates the newest version of PaddleOCR with greatly improved OCR capabilities.

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
  
There is also a CLI version available. Unzip the archive to your desired location and open a terminal in there. Afterwards you can run the following command:

### Windows:
```
.\videocr-cli.exe -h
```

### Linux:

```
./videocr-cli.exe -h
```

### Example usage (Windows):
```
.\videocr-cli.exe --video_path "Path\to\your\video\example.mp4" --output "Path\to\your\desired\subtitle\location\example.srt" --lang en --time_start "18:40" --use_gpu true
```
More info about the arguments can be found in the parameters section further down.

## Performance

The OCR process can be slow on the CPU. Using this in combination with a GPU is highly recommended.

## Tips

When cropping, leave a bit of buffer space above and below the text to ensure accurate readings, but also don't make the box to large.

### Quick Configuration Cheatsheet

|| More Speed | More Accuracy | Notes
-|------------|---------------|--------
Input Video Quality       | Use lower quality           | Use higher quality  | Performance impact of using higher resolution video can be reduced with cropping
`frames_to_skip`          | Higher number               | Lower number        | For perfectly accurate timestamps this parameter needs to be set to 0.
`SSIM threshold`          | Lower threshold             | Higher Threshold    | If the SSIM between consecutive frames exceeds this threshold, the frame is considered similar and skipped for OCR. A lower value can greatly reduce the number of images OCR needs to be performed on.


## Command Line Parameters (CLI version)

- `video_path`

  Path for the video where subtitles should be extracted from.

- `output`

  Path for the desired location where the .srt file should be stored.

- `lang`

  The language of the subtitles. See [PaddleOCR docs](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.10/docs/ppocr/blog/multi_languages.en.md#5-support-languages-and-abbreviations) for list of supported languages and their abbreviations.
  
- `subtitle_position`

  Specifies the alignment of subtitles in the video and allows for better text recognition.

- `conf_threshold`

  Confidence threshold for word predictions. Words with lower confidence than this value will be discarded. The default value `75` is fine for most cases. 

  Make it closer to 0 if you get too few words in each line, or make it closer to 100 if there are too many excess words in each line.

- `sim_threshold`

  Similarity threshold for subtitle lines. Subtitle lines with larger [Levenshtein](https://en.wikipedia.org/wiki/Levenshtein_distance) ratios than this threshold will be merged together. The default value `80` is fine for most cases.

  Make it closer to 0 if you get too many duplicated subtitle lines, or make it closer to 100 if you get too few subtitle lines.
  
- `ssim_threshold`

  If the SSIM between consecutive frames exceeds this threshold, the frame is considered similar and skipped for OCR. A lower value can greatly reduce the number of images OCR needs to be performed on. On relatively tight crop boxes around the subtitle area good results could be seen with this value all the way lowered to 85.
  
- `post_processing`

  This parameter adds a post processing step to the subtitle detection. The detected text will be analyzed for missing spaces (as this is a common issue with PaddleOCR) and tries to insert them automatically. Currently only available for English, Spanish, Portuguese, German, Italian and French. For more info check out my [wordninja-enhanced](https://github.com/timminator/wordninja-enhanced) repository.

- `max_merge_gap`

  Maximum allowed time gap (in seconds) between two subtitles to be considered for merging if they are similar. The default value 0.09 (i.e., 90 milliseconds) works well in most scenarios.

  Increase this value if you notice that the output SRT file contains several subtitles with the same text that should be merged into a single one and are wrongly split into multiple ones. This can happen if the PaddleOCR OCR engine is not able to detect any text for a short amount of time while the subtitle is displayed in the selected video.

- `time_start` and `time_end`

  Extract subtitles from only a clip of the video. The subtitle timestamps are still calculated according to the full video length.

- `use_fullframe`

  By default, the specified cropped area is used for OCR or if a crop is not specified, then the bottom third of the frame will be used. By setting this value to `True` the entire frame will be used.
  
- `use_dual_zone`

  This parameter allows two specify two areas that will be used for OCR.

- `crop_x(2)`, `crop_y(2)`, `crop_width(2)`, `crop_height(2)`

  Specifies the bounding area(s) in pixels for the portion of the frame that will be used for OCR. See image below for example:
  ![image](https://github.com/timminator/VideOCR/blob/master/Pictures/crop_example.png)

- `use_gpu`

  Set to `True` if performing OCR with GPU.

- `use_angle_cls`

  Set to `True` if classification should be enabled.
  
- `brightness_threshold`
  
  If set, pixels whose brightness are less than the threshold will be blackened out. Valid brightness values range from 0 (black) to 255 (white). This can help improve accuracy when performing OCR on videos with white subtitles.

- `frames_to_skip`

  The number of frames to skip before sampling a frame for OCR. Keep in mind the fps of the input video before increasing.
  
- `min_subtitle_duration`

  Subtitles shorter than this threshold will be omitted from the final subtitle file.

- `use_server_model`

  By default the smaller model are used for the OCR process. This parameter enables the usage of the server models for OCR. This can result in better text detection at the cost of more processing power. Should only ever be used in the GPU version.


## Build and Compile Instructions

- Requirements:
    - Python 3.9 or higher

    - Windows:
        - C++ Build Tools (e.g Visual Studio with "Desktop development with C++" kit installed)
        - 7zip (needs to be available from path)
        - Tkinter (comes with the default python installation on Windows)

    - Linux:
        - Tkinter
        - Working dbus installation is recommended

- Instructions:

    - Clone the repository to your desired location:
      ```bash
      git clone https://github.com/timminator/VideOCR.git
      ```
    - Navigate into the cloned folder and install all dependencies:
      ```bash
      cd VideOCR
      pip install -e ".[dev]"
      ```
    - Execute the build script to create the desired build:
      ```bash
      python build.py --target cpu
      ```
    More info can be found via:
    ```bash
    python build.py -h
    ```
