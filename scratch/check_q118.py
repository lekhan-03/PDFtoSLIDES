import src.extract_pdf as ep
import pymupdf, json
doc = pymupdf.open('data/tests/chemistry.pdf')
repeating = ep.find_repeating_lines(doc)
all_items = []
import src.pdf_spans as pdf_spans
for page_num, page in enumerate(doc):
    pdict = page.get_text('dict')
    items = pdf_spans.page_items(pdict, page_num + 1, repeating_lines=repeating)
    for it in items: it.setdefault('line_y0', it['bbox'][1])
    items.sort(key=lambda i: (i['line_y0'], i['bbox'][0]))
    all_items.extend(items)

min_x0 = min((i['bbox'][0] for i in all_items if i['type'] == 'text'), default=0)
regions = []
current_region = []
import re
current_q_num = 0
for item in all_items:
    if item['type'] == 'text':
        text = item['text']
        x0 = item['bbox'][0]
        m1 = re.match(r'^\s*(\d+)\.', text)
        is_start = False
        if m1 and abs(x0 - min_x0) < 40:
            is_start = True
            current_q_num = int(m1.group(1))
        elif re.match(r'^\d{4}(,\d{4})*(-\d+)?M?$', text):
            is_start = True
            
        if is_start:
            if current_region: regions.append({'num': current_q_num if not is_start else current_region[0].get('q_num', 0), 'items': current_region})
            current_region = [item]
            item['q_num'] = current_q_num
            continue
    current_region.append(item)
if current_region: regions.append({'num': current_q_num, 'items': current_region})

for region_obj in regions:
    if region_obj['num'] == 118:
        print('Items before sort (using only y0, x0):')
        bad_sort = sorted(region_obj['items'], key=lambda i: (i.get('line_y0', i['bbox'][1]), i['bbox'][0]))
        for it in bad_sort:
            if it['type'] == 'text':
                print(f"  page={it.get('page', 0)}, y={it.get('line_y0', 0):.2f}, text='{it.get('text', '')}'")
        
        print('\nItems after sort (using page, y0, x0):')
        good_sort = sorted(region_obj['items'], key=lambda i: (i.get('page', 0), i.get('line_y0', i['bbox'][1]), i['bbox'][0]))
        for it in good_sort:
            if it['type'] == 'text':
                print(f"  page={it.get('page', 0)}, y={it.get('line_y0', 0):.2f}, text='{it.get('text', '')}'")
        break
