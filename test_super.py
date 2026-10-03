import pymupdf
doc = pymupdf.open('data/tests/chemistry.pdf')
page = doc[8]
for b in page.get_text('dict').get('blocks', []):
    if b.get('type') == 0:
        for l in b.get('lines', []):
            for s in l.get('spans', []):
                t = s.get('text', '').strip()
                if 'Rate' in t or 'K' in t or 'A' in t or '2' in t:
                    print(f"{t!r} size={s.get('size', 0):.1f} y0={s['bbox'][1]:.1f} y1={s['bbox'][3]:.1f}")
