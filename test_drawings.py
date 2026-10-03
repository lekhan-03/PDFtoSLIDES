import re
import pymupdf

NOISE_PATTERNS = [
    r"^Midterm Multiple Choice Questions$",
    r"^For: Boards$",
    r".*learn@simplifiedminds\.com$",
    r"^Play Store$",
    r"^7411-008-008$",
    r"^SimplifiedMinds Karnataka$",
    r"^www\.simplifiedminds\.com$",
    r"^simplified_minds$",
]
NOISE_RE = re.compile("|".join(f"(?:{p})" for p in NOISE_PATTERNS))

def is_noise(text):
    return bool(NOISE_RE.match(text))

def get_page_items(page):
    items = []
    
    # 1. Get text spans
    pdict = page.get_text("dict")
    for block in pdict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text and not is_noise(text):
                        items.append({
                            "type": "text",
                            "text": text,
                            "bbox": span["bbox"], # (x0, y0, x1, y1)
                            "size": span["size"],
                            "font": span["font"]
                        })
                        
    # 2. Get drawings (lines)
    for p in page.get_drawings():
        # A drawing path can have multiple items (lines, curves, rects)
        for item in p["items"]:
            # We are interested in horizontal lines
            if item[0] == "l": # line: ("l", p1, p2)
                p1, p2 = item[1], item[2]
                # If it's roughly horizontal
                if abs(p1.y - p2.y) < 2:
                    x0, x1 = min(p1.x, p2.x), max(p1.x, p2.x)
                    y = (p1.y + p2.y) / 2
                    # width > 5 to avoid dots
                    if x1 - x0 > 5:
                        items.append({
                            "type": "draw",
                            "bbox": (x0, y-1, x1, y+1)
                        })
            elif item[0] == "re": # rect: ("re", rect, ...)
                rect = item[1]
                if rect.height < 3 and rect.width > 5:
                    items.append({
                        "type": "draw",
                        "bbox": (rect.x0, rect.y0, rect.x1, rect.y1)
                    })
                    
    return items

def test_items(pdf_path):
    doc = pymupdf.open(pdf_path)
    items = get_page_items(doc[0])
    for item in items:
        if item["type"] == "draw":
            print(item)

if __name__ == "__main__":
    test_items("data/tests/chemistry.pdf")
