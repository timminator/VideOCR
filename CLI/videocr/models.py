from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import wordninja_enhanced as wordninja
from thefuzz import fuzz

from . import utils


@dataclass
class PredictedText:
    __slots__ = 'bounding_box', 'confidence', 'text'
    bounding_box: list
    confidence: float
    text: str


class PredictedFrames:
    start_index: int  # 0-based index of the frame
    end_index: int
    zone_index: int
    words: list[PredictedText]
    confidence: float  # total confidence of all words
    text: str

    def __init__(self, index: int, pred_data: list[list], conf_threshold: float, zone_index: int):
        self.start_index = index
        self.end_index = index
        self.zone_index = zone_index
        self.lines = []

        all_words = []
        for word_pred in pred_data[0]:
            if len(word_pred) < 2:
                continue
            bounding_box = word_pred[0]
            text = word_pred[1][0]
            conf = word_pred[1][1]

            if conf >= conf_threshold:
                all_words.append(PredictedText(bounding_box, conf, text))

        if not all_words:
            self.confidence = 100 if not pred_data[0] else 0
            self.text = ''
            return

        lines_of_words = []
        for word in all_words:
            placed = False
            for line in lines_of_words:
                if utils.is_on_same_line(word, line[0]):
                    line.append(word)
                    placed = True
                    break
            if not placed:
                lines_of_words.append([word])

        lines_of_words.sort(key=lambda line: min(p[1] for p in line[0].bounding_box))

        for line in lines_of_words:
            line.sort(key=lambda word: word.bounding_box[0][0])

        self.lines = lines_of_words

        if self.lines:
            total_conf = sum(word.confidence for line in self.lines for word in line)
            word_count = sum(len(line) for line in self.lines)
            self.confidence = total_conf / word_count if word_count > 0 else 0
        else:
            self.confidence = 0

        self.text = '\n'.join(' '.join(word.text for word in line) for line in self.lines)

    def is_similar_to(self, other: PredictedFrames, threshold=70) -> bool:
        return fuzz.partial_ratio(self.text, other.text) >= threshold


class PredictedSubtitle:
    frames: list[PredictedFrames]
    zone_index: int
    sim_threshold: int
    text: str
    lang: str
    _language_model: wordninja.LanguageModel | None

    def __init__(self, frames: list[PredictedFrames], zone_index: int, sim_threshold: int, lang: str, language_model: wordninja.LanguageModel | None = None):
        self.frames = [f for f in frames if f.confidence > 0]
        self.frames.sort(key=lambda frame: frame.start_index)
        self.zone_index = zone_index
        self.sim_threshold = sim_threshold
        self.lang = lang
        self._language_model = language_model

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
        return f'{self.index_start} - {self.index_end}. {self.text}'

    def finalize_text(self, post_processing: bool) -> None:
        text_counts = Counter()
        text_confidences = defaultdict(list)

        for frame in self.frames:
            text_counts[frame.text] += 1
            text_confidences[frame.text].append(frame.confidence)

        max_count = max(text_counts.values())
        candidates = [text for text, count in text_counts.items() if count == max_count]

        if len(candidates) == 1:
            final_text = candidates[0]
        else:
            final_text = max(
                candidates,
                key=lambda t: sum(text_confidences[t]) / len(text_confidences[t])
            )

        if post_processing:
            if self.lang in ("en", "fr", "german", "it", "es", "pt"):
                final_text = self._language_model.rejoin(final_text)
            elif self.lang == "ch":
                segments = utils.extract_non_chinese_segments(final_text)
                rebuilt_text = ''

                for typ, seg in segments:
                    if typ == 'non_chinese':
                        rebuilt_text += wordninja.rejoin(seg)
                    else:
                        rebuilt_text += seg

                final_text = rebuilt_text

        self.text = final_text
