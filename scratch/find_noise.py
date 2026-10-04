import fitz
import collections

doc = fitz.open("data/tests/chemistry.pdf")
num_pages = len(doc)
threshold = num_pages * 0.30

# We want lines that repeat on >=30% of pages at the same y.
# A line can be identified by its text and its y-coordinate. Let's round y to nearest integer.
line_counts = collections.defaultdict(set)

for i, page in enumerate(doc):
    blocks = page.get_text("dict").get("blocks", [])
    for b in blocks:
        if b.get("type") == 0:
            for l in b.get("lines", []):
                y = round(l["bbox"][3]) # y1 coordinate
                text = "".join([s["text"] for s in l.get("spans", [])]).strip()
                if text:
                    line_counts[(text, y)].add(i)

repeating_lines = {k: v for k, v in line_counts.items() if len(v) >= threshold}
print(f"Total pages: {num_pages}, Threshold: {threshold}")
print("Repeating lines:")
for (text, y), pages in repeating_lines.items():
    print(f"y={y}: '{text}' (on {len(pages)} pages)")
