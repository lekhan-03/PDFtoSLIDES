import fitz

doc = fitz.open('data/tests/chemistry.pdf')
# Q42 is probably on page 4, 5 or 6? We will search for '42.'
q42_page = None
q42_y = None
for i, page in enumerate(doc):
    text = page.get_text()
    if '42. ' in text:
        q42_page = page
        break

print(f"Q42 on page {q42_page.number}")

words = q42_page.get_text("words")
for w in words:
    if w[4].startswith('42.'):
        print(f"Q42 starts at y={w[1]}")
        break

# The formula line would be below that. Let's find spans in blocks
blocks = q42_page.get_text("dict")["blocks"]
formula_blocks = []
in_q42 = False
for b in blocks:
    if "lines" not in b: continue
    for l in b["lines"]:
        for s in l["spans"]:
            if s["text"].strip() == "42.":
                in_q42 = True
            elif in_q42 and s["text"].strip().startswith("43."):
                in_q42 = False
                break
        if in_q42:
            formula_blocks.append(l)

print("Formula lines spans for Q42:")
for l in formula_blocks:
    full_text = "".join([s["text"] for s in l["spans"]])
    if "E" in full_text or "Fe" in full_text or "Cu" in full_text or "Cr" in full_text:
        print(f"Line: {full_text}")
        for s in l["spans"]:
            print(f"  Span: '{s['text']}' | size: {s['size']} | origin y: {s['origin'][1]}")

print("\nSearching for 3+ and 2+:")
for i, page in enumerate(doc):
    words = page.get_text("words")
    for j, w in enumerate(words):
        if w[4] in ("3+", "2+"):
            nbrs = [words[k][4] for k in range(max(0, j-2), min(len(words), j+3))]
            print(f"Page {i}, Word: {w[4]}, bbox: {w[:4]}, neighbors: {' '.join(nbrs)}")
