from src.extract_pdf import *
import pymupdf
doc = pymupdf.open("data/tests/chemistry.pdf")
repeating = find_repeating_lines(doc)
all_items = []
for page_num, page in enumerate(doc):
    pdict = page.get_text("dict")
    import src.pdf_spans as pdf_spans
    items = pdf_spans.page_items(pdict, page_num + 1, repeating)
    for it in items: it.setdefault("line_y0", it["bbox"][1])
    items.sort(key=lambda i: (i["line_y0"], i["bbox"][0]))
    all_items.extend(items)

def test_q52():
    regions = []
    current_region = []
    for item in all_items:
        if item["type"] == "text":
            text = item["text"]
            if re.match(r"^\d+\.", text) and item["bbox"][0] < 100:
                if current_region: regions.append(current_region)
                current_region = [item]
            else:
                if current_region: current_region.append(item)
    if current_region: regions.append(current_region)
    for region in regions:
        if any("52." in i.get("text", "") for i in region):
            sorted_items = sorted(region, key=lambda i: i.get('line_y0', i['bbox'][1]))
            text_items = []
            for i in sorted_items:
                if i['type'] == 'text': text_items.append(i)
            text_items.sort(key=lambda i: (i['line_y0'], i['bbox'][0]))
            line_str = " ".join([t['text'] for t in text_items])
            print("Raw text:")
            print(line_str)
test_q52()
