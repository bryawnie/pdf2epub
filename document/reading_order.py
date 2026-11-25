"""Orden de lectura de las líneas y regiones de una página."""
from equations import merge_math_regions
from layout import FULL_WIDTH, LEFT_COLUMN, MATH_LINE, RIGHT_COLUMN, Line, PageLayout

LAST_POSITION = 1e9


def order_page_items(layout: PageLayout) -> list:
    """Líneas de texto y regiones de la página en orden de lectura.

    Con dos columnas, los elementos de ancho completo dividen la página en bandas; dentro
    de cada banda se lee primero la columna izquierda y luego la derecha.
    """
    items = layout.lines + layout.regions
    if layout.gutter is None:
        return sorted(items, key=lambda item: (item.top, item.x0))

    full_width_items = sorted((item for item in items if item.column == FULL_WIDTH), key=lambda item: item.top)
    column_items = [item for item in items if item.column != FULL_WIDTH]

    ordered = []
    band_start = -LAST_POSITION
    for full_width_item in full_width_items + [None]:
        band_end = full_width_item.top if full_width_item else LAST_POSITION
        band = [item for item in column_items if band_start <= item.top < band_end]
        for column in (LEFT_COLUMN, RIGHT_COLUMN):
            in_column = [item for item in band if item.column == column]
            ordered += sorted(in_column, key=lambda item: (item.top, item.x0))
        if full_width_item:
            ordered.append(full_width_item)
        band_start = band_end
    return ordered


def order_with_equation_regions(layout: PageLayout, body_size: float) -> list:
    """Orden de lectura donde las líneas de cada ecuación se reemplazan por su región."""
    ordered = order_page_items(layout)
    ordered_lines = [item for item in ordered if isinstance(item, Line)]
    equation_regions = merge_math_regions(layout, ordered_lines, body_size)
    region_by_first_line = {id(region.lines[0]): region for region in equation_regions}

    result = []
    for item in ordered:
        if isinstance(item, Line) and item.kind == MATH_LINE:
            region = region_by_first_line.get(id(item))
            if region:
                result.append(region)
            continue
        result.append(item)
    return result
