[English](https://github.com/timminator/VideOCR/blob/master/README.md) | 中文

<p align="center">
<img src="https://github.com/timminator/VideOCR/raw/master/Pictures/VideOCR.png" alt="VideOCR 图标" width="128">
  <h1 align="center">VideOCR</h1>
  <p align="center">
    从视频中提取硬编码字幕！
    <br />
  </p>
</p>

<br>

## ℹ 关于

通过简单易用的图形界面，利用 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) OCR引擎，从视频中提取硬编码（烧录）字幕。所有配置均可通过点击轻松完成。

此仓库还提供了可与PaddleOCR结合使用的命令行版本VideOCR。

最新版本集成了PaddleOCR的最新版本，OCR能力大幅提升。

## 安装

### Windows:
您可以使用安装程序进行安装，也可以直接下载包含所有必需文件（包括可执行文件）的压缩包，解压到目标位置即可。

### Linux:
从发布页面下载压缩包，解压到目标位置。  
如需将VideOCR添加到应用程序菜单，可在解压后的目录中打开终端并运行以下命令：
```
./install_videocr.sh
```
此命令将创建VideOCR的快捷方式。如需移除，可运行：  
```
./uninstall_videocr.sh
```

## 使用说明

导入视频后，可通过时间轴或左右方向键浏览视频内容。通过点击拖拽的方式在视频上绘制裁剪框，选择字幕区域。完成后，点击“运行”按钮开始字幕提取。

更多选项可在“高级设置”选项卡中配置，详细信息可参考CLI版本的参数说明。
![image](https://github.com/timminator/VideOCR/raw/master/Pictures/GUI.png)

## 命令行版本（CLI）使用说明

解压压缩包后，在目标位置打开终端，运行以下命令：

### Windows:
```
.\videocr-cli.exe -h
```

### Linux:
```
./videocr-cli.bin -h
```

### 示例用法（Windows）:
```
.\videocr-cli.exe --video_path "视频路径\example.mp4" --output "字幕保存路径\example.srt" --lang en --time_start "18:40" --use_gpu true
```
更多参数说明请参考下文。

## 性能说明

在CPU上运行OCR过程可能较慢，建议搭配GPU使用。

## 小贴士

裁剪时，在文字上下方留出一定的缓冲空间以提高识别准确率，但不要将裁剪框设置得过大。

### 快速配置参考

|| 更高速度 | 更高准确率 | 备注
-|------------|---------------|--------
输入视频质量       | 使用较低质量           | 使用较高质量  | 高分辨率视频的性能影响可通过裁剪减轻
`frames_to_skip`          | 数值更高               | 数值更低        | 如需完全准确的时间戳，此参数需设为0。
`SSIM阈值`          | 阈值更低             | 阈值更高    | 若连续帧的SSIM超过此阈值，则跳过OCR。较低的值可显著减少OCR处理的帧数。

## 命令行参数说明（CLI版本）

- `video_path`

  待提取字幕的视频路径。

- `output`

  字幕文件（.srt）保存路径。

- `lang`

  字幕语言。支持的语言及缩写请参考[PaddleOCR文档](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.10/docs/ppocr/blog/multi_languages.en.md#5-support-languages-and-abbreviations)。
  
- `subtitle_position`

  指定字幕在视频中的对齐方式，有助于提升识别准确率。

- `subtitle_alignment`

  （区域1）字幕对齐。此参数允许您使用ASS（Advanced SubStation Alpha）标签控制视频帧内字幕的位置。有效值包括：`bottom-left`、`bottom-center`、`bottom-right`、`middle-left`、`middle-center`、`middle-right`、`top-left`、`top-center`、`top-right`。

- `subtitle_alignment2`

  （区域2）字幕对齐。此参数与`--subtitle_alignment`功能相同，但当启用`--use_dual_zone`时应用于第二个OCR区域。

- `conf_threshold`

  文字预测的置信度阈值。低于此值的文字将被忽略。默认值`75`适用于大多数场景。

  若每行文字过少，可降低此值；若每行文字过多，可提高此值。

- `sim_threshold`

  字幕行的相似度阈值。基于[Levenshtein距离](https://en.wikipedia.org/wiki/Levenshtein_distance)，高于此阈值的字幕行将被合并。默认值`80`适用于大多数场景。

  若字幕行重复过多，可降低此值；若字幕行过少，可提高此值。
  
- `ssim_threshold`

  若连续帧的SSIM超过此阈值，则跳过OCR。较低的值可减少OCR处理的帧数。在字幕区域裁剪较精确时，此值可降至85。
  
- `post_processing`

  启用后处理步骤，自动分析并修复缺失的空格（PaddleOCR常见问题）。目前仅支持英语、西班牙语、葡萄牙语、德语、意大利语和法语。详情请参考[wordninja-enhanced](https://github.com/timminator/wordninja-enhanced)仓库。

- `max_merge_gap`

  合并相似字幕的最大时间间隔（秒）。默认值0.09（90毫秒）适用于大多数场景。

  若发现相同字幕被错误分割为多条，可增加此值。

- `time_start` 和 `time_end`

  仅提取视频片段中的字幕。时间戳仍以完整视频长度计算。

- `use_fullframe`

  默认使用裁剪区域或底部三分之一帧进行OCR。设为`True`时，将使用完整帧。
  
- `use_dual_zone`

  启用后，可指定两个OCR区域。

- `crop_x(2)`, `crop_y(2)`, `crop_width(2)`, `crop_height(2)`

  指定OCR区域的像素范围。示例见下图：
  ![image](https://github.com/timminator/VideOCR/raw/master/Pictures/crop_example.png)

- `max_ocr_image_width`

  在传递给OCR引擎之前缩小裁剪的图像帧，使其宽度不超过此设定值。较低的数值可缩短处理时间，但设置过低可能会降低OCR识别的准确率。

- `use_gpu`

  设为`True`时，使用GPU进行OCR。

- `use_angle_cls`

  设为`True`时，启用分类功能。
  
- `brightness_threshold`
  
  若设置，亮度低于此阈值的像素将被置黑。有效范围为0（黑）至255（白）。适用于白色字幕的视频。
  
- `frames_to_skip`

  OCR前跳过的帧数。调整时需注意视频的fps。
  
- `min_subtitle_duration`

  短于此阈值的字幕将被忽略。

- `normalize_to_simplified_chinese`

  在处理前将繁体中文字符转换为简体中文。仅适用于 "Chinese & English" 模式。旨在修复因 OCR 模型在简体文本中不一致地混入繁体字符而导致的字幕合并问题。

- `use_server_model`

  默认使用轻量模型进行OCR。启用后将使用服务器模型，提升检测效果，但会消耗更多资源。建议仅在GPU版本中使用。

## 构建与编译说明

- 要求：
    - Python 3.9或更高版本
    - Windows:
        - C++构建工具（如Visual Studio的“使用C++的桌面开发”套件）
        - 7zip（需添加到PATH）
        - Tkinter（Windows默认Python安装包含）
    - Linux:
        - 7zip
        - Tkinter
        - 建议安装dbus

- 步骤：
    - 克隆仓库到目标位置：
      ```bash
      git clone https://github.com/timminator/VideOCR.git
      ```
    - 进入目录并安装依赖：
      ```bash
      cd VideOCR
      pip install -e ".[dev]"
      ```
    - 运行构建脚本：
      ```bash
      python build.py --target cpu
      ```
    更多信息可通过以下命令查看：
    ```bash
    python build.py -h
    ```
