"""Estructuras de datos del análisis de página: líneas de texto y regiones recortables."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from common import BULLET_RE, chars_to_plain_text, is_big_operator_font, split_into_words

# Columna a la que pertenece un elemento
LEFT_COLUMN = "L"
RIGHT_COLUMN = "R"
FULL_WIDTH = "F"        # ancho completo, o única columna

# Tipos de línea (`Line.kind`)
TEXT_LINE = "text"      # texto normal
MATH_LINE = "math"      # parte de una ecuación en display
ABSORBED_LINE = "region"  # texto absorbido por una figura o tabla

# Tipos de región (`Region.kind`)
FIGURE_REGION = "figure"
TABLE_REGION = "table"
EQUATION_REGION = "eq"


@dataclass
class Line:
    chars: list
    page_index: int
    column: str = FULL_WIDTH
    kind: str = TEXT_LINE
    x0: float = 0
    x1: float = 0
    top: float = 0
    bottom: float = 0
    size: float = 0           # tamaño de fuente predominante
    text: str = ""

    @classmethod
    def from_chars(cls, chars: list, page_index: int, column: str) -> "Line":
        line = cls(chars, page_index, column)
        line.refresh_geometry()
        return line

    def refresh_geometry(self) -> "Line":
        """Recalcula caja, tamaño predominante y texto a partir de los caracteres."""
        chars = self.chars
        self.x0 = min(char["x0"] for char in chars)
        self.x1 = max(char["x1"] for char in chars)
        self.top = min(char["top"] for char in chars)
        self.bottom = max(char["bottom"] for char in chars)
        size_counts = Counter(round(char["size"], 1) for char in chars if char["text"].strip())
        if size_counts:
            self.size = max(size_counts, key=lambda size: (size_counts[size], size))
        else:
            self.size = chars[0]["size"]
        self.chars.sort(key=lambda char: char["x0"])
        self.text = chars_to_plain_text(self.chars)
        return self

    @property
    def core_extent(self) -> tuple[float, float]:
        """(top, bottom) de los caracteres de tamaño normal, sin radicales ni delimitadores grandes."""
        normal_chars = [char for char in self.chars
                        if char["size"] >= self.size * 0.9 and not is_big_operator_font(char["fontname"])]
        normal_chars = normal_chars or self.chars
        return min(char["top"] for char in normal_chars), max(char["bottom"] for char in normal_chars)

    @property
    def text_start_x(self) -> float:
        """x donde empieza el texto, saltando una viñeta o marcador inicial."""
        if not BULLET_RE.match(self.text):
            return self.x0
        words = split_into_words(self.chars, compare_with_previous_size=False)
        return words[1][0]["x0"] if len(words) > 1 else self.x0


@dataclass
class Region:
    """Zona que se recorta del PDF como imagen: figura, tabla o ecuación."""
    kind: str
    page_index: int
    x0: float
    top: float
    x1: float
    bottom: float
    column: str = FULL_WIDTH
    lines: list = field(default_factory=list)

    def expand_to_include(self, x0, top, x1, bottom):
        self.x0, self.top = min(self.x0, x0), min(self.top, top)
        self.x1, self.bottom = max(self.x1, x1), max(self.bottom, bottom)

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.bottom - self.top
