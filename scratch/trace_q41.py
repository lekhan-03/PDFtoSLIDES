import pymupdf
import src.pdf_spans as pdf_spans
from src.extract_pdf import find_repeating_lines

doc = pymupdf.open("data/tests/chemistry.pdf")
repeating = find_repeating_lines(doc)
page = doc[4] # Page 5 usually has Q41
items = pdf_spans.page_items(page.get_text("dict"), 5, gap_factor=2.0, repeating_lines=repeating)
for i in items:
    if "Cu" in i["text"]:
        print(i)
