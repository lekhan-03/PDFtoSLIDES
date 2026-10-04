"""usage: python dump_lines.py file.pdf "Arrhenius equation"   -> every text line near the match, with block/line ids and x/y"""
import sys, fitz

pdf, needle = sys.argv[1], sys.argv[2]
for pno, page in enumerate(fitz.open(pdf), 1):
    hits = page.search_for(needle)
    if not hits:
        continue
    top = hits[0].y0 - 6
    lines = {}
    for x0, y0, x1, y1, w, b, l, n in page.get_text("words"):
        if top <= y0 < top + 230:
            lines.setdefault((b, l), []).append((x0, y0, w))
    print(f"page {pno}")
    for key, ws in sorted(lines.items(), key=lambda kv: (round(kv[1][0][1]), kv[1][0][0])):
        ws.sort()
        print(f"  block {key[0]:>2} line {key[1]:>2}  x0={ws[0][0]:6.1f} y={ws[0][1]:6.1f} | " + " ".join(w for _, _, w in ws))
    break
else:
    print("not found:", needle)
