"""Expresiones regulares y tablas de caracteres usadas para clasificar texto y fuentes."""
import re

# --------------------------------------------------------------------------- #
# Clasificación de fuentes (por nombre de fuente del PDF)
# --------------------------------------------------------------------------- #
MATH_FONT_RE = re.compile(
    r"CMMI|CMSY|CMEX|CMBSY|MSAM|MSBM|EUFM|EUSM|EUEX|RSFS|STMARY|WASY|"
    r"LMMathItalic|LMMathSymbols|LMMathExtension|LatinModernMath|"
    r"Math|MTMI|MTSY|MTEX|Symbol|txsy|txmi|txex|pxsy|pxmi|pxex|rtxmi|"
    r"NewCM.*Math|Asana|Euler|LinLibertineI\d*$|LibertinusMath|ntxmi|ntxsy|ntxex|zxlmi|zplmi|rtxr", re.I)
# Fuentes de operadores "grandes" (sumatorias, integrales, delimitadores extensibles)
BIG_OPERATOR_FONT_RE = re.compile(r"CMEX|LMMathExtension|MTEX|txex|pxex|ntxex|EUEX", re.I)
BOLD_FONT_RE = re.compile(r"(?:T|S|-|_)B\d*$|Bold|CMBX|CMB10|CMBSY|Black|Heavy|Semibold|SemiBold|Demi|-Bd|\.B\b|Medi", re.I)
ITALIC_FONT_RE = re.compile(r"(?:T|-|_)I\d*$|Italic|Oblique|CMTI|CMSL|-It\b|-Ital|Slant|\bIt\b", re.I)
MONOSPACE_FONT_RE = re.compile(r"CMTT|Mono|Courier|Consol|Inconsolata|\bTT\b", re.I)

# Fuentes de letras "blackboard" (ℝ, ℕ...) y caligráficas (ℒ, ℱ...)
BLACKBOARD_FONT_RE = re.compile(r"MSBM|bbold|dsrom|Bbb|DoubleStruck|txsyb|pxsyb|ntxsyb|zlmsyb", re.I)
CALLIGRAPHIC_FONT_RE = re.compile(r"CMSY|txsy|pxsy|rsfs|EUSM|LMMathSymbols|MTSY|Script|Calligr", re.I)

BLACKBOARD_LETTERS = {"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"}
CALLIGRAPHIC_LETTERS = {"B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ"}

# --------------------------------------------------------------------------- #
# Clasificación de texto
# --------------------------------------------------------------------------- #
MATH_CHARS = set("=±∓×÷≤≥≠≈≡∼≃≅∝∞∑∏∫∮∂∇√∈∉⊂⊆⊃⊇∪∩∧∨¬∀∃→←↔⇒⇐⇔↦⊤⊥⊗⊕·∘′″"
                 "αβγδεϵζηθϑικλμνξπϖρϱσςτυφϕχψωΓΔΘΛΞΠΣΥΦΨΩ")
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}

CAPTION_RE = re.compile(r"^(Figure|Fig\.|FIGURE|FIG\.|Table|TABLE|Tab\.|Algorithm|Listing)\s*[A-Z]?\d+")
EQUATION_NUMBER_RE = re.compile(r"\(\s*[A-Z]?\d+(\.\d+)*[a-z]?\s*\)$")
BULLET_RE = re.compile(r"^(•|◦|▪|–|—|\*|\[\d+\]|\d+\.\s|\(\w\)\s)")
# Línea de índice: texto seguido de puntos guía y número de página
TOC_LEADER_RE = re.compile(r"\s*(\.\s*){4,}\s*[\dixvlcIXVLC]*\s*$")
PAGE_NUMBER_RE = re.compile(r"\d+|[ivxlc]+")
STANDALONE_PAGE_LABEL_RE = re.compile(r"[\divxlcIVXLC\-–— ]{1,8}|page \d+( of \d+)?", re.I)
