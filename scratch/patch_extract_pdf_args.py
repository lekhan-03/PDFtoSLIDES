with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace("items = pdf_spans.page_items(pdict, page_num + 1, repeating)", "items = pdf_spans.page_items(pdict, page_num + 1, repeating_lines=repeating)")
with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text)
