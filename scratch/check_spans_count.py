import pymupdf
import src.pdf_spans as pdf_spans
from src.extract_pdf import find_repeating_lines

doc = pymupdf.open("data/tests/chemistry.pdf")
repeating = find_repeating_lines(doc)
total = 0
for i in range(len(doc)):
    page = doc[i]
    items = pdf_spans.page_items(page.get_text("dict"), i+1, gap_factor=2.0, repeating_lines=repeating)
    total += len(items)
print(f"Total items from pdf_spans: {total}")
