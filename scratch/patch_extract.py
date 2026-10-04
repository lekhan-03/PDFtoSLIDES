import re
with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text = f.read()

# Remove NOISE_PATTERNS and NOISE_RE and is_noise
text = re.sub(r'NOISE_PATTERNS = \[.*?\]\s*', '', text, flags=re.DOTALL)
text = re.sub(r'NOISE_RE = re.compile.*?is_noise\(text: str\) -> bool:.*?return bool\(NOISE_RE.match\(text\)\)\s*', '', text, flags=re.DOTALL)

# Add noise filtering inside extract_pdf_questions
idx = text.find('def extract_pdf_questions(pdf_path: str) -> list[dict]:')

clean_insertion = """
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

def extract_pdf_questions(pdf_path: str) -> list[dict]:
    import src.pdf_spans as pdf_spans
    doc = pymupdf.open(pdf_path)
    repeating = find_repeating_lines(doc)
    
    all_items = []
    
    for page_num, page in enumerate(doc):
        pdict = page.get_text("dict")
        
        # Use pdf_spans
        items = pdf_spans.page_items(pdict, page_num + 1, repeating)
        
"""

# Replace from extract_pdf_questions to 'for p in page.get_drawings():'
idx3 = text.find('        for p in page.get_drawings():')

text = text[:idx] + clean_insertion + text[idx3:]

# Replace the sorting logic to use line_y0
text = text.replace('items.sort(key=lambda i: (i["bbox"][1], i["bbox"][0]))',
                    'for it in items: it.setdefault("line_y0", it["bbox"][1])\n        items.sort(key=lambda i: (i["line_y0"], i["bbox"][0]))')

# Replace group_and_rebuild's sort
text = text.replace('sorted_items = sorted(region, key=lambda i: i[\'bbox\'][1])',
                    'sorted_items = sorted(region, key=lambda i: i.get(\'line_y0\', i[\'bbox\'][1]))')

with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text)
    print("Patched extract_pdf.py")
