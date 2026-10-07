from src.headings import is_heading
"""Extract and parse questions from PDF using geometry."""
import re
import pymupdf

def clean_text(text: str) -> str:
    # C. Clean the text before conversion.
    # Collapse repeated function names
    text = re.sub(r'\b(sin|cos|tan|cot|sec|cosec|csc|log|ln)\s+\1\b', r'\1', text)
    
    # Replace cosec/csc with \operatorname{cosec}, others with \name
    text = re.sub(r'\b(cosec|csc)\b', r'\\operatorname{cosec} ', text)
    funcs = r'(sin|cos|tan|cot|sec|log|ln)'
    text = re.sub(rf'\b{funcs}\b', r'\\\1 ', text)
    
    # Replace ". dx" and ".dx" with "\,dx"
    text = text.replace('. dx', '\\,dx').replace('.dx', '\\,dx')
    
    # fix multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def find_repeating_lines(doc, threshold_ratio=0.30):
    import collections
    line_counts = collections.defaultdict(set)
    num_pages = len(doc)
    threshold = num_pages * threshold_ratio
    for i, page in enumerate(doc):
        blocks = page.get_text("dict").get("blocks", [])
        for b in blocks:
            if b.get("type") == 0:
                for l in b.get("lines", []):
                    y = round(l["bbox"][3])
                    t = "".join([s.get("text", "") for s in l.get("spans", [])]).strip()
                    if t:
                        line_counts[(t, y)].add(i)
    return {text for (text, y), pages in line_counts.items() if len(pages) >= threshold}

def extract_pdf_blocks(pdf_path: str):
    from src.document_model import DocumentBlock
    import src.pdf_spans as pdf_spans
    doc = pymupdf.open(pdf_path)
    repeating = find_repeating_lines(doc)
    
    blocks = []
    global_id = 1
    
    for page_num, page in enumerate(doc):
        pdict = page.get_text("dict")
        items = pdf_spans.page_items(pdict, page_num + 1, repeating_lines=repeating)
        
        for p in page.get_drawings():
            for d_item in p["items"]:
                if d_item[0] == "l":
                    p1, p2 = d_item[1], d_item[2]
                    if abs(p1.y - p2.y) < 2:
                        x0, x1 = min(p1.x, p2.x), max(p1.x, p2.x)
                        y = (p1.y + p2.y) / 2
                        if x1 - x0 > 5:
                            items.append({
                                "type": "draw",
                                "bbox": (x0, y-1, x1, y+1),
                                "page": page_num + 1
                            })
                elif d_item[0] == "re":
                    rect = d_item[1]
                    if rect.height < 3 and rect.width > 5:
                        items.append({
                            "type": "draw",
                            "bbox": (rect.x0, rect.y0, rect.x1, rect.y1),
                            "page": page_num + 1
                        })
                        
        for it in items: it.setdefault("line_y0", it["bbox"][1])
        items.sort(key=lambda i: (round(i["line_y0"] / 5) * 5, i["bbox"][0]))
        
        lines = group_and_rebuild(items)
        for line in lines:
            line = line.strip()
            if not line: continue
            blocks.append(DocumentBlock(
                block_id=global_id,
                block_type="paragraph",
                text=line,
                page=page_num + 1,
                order=global_id
            ))
            global_id += 1
            
    return blocks

def group_and_rebuild(region):
    sorted_items = sorted(region, key=lambda i: (i.get('page', 0), i.get('line_y0', i['bbox'][1]), i['bbox'][0]))
    
    groups = []
    if not sorted_items:
        return []
        
    current_group = [sorted_items[0]]
    current_y1 = sorted_items[0]['bbox'][3]
    current_page = sorted_items[0].get('page', 0)
    
    for item in sorted_items[1:]:
        y0 = item['bbox'][1]
        y1 = item['bbox'][3]
        page = item.get('page', 0)
        
        if page == current_page and y0 <= current_y1:
            current_group.append(item)
            current_y1 = max(current_y1, y1)
        else:
            groups.append(current_group)
            current_group = [item]
            current_y1 = y1
            current_page = page
            
    if current_group:
        groups.append(current_group)
        
    lines = []
    for group in groups:
        lines.append(rebuild_group(group))
        
    return lines

def rebuild_group(group):
    text_items = [i for i in group if i['type'] == 'text']
    draw_items = [i for i in group if i['type'] == 'draw']
    
    # Rebuild super/subscripts before merging lines
    if len(text_items) > 1:
        sizes = sorted([t.get('size', 0) for t in text_items if t.get('size')])
        y1s = sorted([t['bbox'][3] for t in text_items])
        
        if sizes and y1s:
            median_size = sizes[len(sizes)//2]
            median_y1 = y1s[len(y1s)//2]
            
            for t in text_items:
                size = t.get('size', median_size)
                y1 = t['bbox'][3]
                
                # Check if it's noticeably smaller
                if size > 0 and size < median_size * 0.85:
                    if y1 < median_y1 - (median_size * 0.2):
                        # Superscript
                        t['text'] = f"^{{{t['text']}}}"
                    elif y1 > median_y1 + (median_size * 0.2):
                        # Subscript
                        t['text'] = f"_{{{t['text']}}}"
    
    # Sqrt
    for draw in draw_items[:]:
        dx0, dy0, dx1, dy1 = draw['bbox']
        above, below, others = [], [], []
        
        for t in text_items:
            tx0, ty0, tx1, ty1 = t['bbox']
            tx_c = (tx0 + tx1) / 2
            if dx0 - 15 <= tx_c <= dx1 + 15:
                if ty1 <= dy0 + 5: above.append(t)
                elif ty0 >= dy1 - 5: below.append(t)
                else: others.append(t)
            else:
                others.append(t)
                
        if not above and below:
            root_item = next((t for t in others if '√' in t['text'] and abs(t['bbox'][2] - dx0) < 15), None)
            if root_item:
                below_text = "".join([t['text'] for t in sorted(below, key=lambda i: i['bbox'][0])])
                new_item = {
                    'type': 'text',
                    'text': f"\\sqrt{{{below_text}}}",
                    'bbox': (root_item['bbox'][0], min([t['bbox'][1] for t in below]), dx1, max([t['bbox'][3] for t in below]))
                }
                others.remove(root_item)
                text_items = others + [new_item]
                draw_items.remove(draw)
                
    # Fraction
    for draw in draw_items[:]:
        dx0, dy0, dx1, dy1 = draw['bbox']
        above, below, others = [], [], []
        for t in text_items:
            tx0, ty0, tx1, ty1 = t['bbox']
            tx_c = (tx0 + tx1) / 2
            if dx0 - 15 <= tx_c <= dx1 + 15:
                if ty1 <= dy0 + 5: above.append(t)
                elif ty0 >= dy1 - 5: below.append(t)
                else: others.append(t)
            else:
                others.append(t)
                
        if above and below:
            above_text = "".join([t['text'] for t in sorted(above, key=lambda i: i['bbox'][0])])
            below_text = "".join([t['text'] for t in sorted(below, key=lambda i: i['bbox'][0])])
            new_item = {
                'type': 'text',
                'text': f"\\frac{{{above_text}}}{{{below_text}}}",
                'bbox': (dx0, min([t['bbox'][1] for t in above]), dx1, max([t['bbox'][3] for t in below]))
            }
            text_items = others + [new_item]
            draw_items.remove(draw)
            
    # Integral
    for t in text_items[:]:
        if '∫' in t['text']:
            ix0, iy0, ix1, iy1 = t['bbox']
            ic_y = (iy0 + iy1) / 2
            upper, lower, others = None, None, []
            
            for o in text_items:
                if o == t: continue
                ox0, oy0, ox1, oy1 = o['bbox']
                if 0 <= (ox0 - ix1) <= 15:
                    if oy1 <= ic_y + 3: upper = o
                    elif oy0 >= ic_y - 3: lower = o
                    else: others.append(o)
                else: others.append(o)
                    
            if upper or lower:
                res = "\\int"
                if lower: res += f"_{{{lower['text']}}}"
                if upper: res += f"^{{{upper['text']}}}"
                t['text'] = res
                if upper in text_items: text_items.remove(upper)
                if lower in text_items: text_items.remove(lower)

    text_items.sort(key=lambda i: i['bbox'][0])
    line_str = " ".join([t['text'] for t in text_items])
    return clean_text(line_str)
