with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(r"m1 = re.match(r'^\s*(\d+)\.\s*$', text)", r"m1 = re.match(r'^\s*(\d+)\.', text)")

with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text)
