import json
import re
from src.parser import split_questions, parse_block
from src.extract_docx import extract_lines
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    lines = extract_lines("data/tests/Integrals_PU_board_Questions.docx")
    blocks = split_questions(lines)
    
    # Task 4 is about suspect_swallowed(). Since we don't have the full stage2 loop here, I will just run over the blocks
    from src.unmarked import suspect_swallowed
    print("--- TASK 4: suspect_swallowed ---")
    swallowed = []
    for b in blocks:
        p = parse_block(b)
        s = suspect_swallowed(p["options"])
        if s:
            swallowed.append((p.get("stem", "")[:30], s))
            print(f"Flagged options: {s} in stem '{p.get('stem', '')[:30]}...'")

    # Task 5
    from src.unmarked import split_runs_auto
    from src.run_merge import merge_runs
    print("\n--- TASK 5: Real runs ---")
    for b in blocks:
        p = parse_block(b)
        opts = p.get("options", {})
        
        # Integrals question whose options are secx+C etc.
        if any("secx+C" in v.replace(" ", "") for v in opts.values()):
            print("Question: secx+C")
            print(f"Stem: {repr(p.get('stem', ''))}")
            print("Runs for Stem:")
            tag, r = split_runs_auto(p.get('stem', ''))
            print(merge_runs(r))
            for k, v in opts.items():
                print(f"Option {k}: {repr(v)}")
                tag, r = split_runs_auto(v)
                print(merge_runs(r))
                
        # Find the value of ∫_{-1}^{1} x^{99} dx =
        if "x^{99} dx =" in p.get('stem', ''):
            print("Question: x^{99}")
            print(f"Stem: {repr(p.get('stem', ''))}")
            print("Runs for Stem:")
            tag, r = split_runs_auto(p.get('stem', ''))
            print(merge_runs(r))
            for k, v in opts.items():
                tag, r = split_runs_auto(v)
                print(f"Option {k} runs:", merge_runs(r))
                
        # The point of inflection for the following graph is
        if "inflection for the following graph" in p.get('stem', ''):
            print("Question: inflection")
            print(f"Stem: {repr(p.get('stem', ''))}")
            for k, v in opts.items():
                print(f"Option {k}: {repr(v)}")

    # Task 6
    print("\n--- TASK 6: Images ---")
    image_qs = []
    for i, b in enumerate(blocks):
        text = "\n".join(b["lines"])
        if "[IMG" in text:
            image_qs.append((i, text))
            print(f"Block {i} has image: {repr(text[:50])}...")
            
if __name__ == "__main__":
    main()
