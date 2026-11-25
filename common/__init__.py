"""Constantes y utilidades de bajo nivel sobre fuentes y caracteres de pdfplumber."""
from .patterns import (BIG_OPERATOR_FONT_RE, BLACKBOARD_FONT_RE, BLACKBOARD_LETTERS, BOLD_FONT_RE, BULLET_RE,
                       CALLIGRAPHIC_FONT_RE, CALLIGRAPHIC_LETTERS, CAPTION_RE, EQUATION_NUMBER_RE,
                       ITALIC_FONT_RE, MONOSPACE_FONT_RE, PAGE_NUMBER_RE, STANDALONE_PAGE_LABEL_RE,
                       TOC_LEADER_RE)
from .text_utils import (chars_to_plain_text, contains_math, is_big_operator_font, is_math_char, is_math_font,
                         math_char_ratio, replace_ligatures, split_into_words)
