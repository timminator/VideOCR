from __future__ import annotations
from typing import List
from dataclasses import dataclass
from thefuzz import fuzz

@dataclass
class PredictedText:
    __slots__ = 'bounding_box', 'confidence', 'text'
    bounding_box: list
    confidence: float
    text: str


class PredictedFrames:
    start_index: int  # 0-based index of the frame
    end_index: int
    words: List[PredictedText]
    confidence: float  # total confidence of all words
    text: str

    def __init__(self, index: int, pred_data: list[list], conf_threshold: float):
        # Fix for PaddleOCR versions greater than 2.7.0.2
        if not pred_data or pred_data[0] is None:
            pred_data = [[]]

        self.start_index = index
        self.end_index = index
        self.lines = []

        total_conf = 0
        word_count = 0
        current_line = []
        current_line_max_y = None
        for l in pred_data[0]:
            if len(l) < 2:
                continue
            bounding_box = l[0]
            text = l[1][0]
            conf = l[1][1]

            # word predictions with low confidence will be filtered out
            if conf >= conf_threshold:
                total_conf += conf
                word_count += 1

                # add word to current line or create a new line
                max_y = max(bounding_box[0][1], bounding_box[1][1], bounding_box[2][1], bounding_box[3][1])

                if current_line_max_y is None:
                    current_line_max_y = max_y
                    current_line.append(PredictedText(bounding_box, conf, text))
                else:
                    min_y = min(bounding_box[0][1], bounding_box[1][1], bounding_box[2][1], bounding_box[3][1])
                    height = max_y - min_y
                    height_overlap_allowance = height * 0.1
                    if min_y >= current_line_max_y - height_overlap_allowance: # new line
                        self.lines.append(current_line)
                        current_line = [PredictedText(bounding_box, conf, text)]
                        current_line_max_y = max_y
                    else:
                        current_line.append(PredictedText(bounding_box, conf, text))
                        current_line_max_y = max(current_line_max_y, max_y)

        if len(current_line) > 0:
            self.lines.append(current_line)
        if self.lines:
            self.confidence = total_conf/word_count
            for line in self.lines:
                line.sort(key=lambda word: word.bounding_box[0][0])
        elif len(pred_data[0]) == 0:
            self.confidence = 100
        else:
            self.confidence = 0
        self.text = '\n'.join(' '.join(word.text for word in line) for line in self.lines)

    def is_similar_to(self, other: PredictedFrames, threshold=70) -> bool:
        return fuzz.partial_ratio(self.text, other.text) >= threshold


class PredictedSubtitle:
    frames: List[PredictedFrames]
    sim_threshold: int
    text: str

    def __init__(self, frames: List[PredictedFrames], sim_threshold: int):
        self.frames = [f for f in frames if f.confidence > 0]
        self.frames.sort(key=lambda frame: frame.start_index)
        self.sim_threshold = sim_threshold

        if self.frames:
            self.text = max(self.frames, key=lambda f: f.confidence).text
        else:
            self.text = ''

    @property
    def index_start(self) -> int:
        if self.frames:
            return self.frames[0].start_index
        return 0

    @property
    def index_end(self) -> int:
        if self.frames:
            return self.frames[-1].end_index
        return 0

    def is_similar_to(self, other: PredictedSubtitle) -> bool:
        return fuzz.partial_ratio(self.text.replace(' ', ''), other.text.replace(' ', '')) >= self.sim_threshold

    def __repr__(self):
        return '{} - {}. {}'.format(self.index_start, self.index_end, self.text)
