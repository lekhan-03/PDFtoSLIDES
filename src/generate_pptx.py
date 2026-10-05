
"""PPTX slide deck generator — reads questions.json → questions.pptx

Slide types produced:
    Title slide     — always first
    Section divider — one per section transition
    Normal MCQ      — 2x2 option grid (A top-left, B top-right, C/D bottom row)
    Match-column    — two-column stem display + 4 stacked full-width options

Usage (run from project root):
    # Output auto-named next to the input file
    python -m src.generate_pptx data/outputs/chemistry_2026_09_29_123258.json

    # Explicit output path
    python -m src.generate_pptx data/outputs/questions.json data/outputs/deck.pptx

    # Custom deck title / subtitle
    python -m src.generate_pptx questions.json deck.pptx \\
        --title "Chemistry Midterm" --subtitle "195 Qs · Boards 2026"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Load .env (same pattern as main.py) ───────────────────────────────────────
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

_load_dotenv()
# ─────────────────────────────────────────────────────────────────────────────

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Inches, Pt, Emu
except ImportError:
    sys.exit(
        "python-pptx is not installed.\n"
        "Run:  pip install python-pptx"
    )

try:
    from src.formula_render import render_math_text
except ImportError:
    try:
        from formula_render import render_math_text  # type: ignore
    except ImportError:
        render_math_text = None

# ── Color palette (dark theme, matches template) ──────────────────────────────
BG         = RGBColor(0x05, 0x05, 0x05)   # pure dark background
GOLD       = RGBColor(0xFA, 0xD0, 0x2C)   # question text / accents
CYAN       = RGBColor(0x00, 0xB0, 0xF0)   # option letters, col headers
OFF_WHITE  = RGBColor(0xF0, 0xF0, 0xF0)   # option body text
DIM_WHITE  = RGBColor(0xAA, 0xAA, 0xAA)   # subtitle / secondary text
BADGE_BG   = RGBColor(0x16, 0x13, 0x0B)   # section badge background (subtle)
LOGO_BG    = RGBColor(0x1C, 0x1C, 0x38)   # logo placeholder background
DIVIDER_LINE = RGBColor(0x33, 0x33, 0x66) # subtle column divider
CITATION_COLOR = RGBColor(0x8A, 0xC4, 0xFF) # Soft Sky/Ice Blue for citations
CITATION_FONT  = 'Georgia'

# ── Slide size: widescreen 16:9 ───────────────────────────────────────────────
SW = 13.33   # slide width  (inches)
SH = 7.5     # slide height (inches)

# ── Layout constants (inches) ─────────────────────────────────────────────────
M = 0.5      # standard margin

# Header row
HDR_TOP = 0.20
HDR_H   = 0.44
LOGO_W  = 1.5
LOGO_H  = 0.5
LOGO_L  = SW - M - LOGO_W

# Question text area (normal slides)
Q_L      = M
Q_TOP    = 0.80
Q_W      = SW - 2 * M
Q_H_STD  = 1.5    # normal MCQ


# 1x4 side-by-side options (Default arrangement)
GAP_1X4        = 0.20                     # horizontal padding between options
OPT_W_1X4      = (SW - 2 * M - 3 * GAP_1X4) / 4.0  # 2.93 inches per option
OPT_TEXT_W_1X4 = OPT_W_1X4 - 0.35        # usable text width

# 2x2 grid options (Fallback for longer options)
GAP_2X2        = 0.35                     # horizontal gap between columns
GAP_V_2X2      = 0.12                     # vertical gap between rows
OPT_W_2X2      = (SW - 2 * M - GAP_2X2) / 2.0      # 5.99 inches per option
OPT_TEXT_W_2X2 = OPT_W_2X2 - 0.40        # usable text width

# Match-the-column layout
MC_Q_H   = 0.8     # intro line height
MC_CH_H   = 0.28
MC_C_H    = 1.5    # column data area height
MC_CW    = (SW - 2 * M - 0.2) / 2   # each column width
MC_LCOL  = M
MC_RCOL  = M + MC_CW + 0.2

MC_OPT_W   = SW - 2 * M
MC_OPT_H   = 0.40
MC_OPT_GAP = 0.05




# ── Low-level drawing helpers ─────────────────────────────────────────────────

def _blank_slide(prs: Presentation):
    """Return a completely blank slide (layout index 6)."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def _bg(slide, color: RGBColor = BG) -> None:
    """Fill slide background with a solid color."""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _rect(slide, l: float, t: float, w: float, h: float,
          fill: RGBColor, rounded: bool = True,
          border: RGBColor | None = None):
    """Add a filled rectangle / rounded-rectangle. Returns the shape."""
    # Rounded rectangle shape type is 5, standard is 1
    shp = slide.shapes.add_shape(5 if rounded else 1,
                                  Inches(l), Inches(t),
                                  Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if border:
        shp.line.color.rgb = border
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    return shp


def _rgb_to_hex(c: RGBColor) -> str:
    return '#%02X%02X%02X' % (c[0], c[1], c[2])


def _add_rich_text_fallback(p, text: str, size: float, color: RGBColor,
                            bold: bool = True, font_name: str = 'Cambria'):
    """Fallback: use baseline XML for sub/superscript when matplotlib unavailable."""
    text = re.sub(r'Δ([oO0])', r'Δ<sub>\1</sub>', text)
    text = re.sub(r'\bt(\d)2g\b', r't2g\1', text)
    text = re.sub(r'\be(\d)g\b', r'eg\1', text)
    text = re.sub(r'\bt2g(\d*)', r't<sub>2g</sub><sup>\1</sup>', text)
    text = re.sub(r'\beg(\d*)', r'e<sub>g</sub><sup>\1</sup>', text)
    text = re.sub(r'\b([1-7]?[sfpd])(\d{1,2})\b', r'\1<sup>\2</sup>', text)
    text = re.sub(r'([A-Za-z0-9\)])(\d?[+-])(?=[\s.,;:<>]|$)', r'\1<sup>\2</sup>', text)
    text = re.sub(r'([A-Z][a-z]?|[\)])(\d+)', r'\1<sub>\2</sub>', text)
    text = text.replace('<sup></sup>', '')
    parts = re.split(r'(</?su[bp]>)', text)
    is_sub = is_sup = False
    for part in parts:
        if part == '<sub>':   is_sub = True
        elif part == '</sub>': is_sub = False
        elif part == '<sup>':  is_sup = True
        elif part == '</sup>': is_sup = False
        elif part:
            run = p.add_run()
            run.text = part
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.font.bold = bold
            run.font.name = font_name
            if is_sub:  run.font._element.set('baseline', '-25000')
            elif is_sup: run.font._element.set('baseline', '30000')


_CITATION_SEARCH_RE = re.compile(
    r'(\(\s*(?:19|20)\d{2}[a-zA-Z0-9,\s\-/–—]*\))',
    re.IGNORECASE
)


def extract_citation(stem: str) -> tuple[str, str | None]:
    """Extract citations like '(2025)', '(2016-m)', '(2024M,2026,2025-2)' from question stem."""
    if not stem:
        return stem, None
    # 1. Look for citation at the very end
    m_end = re.search(r'\s*(\(\s*(?:19|20)\d{2}[a-zA-Z0-9,\s\-/–—]*\))\s*\.?\s*$', stem, re.I)
    if m_end:
        cit = m_end.group(1).strip().rstrip('.').strip()
        cleaned_stem = stem[:m_end.start()].strip().rstrip(':').strip()
        return cleaned_stem, cit

    # 2. Look for citation embedded inside
    matches = list(_CITATION_SEARCH_RE.finditer(stem))
    if matches:
        last_m = matches[-1]
        cit = last_m.group(1).strip().rstrip('.').strip()
        cleaned_stem = (stem[:last_m.start()] + stem[last_m.end():]).strip()
        cleaned_stem = re.sub(r'\s{2,}', ' ', cleaned_stem).strip()
        return cleaned_stem, cit

    return stem, None


import pypandoc
import zipfile
import tempfile
import uuid
from lxml import etree

def _extract_and_add_images(slide, text: str, left: float, top: float, width: float, height: float) -> str:
    """Find [IMG: path], add to slide right of text, and return text without IMG tags."""
    import re
    from pptx.util import Inches
    import os
    
    matches = re.findall(r'\[IMG:\s*([^\]]+)\]', text)
    if matches:
        # Just add them on the right side of the slide/textbox
        img_left = left + width + 0.2
        img_top = top
        for img_path in matches:
            if os.path.exists(img_path):
                try:
                    # insert with max width 3 inches
                    slide.shapes.add_picture(img_path, Inches(img_left), Inches(img_top), width=Inches(3))
                    img_top += 2.0  # stack multiple images vertically
                except Exception:
                    pass
    return re.sub(r'\[IMG:\s*[^\]]+\]', '', text).strip()

def _insert_omml_math_into_paragraph(p, markdown_text: str, size: float, color: RGBColor, bold: bool = True, font_name: str = 'Cambria', slide=None):
    """Convert latex/markdown text to docx via pandoc, extract OMML, and inject into python-pptx paragraph."""
    
    def _safe_plain_text(text: str) -> str:
        text = text.replace('$', '')
        text = re.sub(r'\^\{([^}]*)\}', r'^\1', text)
        text = re.sub(r'_\{([^}]*)\}', r'_\1', text)
        text = text.replace(r'\{', '{').replace(r'\}', '}')
        return text.strip()
    
    # Pre-process the math blocks using our internal converter to fix \cosec, _____, etc.
    try:
        from src.convert.math import convert_math
        import re
        def _math_repl(m):
            return f"${convert_math(m.group(1))}$"
        markdown_text = re.sub(r'\$(.+?)\$', _math_repl, markdown_text, flags=re.S)
    except Exception as e:
        print(f"[!] Preprocessing math failed: {e}")
        pass

    if markdown_text.count('{') != markdown_text.count('}'):
        s_num = slide.part.partname if slide and hasattr(slide, 'part') else 'Unknown'
        print(f"[!] Slide {s_num}: Unbalanced braces in formula, falling back: {markdown_text}")
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return
        
    if markdown_text.count('\\begin') != markdown_text.count('\\end'):
        s_num = slide.part.partname if slide and hasattr(slide, 'part') else 'Unknown'
        print(f"[!] Slide {s_num}: Unbalanced begin/end in formula, falling back: {markdown_text}")
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return

    tmp_path = Path(tempfile.gettempdir()) / f"tmp_{uuid.uuid4().hex}.docx"
    try:
        pypandoc.convert_text(markdown_text, 'docx', format='markdown-fancy_lists', outputfile=str(tmp_path))
        with zipfile.ZipFile(tmp_path) as z:
            xml_data = z.read('word/document.xml')
    except Exception as e:
        print(f"[!] Pandoc DOCX OMML error: {e}")
        # fallback
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        if tmp_path.exists(): tmp_path.unlink(missing_ok=True)
        return
        
    if tmp_path.exists(): tmp_path.unlink(missing_ok=True)
        
    root = etree.fromstring(xml_data)
    w_ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    m_ns = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}

    # Check if pandoc failed to parse the math (it leaves literal $ or ^{ in the text)
    # We can just check the raw xml_data string
    xml_str = xml_data.decode('utf-8', errors='ignore')
    
    # Improved structural checking for actual OMML math vs literal fallbacks
    # A true OMML equation will contain <m:oMath>
    # If Pandoc failed to parse the math, it will output regular text containing $ or ^{
    if ('<m:oMath' not in xml_str and '$' in xml_str) or '^{' in xml_str:
        s_num = getattr(getattr(slide, 'part', None), 'partname', 'Unknown')
        print(f"[!] Pandoc failed to parse formula on Slide {s_num}, falling back to plain text:\n    {markdown_text}")
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return
        
    w_ps = root.xpath('.//w:p', namespaces=w_ns)
    
    a_ns = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    
    # Set default paragraph run properties (defRPr) to style math OMML runs
    pPr = p._p.find(f'{a_ns}pPr')
    if pPr is None:
        pPr = etree.Element(f'{a_ns}pPr')
        p._p.insert(0, pPr)
        
    defRPr = pPr.find(f'{a_ns}defRPr')
    if defRPr is None:
        defRPr = etree.SubElement(pPr, f'{a_ns}defRPr')
        
    defRPr.set('sz', str(int(size * 100)))
    if bold: defRPr.set('b', '1')
    
    # Clean up existing fill/font if present, then set
    for el in [f'{a_ns}solidFill', f'{a_ns}latin']:
        old = defRPr.find(el)
        if old is not None: defRPr.remove(old)
        
    solidFill = etree.SubElement(defRPr, f'{a_ns}solidFill')
    srgbClr = etree.SubElement(solidFill, f'{a_ns}srgbClr')
    srgbClr.set('val', f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")
    
    latin = etree.SubElement(defRPr, f'{a_ns}latin')
    latin.set('typeface', font_name)
    
    # Remove empty runs from p._p before appending
    for child in list(p._p):
        if child.tag == f'{a_ns}r':
            t = child.find(f'{a_ns}t')
            if t is None or not t.text:
                p._p.remove(child)
        
    for w_p in w_ps:
        for child in w_p:
            tag_name = child.tag.split('}')[-1]
            ns = child.tag.split('}')[0][1:] if '}' in child.tag else ''
            
            if ns == w_ns['w']:
                if tag_name == 'r':
                    a_r = etree.Element('{http://schemas.openxmlformats.org/drawingml/2006/main}r')
                    
                    # Apply text run properties
                    a_rPr = etree.SubElement(a_r, '{http://schemas.openxmlformats.org/drawingml/2006/main}rPr')
                    a_rPr.set('lang', 'en-US')
                    a_rPr.set('sz', str(int(size * 100))) # sz is in 1/100ths of point
                    if bold: a_rPr.set('b', '1')
                    
                    solidFill = etree.SubElement(a_rPr, '{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill')
                    srgbClr = etree.SubElement(solidFill, '{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
                    srgbClr.set('val', f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")
                    
                    latin = etree.SubElement(a_rPr, '{http://schemas.openxmlformats.org/drawingml/2006/main}latin')
                    latin.set('typeface', font_name)
                    
                    # Copy text
                    for w_t in child.xpath('.//w:t', namespaces=w_ns):
                        a_t = etree.SubElement(a_r, '{http://schemas.openxmlformats.org/drawingml/2006/main}t')
                        a_t.text = w_t.text
                    p._p.append(a_r)
            elif ns == m_ns['m']:
                omaths = []
                if tag_name == 'oMathPara':
                    omaths = child.xpath('.//m:oMath', namespaces=m_ns)
                elif tag_name == 'oMath':
                    omaths = [child]
                    
                for omath in omaths:
                    # PowerPoint requires oMath to be wrapped in mc:AlternateContent/mc:Choice/a14:m
                    mc_ns = "http://schemas.openxmlformats.org/markup-compatibility/2006"
                    a14_ns = "http://schemas.microsoft.com/office/drawing/2010/main"
                    
                    alt_content = etree.Element(f"{{{mc_ns}}}AlternateContent", nsmap={'mc': mc_ns, 'a14': a14_ns})
                    choice = etree.SubElement(alt_content, f"{{{mc_ns}}}Choice", Requires="a14")
                    a14_m = etree.SubElement(choice, f"{{{a14_ns}}}m")
                    a14_m.append(omath)
                    
                    p._p.append(alt_content)


def _get_content_height(text: str, width_in: float, font_size: float) -> float:
    """Measure the exact height in inches of text or rendered formula."""
    if not text:
        return 0.35
    if render_math_text:
        text = render_math_text(text)
    # Plain text / fallback height calculation
    lines = text.split('\n')
    chars_per_line = max(35, int(width_in / (font_size * 0.0062)))
    total_visual_lines = sum(max(1, (len(l.strip()) + chars_per_line - 1) // chars_per_line) for l in lines)
    return max(0.35, total_visual_lines * (font_size * 0.0185))


def _tb(slide, text: str,
        l: float, t: float, w: float, h: float,
        size: float, color: RGBColor,
        bold: bool = True,
        align = PP_ALIGN.LEFT,
        wrap: bool = True):
    """Add a textbox. Uses OMML formula pipeline if needed."""
    text = _extract_and_add_images(slide, text, l, t, w, h)
    
    use_omml = False
    if render_math_text:
        text = render_math_text(text)
        if '$' in text or '\\' in text:
            use_omml = True

    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = txb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = Inches(0)
    tf.margin_right = Inches(0)
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = align
    
    if use_omml:
        _insert_omml_math_into_paragraph(p, text, size, color, bold, 'Cambria', slide)
    else:
        _add_rich_text_fallback(p, text, size, color, bold, 'Cambria')
    return txb


def _shape_text(shape, slide, # Added slide to pass to _extract_and_add_images (Wait, _shape_text is used for options, need to check if slide is passed!)
                letter: str, body: str,
                letter_size: float, body_size: float,
                center_v: bool = False,
                left_in: float = 0, top_in: float = 0, width_in: float = 0) -> None:
    """Write cyan letter + off-white body text into an existing shape's text frame."""
    body = _extract_and_add_images(slide, body, left_in, top_in, width_in, 0.5)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left   = Inches(0)
    tf.margin_right  = Inches(0.08)
    tf.margin_top    = Inches(0)
    tf.margin_bottom = Inches(0)
    if center_v:
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    else:
        tf.vertical_anchor = MSO_ANCHOR.TOP

    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT

    r1 = p.add_run()
    r1.text = f"{letter}. "
    r1.font.bold  = True
    r1.font.size  = Pt(letter_size)
    r1.font.color.rgb = CYAN
    r1.font.name = 'Cambria'
    
    use_omml = False
    if render_math_text:
        body = render_math_text(body)
        if '$' in body or '\\' in body:
            use_omml = True

    if use_omml:
        _insert_omml_math_into_paragraph(p, body, body_size, OFF_WHITE, True, 'Cambria', slide)
    else:
        _add_rich_text_fallback(p, body, body_size, OFF_WHITE, True, 'Cambria')


def _logo(slide, logo_path: Path | None = None) -> None:
    """Draw the logo placeholder (top-right) or add an image if provided."""
    if logo_path and logo_path.exists():
        slide.shapes.add_picture(str(logo_path), Inches(LOGO_L), Inches(HDR_TOP - 0.1), width=Inches(LOGO_W))
        return

    # Transparent placeholder with subtle border so it doesn't clash with inserted image
    box = _rect(slide, LOGO_L, HDR_TOP - 0.1, LOGO_W, LOGO_H, fill=BG, rounded=True, border=DIM_WHITE)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "Insert Logo Here"
    r.font.size = Pt(10)
    r.font.color.rgb = DIM_WHITE
    r.font.bold = False
    r.font.name = 'Cambria'


def _calc_badge_width(text: str, font_size: float = 15.0) -> float:
    """Calculate dynamic width for badge container wrapping text tightly."""
    char_w_sum = 0.0
    for ch in text:
        if ch in ', -/':
            char_w_sum += font_size * 0.0045
        elif ch in '1I':
            char_w_sum += font_size * 0.0050
        elif ch in 'MW':
            char_w_sum += font_size * 0.0095
        else:
            char_w_sum += font_size * 0.0078
    return round(char_w_sum + 0.36, 2)


def _badge(slide, text: str | None) -> None:
    """Draw the prominent top-left badge tightly wrapping citation text without parentheses."""
    if not text:
        return
    label = text.strip()
    # Strip enclosing parentheses: '(2025)' -> '2025'
    if label.startswith('(') and label.endswith(')'):
        label = label[1:-1].strip()
    label = label.upper()
    if not label:
        return

    # Dynamic width tightly wrapping the citation text
    w = _calc_badge_width(label, 15.0)

    # Dark background container with subtle gold border
    _rect(slide, M, HDR_TOP, w, HDR_H, fill=RGBColor(0x1A, 0x16, 0x08), rounded=True, border=GOLD)

    # Prominent gold accent bar on the left
    _rect(slide, M + 0.03, HDR_TOP + 0.05, 0.06, HDR_H - 0.10, fill=GOLD, rounded=False)

    # Text: bold, Arial, vibrant gold color, size 15pt, vertically centered
    txb = slide.shapes.add_textbox(Inches(M + 0.15), Inches(HDR_TOP), Inches(w - 0.18), Inches(HDR_H))
    tf = txb.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = label
    r.font.size = Pt(15)
    r.font.color.rgb = GOLD
    r.font.bold = True
    r.font.name = 'Cambria'



def _can_fit_1x4(options: dict[str, str], text_width: float = OPT_TEXT_W_1X4) -> bool:
    """True if all 4 options can fit comfortably in a 1x4 horizontal side-by-side row."""
    if not options or len(options) < 4:
        return False
    for letter in "ABCD":
        text = options.get(letter, "").strip()
        if not text:
            return False
        # If plain text is longer than 32 characters, use 2x2 grid for readability
        if len(text) > 32:
            return False
        h = _get_content_height(text, text_width, 16)
        if h > 0.75:
            return False
    return True



# ── Match-the-column stem parser ──────────────────────────────────────────────

def _parse_match_col(stem: str):
    """Decompose a match-the-column question stem.

    Returns:
        intro      (str)        the opening sentence
        col1_label (str)        e.g. "Compound"
        col2_label (str)        e.g. "Application"
        col1_items (list[str])  e.g. ["(1)  CCl4", "(2)  CHI3", ...]
        col2_items (list[str])  e.g. ["(A)  Fire ext.", "(B)  Antiseptic", ...]
    """
    # Find where the actual column items begin
    first_item_match = re.search(r'\((?:i{1,3}|iv|v|\d|I{1,3}|IV|V|[a-dA-D])\)', stem)
    split_at_items = first_item_match.start() if first_item_match else len(stem)
    
    header_part = stem[:split_at_items]
    rest = stem[split_at_items:]

    c1_matches = list(re.finditer(r'\bColumn\s+I\b(?:\s*\(([^)]+)\))?', header_part, re.I))
    c2_matches = list(re.finditer(r'\bColumn\s+II\b(?:\s*\(([^)]+)\))?', header_part, re.I))

    c1m = c1_matches[-1] if c1_matches else None
    c2m = c2_matches[-1] if c2_matches else None

    col1_label = c1m.group(1).strip() if (c1m and c1m.group(1)) else "Column I"
    col2_label = c2m.group(1).strip() if (c2m and c2m.group(1)) else "Column II"

    split_at_headers = c1m.start() if c1m else split_at_items
    intro = header_part[:split_at_headers].strip().rstrip(':').strip()

    digit_items = re.findall(
        r'\((i{1,3}|iv|v|\d|I{1,3}|IV|V)\)\s*(.*?)(?=\s*\((?:i{1,3}|iv|v|\d|I{1,3}|IV|V|[a-dA-D])\)|\s*$)',
        rest, re.DOTALL
    )
    letter_items = re.findall(
        r'\(([a-dA-D])\)\s*(.*?)(?=\s*\((?:i{1,3}|iv|v|\d|I{1,3}|IV|V|[a-dA-D])\)|\s*$)',
        rest, re.DOTALL
    )

    col1_items = [f"({n})  {t.strip()}" for n, t in digit_items]
    col2_items = [f"({l})  {t.strip()}" for l, t in letter_items]

    return intro, col1_label, col2_label, col1_items, col2_items


# ── Slide builders ────────────────────────────────────────────────────────────

def build_title_slide(prs: Presentation, title: str, subtitle: str, logo_path: Path | None = None) -> None:
    slide = _blank_slide(prs)
    _bg(slide)
    _logo(slide, logo_path)

    _rect(slide, M, 3.15, SW - 2 * M, 0.04, fill=GOLD, rounded=False)

    _tb(slide, title,
        M, 1.8, SW - 2 * M, 1.2,
        size=44, color=GOLD, bold=True,
        align=PP_ALIGN.CENTER)

    _tb(slide, subtitle,
        M, 3.35, SW - 2 * M, 0.65,
        size=24, color=DIM_WHITE,
        align=PP_ALIGN.CENTER)


def build_divider_slide(prs: Presentation, section: str, logo_path: Path | None = None) -> None:
    slide = _blank_slide(prs)
    _bg(slide)
    _logo(slide, logo_path)

    _rect(slide, M, 2.35, 0.07, 2.8, fill=GOLD, rounded=False)

    _tb(slide, section.upper(),
        M + 0.22, 2.35, SW - 2 * M - 0.22, 2.8,
        size=50, color=GOLD, bold=True,
        align=PP_ALIGN.LEFT)


def build_normal_slide(prs: Presentation, q: dict, logo_path: Path | None = None) -> None:
    slide = _blank_slide(prs)
    _bg(slide)

    # Question stem & citation separation
    stem_raw = q.get('question', '')
    stem_text, citation = extract_citation(stem_raw)

    opts = dict(q.get("options", {}))
    if not citation and "D" in opts:
        cleaned_d, cit_d = extract_citation(opts["D"])
        if cit_d:
            citation = cit_d
            opts["D"] = cleaned_d

    # Top-left badge: displays citation only if citation exists
    if citation:
        _badge(slide, citation)
    _logo(slide, logo_path)


    # Dynamic measurement of question height
    q_h = _get_content_height(stem_text, Q_W, 18)
    q_bottom = Q_TOP + q_h

    # Render Question stem
    _tb(slide, stem_text,
        Q_L, Q_TOP, Q_W, q_h,
        size=18, color=GOLD, bold=True)

    # Dynamic positioning of Options directly below question
    opt_top = q_bottom + 0.18

    if _can_fit_1x4(opts):
        # ── 1x4 side-by-side horizontal arrangement (DEFAULT) ──
        h_a = _get_content_height(opts.get('A', ''), OPT_TEXT_W_1X4, 16)
        h_b = _get_content_height(opts.get('B', ''), OPT_TEXT_W_1X4, 16)
        h_c = _get_content_height(opts.get('C', ''), OPT_TEXT_W_1X4, 16)
        h_d = _get_content_height(opts.get('D', ''), OPT_TEXT_W_1X4, 16)
        row_h = max(0.50, h_a, h_b, h_c, h_d)

        for i, letter in enumerate("ABCD"):
            l = M + i * (OPT_W_1X4 + GAP_1X4)
            txb = slide.shapes.add_textbox(Inches(l), Inches(opt_top), Inches(OPT_W_1X4), Inches(row_h))
            _shape_text(txb, slide, letter, opts.get(letter, ""),
                        letter_size=16, body_size=16,
                        left_in=l, top_in=opt_top, width_in=OPT_W_1X4)
    else:
        # ── 2x2 grid arrangement (Fallback for longer options) ──
        h_a = _get_content_height(opts.get('A', ''), OPT_TEXT_W_2X2, 16)
        h_b = _get_content_height(opts.get('B', ''), OPT_TEXT_W_2X2, 16)
        row1_h = max(0.50, h_a, h_b)

        opt_r2 = opt_top + row1_h + GAP_V_2X2

        h_c = _get_content_height(opts.get('C', ''), OPT_TEXT_W_2X2, 16)
        h_d = _get_content_height(opts.get('D', ''), OPT_TEXT_W_2X2, 16)
        row2_h = max(0.50, h_c, h_d)

        col_left = M
        col_right = M + OPT_W_2X2 + GAP_2X2

        grid = [
            ("A", col_left, opt_top, row1_h),
            ("B", col_right, opt_top, row1_h),
            ("C", col_left, opt_r2, row2_h),
            ("D", col_right, opt_r2, row2_h),
        ]
        for letter, l, t, h in grid:
            txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(OPT_W_2X2), Inches(h))
            _shape_text(txb, slide, letter, opts.get(letter, ""),
                        letter_size=16, body_size=16,
                        left_in=l, top_in=t, width_in=OPT_W_2X2)




def build_open_question_slide(prs: Presentation, q: dict, logo_path: Path | None = None) -> None:
    """Slide for short-answer / long-answer (no options) questions.
    Shows citation in top-left badge + question in gold, with clean blank space below.
    """
    slide = _blank_slide(prs)
    _bg(slide)

    stem_raw = q.get('question', '')
    stem_text, citation = extract_citation(stem_raw)

    if citation:
        _badge(slide, citation)
    _logo(slide, logo_path)


    # Question text moved up and font size reduced; no Answer box below
    _tb(slide, stem_text,
        Q_L, Q_TOP, Q_W, 3.0,
        size=18, color=GOLD, bold=True)


def build_match_col_slide(prs: Presentation, q: dict, logo_path: Path | None = None) -> None:
    slide = _blank_slide(prs)
    _bg(slide)

    stem = q.get("question", "")
    intro, col1_lbl, col2_lbl, col1_items, col2_items = _parse_match_col(stem)
    intro_cleaned, citation = extract_citation(intro)

    if citation:
        _badge(slide, citation)
    _logo(slide, logo_path)


    intro_h = _get_content_height(intro_cleaned, Q_W, 18)
    intro_bottom = Q_TOP + intro_h

    # Intro line moved up and size reduced
    _tb(slide, intro_cleaned,
        Q_L, Q_TOP, Q_W, intro_h,
        size=18, color=GOLD, bold=True)

    ch_top = intro_bottom + 0.18
    c_top = ch_top + MC_CH_H + 0.05

    # Column headers
    _tb(slide, col1_lbl.upper(),
        MC_LCOL, ch_top, MC_CW, MC_CH_H,
        size=14, color=CYAN, bold=True)
    _tb(slide, col2_lbl.upper(),
        MC_RCOL, ch_top, MC_CW, MC_CH_H,
        size=14, color=CYAN, bold=True)

    # Vertical divider between columns
    n = max(len(col1_items), len(col2_items), 1)
    row_h = max(0.32, MC_C_H / n)
    actual_col_h = n * row_h

    _rect(slide,
          MC_LCOL + MC_CW + 0.07,
          ch_top,
          0.02,
          MC_CH_H + 0.05 + actual_col_h,
          fill=DIVIDER_LINE, rounded=False)

    # Column I items
    for i, item in enumerate(col1_items):
        _tb(slide, item,
            MC_LCOL, c_top + i * row_h, MC_CW, row_h,
            size=14, color=OFF_WHITE)

    # Column II items
    for i, item in enumerate(col2_items):
        _tb(slide, item,
            MC_RCOL, c_top + i * row_h, MC_CW, row_h,
            size=14, color=OFF_WHITE)

    # Options — stacked full-width dynamically placed right below the columns
    opt_top = c_top + actual_col_h + 0.18
    opts = q.get("options", {})
    for i, letter in enumerate("ABCD"):
        opt_text = opts.get(letter, "")
        opt_h = max(MC_OPT_H, _get_content_height(opt_text, MC_OPT_W - 0.5, 14))
        t = opt_top + i * (MC_OPT_H + MC_OPT_GAP)
        txb = slide.shapes.add_textbox(Inches(M), Inches(t), Inches(MC_OPT_W), Inches(opt_h))
        _shape_text(txb, slide, letter, opt_text,
                    letter_size=14, body_size=14, center_v=True,
                    left_in=M, top_in=t, width_in=MC_OPT_W)




# ── Main generator ────────────────────────────────────────────────────────────

def generate(json_path: Path, output_path: Path,
             title: str = "Chemistry Midterm — MCQ Practice",
             subtitle: str | None = None,
             logo_path: Path | None = None) -> None:
    """Read a questions JSON file and write a slide deck PPTX."""
    questions: list[dict] = json.loads(json_path.read_text(encoding="utf-8"))
    ok_qs = [q for q in questions if q.get("parsed_ok")]

    if subtitle is None:
        subtitle = f"{len(ok_qs)} Questions  ·  For: Boards"

    prs = Presentation()
    prs.slide_width  = Inches(SW)
    prs.slide_height = Inches(SH)

    print(f"[*] Building deck for {len(ok_qs)} questions ...")

    # Title slide
    build_title_slide(prs, title, subtitle, logo_path)

    # Walk sorted questions; insert section divider on each section change
    last_section: str | None = None
    match_col_count = 0
    open_count = 0
    divider_count = 0

    for q in ok_qs:
        section = q.get("section") or "General"
        if section != last_section:
            # build_divider_slide(prs, section, logo_path)
            last_section = section
            # print(f"   -> Section divider: {section}")

        q_type = q.get("question_type", "mcq")
        is_match = q_type == "match_the_column" or (
            "Match" in q.get("question", "") and "Column I" in q.get("question", "")
        )

        if is_match:
            build_match_col_slide(prs, q, logo_path)
            match_col_count += 1
        elif q_type == "open":
            build_open_question_slide(prs, q, logo_path)
            open_count += 1
        elif q_type == "divider":
            build_divider_slide(prs, q.get("question", "Section"), logo_path)
            divider_count += 1
        else:
            build_normal_slide(prs, q, logo_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prs.save(str(output_path))
    except PermissionError:
        from datetime import datetime
        alt_path = output_path.with_name(f"{output_path.stem}_{datetime.now().strftime('%H%M%S')}.pptx")
        print(f"⚠️  Permission denied for {output_path} (file is open in PowerPoint). Saved to: {alt_path}")
        prs.save(str(alt_path))
        output_path = alt_path

    total = len(prs.slides)
    mcq_count = len(ok_qs) - match_col_count - open_count - divider_count
    
    print(f"\n[OK] Saved {total} slides -> {output_path}")
    print(f"    1 title  +  {divider_count} dividers  "
          f"+  {mcq_count} MCQ  "
          f"+  {open_count} open/SA  "
          f"+  {match_col_count} match-the-column")

    # Post-run verification
    leaked_count = 0
    print("\n[*] Verifying no literal '$' or '^{' leaked into slides...")
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if hasattr(shape, "text_frame"):
                text = shape.text
                if '$' in text or '^{' in text:
                    print(f"    [!] Leaked math text on Slide {i+1}:\n        {text.strip()}")
                    leaked_count += 1
                    
    print(f"✅  Verification complete: {leaked_count} leaks detected.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _auto_pptx_path(json_path: Path) -> Path:
    """Place output .pptx next to the input JSON, same stem."""
    return json_path.with_suffix(".pptx")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a PPTX slide deck from an MCQ questions JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input",
                    help="Path to questions.json produced by main.py")
    ap.add_argument("output", nargs="?", default=None,
                    help="Output .pptx path (default: same name as input, .pptx extension)")
    ap.add_argument("--title",    default="Chemistry Midterm — MCQ Practice",
                    help="Deck title on the title slide")
    ap.add_argument("--subtitle", default=None,
                    help="Subtitle (auto-generated from question count if omitted)")
    ap.add_argument("--logo", default=None,
                    help="Path to logo PNG/JPG to add to slides")
    args = ap.parse_args()

    json_path = Path(args.input)
    if not json_path.exists():
        sys.exit(f"[ERROR] Input file not found: {json_path}")

    out_path = Path(args.output) if args.output else _auto_pptx_path(json_path)
    print(f"[INFO] Output will be written to: {out_path}")

    default_logo = Path(__file__).resolve().parent / "simplified_Logo.png"
    generate(
        json_path=json_path,
        output_path=out_path,
        title=args.title,
        subtitle=args.subtitle,
        logo_path=Path(args.logo) if args.logo else default_logo,
    )


if __name__ == "__main__":
    main()
