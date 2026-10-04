def page_items(pdict: dict, page_num: int, repeating_lines: set = None) -> list[dict]:
    if repeating_lines is None:
        repeating_lines = set()
        
    items = []
    for block in pdict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                # Filter out noise (repeating lines)
                full_text = "".join([s.get("text", "") for s in line.get("spans", [])]).strip()
                if full_text in repeating_lines:
                    continue
                
                # Use the line's y0 to prevent superscripts from floating up during sorting
                line_y0 = line["bbox"][1]
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        x0, y0, x1, y1 = span["bbox"]
                        items.append({
                            "type": "text",
                            "text": text,
                            "bbox": (x0, y0, x1, y1),
                            "line_y0": line_y0,
                            "page": page_num,
                            "size": span.get("size", 0)
                        })
    return items
