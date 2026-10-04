import pymupdf
doc = pymupdf.open('data/tests/chemistry.pdf')
from src.extract_pdf import segment_and_process, group_and_rebuild
all_items = []
for page_num, page in enumerate(doc):
    items = []
    pdict = page.get_text("dict")
    for block in pdict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        items.append({"type": "text", "text": text, "bbox": span["bbox"], "page": page_num + 1, "size": span.get("size")})
    items.sort(key=lambda i: (i["bbox"][1], i["bbox"][0]))
    all_items.extend(items)

min_x0 = min((i["bbox"][0] for i in all_items if i["type"] == "text"), default=0)
regions = []
current_region = []
current_q_num = 0
import re
for item in all_items:
    if item["type"] == "text":
        text = item["text"]
        x0 = item["bbox"][0]
        is_start = False
        m1 = re.match(r'^\s*(\d+)\.\s*$', text)
        if m1 and abs(x0 - min_x0) < 40:
            is_start = True
            current_q_num = int(m1.group(1))
        if is_start:
            if current_region: regions.append({'num': current_q_num if not is_start else current_region[0].get('q_num', 0), 'items': current_region})
            current_region = [item]
            item['q_num'] = current_q_num
            continue
    current_region.append(item)
if current_region: regions.append({'num': current_q_num, 'items': current_region})

q42_region = next(r for r in regions if r['num'] == 42)
print("Before group_and_rebuild:")
for i in q42_region['items']:
    print(i['text'], i.get('size'))
lines = group_and_rebuild(q42_region['items'])
print("\nAfter:")
print(lines)
