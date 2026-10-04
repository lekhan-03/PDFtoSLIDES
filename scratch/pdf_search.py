import fitz
doc = fitz.open('data/tests/chemistry.pdf')
for i, page in enumerate(doc):
    words = page.get_text("words")
    for j, w in enumerate(words):
        if w[4] in ("2+", "3+"):
            nbrs = [words[k][4] for k in range(max(0, j-2), min(len(words), j+3))]
            print(f"Page {i}, Word: {w[4]}, bbox: {w[:4]}, neighbors: {' '.join(nbrs)}")
