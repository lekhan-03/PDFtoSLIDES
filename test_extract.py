import pymupdf
import sys
sys.stdout.reconfigure(encoding='utf-8')
doc = pymupdf.open("data/tests/chemistry.pdf")
page = doc[0]
for b in page.get_text("dict")["blocks"]:
    if b.get("type") == 0:
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                print(repr(s["text"]), s["bbox"])
