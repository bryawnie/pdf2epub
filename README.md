# pdf2epub
Utilities for reading math/computing papers in e-readers

`main.py` convierte papers técnicos en PDF a EPUB **refluible**: el texto se adapta al tamaño de letra y de pantalla del e-reader, mientras que las ecuaciones, figuras y tablas se recortan del PDF como imágenes nítidas.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

```bash
python main.py paper.pdf                  # genera paper.epub
python main.py paper.pdf -o salida.epub --grayscale --max-width 1000
python main.py paper.pdf --pages 1-30     # probar con un tramo
```

| Opción | Descripción |
|---|---|
| `-o, --output` | Archivo de salida (por defecto, mismo nombre con `.epub`) |
| `--dpi` | Resolución de ecuaciones y figuras (por defecto 300) |
| `--grayscale` | Figuras en escala de grises (e-ink, archivo más liviano) |
| `--max-width` | Ancho máximo en píxeles de figuras/tablas (por defecto 1400) |
| `--inline-math auto\|text\|image` | Matemática dentro del texto: como texto cuando es posible (`auto`), siempre texto o siempre imagen |
| `--pages` | Rango de páginas, p. ej. `1-20,35` |
| `--title`, `--author`, `--lang` | Metadatos del EPUB |
| `--keep-headers` | No eliminar encabezados/pies de página repetidos |

## Cómo funciona

- **Texto:** reconstruye el orden de lectura (una o dos columnas), une líneas en párrafos, elimina encabezados y números de página, y une palabras cortadas con guion. Detecta títulos para el índice navegable.
- **Ecuaciones en display:** se recortan como imagen con tamaño en `em`, así escalan con la fuente elegida en el lector.
- **Matemática inline:** como texto con `<sub>`/`<sup>` cuando es simple; como imagen pequeña cuando no (raíces, delimitadores grandes, glifos sin Unicode).
- **Figuras, tablas y algoritmos:** se recortan como imagen junto con sus etiquetas; los pies de figura quedan como texto.

## Estructura del código

`main.py` es el punto de entrada (CLI). El resto se reparte en paquetes por responsabilidad; cada uno expone su API pública en su `__init__.py` y los demás paquetes solo importan de ahí.

| Paquete | Responsabilidad |
|---|---|
| `conversion/` | Pipeline completo PDF → EPUB (`convert`) |
| `layout/` | Análisis de cada página: columnas, líneas, figuras/tablas, encabezados y pies repetidos |
| `equations/` | Detección de ecuaciones en display |
| `rendering/` | Recorte de zonas del PDF como PNG |
| `document/` | Orden de lectura, títulos, líneas → HTML inline y armado de bloques (párrafos, ecuaciones, figuras) |
| `epub/` | Escritura del EPUB (capítulos, índice, CSS) |
| `common/` | Expresiones regulares y utilidades de texto/fuentes compartidas |

Dependencias entre paquetes: `common` ← `layout` ← `equations`, `rendering` ← `document` ← `epub` ← `conversion` ← `main.py`.

## Limitaciones

- No hace OCR: en PDFs escaneados cada página queda como imagen.
- Las ecuaciones no se reacomodan ni son buscables (son imágenes).
- Las heurísticas de layout pueden fallar con maquetaciones inusuales.
