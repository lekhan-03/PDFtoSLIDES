import pymupdf
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def check_pdf(pdf_path, text_snippets):
    doc = pymupdf.open(pdf_path)
    for p_num, page in enumerate(doc):
        text_page = page.get_text("dict")
        for b in text_page.get("blocks", []):
            if b.get("type") != 0: continue
            for l in b.get("lines", []):
                line_str = " ".join([s.get("text", "") for s in l.get("spans", [])]).strip()
                for snippet in text_snippets:
                    if snippet in line_str or line_str in snippet:
                        print(f"Page {p_num+1} | {line_str!r} | bbox: {l['bbox']}")

print("Integrals ID 6:")
check_pdf("data/tests/Integrals.pdf", ["((1)/(sqrt(1+X^{2})) )", "log|x +sqrt(1+X^{2})|"])
print("\nChemistry ID 52:")
check_pdf("data/chemistry.pdf", ["Rate = k[A][B]", "2.0 × 10^{-3}"])
print("\nChemistry ID 33:")
check_pdf("data/chemistry.pdf", ["half-life", "radioactive decay"])
