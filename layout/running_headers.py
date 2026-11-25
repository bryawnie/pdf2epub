"""Eliminación de encabezados y pies de página repetidos y números de página."""
import re
from collections import Counter

from .models import Line
from .page_layout import PageLayout
from common import PAGE_NUMBER_RE, STANDALONE_PAGE_LABEL_RE

MIN_PAGES_FOR_REPETITION_CHECK = 3
FOOTER_ZONE_START = 0.92
MAX_RUNNING_HEADER_CHARS = 90
MAX_RUNNING_HEADER_WORDS = 12


def _normalize_for_repetition(text: str) -> str:
    """Los números de página varían entre páginas: se reemplazan por '#' para comparar."""
    return re.sub(r"\d+", "#", text.strip().lower())


def _is_in_margin(line: Line, layout: PageLayout) -> bool:
    return line.top < layout.header_limit or line.bottom > layout.origin_y + FOOTER_ZONE_START * layout.height


def _is_page_numbered_running_line(line: Line, layout: PageLayout, body_size: float) -> bool:
    """Línea en el extremo de la página con un número al inicio o al final (p. ej. "12  Smith et al.")."""
    words = line.text.split()
    has_page_number = bool(words) and bool(PAGE_NUMBER_RE.fullmatch(words[0]) or PAGE_NUMBER_RE.fullmatch(words[-1]))
    topmost = line is min(layout.lines, key=lambda other: other.top)
    bottommost = line is max(layout.lines, key=lambda other: other.bottom)
    return (has_page_number and (topmost or bottommost)
            and len(line.text) < MAX_RUNNING_HEADER_CHARS and line.size <= body_size * 1.05
            and len(words) <= MAX_RUNNING_HEADER_WORDS)


def remove_running_headers(layouts: list[PageLayout], body_size: float):
    """Quita de cada página las líneas de margen que se repiten o son solo un número de página."""
    if len(layouts) < MIN_PAGES_FOR_REPETITION_CHECK:
        return

    margin_line_counts = Counter()
    for layout in layouts:
        for line in layout.lines:
            if _is_in_margin(line, layout):
                margin_line_counts[_normalize_for_repetition(line.text)] += 1
    min_repetitions = max(2, 0.4 * len(layouts))

    for layout in layouts:
        kept_lines = []
        for line in layout.lines:
            in_margin = _is_in_margin(line, layout)
            if in_margin and _is_page_numbered_running_line(line, layout, body_size):
                continue
            is_repeated = margin_line_counts[_normalize_for_repetition(line.text)] >= min_repetitions
            is_page_label = bool(STANDALONE_PAGE_LABEL_RE.fullmatch(line.text.strip()))
            if in_margin and (is_repeated or is_page_label):
                continue
            kept_lines.append(line)
        layout.lines = kept_lines
