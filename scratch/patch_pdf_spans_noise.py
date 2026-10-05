import re

def patch():
    with open("src/pdf_spans.py", "r", encoding="utf-8") as f:
        text = f.read()

    # Change signature
    old_sig = 'def page_items(page_dict, page_no, gap_factor=2.0):'
    new_sig = 'def page_items(page_dict, page_no, gap_factor=2.0, repeating_lines=None):\n    repeating_lines = repeating_lines or set()'
    text = text.replace(old_sig, new_sig)

    # Insert noise filtering
    old_spans = '            spans = sorted((s for s in line.get("spans", []) if s["text"] != ""), key=lambda s: s["bbox"][0])\n            if not spans:\n                continue'
    
    new_spans = """            spans = sorted((s for s in line.get("spans", []) if s["text"] != ""), key=lambda s: s["bbox"][0])
            if not spans:
                continue
            full_text = "".join([s.get("text", "") for s in line.get("spans", [])]).strip()
            if full_text in repeating_lines:
                continue"""
    
    text = text.replace(old_spans, new_spans)

    with open("src/pdf_spans.py", "w", encoding="utf-8") as f:
        f.write(text)

patch()
