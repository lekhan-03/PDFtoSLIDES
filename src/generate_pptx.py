"""PPTX slide deck generator — reads questions.json → questions.pptx

Slide types produced:
    Title slide     — always first
    Section divider — one per section transition
    Normal MCQ      — 2x2 option grid or 1x4 side-by-side
    Match-column    — two-column stem display + 4 stacked full-width options
    Subjective/Open — question text + formulas/tables/images, without option boxes

Usage (run from project root):
    # Output auto-named next to the input file
    venv\\Scripts\\python.exe -m src.generate_pptx "data\\testres\\tested.json"

    # Explicit output path
    venv\\Scripts\\python.exe -m src.generate_pptx data/outputs/questions.json data/outputs/deck.pptx

    # Custom deck title / subtitle
    venv\\Scripts\\python.exe -m src.generate_pptx questions.json deck.pptx \\
        --title "Chemistry Midterm" --subtitle "195 Qs · Boards 2026"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from lxml import etree

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
    import pypandoc
except ImportError:
    pypandoc = None

try:
    from src.formula_render import render_math_text
except ImportError:
    try:
        from formula_render import render_math_text  # type: ignore
    except ImportError:
        render_math_text = None

# ── Color palette (dark theme, matches approved template) ──────────────────────
BG           = RGBColor(0x05, 0x05, 0x05)   # pure dark background
GOLD         = RGBColor(0xFA, 0xD0, 0x2C)   # question text / accents
CYAN         = RGBColor(0x00, 0xB0, 0xF0)   # option letters, col headers
OFF_WHITE    = RGBColor(0xF0, 0xF0, 0xF0)   # option body text
DIM_WHITE    = RGBColor(0xAA, 0xAA, 0xAA)   # subtitle / secondary text
BADGE_BG     = RGBColor(0x16, 0x13, 0x0B)   # section badge background (subtle)
LOGO_BG      = RGBColor(0x1C, 0x1C, 0x38)   # logo placeholder background
DIVIDER_LINE = RGBColor(0x33, 0x33, 0x66)   # subtle column divider
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
GAP_V_2X2      = 0.05                     # vertical gap between rows
OPT_W_2X2      = (SW - 2 * M - GAP_2X2) / 2.0      # 5.99 inches per option
OPT_TEXT_W_2X2 = OPT_W_2X2 - 0.40        # usable text width

# Match-the-column layout
MC_Q_H   = 0.8     # intro line height
MC_CH_H  = 0.28
MC_C_H   = 1.5     # column data area height
MC_CW    = (SW - 2 * M - 0.2) / 2   # each column width
MC_LCOL  = M
MC_RCOL  = M + MC_CW + 0.2

MC_OPT_W   = SW - 2 * M
MC_OPT_H   = 0.40
MC_OPT_GAP = 0.05

# ── Low-level drawing helpers ─────────────────────────────────────────────────

def _blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])

def _bg(slide, color=BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

def _rect(slide, l, t, w, h, fill, rounded=True, border=None):
    shp = slide.shapes.add_shape(5 if rounded else 1, Inches(l), Inches(t), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if border:
        shp.line.color.rgb = border
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    return shp

def _add_rich_text_fallback(p, text, size, color, bold=True, font_name='Cambria'):
    text = re.sub(r'Δ([oO0])', r'Δ<sub>\g<1></sub>', text)
    text = re.sub(r' t(\d)2g ', r't2g\g<1>', text)
    text = re.sub(r' e(\d)g ', r'eg\g<1>', text)
    text = re.sub(r' t2g(\d*)', r't<sub>2g</sub><sup>\g<1></sup>', text)
    text = re.sub(r' eg(\d*)', r'e<sub>g</sub><sup>\g<1></sup>', text)
    text = re.sub(r' ([1-7]?[sfpd])(\d{1,2}) ', r'\g<1><sup>\g<2></sup>', text)
    text = re.sub(r'([A-Za-z0-9\)])(\d?[+-])(?=[\s.,;:<>]|$)', r'\g<1><sup>\g<2></sup>', text)
    text = re.sub(r'([A-Z][a-z]?|[\)])(\d+)', r'\g<1><sub>\g<2></sub>', text)
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

_CITATION_SEARCH_RE = re.compile(r'(\(\s*(?:19|20)\d{2}[a-zA-Z0-9,\s\-/–—]*\))', re.IGNORECASE)

def extract_citation(stem):
    if not stem: return stem, None
    m_end = re.search(r'\s*(\(\s*(?:19|20)\d{2}[a-zA-Z0-9,\s\-/–—]*\))\s*\.?\s*$', stem, re.I)
    if m_end:
        return stem[:m_end.start()].strip().rstrip(':').strip(), m_end.group(1).strip().rstrip('.').strip()
    matches = list(_CITATION_SEARCH_RE.finditer(stem))
    if matches:
        last_m = matches[-1]
        cit = last_m.group(1).strip().rstrip('.').strip()
        cleaned = (stem[:last_m.start()] + stem[last_m.end():]).strip()
        return re.sub(r'\s{2,}', ' ', cleaned).strip(), cit
    return stem, None

def _insert_omml_math_into_paragraph(p, markdown_text, size, color, bold=True, font_name='Cambria', slide=None):
    def _safe_plain_text(text):
        text = text.replace('$', '')
        text = re.sub(r'\^\{([^}]*)\}', r'^\g<1>', text)
        text = re.sub(r'_\{([^}]*)\}', r'_\g<1>', text)
        return text.replace(r'\{', '{').replace(r'\}', '}').strip()
        
    try:
        from src.convert.math import convert_math
        def _math_repl(m): return f"${convert_math(m.group(1))}$"
        markdown_text = re.sub(r'\$(.+?)\$', _math_repl, markdown_text, flags=re.S)
    except Exception:
        pass

    if markdown_text.count('{') != markdown_text.count('}'):
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return
        
    if markdown_text.count('\\begin') != markdown_text.count('\\end'):
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return

    if not pypandoc:
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return

    tmp_path = Path(tempfile.gettempdir()) / f"tmp_{uuid.uuid4().hex}.docx"
    try:
        pypandoc.convert_text(markdown_text, 'docx', format='markdown-fancy_lists', outputfile=str(tmp_path))
        with zipfile.ZipFile(tmp_path) as z:
            xml_data = z.read('word/document.xml')
    except Exception:
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        if tmp_path.exists(): tmp_path.unlink(missing_ok=True)
        return
        
    if tmp_path.exists(): tmp_path.unlink(missing_ok=True)
        
    root = etree.fromstring(xml_data)
    w_ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    m_ns = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}

    xml_str = xml_data.decode('utf-8', errors='ignore')
    if ('<m:oMath' not in xml_str and '$' in xml_str) or '^{' in xml_str:
        _add_rich_text_fallback(p, _safe_plain_text(markdown_text), size, color, bold, font_name)
        return
        
    w_ps = root.xpath('.//w:p', namespaces=w_ns)
    a_ns = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    
    pPr = p._p.find(f'{a_ns}pPr')
    if pPr is None:
        pPr = etree.Element(f'{a_ns}pPr')
        p._p.insert(0, pPr)
        
    defRPr = pPr.find(f'{a_ns}defRPr')
    if defRPr is None:
        defRPr = etree.SubElement(pPr, f'{a_ns}defRPr')
        
    defRPr.set('sz', str(int(size * 100)))
    if bold: defRPr.set('b', '1')
    
    for el in [f'{a_ns}solidFill', f'{a_ns}latin']:
        old = defRPr.find(el)
        if old is not None: defRPr.remove(old)
        
    solidFill = etree.SubElement(defRPr, f'{a_ns}solidFill')
    srgbClr = etree.SubElement(solidFill, f'{a_ns}srgbClr')
    srgbClr.set('val', f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")
    
    latin = etree.SubElement(defRPr, f'{a_ns}latin')
    latin.set('typeface', font_name)
    
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
                    a_rPr = etree.SubElement(a_r, '{http://schemas.openxmlformats.org/drawingml/2006/main}rPr')
                    a_rPr.set('lang', 'en-US')
                    a_rPr.set('sz', str(int(size * 100)))
                    if bold: a_rPr.set('b', '1')
                    
                    solidFill = etree.SubElement(a_rPr, '{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill')
                    srgbClr = etree.SubElement(solidFill, '{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
                    srgbClr.set('val', f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")
                    
                    latin = etree.SubElement(a_rPr, '{http://schemas.openxmlformats.org/drawingml/2006/main}latin')
                    latin.set('typeface', font_name)
                    
                    for w_t in child.xpath('.//w:t', namespaces=w_ns):
                        a_t = etree.SubElement(a_r, '{http://schemas.openxmlformats.org/drawingml/2006/main}t')
                        a_t.text = w_t.text
                    p._p.append(a_r)
            elif ns == m_ns['m']:
                omaths = child.xpath('.//m:oMath', namespaces=m_ns) if tag_name == 'oMathPara' else [child]
                for omath in omaths:
                    mc_ns = "http://schemas.openxmlformats.org/markup-compatibility/2006"
                    a14_ns = "http://schemas.microsoft.com/office/drawing/2010/main"
                    alt_content = etree.Element(f"{{{mc_ns}}}AlternateContent", nsmap={'mc': mc_ns, 'a14': a14_ns})
                    choice = etree.SubElement(alt_content, f"{{{mc_ns}}}Choice", Requires="a14")
                    a14_m = etree.SubElement(choice, f"{{{a14_ns}}}m")
                    a14_m.append(omath)
                    p._p.append(alt_content)

def _get_content_height(text, width_in, font_size):
    if not text: return 0.35
    if render_math_text: text = render_math_text(text)
    lines = text.split('\n')
    chars_per_line = max(35, int(width_in / (font_size * 0.0085)))
    total_visual_lines = sum(max(1, (len(l.strip()) + chars_per_line - 1) // chars_per_line) for l in lines)
    # Give a bit more vertical padding per line to prevent clipping
    return max(0.35, total_visual_lines * (font_size * 0.0185))

def _tb(slide, text, l, t, w, h, size, color, bold=True, align=PP_ALIGN.LEFT, wrap=True):
    use_omml = False
    if render_math_text:
        text = render_math_text(text)
        if '$' in text or '\\' in text: use_omml = True

    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = txb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = align
    
    if use_omml:
        _insert_omml_math_into_paragraph(p, text, size, color, bold, 'Cambria', slide)
    else:
        _add_rich_text_fallback(p, text, size, color, bold, 'Cambria')
    return txb

def _shape_text(shape, slide, letter, body, letter_size, body_size, center_v=False):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_bottom = Inches(0)
    tf.margin_right = Inches(0.08)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE if center_v else MSO_ANCHOR.TOP

    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r1 = p.add_run()
    r1.text = f"{letter}. "
    r1.font.bold = True
    r1.font.size = Pt(letter_size)
    r1.font.color.rgb = CYAN
    r1.font.name = 'Cambria'
    
    use_omml = False
    if render_math_text:
        body = render_math_text(body)
        if '$' in body or '\\' in body: use_omml = True

    if use_omml:
        _insert_omml_math_into_paragraph(p, body, body_size, OFF_WHITE, True, 'Cambria', slide)
    else:
        _add_rich_text_fallback(p, body, body_size, OFF_WHITE, True, 'Cambria')

def _logo(slide, logo_path=None):
    if logo_path and Path(logo_path).exists():
        slide.shapes.add_picture(str(logo_path), Inches(LOGO_L), Inches(HDR_TOP - 0.1), width=Inches(LOGO_W))
        return
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

def _calc_badge_width(text, font_size=15.0):
    char_w_sum = 0.0
    for ch in text:
        if ch in ', -/': char_w_sum += font_size * 0.0045
        elif ch in '1I': char_w_sum += font_size * 0.0050
        elif ch in 'MW': char_w_sum += font_size * 0.0095
        else: char_w_sum += font_size * 0.0078
    return round(char_w_sum + 0.36, 2)

def _can_fit_1x4(options, text_width=OPT_TEXT_W_1X4):
    if not options or len(options) < 4: return False
    for letter in "ABCD":
        text = str(options.get(letter, "")).strip()
        if not text: return False
        if len(text) > 32: return False
        if _get_content_height(text, text_width, 16) > 0.75: return False
    return True

def _parse_match_col(stem: str):
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

    digit_items = re.findall(r'\((i{1,3}|iv|v|\d|I{1,3}|IV|V)\)\s*(.*?)(?=\s*\((?:i{1,3}|iv|v|\d|I{1,3}|IV|V|[a-dA-D])\)|\s*$)', rest, re.DOTALL)
    letter_items = re.findall(r'\(([a-dA-D])\)\s*(.*?)(?=\s*\((?:i{1,3}|iv|v|\d|I{1,3}|IV|V|[a-dA-D])\)|\s*$)', rest, re.DOTALL)

    col1_items = [f"({n})  {t.strip()}" for n, t in digit_items]
    col2_items = [f"({l})  {t.strip()}" for l, t in letter_items]

    return intro, col1_label, col2_label, col1_items, col2_items

class LayoutEngine:
    def __init__(self, prs, q, logo_path=None, base_dir=None):
        self.prs = prs
        self.q = q
        self.logo_path = logo_path
        self.base_dir = Path(base_dir) if base_dir else None
        self.slide = None
        self.y = Q_TOP
        self.max_y = SH - 0.4
        self.slide_count = 0
        
        # Determine citations
        stem_raw = str(q.get('question') or '')
        self.stem_text, citation = extract_citation(stem_raw)
        
        # Determine options safely (dict, list, or empty)
        raw_opts = q.get("options")
        if isinstance(raw_opts, dict):
            self.opts = dict(raw_opts)
        elif isinstance(raw_opts, list):
            self.opts = {}
            for idx, item in enumerate(raw_opts):
                if isinstance(item, dict):
                    lbl = item.get("label") or chr(65 + idx)
                    txt = item.get("text", "")
                    self.opts[str(lbl).upper().strip(".() ")] = str(txt)
                elif isinstance(item, str):
                    self.opts[chr(65 + idx)] = item
        else:
            self.opts = {}
            
        if not citation and "D" in self.opts:
            cleaned_d, cit_d = extract_citation(str(self.opts["D"]))
            if cit_d:
                citation = cit_d
                self.opts["D"] = cleaned_d
                
        apps = q.get("appearances", [])
        if apps:
            if isinstance(apps, list):
                formatted = []
                for a in apps:
                    if isinstance(a, str):
                        val = a.strip("()[] \t")
                        if val: formatted.append(val)
                    elif isinstance(a, dict):
                        val = str(a.get("text") or a.get("year") or "").strip("()[] \t")
                        if val: formatted.append(val)
                if formatted:
                    citation = ", ".join(formatted)
            elif isinstance(apps, str) and apps.strip():
                citation = apps.strip("()[] \t")
            
        self.citation = citation
        self.new_slide()

    def new_slide(self):
        self.slide = _blank_slide(self.prs)
        _bg(self.slide)
        _logo(self.slide, self.logo_path)
        
        if self.slide_count == 0 and self.citation:
            self._draw_badge(self.citation)
        elif self.slide_count > 0:
            self._draw_badge("Continued")
            
        self.y = Q_TOP
        self.slide_count += 1
        
    def _draw_badge(self, text):
        label = str(text).strip()
        if label.startswith('(') and label.endswith(')'): label = label[1:-1].strip()
        label = label.upper()
        if not label: return
        
        w = _calc_badge_width(label, 15.0)
        _rect(self.slide, M, HDR_TOP, w, HDR_H, fill=BADGE_BG, rounded=True, border=GOLD)
        _rect(self.slide, M + 0.03, HDR_TOP + 0.05, 0.06, HDR_H - 0.10, fill=GOLD, rounded=False)
        txb = self.slide.shapes.add_textbox(Inches(M + 0.15), Inches(HDR_TOP), Inches(w - 0.18), Inches(HDR_H))
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
        
    def ensure_space(self, required_height):
        if self.y + required_height > self.max_y and self.y > Q_TOP + 0.3:
            self.new_slide()

    def render_text(self, text, indent=0.0):
        if not text: return
        text = str(text).strip()
        if not text: return
        w = Q_W - indent
        h = _get_content_height(text, w, 18)
        self.ensure_space(h)
        _tb(self.slide, text, Q_L + indent, self.y, w, h, size=18, color=GOLD, bold=True)
        self.y += h + 0.05
            
    def render_question(self):
        self.render_text(self.stem_text)

    def render_statements(self):
        stmts = self.q.get("statements")
        if not stmts: return
        if isinstance(stmts, dict):
            for k, v in stmts.items():
                self.render_text(f"{k}. {v}", indent=0.3)
        elif isinstance(stmts, list):
            for s in stmts:
                if isinstance(s, dict):
                    lbl = s.get("label", "")
                    txt = s.get("text", "")
                    if lbl and txt:
                        self.render_text(f"{lbl}. {txt}", indent=0.3)
                    else:
                        self.render_text(txt or lbl, indent=0.3)
                elif isinstance(s, str):
                    self.render_text(s, indent=0.3)

    def render_subparts(self):
        subs = self.q.get("subparts")
        if not subs: return
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict):
                    lbl = sub.get("label", "")
                    txt = sub.get("text", "")
                    if lbl and txt:
                        self.render_text(f"{lbl} {txt}", indent=0.3)
                    else:
                        self.render_text(txt or lbl, indent=0.3)
                elif isinstance(sub, str):
                    self.render_text(sub, indent=0.3)
            
    def render_images(self):
        images = self.q.get("images", [])
        if not images: return
        for img_item in images:
            img_path = None
            if isinstance(img_item, dict):
                img_path = img_item.get("path") or img_item.get("filename") or img_item.get("file_path")
            elif isinstance(img_item, str):
                img_path = img_item
                
            if not img_path:
                continue
                
            candidate_paths = [
                Path(img_path),
                (self.base_dir / img_path) if self.base_dir else None,
                Path.cwd() / img_path,
            ]
            resolved_path = None
            for p in candidate_paths:
                if p and p.exists() and p.is_file():
                    resolved_path = p
                    break
                    
            if not resolved_path:
                print(f"[!] Warning: Image {img_path} not found")
                continue
                
            try:
                from PIL import Image
                with Image.open(resolved_path) as img:
                    w_px, h_px = img.size
                aspect = h_px / w_px
                
                target_w = min(Q_W * 0.8, w_px / 100) # Max 80% width or native size assuming 100 DPI
                target_h = target_w * aspect
                
                if target_h > 4.5:
                    target_h = 4.5
                    target_w = target_h / aspect
                    
                self.ensure_space(target_h)
                self.slide.shapes.add_picture(str(resolved_path), Inches(Q_L), Inches(self.y), width=Inches(target_w), height=Inches(target_h))
                self.y += target_h + 0.05
            except Exception as e:
                print(f"[!] Failed to render image {img_path}: {e}")
                
    def render_tables(self):
        if self.q.get("table"):
            self._render_table(self.q["table"])
        for tbl in self.q.get("tables", []):
            if isinstance(tbl, dict) and "rows" in tbl:
                self._render_table(tbl)
                
    def _render_table(self, table_data):
        if not isinstance(table_data, dict): return
        rows = table_data.get("rows", [])
        if not rows or not isinstance(rows, list): return
        num_rows = len(rows)
        num_cols = max(len(r) for r in rows if isinstance(r, list)) if rows else 0
        if num_cols == 0: return
        
        row_h = 0.35
        total_h = num_rows * row_h
        self.ensure_space(total_h)
        
        table_shape = self.slide.shapes.add_table(num_rows, num_cols, Inches(Q_L), Inches(self.y), Inches(Q_W), Inches(total_h))
        tbl = table_shape.table
        
        for r_idx, row in enumerate(rows):
            if not isinstance(row, list): continue
            for c_idx, cell_text in enumerate(row):
                if c_idx < num_cols:
                    cell = tbl.cell(r_idx, c_idx)
                    cell.text = str(cell_text) if cell_text is not None else ""
                    for p in cell.text_frame.paragraphs:
                        p.font.size = Pt(14)
                        p.font.color.rgb = OFF_WHITE
                        p.font.name = 'Cambria'
        self.y += total_h + 0.05
        
    def render_options(self):
        opts = self.opts
        if not opts: return
        
        if _can_fit_1x4(opts):
            h_a = _get_content_height(str(opts.get('A', '')), OPT_TEXT_W_1X4, 16)
            h_b = _get_content_height(str(opts.get('B', '')), OPT_TEXT_W_1X4, 16)
            h_c = _get_content_height(str(opts.get('C', '')), OPT_TEXT_W_1X4, 16)
            h_d = _get_content_height(str(opts.get('D', '')), OPT_TEXT_W_1X4, 16)
            row_h = max(0.50, h_a, h_b, h_c, h_d)
            
            self.ensure_space(row_h)
            for i, letter in enumerate("ABCD"):
                l = M + i * (OPT_W_1X4 + GAP_1X4)
                txb = self.slide.shapes.add_textbox(Inches(l), Inches(self.y), Inches(OPT_W_1X4), Inches(row_h))
                _shape_text(txb, self.slide, letter, str(opts.get(letter, "")), letter_size=16, body_size=16)
            self.y += row_h + 0.05
        else:
            h_a = _get_content_height(str(opts.get('A', '')), OPT_TEXT_W_2X2, 16)
            h_b = _get_content_height(str(opts.get('B', '')), OPT_TEXT_W_2X2, 16)
            row1_h = max(0.50, h_a, h_b)
            
            self.ensure_space(row1_h)
            col_left = M
            col_right = M + OPT_W_2X2 + GAP_2X2
            
            if "A" in opts:
                txb_a = self.slide.shapes.add_textbox(Inches(col_left), Inches(self.y), Inches(OPT_W_2X2), Inches(row1_h))
                _shape_text(txb_a, self.slide, "A", str(opts.get("A", "")), 16, 16)
            if "B" in opts:
                txb_b = self.slide.shapes.add_textbox(Inches(col_right), Inches(self.y), Inches(OPT_W_2X2), Inches(row1_h))
                _shape_text(txb_b, self.slide, "B", str(opts.get("B", "")), 16, 16)
                
            self.y += row1_h + GAP_V_2X2
            
            h_c = _get_content_height(str(opts.get('C', '')), OPT_TEXT_W_2X2, 16)
            h_d = _get_content_height(str(opts.get('D', '')), OPT_TEXT_W_2X2, 16)
            row2_h = max(0.50, h_c, h_d)
            
            self.ensure_space(row2_h)
            if "C" in opts:
                txb_c = self.slide.shapes.add_textbox(Inches(col_left), Inches(self.y), Inches(OPT_W_2X2), Inches(row2_h))
                _shape_text(txb_c, self.slide, "C", str(opts.get("C", "")), 16, 16)
            if "D" in opts:
                txb_d = self.slide.shapes.add_textbox(Inches(col_right), Inches(self.y), Inches(OPT_W_2X2), Inches(row2_h))
                _shape_text(txb_d, self.slide, "D", str(opts.get("D", "")), 16, 16)
            self.y += row2_h + 0.05

    def render_match_col(self):
        stem = self.stem_text
        intro, col1_lbl, col2_lbl, col1_items, col2_items = _parse_match_col(stem)
        
        intro_h = _get_content_height(intro, Q_W, 18)
        self.ensure_space(intro_h)
        _tb(self.slide, intro, Q_L, self.y, Q_W, intro_h, size=18, color=GOLD, bold=True)
        self.y += intro_h + 0.05
        
        self.ensure_space(MC_CH_H + 1.0) # Ensure space for headers and items
        
        # Headers
        _tb(self.slide, col1_lbl.upper(), MC_LCOL, self.y, MC_CW, MC_CH_H, size=14, color=CYAN, bold=True)
        _tb(self.slide, col2_lbl.upper(), MC_RCOL, self.y, MC_CW, MC_CH_H, size=14, color=CYAN, bold=True)
        
        n = max(len(col1_items), len(col2_items), 1)
        row_h = max(0.32, MC_C_H / n)
        actual_col_h = n * row_h
        
        _rect(self.slide, MC_LCOL + MC_CW + 0.07, self.y, 0.02, MC_CH_H + 0.05 + actual_col_h, fill=DIVIDER_LINE, rounded=False)
        self.y += MC_CH_H + 0.05
        
        c_top = self.y
        for i, item in enumerate(col1_items):
            _tb(self.slide, item, MC_LCOL, c_top + i * row_h, MC_CW, row_h, size=14, color=OFF_WHITE)
            
        for i, item in enumerate(col2_items):
            _tb(self.slide, item, MC_RCOL, c_top + i * row_h, MC_CW, row_h, size=14, color=OFF_WHITE)
            
        self.y += actual_col_h + 0.05
        
        opts = self.opts
        if not opts: return
        for i, letter in enumerate("ABCD"):
            opt_text = str(opts.get(letter, ""))
            opt_h = max(MC_OPT_H, _get_content_height(opt_text, MC_OPT_W - 0.5, 14))
            self.ensure_space(opt_h)
            txb = self.slide.shapes.add_textbox(Inches(M), Inches(self.y), Inches(MC_OPT_W), Inches(opt_h))
            _shape_text(txb, self.slide, letter, opt_text, 14, 14, center_v=True)
            self.y += opt_h + MC_OPT_GAP

def build_title_slide(prs, title, subtitle, logo_path=None):
    slide = _blank_slide(prs)
    _bg(slide)
    _logo(slide, logo_path)
    _rect(slide, M, 3.15, SW - 2 * M, 0.04, fill=GOLD, rounded=False)
    _tb(slide, title, M, 1.8, SW - 2 * M, 1.2, size=44, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    _tb(slide, subtitle, M, 3.35, SW - 2 * M, 0.65, size=24, color=DIM_WHITE, align=PP_ALIGN.CENTER)

def build_divider_slide(prs, section, logo_path=None):
    slide = _blank_slide(prs)
    _bg(slide)
    _logo(slide, logo_path)
    _rect(slide, M, 2.35, 0.07, 2.8, fill=GOLD, rounded=False)
    _tb(slide, section.upper(), M + 0.22, 2.35, SW - 2 * M - 0.22, 2.8, size=50, color=GOLD, bold=True, align=PP_ALIGN.LEFT)

def generate(json_path: Path, output_path: Path, title="Chemistry Midterm — MCQ Practice", subtitle=None, logo_path=None):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        questions = data.get("questions", [])
    elif isinstance(data, list):
        questions = data
    else:
        questions = []

    # Filter out questions that explicitly failed parsing, but preserve older JSONs without parsed_ok key
    ok_qs = [q for q in questions if q.get("parsed_ok", True) is not False]

    if subtitle is None:
        subtitle = f"{len(ok_qs)} Questions  ·  For: Boards"

    prs = Presentation()
    prs.slide_width  = Inches(SW)
    prs.slide_height = Inches(SH)

    print(f"[*] Building deck for {len(ok_qs)} questions ...")
    build_title_slide(prs, title, subtitle, logo_path)

    last_section = None
    match_col_count = 0
    open_count = 0
    divider_count = 0

    base_dir = json_path.parent

    for q in ok_qs:
        section = q.get("section") or "General"
        if section != last_section:
            # build_divider_slide(prs, section, logo_path)
            last_section = section

        q_type = q.get("question_type", "mcq")
        is_match = (
            q_type in ("match_the_column", "match_list", "match")
            and not q.get("table")
        )

        if q_type == "divider":
            build_divider_slide(prs, q.get("question", "Section"), logo_path)
            divider_count += 1
        else:
            engine = LayoutEngine(prs, q, logo_path, base_dir=base_dir)
            if is_match:
                engine.render_match_col()
                match_col_count += 1
            else:
                engine.render_question()
                engine.render_statements()
                engine.render_subparts()
                engine.render_tables()
                engine.render_images()
                engine.render_options()
                if q_type in ("open", "subjective", "numerical", "short_answer", "long_answer", "fill_in_the_blanks") or not engine.opts:
                    open_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prs.save(str(output_path))
    except PermissionError:
        from datetime import datetime
        alt_path = output_path.with_name(f"{output_path.stem}_{datetime.now().strftime('%H%M%S')}.pptx")
        print(f"⚠️  Permission denied. Saved to: {alt_path}")
        prs.save(str(alt_path))
        output_path = alt_path

    total = len(prs.slides)
    mcq_count = len(ok_qs) - match_col_count - open_count - divider_count
    
    print(f"\n[OK] Saved {total} slides -> {output_path}")
    print(f"    1 title  +  {divider_count} dividers  "
          f"+  {mcq_count} MCQ  "
          f"+  {open_count} open/SA  "
          f"+  {match_col_count} match-the-column")

    # Verification pass to confirm no literal uncompiled LaTeX markers leaked
    leaked_count = 0
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if hasattr(shape, "text_frame"):
                if '$' in shape.text or '^{' in shape.text:
                    leaked_count += 1
    if leaked_count > 0:
        print(f"[!] Warning: {leaked_count} potential raw math markers detected on slides.")
    else:
        print("✅  Verification complete: No leaked math tokens detected.")

def _auto_pptx_path(json_path: Path) -> Path:
    return json_path.with_suffix(".pptx")

def main():
    ap = argparse.ArgumentParser(description="Generate a PPTX slide deck from questions JSON file.")
    ap.add_argument("input", help="Path to questions.json")
    ap.add_argument("output", nargs="?", default=None, help="Output .pptx path")
    ap.add_argument("--title", default="Chemistry Midterm — MCQ Practice", help="Deck title on the title slide")
    ap.add_argument("--subtitle", default=None, help="Subtitle")
    ap.add_argument("--logo", default=None, help="Path to logo PNG/JPG")
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
        logo_path=Path(args.logo) if args.logo else default_logo
    )

if __name__ == "__main__":
    main()
