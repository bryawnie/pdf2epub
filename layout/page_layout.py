"""Análisis geométrico de una página: columnas, líneas de texto y regiones gráficas."""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from .geometry import overlap_length
from .models import (ABSORBED_LINE, FIGURE_REGION, FULL_WIDTH, LEFT_COLUMN, RIGHT_COLUMN,
                     TABLE_REGION, TEXT_LINE, Line, Region)
from common import CAPTION_RE, contains_math, is_big_operator_font

# --- detección de columnas ------------------------------------------------- #
MIN_CHARS_FOR_COLUMN_DETECTION = 200
MAX_DOT_FRACTION = 0.18          # más puntos que esto → índice con puntos guía, no hay columnas
GUTTER_SEARCH_RANGE = (0.33, 0.67)   # zona central de la página donde se busca el canal
GUTTER_EMPTINESS = 0.12          # un canal tiene ≤12 % de la "tinta" típica
MIN_GUTTER_WIDTH = 4             # en puntos

# --- agrupación de líneas -------------------------------------------------- #
MIN_VERTICAL_OVERLAP_TO_JOIN_LINE = 0.45
ORPHAN_MAX_CHARS = 3             # un grupo con ≤3 caracteres suele ser un radical o delimitador suelto
ORPHAN_HORIZONTAL_REACH = 20

# --- gráficos -------------------------------------------------------------- #
HEADER_ZONE = 0.10               # fracción superior de la página (encabezado)
FOOTER_ZONE_START = 0.93         # a partir de aquí empieza el pie de página
GRAPHIC_CLUSTER_MARGIN = 8
MAX_HORIZONTAL_RULE_HEIGHT = 1.6
MIN_TABLE_RULE_LENGTH = 40


@dataclass
class _GraphicBox:
    """Caja de un gráfico (imagen o trazo vectorial) o de un grupo de ellos."""
    x0: float
    top: float
    x1: float
    bottom: float
    has_image: bool

    def touches(self, other: "_GraphicBox", margin: float = GRAPHIC_CLUSTER_MARGIN) -> bool:
        return (other.x0 - margin < self.x1 and other.x1 + margin > self.x0 and
                other.top - margin < self.bottom and other.bottom + margin > self.top)

    def absorb(self, other: "_GraphicBox"):
        self.x0, self.top = min(self.x0, other.x0), min(self.top, other.top)
        self.x1, self.bottom = max(self.x1, other.x1), max(self.bottom, other.bottom)
        self.has_image |= other.has_image


class PageLayout:
    def __init__(self, page, page_index):
        self.page = page
        self.idx = page_index
        self.width, self.height = float(page.width), float(page.height)
        self.origin_x, self.origin_y = float(page.bbox[0]), float(page.bbox[1])
        self.chars = [char for char in page.chars
                      if char["text"] and not char["text"].isspace()
                      and char["x1"] > self.origin_x and char["x0"] < self.origin_x + self.width]
        self.rotated_chars: list = []
        self.gutter = None                      # x del canal entre columnas, o None
        self.lines: list[Line] = []
        self.regions: list[Region] = []
        self.column_bounds: dict[str, tuple[float, float]] = {}

    @property
    def header_limit(self) -> float:
        """y por encima del cual está la zona de encabezado."""
        return self.origin_y + HEADER_ZONE * self.height

    @property
    def footer_limit(self) -> float:
        """y por debajo del cual está la zona de pie de página."""
        return self.origin_y + FOOTER_ZONE_START * self.height

    # ------------------------------------------------------------------ #
    # Columnas
    # ------------------------------------------------------------------ #
    def detect_gutter(self):
        """Devuelve la x del canal central si la página tiene dos columnas; si no, None."""
        if len(self.chars) < MIN_CHARS_FOR_COLUMN_DETECTION:
            return None
        dot_count = sum(char["text"] == "." for char in self.chars)
        if dot_count > MAX_DOT_FRACTION * len(self.chars):
            return None

        # Para cada x, en cuántas filas de texto hay tinta
        pixel_columns = int(self.width) + 1
        text_rows_at_x = [set() for _ in range(pixel_columns)]
        for char in self.chars:
            if not char.get("upright", True):
                continue
            row = round(char["top"] / 3)
            first_x = max(0, int(char["x0"] - self.origin_x))
            last_x = min(pixel_columns, int(char["x1"] - self.origin_x) + 1)
            for x in range(first_x, last_x):
                text_rows_at_x[x].add(row)
        ink_at_x = [len(rows) for rows in text_rows_at_x]

        search_start = int(self.width * GUTTER_SEARCH_RANGE[0])
        search_end = int(self.width * GUTTER_SEARCH_RANGE[1])
        inked_columns = [ink for ink in ink_at_x if ink > 0]
        if not inked_columns:
            return None
        typical_ink = statistics.median(sorted(inked_columns)[len(inked_columns) // 2:])

        # El canal es la franja vacía más ancha de la zona central
        best_center, best_width = None, 0
        run_start = None
        for x in range(search_start, search_end + 1):
            if ink_at_x[x] <= GUTTER_EMPTINESS * typical_ink:
                run_start = x if run_start is None else run_start
                run_width = x - run_start + 1
                if run_width > best_width:
                    best_width, best_center = run_width, (run_start + x) / 2
            else:
                run_start = None
        if best_center is not None and best_width >= MIN_GUTTER_WIDTH:
            return best_center + self.origin_x
        return None

    def column_of(self, x0, x1):
        if self.gutter is None:
            return FULL_WIDTH
        if x1 <= self.gutter + 2:
            return LEFT_COLUMN
        if x0 >= self.gutter - 2:
            return RIGHT_COLUMN
        return FULL_WIDTH

    def compute_column_bounds(self):
        """Calcula el margen izquierdo y derecho típico de cada columna."""
        for column in (LEFT_COLUMN, RIGHT_COLUMN, FULL_WIDTH):
            reference_lines = [line for line in self.lines if line.column == column and len(line.text) > 25]
            if not reference_lines and column != FULL_WIDTH:
                continue
            if not reference_lines:
                reference_lines = self.lines
            if not reference_lines:
                self.column_bounds[column] = (self.origin_x, self.origin_x + self.width)
                continue
            left_edges = sorted(line.x0 for line in reference_lines)
            right_edges = sorted(line.x1 for line in reference_lines)
            left = Counter(round(x) for x in left_edges).most_common(1)[0][0]
            if len(right_edges) > 2:
                right = right_edges[int(len(right_edges) * 0.9)]
            else:
                right = right_edges[-1]
            self.column_bounds[column] = (left, right)
        if self.gutter is not None:
            # el ancho completo abarca desde el borde de la izquierda hasta el de la derecha
            left_bounds = self.column_bounds.get(LEFT_COLUMN, (self.origin_x, self.gutter))
            right_bounds = self.column_bounds.get(RIGHT_COLUMN, (self.gutter, self.origin_x + self.width))
            self.column_bounds[FULL_WIDTH] = (left_bounds[0], right_bounds[1])
            self.column_bounds.setdefault(LEFT_COLUMN, left_bounds)
            self.column_bounds.setdefault(RIGHT_COLUMN, right_bounds)

    def column_width(self, column):
        bounds = (self.column_bounds.get(column) or self.column_bounds.get(FULL_WIDTH)
                  or (self.origin_x, self.origin_x + self.width))
        return max(bounds[1] - bounds[0], 1)

    # ------------------------------------------------------------------ #
    # Líneas de texto
    # ------------------------------------------------------------------ #
    def build_lines(self):
        self.gutter = self.detect_gutter()
        upright_chars = [char for char in self.chars if char.get("upright", True)]
        self.rotated_chars = [char for char in self.chars if not char.get("upright", True)]

        if self.gutter is None:
            self.lines = self._group_chars_into_lines(upright_chars, FULL_WIDTH)
            return

        gutter = self.gutter
        left_lines = self._group_chars_into_lines(
            [char for char in upright_chars if (char["x0"] + char["x1"]) / 2 < gutter], LEFT_COLUMN)
        right_lines = self._group_chars_into_lines(
            [char for char in upright_chars if (char["x0"] + char["x1"]) / 2 >= gutter], RIGHT_COLUMN)

        lines, unmatched_right_lines = self._merge_lines_crossing_gutter(left_lines, right_lines)
        self._merge_centered_line_pairs(lines, unmatched_right_lines)
        lines += unmatched_right_lines
        # una línea del lado izquierdo que pasa el canal también es de ancho completo
        for line in lines:
            if line.column == LEFT_COLUMN and line.x1 > gutter + 2:
                line.column = FULL_WIDTH
        self.lines = lines

    def _group_chars_into_lines(self, chars, column) -> list[Line]:
        # Los caracteres grandes definen las bandas; luego se asignan los pequeños.
        chars = sorted(chars, key=lambda char: (-char["size"], char["top"]))
        bands = self._cluster_chars_into_bands(chars)
        self._attach_orphan_bands(bands)
        return [Line.from_chars(sorted(band.chars, key=lambda char: char["x0"]), self.idx, column)
                for band in bands]

    @staticmethod
    def _cluster_chars_into_bands(chars) -> list["_Band"]:
        bands: list[_Band] = []
        for char in chars:
            char_height = max(char["bottom"] - char["top"], 0.1)
            best_band, best_overlap = None, 0
            for band in bands:
                overlap_ratio = overlap_length(char["top"], char["bottom"], band.top, band.bottom) / char_height
                if overlap_ratio > best_overlap:
                    best_band, best_overlap = band, overlap_ratio
            if best_band is not None and best_overlap >= MIN_VERTICAL_OVERLAP_TO_JOIN_LINE:
                best_band.chars.append(char)
                if char["size"] >= 0.9 * best_band.max_size and not is_big_operator_font(char["fontname"]):
                    best_band.top = min(best_band.top, char["top"])
                    best_band.bottom = max(best_band.bottom, char["bottom"])
            else:
                bands.append(_Band(char["top"], char["bottom"], [char], char["size"]))
        return bands

    @staticmethod
    def _attach_orphan_bands(bands: list["_Band"]):
        """Une fragmentos huérfanos (radicales, delimitadores grandes, índices de sumatorias)
        a la línea con la que se superponen verticalmente."""
        changed = True
        while changed:
            changed = False
            for band in bands:
                if not band.is_orphan():
                    continue
                x0, x1, top, bottom = band.extent()
                host, host_overlap = None, 0
                for other in bands:
                    if other is band:
                        continue
                    other_x0, other_x1, other_top, other_bottom = other.extent()
                    if x1 < other_x0 - ORPHAN_HORIZONTAL_REACH or x0 > other_x1 + ORPHAN_HORIZONTAL_REACH:
                        continue
                    vertical_overlap = overlap_length(top, bottom, other_top, other_bottom)
                    if vertical_overlap > host_overlap:
                        host, host_overlap = other, vertical_overlap
                if host is not None and host_overlap > 0.45 * (bottom - top):
                    host.chars.extend(band.chars)
                    bands.remove(band)
                    changed = True
                    break

    def _merge_lines_crossing_gutter(self, left_lines, right_lines):
        """Une las líneas izquierda y derecha que en realidad son una sola que cruza el canal
        (títulos, figuras a ancho completo). Devuelve (líneas, líneas derechas sin pareja)."""
        gutter = self.gutter
        used_right_indexes = set()
        merged_lines = []
        for left_line in left_lines:
            partner_index = None
            for index, right_line in enumerate(right_lines):
                if index in used_right_indexes:
                    continue
                left_top, left_bottom = left_line.core_extent
                right_top, right_bottom = right_line.core_extent
                shared_height = overlap_length(left_top, left_bottom, right_top, right_bottom)
                same_row = shared_height > 0.5 * min(left_bottom - left_top, right_bottom - right_top)
                touching = right_line.x0 - left_line.x1 < 0.45 * max(left_line.size, right_line.size)
                reaches_gutter = left_line.x1 > gutter - 2 * left_line.size
                if same_row and touching and reaches_gutter:
                    partner_index = index
                    break
            if partner_index is not None:
                used_right_indexes.add(partner_index)
                merged_lines.append(Line.from_chars(left_line.chars + right_lines[partner_index].chars,
                                                    self.idx, FULL_WIDTH))
            else:
                merged_lines.append(left_line)
        unmatched_right = [line for index, line in enumerate(right_lines) if index not in used_right_indexes]
        return merged_lines, unmatched_right

    def _merge_centered_line_pairs(self, lines, right_lines):
        """Pares centrados en la misma línea base (p. ej. lista de autores) → ancho completo.
        Modifica `lines` y `right_lines` in situ."""
        left_lines = [line for line in lines if line.column == LEFT_COLUMN]
        if not left_lines or not right_lines:
            return
        left_margin = Counter(round(line.x0) for line in left_lines).most_common(1)[0][0]
        right_margin = Counter(round(line.x0) for line in right_lines).most_common(1)[0][0]
        for left_line in list(lines):
            indented = left_line.x0 >= left_margin + 2 * left_line.size
            ends_before_gutter = left_line.x1 <= self.gutter - 0.6 * left_line.size
            if (left_line.column != LEFT_COLUMN or not indented or not ends_before_gutter
                    or contains_math(left_line.chars)):
                continue
            for right_line in right_lines:
                left_top, left_bottom = left_line.core_extent
                right_top, right_bottom = right_line.core_extent
                if (right_line.x0 > right_margin + 2 * right_line.size
                        and abs(right_line.size - left_line.size) < 0.5
                        and not contains_math(right_line.chars)
                        and overlap_length(left_top, left_bottom, right_top, right_bottom)
                        > 0.5 * (left_bottom - left_top)):
                    lines.remove(left_line)
                    right_lines.remove(right_line)
                    lines.append(Line.from_chars(left_line.chars + right_line.chars, self.idx, FULL_WIDTH))
                    break

    # ------------------------------------------------------------------ #
    # Gráficos: figuras y tablas
    # ------------------------------------------------------------------ #
    def detect_graphic_regions(self):
        horizontal_rules, graphic_boxes = self._collect_graphic_objects()
        clusters = self._cluster_graphic_boxes(graphic_boxes)

        regions = []
        for box in clusters:
            width, height = box.x1 - box.x0, box.bottom - box.top
            if (box.has_image and width > 15 and height > 15) or (width > 35 and height > 25):
                regions.append(Region(FIGURE_REGION, self.idx, box.x0, box.top, box.x1, box.bottom))
        self._add_regions_from_rules(regions, horizontal_rules)
        self.regions = self._merge_overlapping_regions(regions)

    def _collect_graphic_objects(self):
        """Separa los objetos gráficos de la página en reglas horizontales y el resto."""
        page = self.page
        objects = [("img", image["x0"], image["top"], image["x1"], image["bottom"]) for image in page.images]
        for object_type in ("rects", "curves", "lines"):
            for obj in getattr(page, object_type):
                objects.append((object_type, obj["x0"], obj["top"], obj["x1"], obj["bottom"]))

        page_area = self.width * self.height
        horizontal_rules, graphic_boxes = [], []
        for object_type, x0, top, x1, bottom in objects:
            width, height = x1 - x0, bottom - top
            if width * height > 0.85 * page_area:      # fondo de página
                continue
            if bottom < self.header_limit or top > self.footer_limit:   # reglas de encabezado / pie
                continue
            if width < 0.3 and height < 0.3:
                continue
            if object_type != "img" and height <= MAX_HORIZONTAL_RULE_HEIGHT and width > 3:
                horizontal_rules.append((x0, top, x1, bottom))
            else:
                graphic_boxes.append(_GraphicBox(x0, top, x1, bottom, has_image=object_type == "img"))
        return horizontal_rules, graphic_boxes

    @staticmethod
    def _cluster_graphic_boxes(boxes: list[_GraphicBox]) -> list[_GraphicBox]:
        """Agrupa gráficos cercanos en una sola caja."""
        clusters: list[_GraphicBox] = []
        for box in sorted(boxes, key=lambda b: (b.top, b.x0)):
            nearby_cluster = next((cluster for cluster in clusters if cluster.touches(box)), None)
            if nearby_cluster is not None:
                nearby_cluster.absorb(box)
            else:
                clusters.append(replace(box))
        # Repetir hasta que ningún par de clusters se toque
        changed = True
        while changed:
            changed = False
            merged: list[_GraphicBox] = []
            for cluster in clusters:
                for existing in merged:
                    if existing.touches(cluster):
                        existing.absorb(cluster)
                        changed = True
                        break
                else:
                    merged.append(replace(cluster))
            clusters = merged
        return clusters

    def _add_regions_from_rules(self, regions: list[Region], horizontal_rules):
        """Las reglas horizontales alineadas forman tablas (booktabs) o marcos de figura."""
        rules_by_span = defaultdict(list)
        for rule in horizontal_rules:
            if rule[2] - rule[0] < MIN_TABLE_RULE_LENGTH:
                continue
            rules_by_span[(round(rule[0] / 4), round(rule[2] / 4))].append(rule)

        for rules in rules_by_span.values():
            enclosing_region = None
            for region in regions:
                if any(overlap_length(rule[0], rule[2], region.x0, region.x1) > 0.5 * (rule[2] - rule[0])
                       and region.top - 10 < rule[1] < region.bottom + 10 for rule in rules):
                    enclosing_region = region
            if enclosing_region:
                for rule in rules:
                    enclosing_region.expand_to_include(*rule)
                continue
            if len(rules) >= 2:
                top, bottom = min(rule[1] for rule in rules), max(rule[3] for rule in rules)
                if 12 < bottom - top < 0.75 * self.height:
                    regions.append(Region(TABLE_REGION, self.idx, min(rule[0] for rule in rules), top,
                                          max(rule[2] for rule in rules), bottom))

    @staticmethod
    def _merge_overlapping_regions(regions: list[Region]) -> list[Region]:
        changed = True
        while changed:
            changed = False
            merged: list[Region] = []
            for region in regions:
                for existing in merged:
                    if (overlap_length(region.x0, region.x1, existing.x0, existing.x1) > 0
                            and overlap_length(region.top, region.bottom, existing.top, existing.bottom) > 0):
                        existing.expand_to_include(region.x0, region.top, region.x1, region.bottom)
                        changed = True
                        break
                else:
                    merged.append(region)
            regions = merged
        return regions

    # ------------------------------------------------------------------ #
    # Texto dentro de figuras y tablas
    # ------------------------------------------------------------------ #
    def absorb_text_into_regions(self, body_size):
        """Las etiquetas de ejes, celdas de tabla, etc. pasan a formar parte de la imagen."""
        for region in self.regions:
            region.column = self.column_of(region.x0, region.x1)

        changed = True
        while changed:
            changed = False
            for line in self.lines:
                if line.kind != TEXT_LINE:
                    continue
                for region in self.regions:
                    if self._line_belongs_to_region(line, region, body_size):
                        line.kind = ABSORBED_LINE
                        region.lines.append(line)
                        region.expand_to_include(line.x0, line.top, line.x1, line.bottom)
                        changed = True
                        break

        for char in self.rotated_chars:
            for region in self.regions:
                if (region.x0 - 20 <= char["x0"] <= region.x1 + 20
                        and region.top - 5 <= char["top"] <= region.bottom + 5):
                    region.expand_to_include(char["x0"], char["top"], char["x1"], char["bottom"])
                    break

        self.lines = [line for line in self.lines if line.kind != ABSORBED_LINE]
        self.regions = self._merge_overlapping_regions(self.regions)
        # descartar adornos en márgenes (reglas de encabezado/pie) y cajas sin contenido
        self.regions = [region for region in self.regions
                        if not (region.bottom < self.header_limit or region.top > self.footer_limit)
                        and region.height > 4]
        for region in self.regions:
            region.column = self.column_of(region.x0, region.x1)

    def _line_belongs_to_region(self, line: Line, region: Region, body_size) -> bool:
        if CAPTION_RE.match(line.text):
            return False
        center_x, center_y = (line.x0 + line.x1) / 2, (line.top + line.bottom) / 2
        inside = (region.x0 - 1 <= center_x <= region.x1 + 1
                  and region.top - 1 <= center_y <= region.bottom + 1)
        # un texto más grande que el cuerpo solo se absorbe si está bien adentro
        fully_inside = (region.x0 + 2 < line.x0 and line.x1 < region.x1 - 2
                        and region.top + 2 < line.top and line.bottom < region.bottom - 2)
        if line.size > body_size * 1.06 and not fully_inside:
            return False
        if inside:
            return True

        horizontal_distance = max(region.x0 - line.x1, line.x0 - region.x1, 0)
        vertical_distance = max(region.top - line.bottom, line.top - region.bottom, 0)
        is_short = (line.x1 - line.x0) < 0.55 * self.column_width(region.column)
        is_small = line.size < body_size * 0.93
        within_region_width = line.x0 >= region.x0 - 15 and line.x1 <= region.x1 + 15
        return horizontal_distance < 14 and vertical_distance < 10 and (
            (is_short and (is_small or len(line.text) < 18 or region.kind == TABLE_REGION)) or
            (within_region_width and vertical_distance < 8 and (len(line.text) < 45 or is_small)))


@dataclass
class _Band:
    """Franja horizontal de caracteres que formará una línea de texto."""
    top: float
    bottom: float
    chars: list
    max_size: float

    def extent(self):
        return (min(char["x0"] for char in self.chars), max(char["x1"] for char in self.chars),
                min(char["top"] for char in self.chars), max(char["bottom"] for char in self.chars))

    def is_orphan(self) -> bool:
        visible = [char for char in self.chars if char["text"].strip()]
        return len(visible) <= ORPHAN_MAX_CHARS or all(is_big_operator_font(char["fontname"]) for char in visible)
