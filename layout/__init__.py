"""Análisis geométrico de las páginas del PDF: columnas, líneas, regiones y márgenes."""
from .geometry import overlap_length
from .models import (ABSORBED_LINE, EQUATION_REGION, FIGURE_REGION, FULL_WIDTH, LEFT_COLUMN, MATH_LINE,
                     RIGHT_COLUMN, TABLE_REGION, TEXT_LINE, Line, Region)
from .page_layout import PageLayout
from .running_headers import remove_running_headers
