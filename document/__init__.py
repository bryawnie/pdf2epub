"""Construcción del documento: bloques de contenido (títulos, párrafos, ecuaciones, figuras)."""
from .block_builder import BlockBuilder
from .blocks import Block, Equation, Figure, Heading, Paragraph
from .headings import compute_heading_levels, detect_body_font_size
from .inline_html import INLINE_MATH_AUTO, INLINE_MATH_IMAGE, INLINE_MATH_TEXT
