import json
import os
import time
from src.parser import split_questions
from src.extract_docx import extract_lines
from src.block_parse import parse_block
from src.unmarked import split_runs_auto, suspect_swallowed
from src.run_merge import merge_runs

def run_task():
    file_path = "data/testres/Integrals.json"
    mtime = os.path.getmtime(file_path)
    data = json.load(open(file_path, encoding='utf-8'))
    print(f"File: {file_path}, Items: {len(data)}, Modified: {time.ctime(mtime)}")
    
    print("\n--- TASK 4: suspect_swallowed ---")
    for q in data:
        opts = q.get("options", {})
        s = suspect_swallowed(opts)
        if s:
            print(f"Integrals ID {q['id']} - Flagged options: {s}")
            print(f"Reason: swallowed next stem (year tag)")
            for k in s:
                print(f"  Option {k}: {opts[k]}")
                
    chem_file = "data/outputs/chemistry_2026_10_03_130427.json"
    chem_data = json.load(open(chem_file, encoding='utf-8'))
    for q in chem_data:
        opts = q.get("options", {})
        s = suspect_swallowed(opts)
        if s:
            print(f"Chemistry ID {q['id']} - Flagged options: {s}")
            print(f"Reason: swallowed next stem (year tag)")
            for k in s:
                print(f"  Option {k}: {opts[k]}")

    print("\n--- TASK 5: Real runs ---")
    for q in data:
        opts = q.get("options", {})
        stem = q.get("question", "")
        
        # secx+C etc.
        if any("sec" in v for v in opts.values()):
            print(f"\nQuestion ID: {q['id']} (secx+C)")
            print(f"Stem: {repr(stem)}")
            print("Runs for Stem:")
            tag, r = split_runs_auto(stem)
            print(merge_runs(r))
            for k, v in opts.items():
                print(f"Option {k}: {repr(v)}")
                tag, r = split_runs_auto(v)
                print("Runs:", merge_runs(r))
                
        # Find the value of ∫_{-1}^{1} x^{99} dx =
        if "x^{99}dx" in stem.replace(" ", ""):
            print(f"\nQuestion ID: {q['id']} (x^99)")
            print(f"Stem: {repr(stem)}")
            print("Runs for Stem:")
            tag, r = split_runs_auto(stem)
            print(merge_runs(r))
            for k, v in opts.items():
                tag, r = split_runs_auto(v)
                print(f"Option {k} runs:", merge_runs(r))
                
        # The point of inflection for the following graph is
        if "inflection for the following graph" in stem:
            print(f"\nQuestion ID: {q['id']} (inflection)")
            print(f"Stem: {repr(stem)}")
            for k, v in opts.items():
                print(f"Option {k}: {repr(v)}")

    print("\n--- TASK 6: Images ---")
    for q in data:
        if "inflection" in q.get("question", ""):
            print(f"ID {q['id']} stem contains image: {'IMG' in q.get('question', '')}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    run_task()
