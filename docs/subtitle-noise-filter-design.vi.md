# Thiết kế bộ lọc nhiễu subtitle cho PaddleOCR Detection + Google Lens Recognition

Trạng thái: Đề xuất triển khai

Phạm vi mã nguồn: fork `timminator/VideOCR`, từ `master` hiện tại hoặc tag `v1.5.1`

Ngôn ngữ tài liệu: Tiếng Việt

## 1. Mục tiêu

Giảm text noise trong pipeline:

```text
Video frame
→ PaddleOCR text detection
→ lọc và chọn vùng subtitle
→ Google Lens recognition
→ lọc Lens words
→ tạo SRT
```

Các loại noise cần giảm:

- Watermark nhỏ, mờ, cố định gần đáy video.
- Logo ở góc màn hình.
- Scene text hoặc bảng hiệu trong background.
- Text UI/HUD.
- Text không thuộc subtitle nhưng bị ghép vào cùng dòng.

Trường hợp ưu tiên là subtitle anime tiếng Việt:

- Chữ trắng hoặc xám sáng, thường có viền đen.
- Thường nằm ở giữa và gần phía dưới khung hình.
- Có thể có một hoặc hai dòng.
- Có thể rất ngắn theo chiều ngang, ví dụ `Thì...`.
- Watermark nhỏ có thể nằm ngay dưới, phía sau hoặc gần subtitle.

Task này không thay Google Lens, không thay PaddleOCR model và không train model mới.

## 2. Kết quả mong muốn

Khi bật bộ lọc:

1. Chỉ các line candidate có khả năng là subtitle mới được dùng cho grouping và SSIM.
2. Frame chỉ có watermark hoặc logo phải được xem là empty nếu geometry đủ để xác định đó không phải subtitle.
3. Google Lens chỉ nhận tight crop bao quanh tối đa một hoặc hai dòng subtitle đã chọn.
4. Lens words nằm ngoài selected line bands hoặc quá nhỏ phải bị loại.
5. Text cố định theo thời gian có thể bị loại bằng temporal watermark filter.
6. Subtitle ngắn không được loại chỉ vì có width nhỏ.
7. PaddleOCR full detection + recognition giữ nguyên hành vi mặc định.
8. Chế độ `off` đi qua legacy path và tái tạo hành vi cũ gần như hoàn toàn.

Đây là bộ lọc heuristic. Không thể bảo đảm loại đúng mọi scene text nếu scene text có cùng vị trí, kích thước và style với subtitle thật.

## 3. Hiện trạng cần sửa

### 3.1 Detection score bị mất

Mỗi PaddleOCR polygon có `dt_score`, nhưng pipeline hiện tại chỉ tính trung bình thành `frame_score`, sau đó tách polygon khỏi score.

Hậu quả:

- Không thể chấm điểm từng line candidate chính xác.
- Một logo hoặc scene text có thể làm sai frame-level score.
- Frame được chọn cho recognition chưa chắc có subtitle tốt nhất.

### 3.2 Ghép dòng chỉ dựa trên vertical overlap

`utils.get_line_rects()` hiện merge rectangle nếu có overlap theo chiều dọc.

Hậu quả:

- Watermark ở xa theo chiều ngang vẫn có thể bị nối vào subtitle.
- Box có height hoặc baseline khác nhau vẫn có thể bị ghép.
- Merge tuần tự phụ thuộc thứ tự rectangle.

### 3.3 Toàn bộ zone được gửi sang Google Lens

Recognition pass hiện gửi toàn bộ `item["img"]` sang Lens. Lens vì vậy có thể nhận dạng cả subtitle, watermark, logo, HUD và scene text.

### 3.4 Lens confidence không phải confidence thật

Google Lens output hiện được gán confidence `1.0`. Lens không cung cấp confidence thật trong pipeline này.

Không được thay `1.0` bằng một confidence giả khác. Thay vào đó:

- `conf_threshold` chỉ áp dụng cho PaddleOCR recognition.
- Lens phải bypass confidence filtering một cách tường minh.
- Nếu cần xếp hạng kết quả Lens, dùng `quality_score` riêng dựa trên detection và geometry.

### 3.5 Word và line grouping còn yếu

`utils.is_on_same_line()` chủ yếu dựa trên vertical overlap, chưa xét:

- Height ratio.
- Center-Y distance.
- Baseline distance.
- Selected subtitle line band.
- Hai word có thuộc hai selected lines khác nhau hay không.

### 3.6 `subtitle_position` chưa lọc detection

`subtitle_position` hiện chủ yếu chọn vùng dùng cho SSIM sample ban đầu. Nó chưa lọc trực tiếp Paddle detections hoặc Lens words.

## 4. Nguyên tắc thiết kế

1. Triển khai trước cho `google_lens`.
2. Không thay đổi legacy PaddleOCR recognition path trong phiên bản đầu.
3. Geometry, vị trí và temporal persistence là tín hiệu chính.
4. Outline/contrast chỉ là soft feature.
5. Không hard-code tên website hoặc nội dung watermark.
6. Không dùng width tối thiểu để loại subtitle.
7. Mọi phép biến đổi tọa độ phải được lưu rõ ràng.
8. Các hàm lọc cốt lõi phải là pure functions để unit test không cần PaddleOCR, Lens hoặc video thật.
9. Debug output phải có giới hạn để không làm đầy ổ đĩa.
10. Mọi default động phải được resolve ở một nơi duy nhất.

## 5. Chế độ hoạt động và backward compatibility

Thêm option:

```text
--subtitle-filter-mode off|balanced|strict
```

Giá trị parser ban đầu nên là `None`, sau đó resolve:

```text
ocr_engine=google_lens + mode chưa được chỉ định → balanced
ocr_engine=paddleocr   + mode chưa được chỉ định → off
```

Trong phiên bản đầu:

- `google_lens + off`: dùng legacy grouping, legacy SSIM và gửi toàn bộ zone sang Lens.
- `google_lens + balanced`: bật geometry selection, tight crop và Lens word filtering; ưu tiên recall.
- `google_lens + strict`: bật hard geometry bounds và temporal watermark filter mặc định.
- `paddleocr`: luôn dùng legacy path. Nếu người dùng truyền `balanced` hoặc `strict`, chương trình cảnh báo rằng filter mới chưa áp dụng cho PaddleOCR recognition và dùng effective mode `off`.

Không nên cho legacy path đi qua các hàm mới rồi cố mô phỏng hành vi cũ. Cần giữ một nhánh rõ ràng:

```python
if ocr_engine == "google_lens" and effective_filter_mode != "off":
    # New subtitle-filter pipeline
else:
    # Legacy pipeline
```

## 6. Cấu hình

Nên tạo một dataclass nội bộ:

```python
@dataclass(frozen=True)
class SubtitleFilterConfig:
    mode: Literal["off", "balanced", "strict"]
    max_subtitle_lines: int = 2
    min_line_height_ratio: float = 0.06
    max_line_height_ratio: float = 0.35
    min_word_height_ratio: float = 0.50
    recognition_padding_x_ratio: float = 0.60
    recognition_padding_y_ratio: float = 0.35
    watermark_filter: bool = False
    watermark_min_occurrences: int = 10
    watermark_min_span_sec: float = 15.0
    watermark_presence_ratio: float = 0.60
    watermark_text_similarity: float = 0.85
    debug_dir: str | None = None
    debug_max_frames: int = 200
```

CLI options:

```text
--subtitle-filter-mode off|balanced|strict
--max-subtitle-lines 2
--min-line-height-ratio 0.06
--max-line-height-ratio 0.35
--min-word-height-ratio 0.50
--recognition-padding-x-ratio 0.60
--recognition-padding-y-ratio 0.35
--watermark-filter [true|false]
--watermark-min-occurrences 10
--watermark-min-span-sec 15
--watermark-presence-ratio 0.60
--watermark-text-similarity 0.85
--debug-subtitle-filter-dir PATH
--debug-subtitle-filter-max-frames 200
```

`watermark_filter` cũng nên có trạng thái parser là `None`:

```text
strict + chưa override   → true
balanced + chưa override → false
off + chưa override      → false
```

GUI đang truyền boolean dưới dạng `true` hoặc `false`, vì vậy CLI parser phải chấp nhận cả:

```text
--watermark-filter
--watermark-filter true
--watermark-filter false
```

Các score weight và threshold nội bộ chưa cần expose trên GUI trong phiên bản đầu.

## 7. Data model

Nên đặt các model và pure functions mới trong:

```text
CLI/videocr/subtitle_filter.py
```

### 7.1 Detection region

```python
@dataclass
class DetectedRegion:
    polygon: list[list[float]]
    rect: list[float]  # [x1, y1, x2, y2], zone-relative
    score: float
    angle_deg: float | None = None
```

Không bỏ `polygon` ngay sau khi tạo `rect`. Nếu polygon đã bị axis-align trong quá trình unstitch thì `angle_deg=None`.

### 7.2 Subtitle line candidate

```python
@dataclass
class SubtitleLineCandidate:
    rect: list[float]
    regions: list[DetectedRegion]
    detector_score: float
    geometry_score: float
    position_score: float
    outline_score: float
    total_score: float
    reject_reason: str | None = None
```

Tất cả component score được normalize về `[0, 1]`.

Initial total score:

```text
0.30 * detector_score
+ 0.30 * geometry_score
+ 0.25 * position_score
+ 0.15 * outline_score
```

Đây là calibration default, cần được điều chỉnh bằng fixture anime thật trước khi release.

### 7.3 Recognition metadata

```python
@dataclass
class RecognitionCropMeta:
    logical_frame_idx: int
    source_frame_idx: int
    zone_idx: int
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    lens_scale_x: float
    lens_scale_y: float
    selected_lines_zone: list[list[float]]
    selected_lines_crop: list[list[float]]
    group_start_frame: int
    group_end_frame: int
    support_count: int
```

Ý nghĩa:

- `logical_frame_idx`: frame dùng cho timestamp bắt đầu của event.
- `source_frame_idx`: frame thật cung cấp pixels và selected rectangles.
- `selected_lines_zone`: tọa độ trong zone, dùng cho temporal signature.
- `selected_lines_crop`: tọa độ trong ảnh gửi Lens, dùng cho Lens word filtering.
- `support_count`: số detection frames mà recognition image đại diện sau SSIM.

Không được dùng một field `frame_idx` duy nhất cho cả timestamp và source image.

## 8. Quy ước hệ tọa độ

Pipeline có bốn hệ tọa độ:

1. `video-global`: khung hình video gốc.
2. `zone-relative`: sau crop zone và resize cho OCR.
3. `recognition-crop-relative`: sau tight crop.
4. `lens-image-relative`: sau optional upscaling trước khi gửi Lens.

Paddle detection và candidate selection hoạt động trong `zone-relative`.

Lens trả normalized geometry trong `lens-image-relative`. Khi parse Lens:

```text
normalized Lens coordinates
→ lens pixels
→ chia lens_scale
→ recognition-crop-relative
→ cộng crop_x/crop_y
→ zone-relative
```

Lens word filtering dùng crop-relative line bands. Temporal watermark clustering bắt buộc dùng zone-relative coordinates. Không dùng crop-relative coordinates cho temporal signature.

## 9. Giữ score của từng detection

Khi parse PaddleOCR JSON:

```python
DetectedRegion(
    polygon=adjusted_polygon,
    rect=polygon_to_rect(adjusted_polygon),
    score=float(score),
)
```

`parsed_detections` phải giữ danh sách `DetectedRegion`, không chỉ polygon.

Frame-level score cũ chỉ được giữ cho legacy path. New path dùng:

- Candidate detector score.
- Selected-set score.
- Source-frame quality score.

Detector score của candidate nên là trung bình có trọng số vừa phải theo region width, nhưng phải giới hạn weight để một box rất lớn không chi phối toàn bộ candidate.

## 10. Unstitch polygon

Hiện tại unstitch chuyển mọi polygon thành rectangle, làm mất orientation.

Phiên bản đầu có hai lựa chọn hợp lệ:

1. Giữ polygon gốc khi polygon nằm hoàn toàn trong một grid cell; translate tất cả point về zone-relative.
2. Nếu polygon cắt biên cell, clip polygon hoặc fallback về axis-aligned rectangle và đặt `angle_deg=None`.

Orientation chỉ là điều kiện phụ. Không được block toàn bộ feature nếu chưa triển khai polygon clipping đầy đủ.

## 11. Xây dựng line candidates

Tạo:

```python
build_line_candidates(
    detections: list[DetectedRegion],
    zone_width: int,
    zone_height: int,
    config: SubtitleFilterConfig,
) -> list[SubtitleLineCandidate]
```

### 11.1 Pairwise compatibility

Hai detection được nối cạnh trong graph khi đồng thời thỏa:

1. Vertical overlap ratio:

   ```text
   overlap_y / min(height_a, height_b) >= 0.45
   ```

2. Height similarity:

   ```text
   max(height_a, height_b) / min(height_a, height_b) <= 1.60
   ```

3. Center-Y distance:

   ```text
   abs(center_y_a - center_y_b)
       <= 0.45 * max(height_a, height_b)
   ```

4. Horizontal gap:

   ```text
   horizontal_gap <= 2.5 * local_median_height
   ```

5. Nếu cả hai polygon có angle:

   ```text
   abs(angle_a - angle_b) <= configured_angle_tolerance
   ```

`local_median_height` được tính từ hai region đang so sánh hoặc các region height tương thích gần đó, không lấy median của toàn frame nếu frame có nhiều kích thước text khác nhau.

### 11.2 Connected components và chống chaining

Tạo connected components từ graph, sau đó validate từng component:

- Height dispersion không quá lớn.
- Baseline dispersion không quá lớn.
- Gap lớn nhất không bất thường so với median height.
- Component không có horizontal span bất hợp lý do một chuỗi box trung gian.

Nếu component không compact, split tại horizontal gap hoặc baseline discontinuity lớn nhất.

Sau khi cluster:

- Tạo union rectangle cho mỗi candidate.
- Sắp xếp candidate theo center Y.
- Không merge hai subtitle lines riêng biệt.

## 12. Chấm điểm subtitle candidate

Tạo:

```python
score_subtitle_candidate(
    candidate,
    image,
    subtitle_position,
    zone_context,
    config,
) -> SubtitleLineCandidate
```

### 12.1 Horizontal-position score

- `center`: ưu tiên center X gần `0.5`.
- `left`: ưu tiên vùng trái.
- `right`: ưu tiên vùng phải.
- `any`: gần như không phạt theo X.

Đây là soft score với plateau đủ rộng. Câu ngắn không bị phạt chỉ vì width nhỏ hoặc vì center dao động nhẹ trong một crop box rộng.

### 12.2 Vertical-position score

Phải có vertical prior để full-frame mode không ưu tiên scene text ở giữa hoặc phía trên:

- Full frame: ưu tiên nửa dưới, mạnh nhất gần vùng subtitle thông thường.
- Default bottom-third: prior nhẹ vì zone đã nằm dưới.
- Custom crop: prior rất nhẹ vì crop thể hiện chủ ý của người dùng.
- Dual zone: chấm điểm độc lập trong từng zone.

Vertical position vẫn là soft score, không phải hard rule tuyệt đối.

### 12.3 Height score

Height ratio tính theo chiều cao zone đã resize:

```text
line_height / zone_height
```

Defaults:

```text
min_line_height_ratio = 0.06
max_line_height_ratio = 0.35
```

Quy tắc:

- `balanced`: dùng hai giá trị trên như soft target; chỉ reject kích thước cực đoan.
- `strict`: dùng làm hard bounds, nhưng phải có điều chỉnh an toàn cho full-frame.
- Không dùng width làm điều kiện reject.
- Custom crop rất sát subtitle không được reject chỉ vì line chiếm hơn 35% crop.

Việc điều chỉnh theo `zone_context` phải được test riêng cho full frame, default crop và custom crop.

### 12.4 Geometry score

Geometry score kết hợp:

- Height score.
- Baseline consistency.
- Height consistency giữa regions.
- Component compactness.
- Gap consistency.

### 12.5 Detector score

Dùng score của các `DetectedRegion` thuộc candidate. Không dùng frame average chứa cả logo và scene text.

### 12.6 Outline/contrast score

Đây là soft feature nhằm ưu tiên subtitle sáng có vùng tối bao quanh:

1. Lấy crop của candidate từ ảnh không bị phá hủy.
2. Xác định foreground sáng tương đối theo local luminance.
3. Dilate foreground để tạo surrounding ring.
4. So sánh luminance của core và ring.
5. Core sáng hơn ring đáng kể thì cộng điểm.

Không:

- Threshold hoặc xóa pixels trực tiếp trên ảnh gốc bằng outline mask.
- Hard reject subtitle màu.
- Thêm dependency nặng chỉ để tính morphology nếu Pillow/NumPy đã đủ.

Nếu `brightness_threshold` đang bật, pipeline phải giữ riêng ảnh sạch cho feature/debug nếu cần. Legacy recognition image vẫn phải giữ hành vi cũ trong mode `off`.

### 12.7 Minimum candidate score

Initial calibration:

```text
balanced minimum total score = 0.42
strict minimum total score   = 0.55
```

Các giá trị này là internal config trong phiên bản đầu và phải được tune bằng fixture thật.

## 13. Chọn tối đa một hoặc hai dòng

Tạo:

```python
select_subtitle_lines(
    candidates,
    config,
) -> list[SubtitleLineCandidate]
```

Không chỉ chọn candidate cao nhất rồi greedily lấy candidate thứ hai. Nên đánh giá:

- Mọi singleton hợp lệ.
- Mọi pair hợp lệ.

Pair hợp lệ khi:

- Height ratio giữa hai dòng không vượt `1.5`.
- Khoảng cách Y phù hợp với hai subtitle lines liên tiếp.
- Center X không lệch bất thường.
- Cả hai đạt minimum score.
- Hai candidate không phải hai mảnh của cùng một dòng.

Pair score gồm:

- Tổng candidate scores.
- Bonus cho height similarity.
- Bonus cho X alignment.
- Bonus cho line spacing hợp lý.

Chọn singleton hoặc pair có joint score cao nhất. Kết quả cuối sắp xếp từ trên xuống dưới.

Default:

```text
max_subtitle_lines = 2
```

Không chọn watermark làm dòng thứ ba. Không yêu cầu subtitle có width lớn.

Nếu không có candidate hợp lệ:

- Đánh dấu `(frame_idx, zone_idx)` là empty.
- Không tạo recognition image.
- Không gửi frame đó sang Lens.

## 14. Lọc trước grouping và SSIM

New path chạy theo thứ tự:

```text
Parse detections
→ build candidates
→ score candidates
→ select 0–2 lines
→ group frames bằng selected lines
→ tight-box SSIM trên selected lines
→ chọn source frame
→ build recognition crop
```

Chỉ selected lines được dùng để:

- So sánh rectangle giữa các frame.
- Group frame geometry.
- Tạo SSIM crops.
- Chọn source-frame quality.
- Tạo recognition crop.

Không dùng raw detections bị reject để tạo group hoặc kéo dài event.

## 15. SSIM metadata và source frame

Trong mỗi SSIM-similar batch:

- `logical_frame_idx` là frame đầu batch để giữ timestamp behavior hiện tại.
- `source_frame_idx` là frame có selected-set quality cao nhất và cung cấp pixels.
- Recognition crop dùng selected rectangles của chính `source_frame_idx`.
- Không dùng temporal union rectangle làm recognition crop.

Mỗi surviving item phải giữ:

```text
group_start_frame
group_end_frame
support_count
logical_frame_idx
source_frame_idx
source_selected_lines
```

Temporal union rectangles vẫn có thể dùng để tạo SSIM crops có kích thước ổn định, nhưng không được dùng làm crop cuối gửi Lens.

## 16. Tạo tight recognition crop

Tạo union box của selected lines, sau đó padding:

```text
reference_line_height = median(selected line heights)
pad_x = reference_line_height * recognition_padding_x_ratio
pad_y = reference_line_height * recognition_padding_y_ratio
```

Defaults:

```text
recognition_padding_x_ratio = 0.60
recognition_padding_y_ratio = 0.35
```

Các bước:

1. Clamp union box trong image bounds.
2. Crop đúng source image.
3. Chuyển selected lines từ zone-relative sang crop-relative.
4. Nếu crop quá nhỏ, mở rộng thêm trong bounds.
5. Nếu line height theo pixels quá nhỏ cho Lens, upscale recognition crop.
6. Scale selected line coordinates tương ứng.
7. Lưu đầy đủ crop offsets và scale factors.

Không giảm kích thước crop xuống mức làm Lens mất ngữ cảnh của câu rất ngắn.

Trong mode `off`, tiếp tục gửi toàn bộ `item["img"]` như legacy pipeline.

## 17. Lọc Lens words

Tạo:

```python
filter_lens_words(
    words,
    selected_lines_crop,
    crop_dimensions,
    config,
) -> list[FilteredLensWord]
```

### 17.1 Line assignment

Với mỗi Lens word:

- Tính word height.
- Tính center Y và bottom Y.
- Tính overlap với từng selected line band.
- Tính baseline distance.
- Tính height ratio với median selected line height.
- Gán `line_id` tốt nhất hoặc đánh dấu unassigned.

Line band có thể được mở rộng nhẹ theo Y để Lens geometry không cần trùng tuyệt đối với Paddle box.

### 17.2 Reject rules

Một word bình thường bị loại nếu:

- Height quá nhỏ so với subtitle line.
- Không overlap và cũng không đủ gần line band nào.
- Center Y quá xa mọi selected line.
- Baseline không phù hợp với line được gán.

Default:

```text
min_word_height_ratio = 0.50
```

Balanced dùng rule mềm hơn strict.

### 17.3 Punctuation

Punctuation nhỏ không bị loại chỉ vì height nhỏ.

Nhận diện punctuation bằng Unicode category và nội dung, bao gồm:

- Dấu chấm, phẩy, ba chấm.
- Dấu hỏi và chấm than.
- Dấu hai chấm, chấm phẩy.
- Dấu ngoặc.
- Quote marks và các punctuation Unicode tương đương.

Punctuation nhỏ được giữ nếu:

- Nằm trong hoặc rất gần selected line band; hoặc
- Nằm sát một word hợp lệ trên cùng line.

Không assume Lens luôn trả punctuation thành một word riêng. Punctuation có thể nằm trong `text` hoặc `separator`.

### 17.4 Whitespace

Khi loại word:

- Không để lại separator thừa ở đầu dòng.
- Không làm mất punctuation gắn với word hợp lệ.
- Không nối hai từ sai cách.

Nên giữ `text` và `separator` riêng đến khi hoàn tất word filtering.

## 18. Sửa line grouping của recognized words

API mới:

```python
is_on_same_line(
    word1,
    word2,
    line_profile=None,
) -> bool
```

Khi có `line_profile`:

1. Nếu hai word đã có `line_id` khác nhau thì trả về `False`.
2. Ưu tiên selected line assignment.
3. Kiểm tra center-Y hoặc vertical overlap.
4. Kiểm tra height ratio.
5. Kiểm tra baseline distance.

Khi `line_profile=None` và effective mode `off`, dùng legacy fallback để giữ compatibility.

Tốt hơn nữa, new Lens path có thể group trực tiếp theo `line_id`; `is_on_same_line()` chỉ xử lý unassigned/punctuation fallback.

## 19. Temporal watermark filter

Temporal filter chạy:

```text
Sau khi parse và lọc Lens words của tất cả recognition images
→ trước khi tạo PredictedFrames
```

### 19.1 Signature

Mỗi word hoặc recognized line có:

```text
normalized lowercase text
zone index
quantized zone-relative center X
quantized zone-relative center Y
quantized height
```

Tọa độ bắt buộc là zone-relative, không phải crop-relative.

Text normalization:

- Unicode normalization.
- Lowercase.
- Trim và collapse whitespace.
- Không xóa toàn bộ punctuation nếu punctuation có ý nghĩa.

### 19.2 Fuzzy clustering

Chỉ fuzzy-match text khi position và height đã gần nhau.

Default:

```text
watermark_min_occurrences = 10
watermark_min_span_sec = 15
watermark_presence_ratio = 0.60
watermark_text_similarity = 0.85
```

Một cluster bị đánh dấu watermark chỉ khi đồng thời:

- Text gần như không đổi.
- Zone-relative position gần như không đổi.
- Height gần như không đổi.
- Weighted occurrence count đạt minimum.
- Time span đạt minimum.
- Presence ratio đạt minimum.

### 19.3 Tính occurrence sau SSIM

Không chỉ đếm số Lens responses. Mỗi recognition result có thể đại diện cho nhiều detection frames.

Sử dụng:

```text
weighted_occurrences = sum(support_count)
```

Presence ratio phải dùng cùng đơn vị support:

```text
cluster support / eligible active support in zone
```

Đồng thời vẫn cần tối thiểu số recognition observations độc lập hoặc số time bins khác nhau để tránh kết luận watermark từ đúng một OCR sample dài.

Một đề xuất an toàn:

- Ít nhất 3 recognition observations độc lập hoặc 3 time bins.
- Trừ khi geometry stage đã đánh dấu candidate là rất nhỏ và có raw positional persistence mạnh.

### 19.4 Bảo vệ subtitle ngắn

Không loại chỉ vì text ngắn xuất hiện vài lần.

Với text rất ngắn:

- Yêu cầu exact hoặc gần-exact text match cao hơn.
- Yêu cầu span và presence ratio chặt hơn.
- Không cluster nếu position thay đổi.
- Không loại các câu như `Ừ`, `Không`, `Thì...` chỉ vì lặp lại rải rác.

### 19.5 Granularity

Ưu tiên loại persistent word trước. Chỉ loại cả line nếu:

- Toàn bộ line thuộc watermark cluster; hoặc
- Sau word removal line không còn nội dung có nghĩa.

Điều này cho phép bỏ watermark nằm gần subtitle mà vẫn giữ phần subtitle thay đổi.

### 19.6 Giới hạn

Temporal filter là fallback, không thay geometry stage.

Watermark-only có thể đã bị SSIM rút xuống rất ít recognition samples. Vì vậy watermark nhỏ phải được reject sớm bằng geometry khi có thể.

## 20. Tạo PredictedFrames

Sau Lens word filtering và optional temporal filtering:

1. Chuyển các word còn lại thành `PredictedText`.
2. Group theo selected `line_id`.
3. Giữ line order từ trên xuống dưới.
4. Tạo text theo line.
5. Tạo empty `PredictedFrames` cho các active frame coordinates không còn recognized subtitle.

Lens không dùng `conf_threshold`. Nếu cần chọn text tốt nhất giữa nhiều frames, thêm `quality_score` riêng thay vì giả lập confidence.

Timestamp và SRT merging hiện tại không thay đổi ngoài việc input frames sạch hơn.

## 21. Debug output

Khi có:

```text
--debug-subtitle-filter-dir PATH
```

lưu tối đa `debug_max_frames`, mặc định 200.

### 21.1 Detection overlay

- Đỏ: raw Paddle detections.
- Vàng: line candidates.
- Xanh: selected subtitle lines.
- Xám: rejected candidates.
- Text cạnh candidate: detector, geometry, position, outline và total score.

### 21.2 Recognition debug

- Tight crop cuối cùng gửi Lens.
- Selected line bands trong crop.
- Lens words trước filtering.
- Lens words sau filtering.
- Persistent watermark words nếu temporal filter loại chúng.

### 21.3 Tên file

Tên file chứa:

```text
logical frame index
source frame index
timestamp
zone index
debug stage
```

Ví dụ:

```text
frame_00001234_source_00001238_00-00-41.120_zone0_detection.jpg
frame_00001234_source_00001238_00-00-41.120_zone0_lens.jpg
```

### 21.4 Metadata

Tạo JSONL:

```text
frame_idx
source_frame_idx
zone_idx
candidate_rect
detector_score
geometry_score
position_score
outline_score
total_score
selected
reject_reason
crop_rect
support_count
```

Reject reasons tối thiểu:

```text
too_small
too_large
low_total_score
position_penalty
component_not_compact
too_far_from_selected_line
word_too_small
wrong_line_band
persistent_watermark
```

Debug I/O không được chạy khi `debug_dir=None`.

## 22. CLI, API, GUI và config

### 22.1 CLI

Cập nhật:

```text
CLI/videocr_cli.py
```

Parser cần:

- Validate enum.
- Validate ratio trong `[0, 1]` khi phù hợp.
- Validate count và time span không âm.
- Resolve dynamic defaults sau `parse_args()`.

### 22.2 Python API

Cập nhật:

```text
CLI/videocr/api.py
CLI/videocr/video.py
```

API public có thể nhận các option chi tiết, nhưng nên gom thành `SubtitleFilterConfig` trước khi gọi `Video.run_ocr()` để tránh truyền hơn mười positional arguments.

Các tham số mới nên là keyword-only nếu có thể mà không phá compatibility.

### 22.3 GUI

GUI phiên bản đầu expose:

- Checkbox: Enable subtitle noise filter.
- Combo: Balanced / Strict.
- Checkbox: Persistent watermark filter.
- Checkbox: Save filter debug images.
- Optional directory picker cho debug output.

Hành vi:

- Với Google Lens, checkbox filter mặc định bật và mode mặc định Balanced.
- Với PaddleOCR, control bị disable hoặc hiển thị ghi chú feature chưa áp dụng.
- Strict bật watermark filter mặc định nếu người dùng chưa override.
- Người dùng vẫn có thể tắt watermark filter trong Strict.

### 22.4 Config persistence và batch queue

Cập nhật:

- `get_default_settings()`.
- Save/load config.
- Autosave keys.
- GUI validation.
- Snapshot args khi thêm batch job.
- Edit/requeue job.
- CLI command serialization.

Batch job phải giữ đúng filter settings tại thời điểm được thêm vào queue, không đọc lại GUI values khi bắt đầu chạy.

### 22.5 Languages

Thêm English keys vào `languages/en.json` và tất cả language files.

Nếu chưa có bản dịch:

- Dùng English text trong file đó; hoặc
- Dùng `LANG.get(key, english_fallback)` an toàn.

Không được để thiếu key làm crash GUI.

## 23. Tests

Thêm `pytest` vào dev dependencies và tạo:

```text
tests/
```

Các core tests không gọi network, PaddleOCR CLI hoặc Google Lens CLI.

### 23.1 Line clustering

1. Hai word cùng baseline, height tương tự, gap vừa phải → cùng candidate.
2. Watermark ở góc có cùng vertical range nhưng horizontal gap lớn → không merge.
3. Hai subtitle lines → đúng hai candidates.
4. Scene text có height khác nhiều → không merge.
5. Chaining qua box trung gian → component được split.
6. Detection polygon có angle khác lớn → không merge khi angle khả dụng.

### 23.2 Candidate scoring và selection

1. Subtitle hai dòng ở giữa phía dưới → chọn cả hai.
2. Subtitle ngắn `Thì...` → vẫn chọn.
3. Watermark nhỏ phía dưới → reject watermark, giữ subtitle.
4. Frame chỉ có watermark nhỏ → empty.
5. Logo góc trên trái trong center mode → không chọn.
6. Left/right/any → hoạt động theo `subtitle_position`.
7. Full-frame subtitle có height dưới 6% → Balanced vẫn có thể giữ.
8. Custom crop rất sát subtitle → không reject sai do max ratio.

### 23.3 Coordinate transforms

1. Tight crop đúng bounds.
2. Zone-relative selected line → crop-relative chính xác.
3. Crop upscaling cập nhật line coordinates chính xác.
4. Lens normalized → crop-relative chính xác.
5. Lens crop-relative → zone-relative chính xác.
6. Padding không vượt image bounds.
7. Source-frame rectangles được dùng thay vì logical-frame rectangles.

### 23.4 Lens word filtering

1. Word subtitle chuẩn → giữ.
2. Watermark nhỏ → loại.
3. Dấu `...` nhỏ sát word hợp lệ → giữ.
4. Punctuation Unicode → giữ đúng.
5. Word thuộc line khác → không ghép sai.
6. Word ngoài cả hai line bands → loại.
7. Loại word không làm hỏng whitespace.

### 23.5 Temporal watermark

1. Cùng text và cùng zone-relative position qua nhiều time bins → loại.
2. Cùng text nhưng crop offsets khác nhau, zone position giống nhau → vẫn cluster.
3. Cùng text nhưng zone position thay đổi → giữ.
4. Text chỉ lặp vài lần → giữ.
5. Subtitle thật thay đổi liên tục tại cùng vị trí → giữ.
6. Câu ngắn lặp rải rác → giữ.
7. Một recognition result có `support_count` lớn nhưng không đủ observations → không loại nhầm.
8. Persistent word nằm cạnh subtitle thay đổi → chỉ loại word persistent.

### 23.6 Backward compatibility

Với:

```text
--subtitle-filter-mode off
```

test xác nhận:

- Legacy line grouping được dùng.
- Recognition image vẫn là toàn zone.
- Lens words không bị geometry filter.
- PaddleOCR default path không thay đổi.

### 23.7 Integration

Integration tests có thể dùng recorded fixtures:

- Paddle detection JSON.
- Stitched mapping.
- Lens JSON response.
- Synthetic frame images.

End-to-end test thật với Google Lens nên là manual hoặc opt-in vì phụ thuộc network và external CLI.

## 24. Benchmark

Acceptance về hiệu năng:

```text
Local preprocessing overhead <= khoảng 15%
```

Đo riêng:

- Candidate construction.
- Candidate scoring.
- Outline scoring.
- Debug disabled.
- Lens word filtering.
- Temporal clustering.

Không tính network latency của Google Lens vào local preprocessing.

So sánh trên cùng clip, cùng `frames_to_skip`, cùng crop và cùng detection outputs nếu có thể.

Ngoài wall time, ghi:

- Số detection frames.
- Số empty frames sau geometry.
- Số recognition images.
- Tổng pixel area gửi Lens.
- Peak memory.

Số recognition images của filter mode phải không lớn hơn legacy baseline. Tổng pixel area gửi Lens nên giảm đáng kể.

## 25. Acceptance fixture

Fixture hoặc test clip cần có:

- Logo ở góc trên trái.
- Subtitle trắng viền đen ở giữa phía dưới.
- Watermark nhỏ, mờ gần đáy.
- Subtitle một dòng.
- Subtitle hai dòng.
- Câu ngắn `Thì...`.
- Frame chỉ có watermark.
- Ít nhất một scene text trong background.

Kết quả:

1. SRT không chứa logo góc trên.
2. SRT không chứa watermark nhỏ cố định.
3. Subtitle hai dòng giữ đủ hai dòng, đúng thứ tự.
4. Câu `Thì...` được giữ.
5. Frame chỉ có watermark không tạo SRT event.
6. Số recognition images không tăng.
7. Local preprocessing overhead không vượt khoảng 15% trên benchmark đã định.
8. Debug images giải thích được candidate nào được chọn hoặc loại.
9. Không crash ở full frame, default crop, custom crop và dual zone.
10. Không crash với `center`, `left`, `right`, `any`.
11. Lens timeout, malformed word geometry hoặc empty response được xử lý an toàn.

Các tiêu chí 1–5 là mục tiêu trên fixture xác định, không phải cam kết loại đúng mọi text trong mọi video.

## 26. Thứ tự triển khai

### Commit 1 — Geometry filter, metadata và tight crop

- Thêm `SubtitleFilterConfig`.
- Thêm data models.
- Giữ score từng detection.
- Bổ sung CLI/API plumbing tối thiểu.
- Xây line candidates.
- Chấm điểm và chọn tối đa hai lines.
- Tách logical frame và source frame.
- Lưu SSIM support metadata.
- Tạo tight recognition crop.
- Thêm coordinate transform tests.
- Thêm geometry/selection tests.
- Thêm detection debug overlays.

Commit này phải có mode `off`; không chờ đến commit 3 mới thêm CLI/API.

### Commit 2 — Lens word filtering

- Parse Lens word thành model giữ riêng text/separator/geometry.
- Gán selected line ID.
- Filter theo height, band và baseline.
- Giữ punctuation.
- Sửa new-path line grouping.
- Thêm Lens before/after debug overlays.
- Thêm unit tests cho word filtering.

### Commit 3 — Temporal watermark và GUI

- Fuzzy temporal clustering trong zone-relative coordinates.
- Dùng support metadata sau SSIM.
- Persistent word/line removal.
- GUI Balanced/Strict.
- Watermark checkbox.
- Debug directory controls.
- Config persistence.
- Batch queue snapshot.
- Language strings.
- Integration fixtures.
- Benchmark và acceptance report.

Mỗi commit phải độc lập, chạy được test và không để default PaddleOCR path ở trạng thái hỏng.

## 27. File dự kiến thay đổi

Tối thiểu:

```text
CLI/videocr/subtitle_filter.py       # mới
CLI/videocr/video.py
CLI/videocr/utils.py
CLI/videocr/models.py
CLI/videocr/api.py
CLI/videocr_cli.py
VideOCR.py
pyproject.toml
languages/*.json
tests/test_subtitle_filter_geometry.py
tests/test_subtitle_filter_coordinates.py
tests/test_lens_word_filter.py
tests/test_temporal_watermark.py
tests/test_filter_backward_compatibility.py
```

Có thể tách debug renderer thành module riêng nếu `subtitle_filter.py` trở nên quá lớn.

## 28. Non-goals

Không thực hiện:

- Không train subtitle/background classifier.
- Không thay PaddleOCR model.
- Không thay Google Lens CLI.
- Không thêm LLM sửa văn bản.
- Không hard-code blacklist website.
- Không xóa pixels watermark khỏi ảnh.
- Không thay đổi lớn timestamp hoặc SRT merging.
- Không refactor toàn bộ project ngoài phạm vi cần thiết.
- Không cam kết phân biệt hoàn hảo scene text giống hệt subtitle.

## 29. Rủi ro và giới hạn còn lại

1. Scene text ở đúng vùng subtitle, cùng font size và style có thể vẫn được chọn.
2. Watermark nằm cùng baseline và cùng kích thước với subtitle có thể chỉ bị loại nhờ temporal filtering.
3. Watermark animation hoặc text thay đổi liên tục khó cluster.
4. Tight crop quá nhỏ có thể giảm Lens accuracy nếu minimum crop/upscale chưa được tune.
5. Outline score có thể yếu với subtitle màu, karaoke hoặc nền sáng.
6. Full-frame và custom crop cần calibration khác nhau.
7. Temporal filtering dựa trên một OCR observation dài có nguy cơ false positive; phải kết hợp observation count/time bins.
8. Debug rendering và outline morphology có thể làm vượt performance budget nếu không có cap hoặc chạy khi debug tắt.

## 30. Output cần cung cấp sau khi hoàn thành

1. Danh sách file đã sửa.
2. Tóm tắt kiến trúc trước và sau.
3. Giải thích từng option mới và dynamic defaults.
4. Test commands.
5. Kết quả unit và integration tests.
6. Benchmark trước/sau.
7. Debug images trước/sau.
8. Số recognition images và pixel area gửi Lens trước/sau.
9. Một đoạn SRT trước/sau filtering.
10. Các giới hạn còn tồn tại.
11. Patch hoặc pull request với ba commit rõ ràng.

Test command dự kiến:

```powershell
python -m pytest
python -m ruff check .
python -m mypy CLI
```

Manual acceptance command dự kiến:

```powershell
python CLI/videocr_cli.py `
  --video_path .\fixtures\anime-subtitle-noise.mp4 `
  --output .\fixtures\anime-subtitle-noise.filtered.srt `
  --ocr_engine google_lens `
  --lang vi `
  --subtitle-filter-mode strict `
  --watermark-filter true `
  --debug-subtitle-filter-dir .\debug\subtitle-filter
```
