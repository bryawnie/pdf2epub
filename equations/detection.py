"""Detección de ecuaciones en display y agrupación en regiones recortables."""
import re

from common import (CAPTION_RE, EQUATION_NUMBER_RE, contains_math, is_big_operator_font, is_math_font,
                    math_char_ratio)
from layout import (EQUATION_REGION, FULL_WIDTH, MATH_LINE, TEXT_LINE, Line, PageLayout, Region,
                    overlap_length)


def classify_display_math(layout: PageLayout, body_size: float):
    """Marca como `MATH_LINE` las líneas que forman parte de una ecuación en display."""
    for line in layout.lines:
        if line.kind != TEXT_LINE or not contains_math(line.chars) or CAPTION_RE.match(line.text):
            continue
        column_left, column_right = layout.column_bounds.get(line.column) or layout.column_bounds.get(FULL_WIDTH)
        left_margin, right_margin = line.x0 - column_left, column_right - line.x1
        math_ratio = math_char_ratio(line.chars)
        is_centered = (left_margin > 1.5 * body_size and right_margin > 1.0 * body_size
                       and abs(left_margin - right_margin) < 0.45 * layout.column_width(line.column) + 2 * body_size)
        has_equation_number = _has_detached_equation_number(line, body_size)
        has_big_operator = any(is_big_operator_font(char["fontname"]) for char in line.chars)

        non_math_text = "".join(char["text"] for char in line.chars if not is_math_font(char["fontname"]))
        looks_like_prose = len(re.findall(r"[A-Za-z]{4,}", non_math_text)) >= 6 and math_ratio < 0.35
        if looks_like_prose and not has_equation_number:
            continue

        mostly_math_and_indented = math_ratio > 0.6 and (left_margin > body_size or right_margin > body_size)
        if (has_equation_number
                or (is_centered and (math_ratio > 0.15 or has_big_operator))
                or mostly_math_and_indented):
            line.kind = MATH_LINE


def _has_detached_equation_number(line: Line, body_size: float) -> bool:
    """¿La línea termina en un número de ecuación "(3)" separado del resto por un hueco amplio?"""
    match = EQUATION_NUMBER_RE.search(line.text)
    if not match:
        return False
    number_length = len(match.group(0).replace(" ", ""))
    number_chars = [char for char in line.chars if char["text"].strip()][-number_length:]
    chars_before_number = [char for char in line.chars
                           if char["x1"] <= number_chars[0]["x0"] + 0.1 and char not in number_chars]
    if not chars_before_number:
        return False
    gap = number_chars[0]["x0"] - max(char["x1"] for char in chars_before_number)
    return gap > 2 * body_size


def merge_math_regions(layout: PageLayout, ordered_lines, body_size) -> list[Region]:
    """Une líneas matemáticas consecutivas (fracciones, align) en una región de ecuación."""
    regions: list[Region] = []
    current = None
    for line in ordered_lines:
        if line.kind != MATH_LINE:
            current = None
            continue
        continues_current = (current and current.column == line.column
                             and line.top - current.bottom < 1.3 * body_size
                             and overlap_length(current.x0, current.x1, line.x0, line.x1) > -1)
        if continues_current:
            current.expand_to_include(line.x0, line.top, line.x1, line.bottom)
            current.lines.append(line)
        else:
            current = Region(EQUATION_REGION, layout.idx, line.x0, line.top, line.x1, line.bottom,
                             line.column, [line])
            regions.append(current)

    _absorb_text_inside_equations(layout, regions)
    _include_fraction_bars_and_radicals(layout, regions)
    return regions


def _absorb_text_inside_equations(layout: PageLayout, regions: list[Region]):
    """Líneas cortas de texto que quedaron dentro de la caja de una ecuación (p. ej. "and", "if")."""
    changed = True
    while changed:
        changed = False
        for region in regions:
            for line in layout.lines:
                if line.kind != TEXT_LINE or line.column != region.column:
                    continue
                line_height = max(line.bottom - line.top, 0.1)
                fully_inside = line.top >= region.top - 1 and line.bottom <= region.bottom + 1
                vertical_overlap = overlap_length(line.top, line.bottom, region.top, region.bottom) / line_height
                if fully_inside or (vertical_overlap > 0.35 and contains_math(line.chars)):
                    line.kind = MATH_LINE
                    region.lines.append(line)
                    region.expand_to_include(line.x0, line.top, line.x1, line.bottom)
                    changed = True


def _include_fraction_bars_and_radicals(layout: PageLayout, regions: list[Region]):
    """Incluye trazos (barras de fracción, raíces) que tocan la región."""
    for region in regions:
        for stroke in layout.page.lines + layout.page.rects:
            is_thin = stroke["bottom"] - stroke["top"] < 2
            if (is_thin and region.x0 - 3 <= stroke["x0"] and stroke["x1"] <= region.x1 + 3
                    and region.top - 4 <= stroke["top"] <= region.bottom + 4):
                region.expand_to_include(stroke["x0"], stroke["top"], stroke["x1"], stroke["bottom"])
