"""Escritura del archivo EPUB 3 (con índice NCX por compatibilidad)."""
import datetime
import html
import uuid
import zipfile
from dataclasses import dataclass

from document import Block, Equation, Figure, Heading, Paragraph
from rendering import RenderedImage

MAX_CHAPTER_SPLIT_LEVEL = 2     # se abre un capítulo nuevo en cada título h1/h2

CSS = """
body { font-family: serif; line-height: 1.45; margin: 0 0.4em; }
h1 { font-size: 1.5em; text-align: center; margin: 1em 0 0.6em; }
h2 { font-size: 1.25em; margin: 1.4em 0 0.5em; }
h3 { font-size: 1.1em; margin: 1.2em 0 0.4em; }
h4 { font-size: 1em; margin: 1em 0 0.3em; }
p { margin: 0; text-indent: 1.2em; text-align: justify; }
p.noindent, p.cont { text-indent: 0; }
p.caption { text-indent: 0; font-size: 0.9em; margin: 0.3em 0 1em; text-align: left; }
p.small { font-size: 0.85em; text-indent: 0; margin-top: 0.3em; }
div.eq { text-align: center; margin: 0.6em 0; page-break-inside: avoid; }
div.eq img { max-width: 100%; height: auto; }
div.fig { text-align: center; margin: 1em 0 0.3em; page-break-inside: avoid; }
div.fig img { max-width: 100%; height: auto; }
img.im { max-width: 100%; }
p.toc { text-indent: 0; text-align: left; margin: 0.15em 0; }
p.t1 { margin-left: 1.2em; } p.t2 { margin-left: 2.4em; } p.t3 { margin-left: 3.6em; }
code { font-family: monospace; font-size: 0.95em; }
sub, sup { font-size: 0.75em; line-height: 0; }
"""

CONTAINER_XML = ('<?xml version="1.0"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')


@dataclass
class TocEntry:
    level: int
    text: str
    filename: str
    anchor: str         # "" si apunta al inicio del archivo


@dataclass
class Chapter:
    filename: str
    xhtml: str


def write_epub(out_path, blocks: list[Block], images: list[RenderedImage], title, author, lang):
    chapters, toc = _build_chapters(blocks, title, lang)
    book_id = f"urn:uuid:{uuid.uuid4()}"

    with zipfile.ZipFile(out_path, "w") as epub:
        # el mimetype debe ir primero y sin comprimir
        epub.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        epub.writestr("META-INF/container.xml", CONTAINER_XML, compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/content.opf", _build_package_opf(chapters, images, book_id, title, author, lang),
                      compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/nav.xhtml", _build_nav(toc, lang), compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/toc.ncx", _build_ncx(toc, book_id, title), compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        for chapter in chapters:
            epub.writestr(f"OEBPS/text/{chapter.filename}", chapter.xhtml, compress_type=zipfile.ZIP_DEFLATED)
        for image in images:
            epub.writestr(f"OEBPS/images/{image.filename}", image.png_data, compress_type=zipfile.ZIP_STORED)


# --------------------------------------------------------------------------- #
# Capítulos
# --------------------------------------------------------------------------- #
def _split_into_chapters(blocks: list[Block]) -> list[list[Block]]:
    chapters, current = [], []
    for block in blocks:
        starts_chapter = isinstance(block, Heading) and block.level <= MAX_CHAPTER_SPLIT_LEVEL
        current_has_content = any(not isinstance(other, Heading) for other in current)
        if starts_chapter and current_has_content:
            chapters.append(current)
            current = []
        current.append(block)
    if current:
        chapters.append(current)
    return chapters


def _build_chapters(blocks: list[Block], book_title: str, lang: str) -> tuple[list[Chapter], list[TocEntry]]:
    chapters, toc = [], []
    for chapter_number, chapter_blocks in enumerate(_split_into_chapters(blocks), 1):
        filename = f"ch{chapter_number:03d}.xhtml"
        body_parts = []
        chapter_title = None
        for block_number, block in enumerate(chapter_blocks):
            if isinstance(block, Heading):
                anchor = f"h{chapter_number}_{block_number}"
                body_parts.append(f'<h{block.level} id="{anchor}">{html.escape(block.text)}</h{block.level}>')
                toc.append(TocEntry(block.level, block.text, filename, anchor))
                chapter_title = chapter_title or block.text
            else:
                body_parts.append(_block_to_xhtml(block))
        chapters.append(Chapter(filename, _xhtml_document(chapter_title or book_title, "\n".join(body_parts), lang)))

    if not toc:
        toc = [TocEntry(1, book_title, chapters[0].filename, "")]
    return chapters, toc


def _block_to_xhtml(block: Block) -> str:
    if isinstance(block, Paragraph):
        css_class = f' class="{block.css_class}"' if block.css_class else ""
        return f"<p{css_class}>{block.html}</p>"
    if isinstance(block, Equation):
        return (f'<div class="eq"><img src="../images/{block.image_name}" alt="{html.escape(block.alt_text[:300])}" '
                f'style="width:{block.width_em:.2f}em"/></div>')
    if isinstance(block, Figure):
        return (f'<div class="fig"><img src="../images/{block.image_name}" alt="{block.kind}" '
                f'style="width:{block.width_percent:.0f}%"/></div>')
    raise TypeError(f"Bloque desconocido: {block!r}")


def _xhtml_document(title: str, body: str, lang: str) -> str:
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="{lang}" lang="{lang}">\n<head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
            f'<link rel="stylesheet" type="text/css" href="../style.css"/></head>\n<body>\n{body}\n</body>\n</html>\n')


# --------------------------------------------------------------------------- #
# Paquete, índice y navegación
# --------------------------------------------------------------------------- #
def _build_package_opf(chapters: list[Chapter], images: list[RenderedImage], book_id, title, author, lang) -> str:
    modified = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>']
    spine = []
    for index, chapter in enumerate(chapters):
        manifest.append(f'<item id="c{index}" href="text/{chapter.filename}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{index}"/>')
    for index, image in enumerate(images):
        manifest.append(f'<item id="i{index}" href="images/{image.filename}" media-type="image/png"/>')

    manifest_xml = chr(10).join("  " + item for item in manifest)
    spine_xml = chr(10).join("  " + item for item in spine)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{lang}">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:identifier id="bookid">{book_id}</dc:identifier>
  <dc:title>{html.escape(title)}</dc:title>
  <dc:creator>{html.escape(author)}</dc:creator>
  <dc:language>{lang}</dc:language>
  <meta property="dcterms:modified">{modified}</meta>
 </metadata>
 <manifest>
  {manifest_xml}
 </manifest>
 <spine toc="ncx">
  {spine_xml}
 </spine>
</package>
"""


def _toc_href(entry: TocEntry) -> str:
    return f"text/{entry.filename}" + (f"#{entry.anchor}" if entry.anchor else "")


def _build_nav(toc: list[TocEntry], lang: str) -> str:
    """Índice de navegación EPUB 3: lista plana con una clase de sangría por nivel."""
    items = "\n".join(f'<li class="l{entry.level}"><a href="{_toc_href(entry)}">{html.escape(entry.text)}</a></li>'
                      for entry in toc)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}">'
            f'<head><meta charset="utf-8"/><title>Índice</title></head><body>'
            f'<nav epub:type="toc" id="toc"><h1>Índice</h1><ol>\n{items}\n</ol></nav></body></html>')


def _build_ncx(toc: list[TocEntry], book_id: str, title: str) -> str:
    """Índice NCX (EPUB 2) para lectores antiguos."""
    nav_points = "\n".join(
        f'<navPoint id="np{index}" playOrder="{index + 1}">'
        f'<navLabel><text>{html.escape(("  " * (entry.level - 1)) + entry.text)}</text></navLabel>'
        f'<content src="{_toc_href(entry)}"/></navPoint>'
        for index, entry in enumerate(toc))
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            f'<head><meta name="dtb:uid" content="{book_id}"/></head><docTitle><text>{html.escape(title)}</text></docTitle>'
            f'<navMap>\n{nav_points}\n</navMap></ncx>')
