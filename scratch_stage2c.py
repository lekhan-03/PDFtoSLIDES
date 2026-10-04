import json
import re
import os
import pymupdf

from src.run_merge import merge_runs
from src.chem_extra import attached_subscripts
from src.chem_convert import convert_chem
from src.convert.math import split_question, convert_math

print("="*50)
print("TASK 3: Print processed runs for Integrals ids 6 and 9 and chemistry id 111")
print("="*50)

def do_process(text, is_chem):
    tag, runs = split_question(text)
    runs = merge_runs(runs)
    out = []
    for k, t in runs:
        if k == "MATH":
            out.append((k, t))
        else:
            t = attached_subscripts(t) if is_chem else t
            t = convert_chem(t) if is_chem else t
            out.append((k, t))
    return out

int_data = json.load(open("data/tests/Integrals.json", encoding="utf-8"))
for q in int_data:
    if q.get("id") in [6, 9]:
        print(f"\nIntegrals ID {q['id']}:")
        runs = do_process(q.get("question", ""), False)
        for r in runs:
            print(f"  {r[0]}: {repr(r[1])}")

chem_data = json.load(open("data/outputs/chemistry_2026_10_03_130427.json", encoding="utf-8"))
for q in chem_data:
    if q.get("id") == 111:
        print(f"\nChemistry ID 111:")
        runs = do_process(q.get("raw_stem", "") or q.get("question", ""), True)
        for r in runs:
            print(f"  {r[0]}: {repr(r[1])}")

print("\n" + "="*50)
print("TASK 4 & 5: Chapter-only blocks -> DIVIDER, Question IDs from stem number, Header removal")
print("="*50)

# To properly do this, we should read lines from chemistry.pdf using extract_lines or similar?
# Wait, src.parser.parse_all(lines) is what processes the list of text lines.
# But chemistry.pdf extraction might use extract_pdf.py which does geometry based.
# Let's see what the latest extractor is. 
# The prompt says: "Question ids come from the stem number ("^\d+\.") and must be unique; assert no duplicates."
