English | [中文](https://github.com/timminator/VideOCR/blob/master/README_ch.md)

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

Extract hardcoded (burned-in) subtitles from videos via a simple-to-use GUI. VideOCR supports both 100% local processing utilizing the **[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)** engine, as well as a hybrid cloud-based approach using **Google Lens** for highly accurate text recognition. Everything can be easily configured via a few clicks.

This repository also provides a version of VideOCR that can be used from the command line in combination with the supported OCR engines.

The latest release incorporates the newest version of PaddleOCR for local processing and introduces the new Google Lens hybrid mode.

## Setup

### Windows:
You can either install it with the setup installer or you can just download a folder with all the required files including the executable and unzip it to your desired location.

### Linux:
Download the tarball archive from the releases page and unzip it to your desired location.
Optionally you can add VideOCR to your App menus if you want to.
For this step open a terminal where you unpacked the archive and run:

```
./install_videocr.sh
```
This will create a shortcut for VideOCR. You can remove it via:  

```
./uninstall_videocr.sh
```

### Docker:
The VideOCR CLI can also be entirely run within a Docker container.

#### Requirements:
- **[Docker](https://docs.docker.com/get-docker/)** installed on your system.
- **For GPU acceleration:** An NVIDIA GPU with the **[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)** installed on your host machine.

#### Option A: Download from GitHub Container Registry (GHCR):
Pre-built images are automatically generated and hosted on GitHub. You can pull them directly without needing to compile anything:

- **CPU Version:**
  ```bash
  docker pull ghcr.io/timminator/videocr-cli-cpu:latest
  ```

- **GPU Version (CUDA 11.8 - Nvidia 10 Series graphics cards):**
  ```bash
  docker pull ghcr.io/timminator/videocr-cli-gpu-cuda11.8:latest
  ```

- **GPU Version (CUDA 12.9 - Nvidia 16 - 50 Series graphics cards):**
  ```bash
  docker pull ghcr.io/timminator/videocr-cli-gpu-cuda12.9:latest
  ```

#### Option B: Build Locally:
If you prefer to build the image yourself from the source, clone the repository and use the provided Dockerfile. You can specify the hardware target using the BUILD_TARGET argument (cpu, gpu-cuda11.8, or gpu-cuda12.9).

```bash
# Example: Build the CUDA 12.9 GPU version locally
docker build --build-arg BUILD_TARGET=gpu-cuda12.9 -t videocr-cli-gpu:latest .

# Example: Build the CPU version locally
docker build --build-arg BUILD_TARGET=cpu -t videocr-cli-cpu:latest .
```

### macOS (Apple Silicon / arm64):
There is no prebuilt binary or Docker image for macOS — the bundled standalone PaddleOCR runtime is x86 Windows/Linux only. On Apple Silicon the CLI runs natively from source against a pip-installed PaddleOCR instead. This is also faster than running the x86 Docker image under emulation.

1. Create an environment with Python 3.12 (recommended for PaddlePaddle compatibility) and install the dependencies:
   ```bash
   conda create -n videocr python=3.12 -y
   conda activate videocr
   pip install paddlepaddle paddleocr \
     av scikit-image numpy Pillow opencc thefuzz wordninja-enhanced wakepy psutil
   ```
   > `scikit-image` replaces the `fast_ssim` package, whose bundled native library cannot be loaded on macOS. The x86-only `cpuid` and the GUI-only `PySimpleGUI` are not needed for the CLI.

2. Download the PP-OCRv5 model support files (architecture-independent) and extract them into the `CLI/` folder so the layout is `CLI/PaddleOCR.PP-OCRv5.support.files/`. Grab `PaddleOCR.PP-OCRv5.support.files.VideOCR.tar.xz` from the latest [PaddleOCR-Standalone release](https://github.com/timminator/PaddleOCR-Standalone/releases):
   ```bash
   tar -xf PaddleOCR.PP-OCRv5.support.files.VideOCR.tar.xz -C CLI/
   ```

3. Run the CLI from source:
   ```bash
   python CLI/videocr_cli.py -h
   python CLI/videocr_cli.py \
     --video_path /path/to/video.mp4 \
     --output /path/to/subtitle.srt \
     --lang en --use_server_model true
   ```

A convenience wrapper for extracting Chinese hardcoded subtitles is provided in `ocr_cn.sh`.

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
./videocr-cli.bin -h
```

### Example usage (Windows):
```
.\videocr-cli.exe --video_path "Path\to\your\video\example.mp4" --output "Path\to\your\desired\subtitle\location\example.srt" --lang en --time_start "18:40" --use_gpu true
```
More info about the arguments can be found in the parameters section further down.

### Example Usage (Docker):
When running the Docker container, you must use Docker volumes (-v) to mount your local video folder into the container's /data directory so the application can read the video and save the .srt output.

- **GPU Example:**
  ```bash
  docker run --rm -it --gpus all \
  -v /path/to/your/local/videos:/data \
  ghcr.io/timminator/videocr-cli-gpu-cuda12.9:latest \
  --video_path /data/my_video.mp4 \
  --output /data/my_subtitle.srt \
  --use_gpu true
  ```

- **CPU Example:**
  ```bash
  docker run --rm -it \
  -v /path/to/your/local/videos:/data \
  ghcr.io/timminator/videocr-cli-cpu:latest \
  --video_path /data/my_video.mp4 \
  --output /data/my_subtitle.srt
  ```

Any of the CLI parameters listed in the parameters section can be appended to the end of the docker run command.

## Performance

Local OCR processing with PaddleOCR can be slow on a CPU. Using this in combination with a GPU is highly recommended.

Alternatively, using the google_lens engine offloads the heaviest part of the pipeline (text recognition) to the cloud. This makes it an excellent and fast choice for users without a powerful GPU, provided they have an active internet connection.

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

- `ocr_engine`

  Select the OCR engine to use for text detection and recognition. Valid values are `paddleocr` (default) and `google_lens`. 
  `paddleocr` uses 100% local processing for both text detection and recognition. 
  `google_lens` uses hybrid processing where PaddleOCR handles the text detection locally and Google Lens handles the text recognition. Note: The `google_lens` mode requires an active internet connection.

- `lang`

  The language of the subtitles. The supported languages and abbreviations depend on your selected `ocr_engine`.
  - For `paddleocr`: See the [PaddleOCR docs](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md).
  - For `google_lens`: See the [Google Lens docs](https://docs.cloud.google.com/vision/docs/languages).

- `subtitle_position`

  Specifies the alignment of subtitles in the video and allows for better text recognition.

- `conf_threshold`

  Confidence threshold for word predictions. Words with lower confidence than this value will be discarded. The default value `75` is fine for most cases (PaddleOCR only).

  Make it closer to 0 if you get too few words in each line, or make it closer to 100 if there are too many excess words in each line.

- `sim_threshold`

  Similarity threshold for subtitle lines. Subtitle lines with larger [Levenshtein](https://en.wikipedia.org/wiki/Levenshtein_distance) ratios than this threshold will be merged together. The default value `80` is fine for most cases.

  Make it closer to 0 if you get too many duplicated subtitle lines, or make it closer to 100 if you get too few subtitle lines.

- `ssim_threshold`

  If the SSIM between consecutive frames exceeds this threshold, the frame is considered similar and discarded during initial frame filtering in Step 1. A lower value can greatly reduce the number of images OCR needs to be performed on. On relatively tight crop boxes around the subtitle area good results could be seen with this value all the way lowered to 85.

- `post_processing`

  This parameter adds a post processing step to the subtitle detection. The detected text will be analyzed for missing spaces (as this is a common issue with PaddleOCR) and tries to insert them automatically. Currently only available for English, Spanish, Portuguese, German, Italian and French. For more info check out my [wordninja-enhanced](https://github.com/timminator/wordninja-enhanced) repository.

- `max_merge_gap`

  Maximum allowed time gap (in seconds) between two subtitles to be considered for merging if they are similar. The default value 0.09 (i.e., 90 milliseconds) works well in most scenarios.

  Increase this value if you notice that the output SRT file contains several subtitles with the same text that should be merged into a single one and are wrongly split into multiple ones. This can happen if the PaddleOCR OCR engine is not able to detect any text for a short amount of time while the subtitle is displayed in the selected video.

- `time_start` and `time_end`

  Extract subtitles from only a clip of the video. The subtitle timestamps are still calculated according to the full video length.

- `use_fullframe`

  By default, the specified cropped area is used for OCR or if a crop is not specified, then the bottom third of the frame will be used. By setting this value to `True` the entire frame will be used.

- `crop_x(2)`, `crop_y(2)`, `crop_width(2)`, `crop_height(2)`

  Specifies the bounding area(s) in pixels for the portion of the frame that will be used for OCR. See image below for example:
  ![image](https://github.com/timminator/VideOCR/blob/master/Pictures/crop_example.png)

- `subtitle_alignment(2)`

  Subtitle alignment. This parameter allows you to control the position of the subtitles within the video frame using ASS (Advanced SubStation Alpha) tags. Valid values are: `bottom-left`, `bottom-center`, `bottom-right`, `middle-left`, `middle-center`, `middle-right`, `top-left`, `top-center`, `top-right`.

- `max_ocr_image_width`

  Downscales the cropped image frame so its width does not exceed this value before passing it to the OCR engine. A lower value shortens the processing time, but setting it too low can reduce OCR accuracy.

- `use_gpu`

  Set to `True` if performing OCR with GPU.

- `use_angle_cls`

  Set to `True` if classification should be enabled (PaddleOCR only).

- `brightness_threshold`
  
  If set, pixels whose brightness are less than the threshold will be blackened out. Valid brightness values range from 0 (black) to 255 (white). This can help improve accuracy when performing OCR on videos with white subtitles.

- `frames_to_skip`

  The number of frames to skip before sampling a frame for OCR. Keep in mind the fps of the input video before increasing.

- `min_subtitle_duration`

  Subtitles shorter than this threshold will be omitted from the final subtitle file.

- `normalize_to_simplified_chinese`

  Traditional Chinese characters will be converted to Simplified Chinese before processing. Only active for \"Chinese & English\". Tries to fix subtitle merging issues caused by the OCR model inconsistently mixing Traditional characters into Simplified text.

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
        - 7zip
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
      python -m pip install --upgrade pip
      pip install . --group all
      ```
    - Execute the build script to create the desired build:
      ```bash
      python build.py --target cpu
      ```
    More info can be found via:
    ```bash
    python build.py -h
    ```
