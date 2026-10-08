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

def _add_rich_text_fallback(p, text, size, color, bold=True, font_name='Cambria', italic=False):
    if not isinstance(color, RGBColor):
        color = RGBColor(*color)
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
            run.font.italic = italic
            run.font.name = font_name
            if is_sub:  run.font._element.set('baseline', '-25000')
            elif is_sup: run.font._element.set('baseline', '30000')


def _record_render_diagnostic(diagnostics, context, code, reason, fallback, severity="warning", original=None):
    if diagnostics is None:
        return
    context = context or {}
    component_id = context.get("component_id")
    option_match = re.match(r"option:([A-E])", str(component_id or ""), re.I)
    component_type = ("option" if option_match else "table" if str(component_id or "").startswith("table:")
                     else "stem" if component_id in (None, "question", "stem") else str(component_id).split(":", 1)[0])
    render_path = ("compatibility" if code == "MATH_COMPATIBILITY_RENDERED"
                   else "fallback" if code in ("MATH_RENDER_FAILED", "MATH_FALLBACK_USED") else None)
    entry = {
        "code": code, "severity": severity, "reason": reason,
        "fallback": fallback,
        "fallback_text": fallback if render_path else None,
        "source_text": str(original) if original is not None else None,
        "render_path": render_path,
        "status": "ok" if render_path == "compatibility" else "degraded" if render_path == "fallback" else None,
        "question_id": context.get("question_id"),
        "component_id": context.get("component_id"),
        "component_type": component_type,
        "option_label": option_match.group(1).upper() if option_match else None,
        "source_block_id": _normalize_block_id(context.get("source_block_id")),
        "node_id": context.get("node_id"),
        "math_id": context.get("math_id"),
    }
    if original is not None:
        entry["original"] = str(original)
    diagnostics.append(entry)


def _record_math_outcome(context, render_path, source_text, fallback_text=None,
                        native_entries=0, fallback_entries=0,
                        alternate_fallback_entries=0, reason=None):
    context = context or {}
    collector = context.get("math_outcomes")
    if not isinstance(collector, list):
        return
    math_id = context.get("math_id")
    if not math_id:
        math_id = _canonical_math_id({}, context, 0)
    component_id = context.get("component_id")
    option_match = re.match(r"option:([A-E])", str(component_id or ""), re.I)
    component_type = ("option" if option_match else "table" if str(component_id or "").startswith("table:")
                     else "stem" if component_id in (None, "question", "stem") else str(component_id).split(":", 1)[0])
    outcome = {
        "math_id": str(math_id),
        "question_id": context.get("question_id"),
        "component_type": component_type,
        "option_label": option_match.group(1).upper() if option_match else None,
        "source_block_id": _normalize_block_id(context.get("source_block_id")),
        "node_id": context.get("node_id"),
        "render_path": render_path,
        "status": "ok" if render_path in ("native", "compatibility") else "degraded" if render_path == "fallback" else "failed",
        "source_text": str(source_text or ""),
        "fallback_text": str(fallback_text or ""),
        "native_entries": int(native_entries),
        "fallback_entries": int(fallback_entries),
        "alternate_fallback_entries": int(alternate_fallback_entries),
    }
    if reason:
        outcome["reason"] = str(reason)
    previous = next((i for i, item in enumerate(collector) if item.get("math_id") == outcome["math_id"]), None)
    if previous is None:
        collector.append(outcome)
    else:
        collector[previous] = outcome


def _normalize_block_id(block_id):
    """Normalize renderer-facing source IDs to the schema's string representation."""
    return None if block_id is None else str(block_id)


def _fallback_math_text(value):
    """Make a readable compatibility expression from LaTeX or OMML text."""
    value = str(value or "").replace(r"\_", "_").replace(r"\^", "^")
    value = re.sub(r"(?<!\\)(?:\^|_)\{\s*\}", "", value)
    value = re.sub(r"\\sqrt\(([^()]*)\)", r"\\sqrt{\1}", value)
    try:
        from src.formula_render import _simplify_latex_for_pandoc, latex_to_readable
        value = _simplify_latex_for_pandoc(value)
        readable = latex_to_readable(value)
    except ImportError:
        readable = value.strip().replace("$", "")
    readable = re.sub(r"(?<!\\)(?:\^|_)\{\s*\}", "", readable)
    readable = re.sub(r"\\(?=[√×·±≤≥≠∞∫ΣΠ])", "", readable)
    return readable.strip()


def build_readable_fallback(node):
    """Return readable text for exactly one canonical math node or value."""
    if isinstance(node, dict):
        value = node.get("value") or _canonical_math_latex(node)
    else:
        value = node
    return _fallback_math_text(value)


def _canonical_math_latex(node):
    """Serialize canonical math nodes to the existing LaTeX adapter contract."""
    kind = node.get("kind", "")
    children = node.get("children") or []
    value = str(node.get("value") or "").strip().strip("$")

    def operand(role):
        found = next((child for child in children if child.get("kind") == role), None)
        if found is None:
            return ""
        nested = found.get("children") or []
        return _canonical_math_latex(nested[0]) if nested else str(found.get("value") or "")

    if kind == "fraction":
        return rf"\frac{{{operand('numerator')}}}{{{operand('denominator')}}}"
    if kind in ("superscript", "subscript"):
        base = operand("base")
        script = operand("superscript" if kind == "superscript" else "subscript")
        marker = "^" if kind == "superscript" else "_"
        return f"{base}{marker}{{{script}}}"
    if kind == "subsup":
        return f"{operand('base')}_{{{operand('subscript')}}}^{{{operand('superscript')}}}"
    if kind == "radical":
        degree, radicand = operand("degree"), operand("radicand")
        return rf"\sqrt[{degree}]{{{radicand}}}" if degree else rf"\sqrt{{{radicand}}}"
    if kind == "nary":
        operator = str((node.get("formatting") or {}).get("operator") or "∑")
        latex_operator = {"∫": r"\int", "∑": r"\sum", "∏": r"\prod"}.get(operator, operator)
        limits = ""
        if operand("lower_limit"):
            limits += f"_{{{operand('lower_limit')}}}"
        if operand("upper_limit"):
            limits += f"^{{{operand('upper_limit')}}}"
        return f"{latex_operator}{limits} {operand('body')}"
    if kind == "function":
        return f"{operand('function_name')} {operand('argument')}"
    if kind in ("lower_limit", "upper_limit", "accent", "bar", "delimiter", "group"):
        return "".join(_canonical_math_latex(child) for child in children) or value
    if kind in ("matrix", "matrix_row", "equation_array"):
        if kind == "matrix_row":
            return " & ".join(_canonical_math_latex(child) for child in children)
        rows = [_canonical_math_latex(child) for child in children]
        return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"
    if children:
        return "".join(_canonical_math_latex(child) for child in children)
    return value


def _style_native_math_color(math_element, color, bold=False, italic=False):
    """Reject unverified native math styling; compatibility text is the safe path."""
    raise RuntimeError("native math styling is deferred; use compatibility text rendering")


def _append_alt_math(p, omath, fallback_text, size, color, bold, font_name, italic=False):
    """Reject the obsolete inline AlternateContent architecture."""
    raise RuntimeError("inline native math is deferred; use compatibility text rendering")


def _render_canonical_inline(p, nodes, size, color, bold, font_name, diagnostics, context):
    """Render known canonical inline nodes structurally and diagnose fallbacks."""
    if not isinstance(color, RGBColor):
        color = RGBColor(*color)
    rendered_any = False
    for index, node in enumerate(nodes or []):
        node = dict(node) if isinstance(node, dict) else {}
        kind = node.get("kind", "")
        node_context = dict(context or {})
        node_context["source_block_id"] = node.get("source_block_id", node_context.get("source_block_id"))
        node_context["node_id"] = _canonical_node_id(node, index)
        if kind == "math_sequence":
            node_context["math_id"] = _canonical_math_id(node, node_context, index)
        value = str(node.get("value") or "")
        formatting = node.get("formatting") or {}
        if kind == "line_break":
            p.add_line_break()
            rendered_any = True
        elif kind == "text":
            align = node.get("vertical_align")
            run = p.add_run()
            run.text = value
            run.font.name = font_name
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.font.bold = bool(formatting.get("bold", bold))
            run.font.italic = bool(formatting.get("italic", False))
            run.font.underline = bool(formatting.get("underline", False))
            if align == "superscript":
                run.font._element.set("baseline", "30000")
            elif align == "subscript":
                run.font._element.set("baseline", "-25000")
            rendered_any = True
        elif kind == "image":
            run = p.add_run()
            run.text = "[Image unavailable]"
            run.font.size = Pt(size)
            run.font.color.rgb = color
            _record_render_diagnostic(diagnostics, node_context, "RENDER_NODE_UNSUPPORTED",
                                      "inline image node requires block media placement", "inline placeholder")
            rendered_any = True
        elif kind == "math_sequence":
            readable = build_readable_fallback(node)
            if readable:
                _add_rich_text_fallback(p, readable, size, color,
                                        bool(formatting.get("bold", bold)), font_name,
                                        italic=bool(formatting.get("italic", False)))
                _record_render_diagnostic(diagnostics, node_context, "MATH_COMPATIBILITY_RENDERED",
                                          "native inline math is deferred for PowerPoint package safety",
                                          readable, severity="info", original=value)
                _record_math_outcome(node_context, "compatibility", value, readable)
            else:
                _record_render_diagnostic(diagnostics, node_context, "MATH_RENDER_FAILED",
                                          "canonical math node has no readable expression",
                                          "failed", severity="error", original=value)
                _record_math_outcome(node_context, "failed", value, reason="empty canonical math node")
            rendered_any = True
        else:
            if value:
                run = p.add_run()
                run.text = value
                run.font.size = Pt(size)
                run.font.color.rgb = color
                _record_render_diagnostic(diagnostics, node_context, "RENDER_NODE_UNSUPPORTED",
                                          f"unsupported canonical node kind: {kind or 'unknown'}", "node value")
                rendered_any = True
            else:
                _record_render_diagnostic(diagnostics, node_context, "INVALID_CANONICAL_NODE",
                                          f"node kind {kind or 'unknown'} has no renderable value", "omitted node", "error")
    return rendered_any

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

def _insert_omml_math_into_paragraph(p, markdown_text, size, color, bold=True, font_name='Cambria',
                                     slide=None, diagnostic_context=None, diagnostics=None):
    source = str(markdown_text or "")
    matches = list(re.finditer(r"\$(.+?)\$", source, flags=re.S))
    unmatched_delimiter = source.count("$") % 2 != 0
    if not matches and not unmatched_delimiter and re.search(r"\\(?:frac|sqrt|int|sum|prod|vec|hat)|(?:\^|_)\{", source):
        source = f"${source.strip('$')}$"
        matches = [re.match(r"(?s)\$(.+)\$", source)]

    if unmatched_delimiter:
        readable = _fallback_math_text(source)
        _add_rich_text_fallback(p, readable, size, color, bold, font_name)
        context = dict(diagnostic_context or {})
        context.setdefault("math_id", _canonical_math_id({}, context, 0))
        _record_render_diagnostic(diagnostics, context, "MATH_FALLBACK_USED",
                                  "unbalanced math delimiters", readable, original=source)
        _record_math_outcome(context, "fallback", source, readable, fallback_entries=1,
                             reason="unbalanced math delimiters")
        return

    if not matches:
        _add_rich_text_fallback(p, source, size, color, bold, font_name)
        return

    try:
        from src.convert.math import convert_math
    except ImportError:
        convert_math = lambda expression: expression

    def node_context(index):
        context = dict(diagnostic_context or {})
        base_id = context.get("node_id") or f"{context.get('component_id', 'component')}-compat"
        context["node_id"] = f"{base_id}:math:{index}"
        if not context.get("math_id"):
            context["math_id"] = _canonical_math_id({}, context, index - 1)
        elif index > 1:
            context["math_id"] = f"{context['math_id']}-FRAGMENT-{index:03d}"
        return context

    def issue_for(expression):
        if expression.count("{") != expression.count("}"):
            return "unbalanced braces in math expression"
        if re.search(r"(?:\^|_)\s*\{\s*\}", expression):
            return "empty script operand in math expression"
        if re.search(r"(?:\^|_)\s*$", expression):
            return "script operator has no operand"
        if "$" in expression:
            return "malformed script or math delimiter in normalized expression"
        if expression.count(r"\begin") != expression.count(r"\end"):
            return "unbalanced LaTeX environment"
        return None

    def render_expression(expression, index):
        context = node_context(index)
        original = expression
        try:
            normalized = convert_math(expression)
        except Exception as exc:
            normalized = expression
            reason = f"math normalization failed: {exc}"
        else:
            reason = issue_for(normalized)
        readable = _fallback_math_text(normalized)
        if reason:
            _add_rich_text_fallback(p, readable, size, color, bold, font_name)
            _record_render_diagnostic(diagnostics, context, "MATH_FALLBACK_USED",
                                      reason, readable, original=original)
            _record_math_outcome(context, "fallback", original, readable, fallback_entries=1, reason=reason)
            return
        _add_rich_text_fallback(p, readable, size, color, bold, font_name)
        _record_render_diagnostic(diagnostics, context, "MATH_COMPATIBILITY_RENDERED",
                                  "native inline math is deferred for PowerPoint package safety",
                                  readable, severity="info", original=original)
        _record_math_outcome(context, "compatibility", original, readable)

    def render_text_chunk(chunk, index):
        if not chunk:
            return
        malformed = bool(re.search(r"(?:\\[_^]|(?<!\\)[_^])\s*\{\s*\}", chunk))
        malformed = malformed or bool(re.search(r"\\(?:sqrt|frac)\s*\(", chunk))
        if malformed:
            readable = _fallback_math_text(chunk)
            _add_rich_text_fallback(p, readable, size, color, bold, font_name)
            context = node_context(index)
            _record_render_diagnostic(diagnostics, context, "MATH_FALLBACK_USED",
                                      "malformed math fragment outside a delimited math node",
                                      readable, original=chunk)
        else:
            _add_rich_text_fallback(p, chunk, size, color, bold, font_name)

    cursor = 0
    for index, match in enumerate(matches, 1):
        render_text_chunk(source[cursor:match.start()], index)
        expression = match.group(1) if match.lastindex else source[match.start() + 1:match.end() - 1]
        render_expression(expression, index)
        cursor = match.end()
    render_text_chunk(source[cursor:], len(matches) + 1)

def _get_content_height(text, width_in, font_size):
    if not text: return 0.35
    lines = text.split('\n')
    chars_per_line = max(35, int(width_in / (font_size * 0.0085)))
    total_visual_lines = sum(max(1, (len(l.strip()) + chars_per_line - 1) // chars_per_line) for l in lines)
    # Give a bit more vertical padding per line to prevent clipping
    return max(0.35, total_visual_lines * (font_size * 0.0185))

def _tb(slide, text, l, t, w, h, size, color, bold=True, align=PP_ALIGN.LEFT, wrap=True,
        diagnostics=None, diagnostic_context=None):
    use_omml = bool(re.search(r"\$[^$]+\$", str(text)))

    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = txb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = align
    
    if use_omml:
        _insert_omml_math_into_paragraph(p, text, size, color, bold, 'Cambria', slide,
                                          diagnostic_context=diagnostic_context,
                                          diagnostics=diagnostics)
    else:
        _add_rich_text_fallback(p, text, size, color, bold, 'Cambria')
    return txb

def _shape_text(shape, slide, letter, body, letter_size, body_size, center_v=False,
                inline_nodes=None, diagnostic_context=None, diagnostics=None,
                body_color=CYAN, body_bold=True):
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
    
    if inline_nodes:
        _render_canonical_inline(p, inline_nodes, body_size, body_color, body_bold, 'Cambria',
                                 diagnostics, diagnostic_context)
        return

    use_omml = bool(re.search(r"\$[^$]+\$", str(body)))

    if use_omml:
        _insert_omml_math_into_paragraph(p, body, body_size, body_color, body_bold, 'Cambria', slide,
                                          diagnostic_context=diagnostic_context,
                                          diagnostics=diagnostics)
    else:
        _add_rich_text_fallback(p, body, body_size, body_color, body_bold, 'Cambria')

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


def _canonical_node_text(node):
    if node.get("kind") == "line_break":
        return "\n"
    value = str(node.get("value") or "")
    align = node.get("vertical_align")
    if align == "subscript":
        return value.translate(str.maketrans({**dict(zip("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")), **dict(zip("aehijklmnoprstuvx", "ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))}))
    if align == "superscript":
        return value.translate(str.maketrans({**dict(zip("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")), "−": "⁻"}))
    return value


def _normalize_match_text(value):
    value = str(value or "")
    scripts = str.maketrans({
        **dict(zip("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ", "0123456789+-=()aehijklmnoprstuvx")),
        **dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾", "0123456789+-=()")),
        "−": "-",
    })
    value = value.translate(scripts)
    value = re.sub(r"\\?([_^])\s*\{([^{}]*)\}", r"\2", value)
    value = re.sub(r"\\?([_^])\s*([A-Za-z0-9+-])", r"\2", value)
    value = re.sub(r"\s*([=+\-×*/<>])\s*", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalized_span(haystack, needle):
    """Find normalized text while returning offsets in the original string."""
    def normalize_with_offsets(value):
        chars, offsets = [], []
        script_brace = False
        script_marker = False
        for index, char in enumerate(value):
            if script_marker and char != "{":
                script_marker = False
            if char in "^_" and index + 1 < len(value):
                script_marker = True
                continue
            if char == "{" and script_marker:
                script_brace = True
                script_marker = False
                continue
            if script_brace and char == "}":
                script_brace = False
                continue
            normalized = _normalize_match_text(char)
            if len(normalized) > 1:
                for mapped in normalized:
                    chars.append(mapped)
                    offsets.append((index, index + 1))
                continue
            char = normalized or char
            if char.isspace():
                next_char = next((candidate for candidate in value[index + 1:] if not candidate.isspace()), "")
                operators = "=+-×*/<>"
                if (chars and chars[-1] in operators) or next_char in operators:
                    continue
                if chars and chars[-1] != " ":
                    chars.append(" ")
                    offsets.append((index, index + 1))
                elif offsets:
                    offsets[-1] = (offsets[-1][0], index + 1)
            else:
                chars.append(char)
                offsets.append((index, index + 1))
        while chars and chars[-1] == " ":
            chars.pop()
            offsets.pop()
        return "".join(chars), offsets

    normalized_haystack, offsets = normalize_with_offsets(haystack)
    normalized_needle, _ = normalize_with_offsets(needle)
    pos = normalized_haystack.find(normalized_needle) if normalized_needle else -1
    if pos < 0:
        return None
    return offsets[pos][0], offsets[pos + len(normalized_needle) - 1][1]


def _slice_canonical_nodes(nodes, start, end):
    out, cursor = [], 0
    for original in nodes:
        node = dict(original)
        shown = _canonical_node_text(node)
        node_start, node_end = cursor, cursor + len(shown)
        cursor = node_end
        left, right = max(start, node_start), min(end, node_end)
        if left >= right:
            continue
        if left == node_start and right == node_end:
            out.append(node)
        elif node.get("kind") == "text":
            node["value"] = shown[left - node_start:right - node_start]
            out.append(node)
        else:
            return None
    return out


def _inline_for_component(question, text, component_id):
    nodes = question.get("inline_content") or []
    if not nodes or not text:
        return None, None
    target_text = str(text)
    citation_pattern = re.compile(r"^\s*(?:\[[^\]]*(?:19|20)\d{2}[^\]]*\]|\([^)]*(?:19|20)\d{2}[^)]*\))\s*$")
    nodes = [node for node in nodes if not (
        isinstance(node, dict) and node.get("kind") == "text"
        and citation_pattern.fullmatch(str(node.get("value") or ""))
        and str(node.get("value") or "").strip() not in target_text
    )]
    grouped = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        source_id = node.get("source_block_id", "unknown")
        grouped.setdefault(str(source_id), []).append(node)
    role_by_id = {str(block.get("block_id")): block.get("role")
                  for block in question.get("source_blocks", []) if isinstance(block, dict)}
    preferred = "option" if str(component_id).startswith("option:") else "stem"
    candidates = []
    preferred_nodes = []
    previous_source = None
    for source_id, group in grouped.items():
        if role_by_id.get(source_id) != preferred:
            continue
        if preferred_nodes and source_id != previous_source:
            preferred_nodes.append({"kind": "line_break", "value": "\n", "source_block_id": source_id})
        preferred_nodes.extend(group)
        previous_source = source_id
    if preferred_nodes:
        candidates.append(preferred_nodes)
    component_source = _component_source_block_id(question, component_id)
    if component_source is not None:
        source_key = str(component_source)
        parent_key = source_key.split(".part_", 1)[0]
        selected = grouped.get(source_key) or grouped.get(parent_key)
        if selected is not None:
            candidates.append(selected)
    candidates += [items for source_id, items in grouped.items()
                   if role_by_id.get(source_id) == preferred and items not in candidates]
    candidates += [items for source_id, items in grouped.items() if items not in candidates]
    # A component may span multiple source paragraphs; keep source order stable.
    all_nodes = []
    previous_source = None
    for source_id, group in grouped.items():
        if all_nodes and source_id != previous_source:
            all_nodes.append({"kind": "line_break", "value": "\n", "source_block_id": source_id})
        all_nodes.extend(group)
        previous_source = source_id
    candidates.append(all_nodes)
    target_values = [str(text)]
    stripped_label = re.sub(r"^\s*(?:(?:Statement\s*)?[A-Ea-eIVXivx1-5]+)[.)\:]\s*", "", str(text))
    if stripped_label != str(text):
        target_values.append(stripped_label)
    if str(component_id).startswith("statement:"):
        target_values.append(re.sub(r"^\s*(?:Statement\s*)?[A-Ea-e][.)\:]\s*", "", str(text), flags=re.I))
    target_values.append(re.sub(r"^\s*Statement\s+[A-Ea-eIVXivx1-5]+\s*[:.)]\s*", "", str(text), flags=re.I))
    target_values = list(dict.fromkeys(_normalize_match_text(value) for value in target_values if value.strip()))
    option_letter = str(component_id).split(":", 1)[1][:1].upper() if str(component_id).startswith("option:") else None
    for group in candidates:
        display = "".join(_canonical_node_text(node) for node in group)
        views = [(0, display)]
        if option_letter:
            labels = list(re.finditer(r"(?i)(?<![A-Za-z0-9])([A-D])\s*[.)]\s*", display))
            selected_label = next((pos for pos, label in enumerate(labels)
                                   if label.group(1).upper() == option_letter), None)
            if selected_label is not None:
                label = labels[selected_label]
                end = labels[selected_label + 1].start() if selected_label + 1 < len(labels) else len(display)
                views = [(label.end(), display[label.end():end])]
        for view_offset, view in views:
            for target in target_values:
                span = _normalized_span(view, target)
                if span is None:
                    continue
                span = (span[0] + view_offset, span[1] + view_offset)
                sliced = _slice_canonical_nodes(group, *span)
                if sliced:
                    first = sliced[0]
                    source_id = first.get("source_block_id")
                    return sliced, source_id
    return None, None


def _component_source_block_id(question, component_id):
    """Resolve the source block attached to a rendered component, if known."""
    source_blocks = [block for block in question.get("source_blocks", []) if isinstance(block, dict)]
    if str(component_id).startswith("option:"):
        letter = str(component_id).split(":", 1)[1].upper()
        option_blocks = [block for block in source_blocks if block.get("role") == "option"]
        index = ord(letter[:1]) - ord("A") if letter else -1
        if 0 <= index < len(option_blocks):
            return option_blocks[index].get("block_id")
    stem_blocks = [block for block in source_blocks if block.get("role") == "stem"]
    if stem_blocks:
        return stem_blocks[0].get("block_id")
    return None


def _canonical_node_id(node, index):
    source = node.get("source") or {}
    explicit = source.get("node_id") or node.get("node_id")
    if explicit:
        return explicit
    return f"{node.get('source_block_id', 'unknown')}:{node.get('source_order', 'unknown')}:{index + 1}"


def _canonical_math_id(node, context, index):
    source = node.get("source") or {}
    explicit = node.get("math_id") or source.get("math_id")
    if explicit:
        return str(explicit)
    question = str((context or {}).get("question_id") or "Q").strip()
    question = f"Q{int(question):02d}" if question.isdigit() else question.upper()
    source_id = node.get("source_block_id") or (context or {}).get("source_block_id")
    if source_id is not None:
        component = "BLOCK-" + re.sub(r"[^A-Za-z0-9]+", "-", str(source_id)).strip("-").upper()
    else:
        component = str((context or {}).get("component_id") or "stem")
        if component.startswith("option:"):
            component = f"OPTION-{component.split(':', 1)[1].split(':', 1)[0]}"
        elif component.startswith("table:"):
            component = "TABLE-" + component.split(":", 1)[1].replace(":", "-")
        elif component in ("question", "stem"):
            component = "STEM"
        else:
            component = re.sub(r"[^A-Za-z0-9]+", "-", component).strip("-").upper() or "INLINE"
    ordinal = node.get("inline_index", index)
    try:
        ordinal = int(ordinal) + 1
    except (TypeError, ValueError):
        ordinal = index + 1
    return f"{question}-{component}-MATH-{ordinal:03d}"


def _count_canonical_math_nodes(questions):
    count = 0
    for question in questions:
        if not isinstance(question, dict):
            continue
        stack = [question.get("inline_content") or []]
        table = question.get("table") or {}
        if isinstance(table, dict):
            stack.append(table.get("cell_content") or [])
            for item in table.get("tables") or []:
                if isinstance(item, dict):
                    stack.append(item.get("cell_content") or [])
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                is_math_node = current.get("kind") == "math_sequence"
                if is_math_node:
                    count += 1
                else:
                    stack.extend(value for key, value in current.items()
                                 if key in ("children", "inline_content", "cell_content"))
            elif isinstance(current, list):
                stack.extend(current)
    return count


def _collect_canonical_math_ids(questions):
    """Inventory stable render IDs for canonical math nodes before reconciliation."""
    results = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_id = question.get("id")
        source_roles = {}
        option_sources = []
        for block in question.get("source_blocks", []):
            if not isinstance(block, dict):
                continue
            source_id = str(block.get("block_id", ""))
            role = block.get("role")
            source_roles[source_id] = role
            if role == "option":
                option_sources.append(source_id)
        option_labels = {source: f"option:{chr(65 + i)}" for i, source in enumerate(option_sources)}

        def visit(items, default_component, table_cell=None):
            if isinstance(items, dict):
                if items.get("kind") == "math_sequence":
                    source_id = str(items.get("source_block_id", ""))
                    parent_source = source_id.split(".part_", 1)[0]
                    component_id = default_component
                    if table_cell is not None:
                        component_id = f"table:{table_cell[0]}:{table_cell[1]}"
                    elif parent_source in option_labels:
                        component_id = option_labels[parent_source]
                    context = {"question_id": question_id, "component_id": component_id}
                    results.append({
                        "math_id": _canonical_math_id(items, context, items.get("inline_index", len(results))),
                        "question_id": question_id,
                        "component_type": "table" if component_id.startswith("table:")
                                          else "option" if component_id.startswith("option:") else "stem",
                        "option_label": component_id.split(":", 1)[1] if component_id.startswith("option:") else None,
                        "source_block_id": _normalize_block_id(items.get("source_block_id")),
                        "source_text": str(items.get("value") or ""),
                    })
                    return
                for key in ("children", "inline_content", "cell_content"):
                    if key in items:
                        visit(items[key], default_component, table_cell)
            elif isinstance(items, list):
                for child in items:
                    visit(child, default_component, table_cell)

        visit(question.get("inline_content") or [], "question")
        table = question.get("table")
        tables = [table] if isinstance(table, dict) else []
        tables.extend(item for item in question.get("tables", []) if isinstance(item, dict))
        for table_index, table_data in enumerate(tables):
            for row_index, row in enumerate(table_data.get("cell_content") or []):
                if not isinstance(row, list):
                    continue
                for cell_index, cell in enumerate(row):
                    if isinstance(cell, dict):
                        visit(cell.get("inline_content") or [], "table", (row_index, cell_index))
    return results


def _count_pptx_math_entries(pptx_path):
    native = fallback = 0
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            root = etree.fromstring(archive.read(name))
            native += len(root.xpath(".//*[local-name()='m' and namespace-uri()='http://schemas.microsoft.com/office/drawing/2010/main']"))
            fallback += len(root.xpath(".//*[local-name()='AlternateContent']/*[local-name()='Fallback']"))
    return native, fallback

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
        self.render_diagnostics = []
        self.math_outcomes = []
        
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
            
        if q.get("needs_review") or q.get("parsed_ok") is False:
            citation = f"{citation} · NEEDS REVIEW" if citation else "NEEDS REVIEW"

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

    def render_text(self, text, indent=0.0, component_id="question"):
        if not text: return
        text = str(text).strip()
        if not text: return
        w = Q_W - indent
        h = _get_content_height(text, w, 18)
        self.ensure_space(h)
        inline_nodes, source_block_id = self._component_inline(text, component_id)
        if inline_nodes:
            box = self.slide.shapes.add_textbox(Inches(Q_L + indent), Inches(self.y), Inches(w), Inches(h))
            box.text_frame.word_wrap = True
            box.text_frame.margin_left = box.text_frame.margin_right = Inches(0)
            box.text_frame.margin_top = box.text_frame.margin_bottom = Inches(0)
            p = box.text_frame.paragraphs[0]
            context = {"question_id": self.q.get("id"), "component_id": component_id,
                       "source_block_id": source_block_id, "math_outcomes": self.math_outcomes}
            _render_canonical_inline(p, inline_nodes, 18, GOLD, True, "Cambria",
                                     self.render_diagnostics, context)
        else:
            _tb(self.slide, text, Q_L + indent, self.y, w, h, size=18, color=GOLD, bold=True,
                diagnostics=self.render_diagnostics,
                diagnostic_context={"question_id": self.q.get("id"), "component_id": component_id,
                                    "source_block_id": source_block_id,
                                    "math_outcomes": self.math_outcomes})
        self.y += h + 0.05
            
    def render_question(self):
        self.render_text(self.stem_text)

    def _component_inline(self, text, component_id):
        nodes, source_id = _inline_for_component(self.q, str(text), component_id)
        component_source = _component_source_block_id(self.q, component_id)
        if component_source is not None:
            source_text = str(component_source)
            node_source = str(source_id) if source_id is not None else ""
            # Split option blocks may share one parent canonical node source ID.
            if source_id is None or (".part_" in source_text and source_text.split(".part_", 1)[0] == node_source):
                source_id = component_source
        if not nodes and self.q.get("inline_content"):
            source_nodes = self.q.get("inline_content") or []
            source_text = str(source_id) if source_id is not None else ""
            related = [
                (index, node) for index, node in enumerate(source_nodes)
                if isinstance(node, dict) and (
                    str(node.get("source_block_id")) == source_text
                    or (".part_" in source_text and
                        str(node.get("source_block_id")) == source_text.split(".part_", 1)[0])
                )
            ]
            self.render_diagnostics.append({
                "code": "TEXT_LAYOUT_DEGRADED", "severity": "warning",
                "question_id": self.q.get("id"), "component_id": component_id,
                "source_block_id": _normalize_block_id(source_id),
                "node_id": _canonical_node_id(related[0][1], related[0][0]) if related else None,
                "reason": "canonical nodes could not be aligned with rendered component text",
                "fallback": "compatibility text",
            })
        return nodes, source_id

    def render_statements(self):
        stmts = self.q.get("statements")
        if not stmts: return
        if isinstance(stmts, dict):
            for k, v in stmts.items():
                self.render_text(f"{k}. {v}", indent=0.3, component_id=f"statement:{k}")
        elif isinstance(stmts, list):
            for s in stmts:
                if isinstance(s, dict):
                    lbl = s.get("label", "")
                    txt = s.get("text", "")
                    if lbl and txt:
                        self.render_text(f"{lbl}. {txt}", indent=0.3, component_id=f"statement:{lbl}")
                    else:
                        self.render_text(txt or lbl, indent=0.3, component_id=f"statement:{lbl or 'unknown'}")
                elif isinstance(s, str):
                    self.render_text(s, indent=0.3, component_id="statement")

    def render_subparts(self):
        subs = self.q.get("subparts")
        if not subs: return
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict):
                    lbl = sub.get("label", "")
                    txt = sub.get("text", "")
                    if lbl and txt:
                        self.render_text(f"{lbl} {txt}", indent=0.3, component_id=f"subpart:{lbl}")
                    else:
                        self.render_text(txt or lbl, indent=0.3, component_id=f"subpart:{lbl or 'unknown'}")
                elif isinstance(sub, str):
                    self.render_text(sub, indent=0.3, component_id="subpart")
            
    def render_images(self):
        images = self.q.get("images", [])
        if not images: return
        for image_index, img_item in enumerate(images):
            img_path = None
            media_id = None
            source_block_id = None
            if isinstance(img_item, dict):
                img_path = img_item.get("path") or img_item.get("filename") or img_item.get("file_path")
                media_id = img_item.get("media_id") or img_item.get("id")
                source_block_id = img_item.get("source_block_id") or img_item.get("block_id")
            elif isinstance(img_item, str):
                img_path = img_item
                
            if not img_path:
                self._image_diagnostic(image_index, media_id, source_block_id, img_path,
                                       "missing_path", "ValueError('image path is empty')", "placeholder")
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
                self._image_diagnostic(image_index, media_id, source_block_id, img_path,
                                       "missing_file", "FileNotFoundError", "placeholder")
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
                self._image_diagnostic(image_index, media_id, source_block_id, img_path,
                                       "render_failed", repr(e), "placeholder")

    def _image_diagnostic(self, index, media_id, source_block_id, source_path, reason, exception, fallback):
        diagnostic = {
            "code": "MEDIA_RENDER_FAILED", "severity": "warning",
            "question_id": self.q.get("id"), "source_block_id": _normalize_block_id(source_block_id),
            "component_id": f"image:{media_id or index + 1}",
            "node_id": media_id or f"image-{index + 1}",
            "media_id": media_id or f"image-{index + 1}", "source_path": str(source_path or ""),
            "reason": reason, "exception": exception, "fallback": fallback,
        }
        self.render_diagnostics.append(diagnostic)
        self.ensure_space(0.55)
        _rect(self.slide, Q_L, self.y, min(Q_W, 5.2), 0.48, fill=BADGE_BG, rounded=False, border=GOLD)
        _tb(self.slide, "Image unavailable", Q_L + 0.12, self.y + 0.04,
            min(Q_W - 0.24, 4.96), 0.36, size=12, color=DIM_WHITE)
        self.y += 0.53
                
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
        
        rich_rows = table_data.get("cell_content", [])
        row_heights = []
        for r_idx, row in enumerate(rows):
            if not isinstance(row, list):
                row_heights.append(0.35)
                continue
            cell_width = Q_W / max(1, num_cols)
            measured = 0.35
            for c_idx, cell_text in enumerate(row):
                rich_cell = (rich_rows[r_idx][c_idx]
                             if r_idx < len(rich_rows) and isinstance(rich_rows[r_idx], list)
                             and c_idx < len(rich_rows[r_idx]) else {})
                txt = str((rich_cell or {}).get("text", cell_text or ""))
                measured = max(measured, _get_content_height(txt, cell_width - 0.12, 13) + 0.08)
                inline_nodes = (rich_cell or {}).get("inline_content") or []
                if any(isinstance(node, dict) and node.get("kind") == "math_sequence" for node in inline_nodes):
                    source = " ".join(str(node.get("value", "")) for node in inline_nodes if isinstance(node, dict))
                    measured = max(measured, 0.62 if "\\frac" in source or "<m:f" in source else 0.48)
            row_heights.append(min(max(measured, 0.35), 1.1))
        total_h = sum(row_heights)
        self.ensure_space(total_h)
        
        table_shape = self.slide.shapes.add_table(num_rows, num_cols, Inches(Q_L), Inches(self.y), Inches(Q_W), Inches(total_h))
        tbl = table_shape.table
        
        for r_idx, row in enumerate(rows):
            tbl.rows[r_idx].height = Inches(row_heights[r_idx])
            if not isinstance(row, list): continue
            for c_idx, cell_text in enumerate(row):
                if c_idx < num_cols:
                    cell = tbl.cell(r_idx, c_idx)
                    cell.text = ""
                    p = cell.text_frame.paragraphs[0]
                    p.alignment = PP_ALIGN.LEFT
                    rich_cell = (rich_rows[r_idx][c_idx]
                                 if r_idx < len(rich_rows) and isinstance(rich_rows[r_idx], list)
                                 and c_idx < len(rich_rows[r_idx]) else {})
                    txt = str((rich_cell or {}).get("text", cell_text)) if cell_text is not None else ""
                    inline_nodes = (rich_cell or {}).get("inline_content") or []
                    if (len(inline_nodes) == 1 and inline_nodes[0].get("kind") == "math_sequence"
                            and not inline_nodes[0].get("value") and re.fullmatch(r"\s*\$[^$]+\$\s*", txt)):
                        inline_nodes = [dict(inline_nodes[0], value=txt.strip())]
                    cell_context = {"question_id": self.q.get("id"),
                                    "component_id": f"table:{r_idx}:{c_idx}",
                                    "source_block_id": (rich_cell or {}).get("source_block_id"),
                                    "math_outcomes": self.math_outcomes}
                    inline_text = "".join(_canonical_node_text(node) for node in inline_nodes
                                            if isinstance(node, dict))
                    if inline_nodes and _normalize_match_text(inline_text) == _normalize_match_text(txt):
                        _render_canonical_inline(p, inline_nodes, 14, OFF_WHITE, False, 'Cambria',
                                                 self.render_diagnostics, cell_context)
                    else:
                        if inline_nodes:
                            self.render_diagnostics.append({
                                "code": "TEXT_LAYOUT_DEGRADED", "severity": "warning",
                                **{**cell_context, "source_block_id": _normalize_block_id(cell_context.get("source_block_id"))},
                                "node_id": None,
                                "reason": "table cell canonical nodes do not match compatibility text",
                                "fallback": "compatibility cell text",
                            })
                        use_omml = bool(re.search(r"\$[^$]+\$", str(txt)))
                        if use_omml:
                            _insert_omml_math_into_paragraph(p, txt, 14, OFF_WHITE, False, 'Cambria', self.slide,
                                                              diagnostic_context=cell_context,
                                                              diagnostics=self.render_diagnostics)
                        else:
                            _add_rich_text_fallback(p, txt, 14, OFF_WHITE, False, 'Cambria')
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
                body = str(opts.get(letter, ""))
                inline_nodes, source_id = self._component_inline(body, f"option:{letter}")
                _shape_text(txb, self.slide, letter, body, letter_size=16, body_size=16,
                            inline_nodes=inline_nodes,
                            diagnostic_context={"question_id": self.q.get("id"),
                                                "component_id": f"option:{letter}",
                                                "source_block_id": source_id,
                                                "math_outcomes": self.math_outcomes},
                            diagnostics=self.render_diagnostics)
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
                body = str(opts.get("A", ""))
                inline_nodes, source_id = self._component_inline(body, "option:A")
                _shape_text(txb_a, self.slide, "A", body, 16, 16, inline_nodes=inline_nodes,
                            diagnostic_context={"question_id": self.q.get("id"), "component_id": "option:A",
                                                "source_block_id": source_id, "math_outcomes": self.math_outcomes},
                            diagnostics=self.render_diagnostics)
            if "B" in opts:
                txb_b = self.slide.shapes.add_textbox(Inches(col_right), Inches(self.y), Inches(OPT_W_2X2), Inches(row1_h))
                body = str(opts.get("B", ""))
                inline_nodes, source_id = self._component_inline(body, "option:B")
                _shape_text(txb_b, self.slide, "B", body, 16, 16, inline_nodes=inline_nodes,
                            diagnostic_context={"question_id": self.q.get("id"), "component_id": "option:B",
                                                "source_block_id": source_id, "math_outcomes": self.math_outcomes},
                            diagnostics=self.render_diagnostics)
                
            self.y += row1_h + GAP_V_2X2
            
            h_c = _get_content_height(str(opts.get('C', '')), OPT_TEXT_W_2X2, 16)
            h_d = _get_content_height(str(opts.get('D', '')), OPT_TEXT_W_2X2, 16)
            row2_h = max(0.50, h_c, h_d)
            
            self.ensure_space(row2_h)
            if "C" in opts:
                txb_c = self.slide.shapes.add_textbox(Inches(col_left), Inches(self.y), Inches(OPT_W_2X2), Inches(row2_h))
                body = str(opts.get("C", ""))
                inline_nodes, source_id = self._component_inline(body, "option:C")
                _shape_text(txb_c, self.slide, "C", body, 16, 16, inline_nodes=inline_nodes,
                            diagnostic_context={"question_id": self.q.get("id"), "component_id": "option:C",
                                                "source_block_id": source_id, "math_outcomes": self.math_outcomes},
                            diagnostics=self.render_diagnostics)
            if "D" in opts:
                txb_d = self.slide.shapes.add_textbox(Inches(col_right), Inches(self.y), Inches(OPT_W_2X2), Inches(row2_h))
                body = str(opts.get("D", ""))
                inline_nodes, source_id = self._component_inline(body, "option:D")
                _shape_text(txb_d, self.slide, "D", body, 16, 16, inline_nodes=inline_nodes,
                            diagnostic_context={"question_id": self.q.get("id"), "component_id": "option:D",
                                                "source_block_id": source_id, "math_outcomes": self.math_outcomes},
                            diagnostics=self.render_diagnostics)
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
            inline_nodes, source_id = self._component_inline(opt_text, f"option:{letter}")
            _shape_text(
                txb, self.slide, letter, opt_text, 14, 14, center_v=True,
                inline_nodes=inline_nodes,
                diagnostic_context={"question_id": self.q.get("id"), "component_id": f"option:{letter}",
                                    "source_block_id": source_id, "math_outcomes": self.math_outcomes},
                diagnostics=self.render_diagnostics,
            )
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

def generate(json_path: Path, output_path: Path, title=None, subtitle=None, logo_path=None):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        questions = data.get("questions", [])
    elif isinstance(data, list):
        questions = data
    else:
        questions = []

    # BUG-PPT-001: Do NOT silently drop questions that failed parsing.
    # Keep all questions in the output presentation; questions needing review display a review badge.
    ok_qs = list(questions)
    pipeline_diagnostics = data.get("diagnostics", {}) if isinstance(data, dict) else {}
    count_keys = ("questions_accepted", "questions_needs_review", "questions_rejected")
    if all(isinstance(pipeline_diagnostics.get(key), int) for key in count_keys):
        reported = sum(pipeline_diagnostics[key] for key in count_keys)
        if reported != len(ok_qs):
            raise ValueError(
                f"Question count mismatch before rendering: pipeline reports {reported}, "
                f"JSON contains {len(ok_qs)} questions"
            )

    # BUG-PPT-002: Dynamic title derived from metadata or input filename
    if not title or title == "Chemistry Midterm — MCQ Practice":
        src_meta = data.get("source", {}) if isinstance(data, dict) else {}
        doc_meta = data.get("metadata", {}) if isinstance(data, dict) else {}
        derived = doc_meta.get("title") or src_meta.get("filename") or json_path.stem
        clean_title = Path(derived).stem.replace("_", " ").replace("-", " ").strip().title()
        title = f"{clean_title} — Practice Deck" if clean_title else "Question Presentation"

    # BUG-PPT-003: Reconcile slide/question count with pipeline data
    if subtitle is None:
        total_q = len(ok_qs)
        review_count = sum(1 for q in ok_qs if q.get("needs_review") or q.get("parsed_ok") is False)
        if review_count > 0:
            subtitle = f"{total_q} Questions ({review_count} Flagged for Review) · Exam Prep"
        else:
            subtitle = f"{total_q} Questions · Boards / Competitive Exam"

    prs = Presentation()
    prs.slide_width  = Inches(SW)
    prs.slide_height = Inches(SH)

    print(f"[*] Building deck for {len(ok_qs)} questions ...")
    build_title_slide(prs, title, subtitle, logo_path)

    last_section = None
    match_col_count = 0
    open_count = 0
    divider_count = 0
    render_diagnostics = []
    math_outcomes = []
    question_slide_map = {}

    base_dir = json_path.parent

    for q in ok_qs:
        slide_start = len(prs.slides) + 1
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
            question_slide_map[str(q.get("id"))] = [len(prs.slides)]
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
            render_diagnostics.extend(engine.render_diagnostics)
            math_outcomes.extend(engine.math_outcomes)
            question_slide_map[str(q.get("id"))] = list(range(slide_start, len(prs.slides) + 1))
            for diagnostic in engine.render_diagnostics:
                diagnostic["slide_ids"] = question_slide_map[str(q.get("id"))]

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

    canonical_math_inventory = _collect_canonical_math_ids(ok_qs)
    canonical_math_ids = {item["math_id"]: item for item in canonical_math_inventory}
    outcome_ids = {item.get("math_id") for item in math_outcomes}
    for math_id, item in canonical_math_ids.items():
        if math_id in outcome_ids:
            continue
        context = {
            **item,
            "component_id": (f"option:{item['option_label']}" if item.get("option_label")
                             else "table" if item.get("component_type") == "table" else "question"),
            "math_outcomes": math_outcomes,
            "math_id": math_id,
        }
        _record_math_outcome(context, "failed", item.get("source_text"),
                             reason="canonical math node has no render outcome")
        _record_render_diagnostic(
            render_diagnostics, context, "MATH_RENDER_FAILED",
            "canonical math node has no render outcome", "no output", original=item.get("source_text"),
        )

    outcome_ids = {item.get("math_id") for item in math_outcomes}
    canonical_math_nodes = len(canonical_math_ids)
    native_math_entries, fallback_math_entries = _count_pptx_math_entries(output_path)
    outcome_native_entries = sum(item.get("native_entries", 0) for item in math_outcomes)
    outcome_alternate_fallbacks = sum(item.get("alternate_fallback_entries", 0) for item in math_outcomes)
    failed_math_nodes = sum(item.get("status") == "failed" for item in math_outcomes)
    fallback_math_nodes = sum(item.get("status") == "degraded" for item in math_outcomes)
    compatibility_math_nodes = sum(item.get("render_path") == "compatibility" for item in math_outcomes)
    rendered_canonical_ids = {item.get("math_id") for item in math_outcomes}
    unrendered_canonical = len(set(canonical_math_ids) - rendered_canonical_ids)
    if outcome_native_entries != native_math_entries or outcome_alternate_fallbacks != fallback_math_entries:
        render_diagnostics.append({
            "code": "MATH_RECONCILIATION_FAILED", "severity": "error",
            "question_id": None, "component_id": "math_reconciliation", "component_type": "document",
            "option_label": None, "source_block_id": None, "node_id": None, "math_id": None,
            "reason": "render outcome ledger does not match generated slide XML",
            "fallback": "none", "source_text": None, "fallback_text": None,
            "render_path": "failed", "status": "failed",
            "outcome_native_entries": outcome_native_entries,
            "xml_native_entries": native_math_entries,
            "outcome_alternate_fallbacks": outcome_alternate_fallbacks,
            "xml_fallback_entries": fallback_math_entries,
        })
    math_render_counts = {
        "canonical_math_nodes": canonical_math_nodes,
        "native_math_entries": native_math_entries,
        "fallback_math_entries": fallback_math_entries,
        "fallback_math_nodes": fallback_math_nodes,
        "compatibility_math_nodes": compatibility_math_nodes,
        "failed_math_nodes": failed_math_nodes,
        "unrendered_canonical_math_nodes": unrendered_canonical,
        "native_entries_without_canonical_node": max(0, native_math_entries - outcome_native_entries),
        "math_outcome_nodes": len(math_outcomes),
        "math_outcome_ids_unique": len(outcome_ids) == len(math_outcomes),
    }

    if isinstance(data, dict):
        diagnostics = data.setdefault("diagnostics", {})
        if isinstance(diagnostics, dict):
            diagnostics["rendered_count"] = len(ok_qs)
            diagnostics["rendered_slides"] = total
            diagnostics["render_diagnostics"] = render_diagnostics
            diagnostics["render_status"] = "degraded" if any(
                item.get("severity") in ("warning", "error") for item in render_diagnostics
            ) else "rendered"
            diagnostics["math_fallback_count"] = sum(
                item.get("code") in ("MATH_FALLBACK_USED", "MATH_RENDER_FAILED")
                for item in render_diagnostics
            )
            diagnostic_counts = {}
            for item in render_diagnostics:
                code = item.get("code", "UNKNOWN_RENDER_ERROR")
                diagnostic_counts[code] = diagnostic_counts.get(code, 0) + 1
            diagnostics["render_diagnostic_counts"] = diagnostic_counts
            diagnostics["math_render_counts"] = math_render_counts
            diagnostics["math_render_outcomes"] = math_outcomes
            for question in ok_qs:
                if not isinstance(question, dict):
                    continue
                question_diagnostics = [item for item in render_diagnostics
                                        if str(item.get("question_id")) == str(question.get("id"))
                                        and item.get("severity") in ("warning", "error")]
                question["render"] = {
                    "status": "degraded" if question_diagnostics else "rendered",
                    "diagnostics": question_diagnostics,
                    "slide_ids": question_slide_map.get(str(question.get("id")), []),
                }
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "rendered_questions": len(ok_qs),
        "rendered_slides": total,
        "output_path": str(output_path),
        "math_fallbacks": sum(
            1 for slide in prs.slides for shape in slide.shapes
            if hasattr(shape, "_element") and "<mc:Fallback" in shape._element.xml
        ),
        "leaked_math_markers": leaked_count,
        "render_diagnostics": render_diagnostics,
        "math_render_counts": math_render_counts,
        "math_render_outcomes": math_outcomes,
    }

def _auto_pptx_path(json_path: Path) -> Path:
    return json_path.with_suffix(".pptx")

def main():
    ap = argparse.ArgumentParser(description="Generate a PPTX slide deck from questions JSON file.")
    ap.add_argument("input", help="Path to questions.json")
    ap.add_argument("output", nargs="?", default=None, help="Output .pptx path")
    ap.add_argument("--title", default=None, help="Deck title on the title slide (default: derived from document name)")
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
