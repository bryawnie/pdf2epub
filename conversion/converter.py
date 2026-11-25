"""Pipeline de conversión PDF → EPUB."""
import re
import sys

import pdfplumber

from document import (INLINE_MATH_AUTO, Block, BlockBuilder, Equation, Figure, Heading, Paragraph,
                      compute_heading_levels, detect_body_font_size)
from epub import write_epub
from equations import classify_display_math
from layout import PageLayout, remove_running_headers
from rendering import DEFAULT_MAX_IMAGE_WIDTH, ImageRenderer

MIN_TITLE_LENGTH = 4
UNKNOWN_AUTHOR = "Desconocido"


def convert(pdf_path, out_path, dpi=300, grayscale=False, inline_math_mode=INLINE_MATH_AUTO,
            title=None, author=None, lang="en", keep_headers=False, verbose=True, pages=None,
            max_image_width=DEFAULT_MAX_IMAGE_WIDTH) -> dict:
    """Convierte `pdf_path` en un EPUB en `out_path` y devuelve estadísticas de la conversión."""
    pdf = pdfplumber.open(pdf_path)
    renderer = ImageRenderer(pdf_path, dpi, grayscale, max_image_width)

    layouts = _analyze_pages(pdf, parse_page_selection(pages, len(pdf.pages)), verbose)
    body_size = detect_body_font_size(layouts)
    if not keep_headers:
        remove_running_headers(layouts, body_size)
    for layout in layouts:
        layout.compute_column_bounds()
        layout.absorb_text_into_regions(body_size)
        layout.compute_column_bounds()
        classify_display_math(layout, body_size)

    heading_levels = compute_heading_levels(layouts, body_size)
    builder = BlockBuilder(layouts, renderer, body_size, heading_levels, inline_math_mode)
    for layout in layouts:
        builder.add_page(layout)
        if verbose:
            print(f"\r  generando página {layout.idx + 1}/{len(layouts)}", end="", file=sys.stderr)
    blocks = builder.finish()
    if verbose:
        print(file=sys.stderr)

    metadata = pdf.metadata or {}
    title = title or _resolve_title(metadata, blocks, pdf_path)
    author = author or (metadata.get("Author") or "").strip() or UNKNOWN_AUTHOR
    write_epub(out_path, blocks, renderer.images, title, author, lang)

    return {
        "pages": len(layouts),
        "equations": sum(isinstance(block, Equation) for block in blocks),
        "figures_tables": sum(isinstance(block, Figure) for block in blocks),
        "inline_math_images": sum(image.filename.startswith("inl") for image in renderer.images),
        "paragraphs": sum(isinstance(block, Paragraph) for block in blocks),
        "title": title,
    }


def parse_page_selection(spec, page_count) -> list[int]:
    """Convierte un rango como "1-20,35" en índices de página base 0. Sin spec, todas las páginas."""
    if not spec:
        return list(range(page_count))
    indexes = []
    for part in spec.split(","):
        first, dash, last = part.partition("-")
        first = int(first) if first else 1
        last = int(last) if last else (page_count if dash else first)
        indexes += range(first - 1, min(last, page_count))
    return indexes


def _analyze_pages(pdf, page_indexes, verbose) -> list[PageLayout]:
    layouts = []
    for position, page_index in enumerate(page_indexes):
        layout = PageLayout(pdf.pages[page_index], page_index)
        layout.build_lines()
        layout.detect_graphic_regions()
        layouts.append(layout)
        if verbose:
            print(f"\r  analizando página {position + 1}/{len(page_indexes)}", end="", file=sys.stderr)
    if verbose:
        print(file=sys.stderr)
    return layouts


def _resolve_title(metadata: dict, blocks: list[Block], pdf_path: str) -> str:
    """Título de los metadatos del PDF, o el primer título del texto, o el nombre del archivo."""
    metadata_title = (metadata.get("Title") or "").strip()
    first_heading = next((block.text for block in blocks if isinstance(block, Heading)), None)
    if first_heading and metadata_title and metadata_title.lower() in first_heading.lower():
        metadata_title = first_heading
    if not metadata_title or len(metadata_title) < MIN_TITLE_LENGTH:
        file_name = re.sub(r"\.pdf$", "", pdf_path.split("/")[-1], flags=re.I)
        return first_heading or file_name
    return metadata_title
