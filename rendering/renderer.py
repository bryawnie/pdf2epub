"""Recorte de zonas de la página como imágenes PNG."""
import io
from typing import NamedTuple

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageOps

from layout import PageLayout

POINTS_PER_INCH = 72.0
INK_THRESHOLD = 18               # diferencia mínima respecto al blanco para considerar "tinta"
TRIM_MARGIN_POINTS = 1.5
DEFAULT_MAX_IMAGE_WIDTH = 1400   # pantallas de e-reader ≈ 1072–1404 px


class CropResult(NamedTuple):
    filename: str
    width_pt: float      # tamaño original del recorte, en puntos del PDF
    height_pt: float


class RenderedImage(NamedTuple):
    filename: str
    png_data: bytes


class ImageRenderer:
    def __init__(self, pdf_path, dpi, grayscale, max_image_width=DEFAULT_MAX_IMAGE_WIDTH):
        self.document = pdfium.PdfDocument(pdf_path)
        self.scale = dpi / POINTS_PER_INCH
        self.grayscale = grayscale
        self.max_image_width = max_image_width
        self.images: list[RenderedImage] = []
        self._cached_page_index = None
        self._cached_page_image = None

    def page_image(self, page_index):
        """Imagen de la página completa (cacheada: se suele recortar varias veces la misma)."""
        if self._cached_page_index != page_index:
            page = self.document[page_index]
            self._cached_page_image = page.render(scale=self.scale).to_pil().convert("RGB")
            self._cached_page_index = page_index
        return self._cached_page_image

    def crop(self, layout: PageLayout, x0, top, x1, bottom, kind, pad=2.0, trim=True, gray=False, keep=None):
        """Recorta la caja dada (en puntos) y guarda el PNG. Devuelve un `CropResult` o None.

        kind: figure | table | page | eq | inl (define nombre, escalado y paleta).
        keep: caracteres que pertenecen al recorte; el resto de los caracteres de la
        página que caen dentro se blanquean (evita trozos de líneas vecinas).
        """
        page_image = self.page_image(layout.idx)
        scale = self.scale
        image = page_image
        if keep is not None:
            image = self._blank_foreign_chars(layout, page_image, keep, (x0, top, x1, bottom), pad)

        box = (max(0, int((x0 - layout.origin_x - pad) * scale)),
               max(0, int((top - layout.origin_y - pad) * scale)),
               min(image.width, int((x1 - layout.origin_x + pad) * scale + 1)),
               min(image.height, int((bottom - layout.origin_y + pad) * scale + 1)))
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        cropped = image.crop(box)
        if trim:
            cropped = self._trim_whitespace(cropped)

        width_pt, height_pt = cropped.width / scale, cropped.height / scale
        if kind in ("figure", "table", "page") and cropped.width > self.max_image_width:
            new_height = max(1, round(cropped.height * self.max_image_width / cropped.width))
            cropped = cropped.resize((self.max_image_width, new_height), Image.LANCZOS)
        if gray or self.grayscale:
            cropped = ImageOps.grayscale(cropped)

        # paleta reducida: archivos mucho más livianos sin pérdida visible
        if cropped.mode == "L":
            cropped = cropped.quantize(16 if kind in ("eq", "inl") else 64)
        else:
            cropped = cropped.quantize(256, method=Image.Quantize.MEDIANCUT)
        buffer = io.BytesIO()
        cropped.save(buffer, "PNG", optimize=True)

        filename = f"{kind}_{layout.idx + 1:03d}_{len(self.images) + 1:04d}.png"
        self.images.append(RenderedImage(filename, buffer.getvalue()))
        return CropResult(filename, width_pt, height_pt)

    def _blank_foreign_chars(self, layout: PageLayout, page_image, keep, box, pad):
        """Copia de la página con los caracteres ajenos a `keep` pintados de blanco."""
        x0, top, x1, bottom = box
        scale = self.scale
        kept_ids = {id(char) for char in keep}
        foreign_chars = [char for char in layout.chars
                         if id(char) not in kept_ids
                         and char["x1"] > x0 - pad and char["x0"] < x1 + pad
                         and char["bottom"] > top - pad and char["top"] < bottom + pad]
        if not foreign_chars:
            return page_image

        image = page_image.copy()
        draw = ImageDraw.Draw(image)
        for char in foreign_chars:
            draw.rectangle([int((char["x0"] - layout.origin_x) * scale), int((char["top"] - layout.origin_y) * scale),
                            int((char["x1"] - layout.origin_x) * scale), int((char["bottom"] - layout.origin_y) * scale)],
                           fill="white")
        # re-pintar los propios por si se solapaban con los ajenos
        for char in keep:
            char_box = (int((char["x0"] - layout.origin_x) * scale), int((char["top"] - layout.origin_y) * scale),
                        int((char["x1"] - layout.origin_x) * scale) + 1, int((char["bottom"] - layout.origin_y) * scale) + 1)
            image.paste(page_image.crop(char_box), char_box[:2])
        return image

    def _trim_whitespace(self, image):
        """Recorta el margen blanco alrededor del contenido, dejando un pequeño margen."""
        ink = ImageOps.invert(ImageOps.grayscale(image))
        content_box = ink.point(lambda value: 255 if value > INK_THRESHOLD else 0).getbbox()
        if not content_box:
            return image
        margin = int(TRIM_MARGIN_POINTS * self.scale)
        return image.crop((max(0, content_box[0] - margin), max(0, content_box[1] - margin),
                           min(image.width, content_box[2] + margin), min(image.height, content_box[3] + margin)))
