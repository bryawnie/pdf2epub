#!/usr/bin/env python3
"""pdf2epub — convierte papers técnicos en PDF a EPUB refluible. Ver README.md."""
import argparse
import re

from conversion import convert
from document import INLINE_MATH_AUTO, INLINE_MATH_IMAGE, INLINE_MATH_TEXT
from rendering import DEFAULT_MAX_IMAGE_WIDTH


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2epub",
        description="Convierte un paper PDF a EPUB refluible (texto, ecuaciones y figuras).")
    parser.add_argument("pdf")
    parser.add_argument("-o", "--output", help="archivo .epub de salida (por defecto, mismo nombre)")
    parser.add_argument("--dpi", type=int, default=300, help="resolución de ecuaciones y figuras (por defecto 300)")
    parser.add_argument("--grayscale", action="store_true", help="figuras en escala de grises (e-ink)")
    parser.add_argument("--inline-math", choices=[INLINE_MATH_AUTO, INLINE_MATH_TEXT, INLINE_MATH_IMAGE],
                        default=INLINE_MATH_AUTO,
                        help="auto: texto salvo cuando no se puede representar; image: toda la matemática inline como imagen")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--max-width", type=int, default=DEFAULT_MAX_IMAGE_WIDTH,
                        help="ancho máximo en píxeles de figuras/tablas (menos = EPUB más liviano)")
    parser.add_argument("--pages", help='rango de páginas, p. ej. "1-20,35"')
    parser.add_argument("--keep-headers", action="store_true", help="no eliminar encabezados/pies repetidos")
    return parser


def main():
    args = build_argument_parser().parse_args()
    output_path = args.output or re.sub(r"\.pdf$", "", args.pdf, flags=re.I) + ".epub"
    stats = convert(args.pdf, output_path, dpi=args.dpi, grayscale=args.grayscale,
                    inline_math_mode=args.inline_math, title=args.title, author=args.author,
                    lang=args.lang, keep_headers=args.keep_headers, pages=args.pages,
                    max_image_width=args.max_width)
    print(f"✓ {output_path}")
    print("  " + ", ".join(f"{key}: {value}" for key, value in stats.items()))


if __name__ == "__main__":
    main()
