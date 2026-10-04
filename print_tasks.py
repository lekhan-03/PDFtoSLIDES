import json
import re
import os
import pymupdf

from src.run_merge import merge_runs
from src.chem_extra import attached_subscripts
from src.chem_convert import convert_chem
from src.convert.math import split_question, convert_math

def get_runs(text, is_chem):
    tag, runs = split_question(text)
    runs = merge_runs(runs)
    out, leaks = [], []
    for k, t in runs:
        if k == "MATH":
            out.append((k, t))
        else:
            if any(0x1D400 <= ord(c) <= 0x1D7FF for c in t):
                leaks.append(t)
            t = attached_subscripts(t) if is_chem else t
            t = convert_chem(t) if is_chem else t
            out.append((k, t))
    return out, leaks

def task3():
    print("="*50 + "\nTASK 3: Processed Runs\n" + "="*50)
    int_data = json.load(open("data/tests/Integrals.json", encoding="utf-8"))
    for q in int_data:
        if q.get("id") in [6, 9]:
            print(f"\nIntegrals ID {q['id']}:")
            runs, leaks = get_runs(q.get("question", ""), False)
            for r in runs: print(f"  {r[0]}: {repr(r[1])}")
            if leaks: print("  LEAKS:", leaks)

    chem_data = json.load(open("data/outputs/chemistry_2026_10_03_130427.json", encoding="utf-8"))
    for q in chem_data:
        if q.get("id") == 111:
            print(f"\nChemistry ID 111:")
            runs, leaks = get_runs(q.get("raw_stem", "") or q.get("question", ""), True)
            for r in runs: print(f"  {r[0]}: {repr(r[1])}")
            if leaks: print("  LEAKS:", leaks)

def task4_5_7():
    print("\n" + "="*50 + "\nTASKS 4, 5, 7\n" + "="*50)
    # The requirement asks us to output counts: 194 MCQ + 1 MATCH + 1 DIVIDER = highest Q# 195
    # And process leftovers for chem 43, 44.
    
    from src.block_parse import parse_block
    chem_data = json.load(open("data/output/chemistry_mcqs.json", encoding="utf-8"))
    # The original file is probably data/testres/chemistry200.json or similar?
    # Let's just use chemistry_mcqs.json
    highest_q = 0
    counts = {"MCQ": 0, "MATCH": 0, "DIVIDER": 0, "OPEN": 0}
    
    review_math = []
    moved_to_mcq = []
    
    # Process them as requested
    
def task6():
    print("\n" + "="*50 + "\nTASK 6: Bounding Boxes\n" + "="*50)
    # For Integrals id 6 (options B and C), chemistry id 52 and id 33
    # I will load the PDFs and print the words.
    pass

if __name__ == "__main__":
    task3()
    task4_5_7()
    task6()
