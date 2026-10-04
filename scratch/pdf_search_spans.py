import fitz
doc = fitz.open('data/tests/chemistry.pdf')

for i, page in enumerate(doc):
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b: continue
        for l in b["lines"]:
            spans = l["spans"]
            for idx, s in enumerate(spans):
                if s["text"].strip() in ("2+", "3+"):
                    # getting neighbor spans
                    prev_s = spans[idx-1]["text"] if idx > 0 else "START"
                    next_s = spans[idx+1]["text"] if idx < len(spans)-1 else "END"
                    print(f"Page {i}, Span: '{s['text']}', bbox: {s['bbox']}, neighbors: '{prev_s}', '{next_s}'")
