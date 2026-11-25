"""Utilidades sobre caracteres de pdfplumber: texto plano, palabras y detección de matemática.

Un "carácter" (`char`) es el diccionario que entrega pdfplumber, con claves como
`text`, `fontname`, `size`, `x0`, `x1`, `top` y `bottom`.
"""
from .patterns import (BIG_OPERATOR_FONT_RE, LIGATURES, MATH_CHARS, MATH_FONT_RE)

# Un hueco horizontal mayor a esta fracción del tamaño de letra separa dos palabras.
WORD_GAP_RATIO = 0.12


def is_math_font(font_name: str) -> bool:
    return bool(MATH_FONT_RE.search(font_name or ""))


def is_big_operator_font(font_name: str) -> bool:
    return bool(BIG_OPERATOR_FONT_RE.search(font_name or ""))


def replace_ligatures(text: str) -> str:
    for ligature, letters in LIGATURES.items():
        text = text.replace(ligature, letters)
    return text


def is_math_char(char) -> bool:
    """¿El carácter pertenece a una fuente matemática, es un símbolo matemático o un glifo sin Unicode?"""
    text = char["text"]
    return is_math_font(char["fontname"]) or text in MATH_CHARS or text.startswith("(cid:")


def contains_math(chars) -> bool:
    return any(is_math_char(char) for char in chars)


def math_char_ratio(chars) -> float:
    """Fracción de caracteres visibles que son matemáticos."""
    visible = [char for char in chars if char["text"].strip()]
    if not visible:
        return 0
    return sum(is_math_char(char) for char in visible) / len(visible)


def chars_to_plain_text(chars) -> str:
    """Une los caracteres (ordenados por x) insertando espacios donde hay huecos."""
    pieces, previous = [], None
    for char in chars:
        text = char["text"]
        if previous is not None:
            gap = char["x0"] - previous["x1"]
            needs_space = gap > WORD_GAP_RATIO * min(char["size"], previous["size"])
            if needs_space and not text.isspace() and pieces and not pieces[-1].endswith(" "):
                pieces.append(" ")
        pieces.append(text)
        previous = char
    return replace_ligatures("".join(pieces)).strip()


def split_into_words(chars, compare_with_previous_size: bool = True):
    """Agrupa caracteres consecutivos en palabras según los huecos horizontales.

    Con `compare_with_previous_size` el umbral usa el menor tamaño entre el carácter y el
    anterior; si no, solo el tamaño del carácter actual.
    """
    words, current_word, previous = [], [], None
    for char in chars:
        if previous is not None:
            reference_size = min(char["size"], previous["size"]) if compare_with_previous_size else char["size"]
            if char["x0"] - previous["x1"] > WORD_GAP_RATIO * reference_size:
                words.append(current_word)
                current_word = []
        current_word.append(char)
        previous = char
    if current_word:
        words.append(current_word)
    return words
