"""
pdf_spans.py - build text items from a PyMuPDF page WITHOUT losing superscripts / subscripts.

Problem found in the chemistry PDF: a superscript span such as "2+" (size 8.04, origin y 491.8) sits
slightly ABOVE its line (origin y 496.4). Sorting spans by their own top y put "2+ 2+ 2+" before
the "42." marker, so they ended up in question 41's option D and question 42 lost its charges.

Fix: one item per LINE (or per column segment of a line), sorted by the LINE's y, with raised small
spans written as Unicode superscripts and lowered small spans as subscripts:
    Fe + "2+"(raised)            -> Fe²⁺
    SO + "4"(lowered) + "2-"(raised) -> SO₄²⁻
    [NO] + "2"(raised)           -> [NO]²

    spans_to_text(spans)               spans = [{"text", "size", "origin": (x, y)}, ...]
    page_items(page_dict, page_no)     page_dict = page.get_text("dict")  ->  [{"type","text","bbox","page"}]
"""
from collections import Counter

_SUP_CH = dict(zip("0123456789+-−=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾"))
_SUP_CH.update(dict(zip("abcdefghijklmnoprstuvwxyz", "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")))
_SUB_CH = dict(zip("0123456789+-−=()", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎"))
_SUB_CH.update(dict(zip("aehklmnopstx", "ₐₑₕₖₗₘₙₒₚₛₜₓ")))


def _script(text, table, marker):
    t = text.strip()
    if t and all(ch in table for ch in t):
        return "".join(table[ch] for ch in t)
    return f"{marker}{{{t}}}"                          # unmappable: keep as ^{..} / _{..} for the math path


def spans_to_text(spans, small=0.95, min_shift=1.0):
    real = [s for s in spans if s["text"].strip()]
    if not real:
        return "".join(s["text"] for s in spans)
    top = max(s["size"] for s in real)
    counts = Counter()
    for s in real:
        if s["size"] >= top * small:                    # tiny spans can never define the baseline
            counts[round(s["size"], 1)] += len(s["text"].strip())
    base_size = counts.most_common(1)[0][0]
    base_y = next(s["origin"][1] for s in real if round(s["size"], 1) == base_size)
    out = []
    for s in spans:
        t = s["text"]
        if not t.strip():
            out.append(t)
        elif s["size"] < base_size * small and abs(s["origin"][1] - base_y) >= min_shift:
            out.append(_script(t, _SUP_CH, "^") if s["origin"][1] < base_y else _script(t, _SUB_CH, "_"))
        else:
            out.append(t)
    return "".join(out)


def spans_to_inline_content(spans, small=0.95, min_shift=1.0):
    """Return ordered span data with script roles before Unicode conversion."""
    real = [s for s in spans if s["text"].strip()]
    base_size = None
    base_y = None
    if real:
        top = max(s["size"] for s in real)
        counts = Counter()
        for span in real:
            if span["size"] >= top * small:
                counts[round(span["size"], 1)] += len(span["text"].strip())
        if counts:
            base_size = counts.most_common(1)[0][0]
            base_y = next(s["origin"][1] for s in real if round(s["size"], 1) == base_size)

    result = []
    for span in spans:
        align = None
        if (base_size is not None and span["text"].strip()
                and span["size"] < base_size * small
                and abs(span["origin"][1] - base_y) >= min_shift):
            align = "superscript" if span["origin"][1] < base_y else "subscript"
        result.append({
            "kind": "text",
            "value": span["text"],
            "vertical_align": align,
            "formatting": {"font": span.get("font"), "size": span.get("size"),
                           "color": span.get("color"), "flags": span.get("flags")},
            "source": {"bbox": span.get("bbox"), "origin": span.get("origin")},
        })
    return result


def page_items(page_dict, page_no, gap_factor=2.0, repeating_lines=None):
    repeating_lines = repeating_lines or set()
    """One item per line segment; spans further apart than gap_factor * font size start a new segment
    (so two options on the same line, e.g. '(A) ...   (B) ...', stay separate items)."""
    items = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = sorted((s for s in line.get("spans", []) if s["text"] != ""), key=lambda s: s["bbox"][0])
            if not spans:
                continue
            full_text = "".join([s.get("text", "") for s in line.get("spans", [])]).strip()
            if full_text in repeating_lines:
                continue
            groups, cur = [], [spans[0]]
            for prev, s in zip(spans, spans[1:]):
                if s["bbox"][0] - prev["bbox"][2] > gap_factor * max(prev["size"], s["size"]):
                    groups.append(cur)
                    cur = []
                cur.append(s)
            groups.append(cur)
            ly0, ly1 = line["bbox"][1], line["bbox"][3]
            for g in groups:
                text = spans_to_text(g).strip()
                if text:
                    items.append({"type": "text", "text": text, "page": page_no,
                                  "bbox": (g[0]["bbox"][0], ly0, g[-1]["bbox"][2], ly1),
                                  "inline_content": spans_to_inline_content(g)})
    items.sort(key=lambda i: (round(i["bbox"][1] / 5) * 5, i["bbox"][0]))
    return items
