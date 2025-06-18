import datetime
import os
import yaml
from importlib.metadata import version
from packaging import version as version_parser

PADDLEOCR_FORMAT_CHANGE_VERSION = "3.0.2"

# convert time string to frame index
def get_frame_index(time_str: str, fps: float):
    t = time_str.split(':')
    t = list(map(float, t))
    if len(t) == 3:
        td = datetime.timedelta(hours=t[0], minutes=t[1], seconds=t[2])
    elif len(t) == 2:
        td = datetime.timedelta(minutes=t[0], seconds=t[1])
    else:
        raise ValueError(
            'Time data "{}" does not match format "%H:%M:%S"'.format(time_str))
    index = int(td.total_seconds() * fps)
    return index


# convert frame index into SRT timestamp
def get_srt_timestamp(frame_index: int, fps: float):
    td = datetime.timedelta(seconds=frame_index / fps)
    ms = td.microseconds // 1000
    m, s = divmod(td.seconds, 60)
    h, m = divmod(m, 60)
    return '{:02d}:{:02d}:{:02d},{:03d}'.format(h, m, s, ms)


# check if format conversion is required
def needs_conversion():
    current_version = version("paddleocr")
    return version_parser.parse(current_version) >= version_parser.parse(PADDLEOCR_FORMAT_CHANGE_VERSION)


# convert returned format from paddleocr to old format
def convert_pred_data_to_old_format(new_pred_data):
    old_format = []

    for item in new_pred_data:
        result = []

        rec_texts = item.get('rec_texts', [])
        rec_scores = item.get('rec_scores', [])
        rec_polys = item.get('rec_polys', [])

        for text, score, poly in zip(rec_texts, rec_scores, rec_polys):
            box = [[float(x), float(y)] for x, y in poly.tolist()]
            result.append([box, (text, score)])

        old_format.append(result)

    return old_format


# reads the model name from inference.yml inside the given model directory.
def get_model_name_from_dir(model_dir):
    if model_dir == None:
        return None

    yml_path = os.path.join(model_dir, "inference.yml")
    if not os.path.exists(yml_path):
        return None

    try:
        with open(yml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("Global", {}).get("model_name")
    except Exception as e:
        print(f"Warning: Failed to read model name from {yml_path}: {e}")
        return None
