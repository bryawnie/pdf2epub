"""Bloques de contenido del documento, ya listos para escribirse como XHTML."""
from dataclasses import dataclass


@dataclass
class Heading:
    level: int           # 1–4
    text: str
    page_index: int


@dataclass
class Paragraph:
    html: str
    css_class: str = ""
    # párrafo que continúa tras una ecuación (se mantiene sin sangría)
    continues_after_equation: bool = False


@dataclass
class Equation:
    image_name: str
    width_em: float      # ancho relativo al tamaño de letra del cuerpo
    alt_text: str


@dataclass
class Figure:
    """Figura, tabla o página completa (PDF escaneado) como imagen."""
    image_name: str
    width_percent: float
    kind: str            # figure | table | page


Block = Heading | Paragraph | Equation | Figure
