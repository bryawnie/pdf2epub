"""Detección del tamaño de letra del cuerpo y de los niveles de título."""
from collections import Counter

from common import BOLD_FONT_RE
from layout import TEXT_LINE, Line, PageLayout

DEFAULT_BODY_SIZE = 10.0
HEADING_SIZE_RATIO = 1.12         # un título es ≥12 % más grande que el cuerpo...
MAX_HEADING_CHARS = 120
MAX_BOLD_HEADING_CHARS = 80       # ...o una línea corta en negrita
MAX_HEADING_LEVEL = 4


def detect_body_font_size(layouts: list[PageLayout]) -> float:
    """El tamaño de letra más frecuente en todo el documento."""
    size_counts = Counter()
    for layout in layouts:
        for char in layout.chars:
            size_counts[round(char["size"], 1)] += 1
    return size_counts.most_common(1)[0][0] if size_counts else DEFAULT_BODY_SIZE


def is_mostly_bold(line: Line) -> bool:
    visible_chars = [char for char in line.chars if char["text"].strip()]
    if not visible_chars:
        return False
    bold_count = sum(bool(BOLD_FONT_RE.search(char["fontname"])) for char in visible_chars)
    return bold_count / len(visible_chars) > 0.8


def compute_heading_levels(layouts: list[PageLayout], body_size: float) -> dict[int, int]:
    """Asigna nivel 1..4 a cada tamaño de letra de título (el más grande es el nivel más alto)."""
    heading_sizes = set()
    for layout in layouts:
        for line in layout.lines:
            if line.kind != TEXT_LINE or len(line.text) >= MAX_HEADING_CHARS:
                continue
            is_large = line.size >= body_size * HEADING_SIZE_RATIO
            is_short_and_bold = is_mostly_bold(line) and len(line.text) < MAX_BOLD_HEADING_CHARS
            if is_large or is_short_and_bold:
                heading_sizes.add(round(line.size))

    sizes_largest_first = sorted(heading_sizes, reverse=True)
    first_level = 1
    if sizes_largest_first and sizes_largest_first[0] < body_size * 1.4:
        first_level = 2     # sin título grande: empezar en h2
    return {size: min(rank + first_level, MAX_HEADING_LEVEL)
            for rank, size in enumerate(sizes_largest_first)}
