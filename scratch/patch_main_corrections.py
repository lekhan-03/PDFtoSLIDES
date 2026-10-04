import json
from pathlib import Path

def patch_main():
    main_path = Path("src/main.py")
    text = main_path.read_text(encoding="utf-8")
    
    # We want to call apply_corrections before saving
    # Let's insert the import and the call right before writing to JSON.
    insert_str = """
    # Apply corrections if they exist
    corr_path = Path(f"data/corrections/{in_path.stem}.json")
    if corr_path.exists():
        from src.corrections import apply_corrections
        corr_dict = json.loads(corr_path.read_text(encoding="utf-8"))
        parsed = apply_corrections(parsed, corr_dict)
"""
    
    # Find where to insert it
    target = 'parsed.sort(key=lambda q: q["id"] if q.get("id") is not None else float("inf"))'
    if target in text:
        text = text.replace(target, insert_str + "\n    " + target)
        main_path.write_text(text, encoding="utf-8")
        print("Patched main.py with corrections loader")
    else:
        print("Could not find target in main.py")

patch_main()
