import pymupdf
from src.extract_pdf import find_repeating_lines
doc = pymupdf.open("data/tests/chemistry.pdf")
repeating = find_repeating_lines(doc)
print(f"Lines repeating on >=30% of pages:")
for y, text in repeating.items():
    print(f"y={y:.1f}: '{text}'")
