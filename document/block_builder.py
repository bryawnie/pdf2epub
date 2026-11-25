"""Recorre las páginas en orden de lectura y arma la lista de bloques del documento."""
import html
import re

from .blocks import Block, Equation, Figure, Heading, Paragraph
from .headings import (HEADING_SIZE_RATIO, MAX_BOLD_HEADING_CHARS, MAX_HEADING_CHARS, is_mostly_bold)
from .inline_html import line_to_html, needs_image
from common import BULLET_RE, CAPTION_RE, TOC_LEADER_RE, is_big_operator_font
from layout import EQUATION_REGION, FULL_WIDTH, Line, PageLayout, Region
from rendering import ImageRenderer
from .reading_order import order_with_equation_regions

SMALL_TEXT_RATIO = 0.9            # texto más chico que esto (respecto al cuerpo) va como nota
MIN_FIGURE_WIDTH_PERCENT = 35
SINGLE_COLUMN_FIGURE_BOOST = 1.6  # figuras de una columna se muestran más grandes en proporción
TOC_INDENT_STEP = 1.5             # sangría (en tamaños de cuerpo) por nivel de índice
MAX_TOC_LEVEL = 3


class BlockBuilder:
    def __init__(self, layouts: list[PageLayout], renderer: ImageRenderer, body_size: float,
                 heading_levels: dict[int, int], inline_math_mode: str):
        self.layouts_by_page = {layout.idx: layout for layout in layouts}
        self.renderer = renderer
        self.body_size = body_size
        self.heading_levels = heading_levels
        self.inline_math_mode = inline_math_mode

        self.blocks: list[Block] = []
        self._open_paragraph: Paragraph | None = None   # párrafo que aún recibe líneas
        self._previous_line: Line | None = None

    # ------------------------------------------------------------------ #
    # Páginas
    # ------------------------------------------------------------------ #
    def add_page(self, layout: PageLayout):
        if not layout.chars:
            self._add_full_page_image(layout)
            return
        for item in order_with_equation_regions(layout, self.body_size):
            if isinstance(item, Region):
                self._add_region(layout, item)
            else:
                self._add_text_line(layout, item)

    def finish(self) -> list[Block]:
        self._close_paragraph()
        return self.blocks

    def _add_full_page_image(self, layout: PageLayout):
        """Página escaneada o vacía: se incrusta completa como imagen."""
        self._close_paragraph()
        crop = self.renderer.crop(layout, layout.origin_x, layout.origin_y,
                                  layout.origin_x + layout.width, layout.origin_y + layout.height,
                                  "page", pad=0, trim=True)
        if crop:
            self.blocks.append(Figure(crop.filename, 100, "page"))

    def _close_paragraph(self):
        if self._open_paragraph and self._open_paragraph.html:
            self.blocks.append(self._open_paragraph)
        self._open_paragraph = None

    # ------------------------------------------------------------------ #
    # Regiones: ecuaciones, figuras y tablas
    # ------------------------------------------------------------------ #
    def _add_region(self, layout: PageLayout, region: Region):
        self._close_paragraph()
        if region.kind == EQUATION_REGION:
            if self._is_stray_math_fragment(region):
                return      # no cuenta como contenido: se conserva la línea previa
            self._add_equation(layout, region)
        else:
            self._add_figure(layout, region)
        self._previous_line = None

    @staticmethod
    def _is_stray_math_fragment(region: Region) -> bool:
        """Fragmento suelto de un radical/delimitador que ya quedó incluido en el texto."""
        visible_chars = [char for line in region.lines for char in line.chars if char["text"].strip()]
        return len(visible_chars) <= 3 and all(is_big_operator_font(char["fontname"]) or needs_image(char)
                                               for char in visible_chars)

    def _add_equation(self, layout: PageLayout, region: Region):
        equation_chars = [char for line in region.lines for char in line.chars]
        crop = self.renderer.crop(layout, region.x0, region.top, region.x1, region.bottom, "eq",
                                  pad=2.5, gray=True, keep=equation_chars)
        if crop:
            alt_text = " ".join(line.text for line in sorted(region.lines, key=lambda line: line.top))
            self.blocks.append(Equation(crop.filename, crop.width_pt / self.body_size, alt_text))
        # el texto que sigue a la ecuación continúa el mismo párrafo
        self._open_paragraph = Paragraph("", "cont", continues_after_equation=True)

    def _add_figure(self, layout: PageLayout, region: Region):
        crop = self.renderer.crop(layout, region.x0, region.top, region.x1, region.bottom, region.kind, pad=1.5)
        if crop:
            boost = SINGLE_COLUMN_FIGURE_BOOST if region.column != FULL_WIDTH else 1.0
            width_percent = 100 * crop.width_pt / layout.column_width(FULL_WIDTH) * boost
            width_percent = min(100, max(MIN_FIGURE_WIDTH_PERCENT, width_percent))
            self.blocks.append(Figure(crop.filename, width_percent, region.kind))

    # ------------------------------------------------------------------ #
    # Líneas de texto
    # ------------------------------------------------------------------ #
    def _add_text_line(self, layout: PageLayout, line: Line):
        text = line.text
        if not text:
            return
        column_bounds = layout.column_bounds.get(line.column) or layout.column_bounds.get(FULL_WIDTH)
        indent = line.x0 - column_bounds[0]

        if self._is_heading(line):
            self._add_heading(layout, line)
            self._previous_line = line
            return

        starts_new_paragraph = self._starts_new_paragraph(line, indent, column_bounds)
        if BULLET_RE.match(text) or CAPTION_RE.match(text):
            starts_new_paragraph = True

        if TOC_LEADER_RE.search(text):
            self._add_toc_entry(line, indent)
            return

        paragraph = self._open_paragraph
        continues_after_equation = (
            starts_new_paragraph and paragraph is not None and paragraph.continues_after_equation
            and not paragraph.html and indent < 0.8 * self.body_size and not CAPTION_RE.match(text))
        if continues_after_equation:
            pass    # sigue el párrafo abierto tras una ecuación, sin sangría
        elif starts_new_paragraph:
            self._close_paragraph()
            self._open_paragraph = Paragraph("", self._paragraph_css_class(line, indent))

        self._append_to_open_paragraph(layout, line)
        self._previous_line = line

    def _paragraph_css_class(self, line: Line, indent: float) -> str:
        if CAPTION_RE.match(line.text):
            return "caption"
        if line.size < self.body_size * SMALL_TEXT_RATIO:
            return "small"
        if indent < 0.5 * self.body_size:
            return "noindent"
        return ""

    def _append_to_open_paragraph(self, layout: PageLayout, line: Line):
        paragraph = self._open_paragraph
        line_html = line_to_html(line, layout, self.renderer, self.inline_math_mode)
        if paragraph.html:
            ends_with_hyphenated_word = re.search(r"[a-z]-$", paragraph.html) and re.match(r"^[a-z]", line.text)
            if ends_with_hyphenated_word:
                paragraph.html = paragraph.html[:-1]      # une la palabra cortada con guion
            else:
                paragraph.html += " "
        paragraph.html += line_html

    def _starts_new_paragraph(self, line: Line, indent: float, column_bounds) -> bool:
        paragraph = self._open_paragraph
        previous = self._previous_line
        no_open_text = paragraph is None or not paragraph.html
        if no_open_text:
            return True
        if previous is None:
            return indent > 0.8 * self.body_size

        same_flow = previous.page_index == line.page_index and previous.column == line.column
        previous_bounds = self.layouts_by_page[previous.page_index].column_bounds.get(previous.column) or column_bounds
        if previous.x1 < previous_bounds[1] - 2.5 * self.body_size:
            return True                 # la línea anterior terminó corta
        if same_flow and line.top - previous.bottom > 0.75 * self.body_size + 2:
            return True                 # hay un hueco vertical
        if indent > 0.8 * self.body_size and (line.x0 - previous.text_start_x) > 0.6 * self.body_size:
            return True                 # sangría de primera línea
        return same_flow and abs(line.size - previous.size) > 1.0

    def _add_toc_entry(self, line: Line, indent: float):
        self._close_paragraph()
        level = max(0, round(indent / (TOC_INDENT_STEP * self.body_size)))
        entry_html = html.escape(TOC_LEADER_RE.sub("", line.text))
        self.blocks.append(Paragraph(entry_html, f"toc t{min(level, MAX_TOC_LEVEL)}"))
        self._previous_line = None

    # ------------------------------------------------------------------ #
    # Títulos
    # ------------------------------------------------------------------ #
    def _is_heading(self, line: Line) -> bool:
        text = line.text
        if len(text) >= MAX_HEADING_CHARS or round(line.size) not in self.heading_levels or CAPTION_RE.match(text):
            return False
        is_large = line.size >= self.body_size * HEADING_SIZE_RATIO
        is_short_bold = is_mostly_bold(line) and len(text) < MAX_BOLD_HEADING_CHARS and not text.endswith(":")
        return is_large or is_short_bold

    def _add_heading(self, layout: PageLayout, line: Line):
        level = self.heading_levels[round(line.size)]
        last_block = self.blocks[-1] if self.blocks else None
        previous = self._previous_line
        continues_previous_heading = (
            isinstance(last_block, Heading) and last_block.page_index == layout.idx
            and last_block.level == level and self._open_paragraph is None
            and previous is not None and line.top - previous.bottom < line.size)
        if continues_previous_heading:
            last_block.text += " " + line.text      # título en dos líneas
        else:
            self._close_paragraph()
            self.blocks.append(Heading(level, line.text, layout.idx))
