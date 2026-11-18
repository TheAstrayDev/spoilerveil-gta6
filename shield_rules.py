from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parent
DEFAULTS = json.loads(
    (ROOT / "browser" / "defaults.js").read_text(encoding="utf-8")
    .removeprefix("globalThis.shieldDefaults = ").strip().removesuffix(";")
)
LOOKALIKES = str.maketrans("авекмнорстухіг", "abekmhopctyxig")


def normalized(text):
    clean = (
        ch for ch in unicodedata.normalize("NFKD", text).lower()
        if unicodedata.category(ch)[0] != "M" and unicodedata.category(ch) != "Cf"
    )
    return " ".join(re.findall(r"[^\W_]+", "".join(clean).translate(LOOKALIKES)))


def custom_terms(input_text):
    return list(dict.fromkeys(
        term for line in input_text.splitlines()
        if 2 <= len(term := normalized(line[:240])) <= 150
    ))[:250]


class Filter:
    def __init__(self, extra="", related=True):
        patterns = set()
        for alias in DEFAULTS["aliases"]:
            compact = normalized(alias).replace(" ", "")
            patterns.add(" *".join(map(re.escape, compact)))
        extras = custom_terms(extra)
        if related:
            extras.extend(map(normalized, DEFAULTS["terms"]))
        patterns.update(map(re.escape, extras))
        self.pattern = re.compile(r"(?:^| )(?:"
                                  + "|".join(sorted(patterns, key=len, reverse=True))
                                  + r")(?=$| )")

    def matches(self, text):
        return bool(self.pattern.search(normalized(text)))


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def size(self):
        return self.right - self.left, self.bottom - self.top

    def move(self, x, y):
        return Box(self.left+x, self.top+y, self.right+x, self.bottom+y)

    def padded(self, x, y):
        return Box(self.left-x, self.top-y, self.right+x, self.bottom+y)

    def intersects(self, other):
        return (self.left < other.right and other.left < self.right
                and self.top < other.bottom and other.top < self.bottom)

    def intersection(self, other):
        if self.intersects(other):
            return Box(max(self.left, other.left), max(self.top, other.top),
                       min(self.right, other.right), min(self.bottom, other.bottom))
        return None

    def union(self, other):
        return Box(min(self.left, other.left), min(self.top, other.top),
                   max(self.right, other.right), max(self.bottom, other.bottom))

    def tuple(self):
        return self.left, self.top, self.right, self.bottom


@dataclass(frozen=True)
class Line:
    text: str
    bounds: Box


def masked_lines(lines, matcher):
    masks = []
    for index, line in enumerate(lines):
        bounds = line.bounds
        height = max(9, bounds.bottom - bounds.top)
        matches = matcher.matches(line.text)
        if not matches and index + 1 < len(lines):
            next_line = lines[index + 1]
            next_box = next_line.bounds
            vertical_gap = next_box.top - bounds.bottom
            same_column = (abs(next_box.left - bounds.left) < height*1.7
                           or abs(next_box.right - bounds.right) < height*1.7)
            if (same_column and -height*.24 <= vertical_gap <= height*.65
                    and matcher.matches(line.text + " " + next_line.text)):
                matches = True
                bounds = bounds.union(next_box)
        if matches:
            masks.append(bounds.padded(max(14, height*2), max(11, height*2)))
    return masks
