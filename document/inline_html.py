"""Convierte una línea de texto en HTML inline (negritas, cursivas, sub/superíndices, imágenes)."""
import html
import re
import statistics
from typing import NamedTuple

from common import (BLACKBOARD_FONT_RE, BLACKBOARD_LETTERS, BOLD_FONT_RE, CALLIGRAPHIC_FONT_RE,
                    CALLIGRAPHIC_LETTERS, ITALIC_FONT_RE, MONOSPACE_FONT_RE, chars_to_plain_text,
                    is_big_operator_font, is_math_char, is_math_font, replace_ligatures, split_into_words)
from layout import Line, PageLayout
from rendering import ImageRenderer

# Modos de `--inline-math`
INLINE_MATH_AUTO = "auto"     # texto, salvo cuando no se puede representar
INLINE_MATH_TEXT = "text"     # siempre texto
INLINE_MATH_IMAGE = "image"   # siempre imagen

BASELINE_OFFSET = 0.22        # la línea base está ≈22 % del tamaño por encima del borde inferior
SCRIPT_SIZE_RATIO = 0.85      # un carácter de menos de este tamaño relativo es sub/superíndice
SCRIPT_SHIFT_RATIO = 0.08     # desplazamiento vertical mínimo para considerarlo sub/superíndice
TRAILING_PUNCTUATION = ".,;:"
REPLACEMENT_CHAR = "�"


class Segment(NamedTuple):
    """Fragmento de una línea: HTML ya generado (`is_html`) o caracteres por serializar."""
    is_html: bool
    content: object   # str si is_html, lista de caracteres si no


def needs_image(char) -> bool:
    """¿El carácter no se puede representar como texto Unicode?"""
    text = char["text"]
    if map_char_to_unicode(char) is None or any(0xE000 <= ord(letter) <= 0xF8FF for letter in text):
        return True
    return text.startswith("(cid:") or text == "√" or is_big_operator_font(char["fontname"]) or text == REPLACEMENT_CHAR


def map_char_to_unicode(char):
    """Devuelve el texto Unicode del carácter, o None si no tiene buena representación."""
    text = replace_ligatures(char["text"])
    font_name = char["fontname"]
    if len(text) == 1 and "A" <= text <= "Z":
        if BLACKBOARD_FONT_RE.search(font_name):
            return BLACKBOARD_LETTERS.get(text)
        if CALLIGRAPHIC_FONT_RE.search(font_name):
            return CALLIGRAPHIC_LETTERS.get(text)
    return text


def _text_style(char):
    """(negrita, cursiva, monoespaciada, posición sub/sup) según la fuente del carácter."""
    font_name = char["fontname"]
    is_bold = bool(BOLD_FONT_RE.search(font_name))
    is_italic = bool(ITALIC_FONT_RE.search(font_name))
    is_monospace = bool(MONOSPACE_FONT_RE.search(font_name))
    if is_math_font(font_name) and len(char["text"]) == 1 and char["text"].isalpha():
        # variables en cursiva, salvo en fuentes de símbolos/blackboard
        is_italic = not ("MSBM" in font_name or "CMSY" in font_name)
    return is_bold, is_italic, is_monospace


def _estimate_baseline(line: Line) -> float:
    main_size_chars = [char["bottom"] - BASELINE_OFFSET * char["size"]
                       for char in line.chars if abs(char["size"] - line.size) < 0.6]
    if main_size_chars:
        return statistics.median(main_size_chars)
    return statistics.median(char["bottom"] for char in line.chars)


def _word_is_math(word) -> bool:
    return any(is_math_char(char) for char in word)


def line_to_html(line: Line, layout: PageLayout, renderer: ImageRenderer, inline_math_mode: str) -> str:
    baseline = _estimate_baseline(line)
    words = split_into_words(line.chars)
    segments = _split_into_segments(line, words, baseline, layout, renderer, inline_math_mode)
    return _serialize_segments(segments, line.size, baseline)


def _split_into_segments(line, words, baseline, layout, renderer, inline_math_mode) -> list[Segment]:
    """Palabras de texto quedan como caracteres; grupos de matemática que no se pueden
    escribir como texto se reemplazan por una imagen."""
    segments: list[Segment] = []
    index = 0
    while index < len(words):
        word = words[index]
        if inline_math_mode != INLINE_MATH_TEXT and _word_is_math(word):
            end = index
            math_group = []
            while end < len(words) and (_word_is_math(words[end]) or
                                        all(not char["text"].isalpha() for char in words[end])):
                math_group.append(words[end])
                end += 1
            image_segments = _render_math_group_as_image(
                line, math_group, baseline, layout, renderer, inline_math_mode)
            if image_segments:
                segments += image_segments
                index = end
                continue
        segments.append(Segment(False, word))
        index += 1
    return segments


def _render_math_group_as_image(line, math_group, baseline, layout, renderer, inline_math_mode):
    """Recorta un grupo de palabras matemáticas como imagen inline.
    Devuelve los segmentos resultantes, o None si el grupo se queda como texto."""
    chars = [char for word in math_group for char in word]
    if inline_math_mode != INLINE_MATH_IMAGE and not any(needs_image(char) for char in chars):
        return None

    # la puntuación final de texto normal se queda como texto
    trailing_punctuation = []
    while chars and chars[-1]["text"] in TRAILING_PUNCTUATION and not is_math_font(chars[-1]["fontname"]):
        trailing_punctuation.insert(0, chars.pop())
    if not chars:
        return None

    size = line.size
    core_top, core_bottom = line.core_extent
    top = max(min(min(char["top"] for char in chars), core_top), core_top - 0.6 * size) - 1.0
    bottom = min(max(max(char["bottom"] for char in chars), core_bottom), core_bottom + 0.45 * size) + 0.4
    crop = renderer.crop(layout, min(char["x0"] for char in chars), top, max(char["x1"] for char in chars), bottom,
                         "inl", pad=0.6, trim=False, gray=True, keep=line.chars)
    if not crop:
        return None

    # alinear la línea base del recorte con la del texto
    drop_below_baseline = (bottom + 0.6) - baseline
    alt_text = html.escape(chars_to_plain_text(chars))
    image_html = (f'<img class="im" src="../images/{crop.filename}" alt="{alt_text}" '
                  f'style="height:{crop.height_pt / size:.3f}em;vertical-align:-{drop_below_baseline / size:.3f}em"/>')
    return [Segment(True, image_html)] + [Segment(False, [char]) for char in trailing_punctuation]


def _serialize_segments(segments: list[Segment], line_size: float, baseline: float) -> str:
    parts = []
    for position, segment in enumerate(segments):
        if position > 0:
            parts.append(" ")
        if segment.is_html:
            parts.append(segment.content)
        else:
            parts += _chars_to_html_runs(segment.content, line_size, baseline)
    result = "".join(parts)
    # fusionar etiquetas contiguas idénticas
    return re.sub(r"</i><i>|</b><b>|</sup><sup>|</sub><sub>", "", result)


def _script_position(char, line_size: float, baseline: float) -> str:
    """'sup', 'sub' o '' según la posición vertical de un carácter pequeño respecto a la línea base."""
    if char["size"] >= SCRIPT_SIZE_RATIO * line_size:
        return ""
    char_baseline = char["bottom"] - BASELINE_OFFSET * char["size"]
    if char_baseline < baseline - SCRIPT_SHIFT_RATIO * line_size:
        return "sup"
    if char_baseline > baseline + SCRIPT_SHIFT_RATIO * line_size:
        return "sub"
    return ""


def _chars_to_html_runs(chars, line_size: float, baseline: float) -> list[str]:
    """Agrupa caracteres con el mismo estilo y los envuelve en <b>, <i>, <code>, <sub>, <sup>."""
    runs = []   # [(estilo, [textos])]
    for char in chars:
        style = (*_text_style(char), _script_position(char, line_size, baseline))
        text = map_char_to_unicode(char) or char["text"]
        if text.startswith("(cid:"):
            text = REPLACEMENT_CHAR
        if runs and runs[-1][0] == style:
            runs[-1][1].append(text)
        else:
            runs.append((style, [text]))

    rendered = []
    for (is_bold, is_italic, is_monospace, script), texts in runs:
        run_html = html.escape("".join(texts))
        if is_monospace:
            run_html = f"<code>{run_html}</code>"
        if is_italic:
            run_html = f"<i>{run_html}</i>"
        if is_bold:
            run_html = f"<b>{run_html}</b>"
        if script:
            run_html = f"<{script}>{run_html}</{script}>"
        rendered.append(run_html)
    return rendered
