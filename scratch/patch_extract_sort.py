with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix in extract_pdf_questions
old1 = "sorted_items = sorted(region, key=lambda i: i.get('line_y0', i['bbox'][1]))"
new1 = "sorted_items = sorted(region, key=lambda i: (i.get('page', 0), i.get('line_y0', i['bbox'][1]), i['bbox'][0]))"
text = text.replace(old1, new1)

with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text)
