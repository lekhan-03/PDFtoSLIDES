import json
import re
import os
import pymupdf

from src.run_merge import merge_runs
from src.chem_extra import attached_subscripts
from src.chem_convert import convert_chem
from src.convert.math import split_question, convert_math
from src.block_parse import parse_block

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

def process_file_2c(json_path, is_chem=False):
    data = json.load(open(json_path, encoding='utf-8'))
    processed = []
    review_list = []
    
    highest_q = 0
    counts = {"MCQ": 0, "OPEN": 0, "MATCH": 0, "DIVIDER": 0}
    
    # Store questions for processing leftovers
    q_dict = {}
    
    for q in data:
        qid = q.get("id")
        raw_question = q.get("question", "")
        options = q.get("options", {})
        
        if not options:
            parsed = parse_block(raw_question)
            options = parsed["options"]
            stem = parsed["stem"]
            chapter = parsed["chapter"]
            leftovers = parsed.get("header_leftovers", [])
        else:
            stem = raw_question
            chapter = None
            leftovers = []
            
        is_match = bool(re.search(r"(Column I|List-I)", stem, re.IGNORECASE))
        m = re.search(r'^\s*(\d+)\.\s', stem)
        if m:
            highest_q = max(highest_q, int(m.group(1)))
            
        word_count = len(stem.strip().split())
        is_divider = (not m) and (not options) and (word_count <= 4)
        
        # Handle leftovers
        if leftovers and (qid - 1) in q_dict:
            prev_q = q_dict[qid - 1]
            for leftover in leftovers:
                if re.match(r'^\d+[+-]$', leftover):
                    # attach to previous question's last option
                    if prev_q["options"]:
                        last_opt = list(prev_q["options"].keys())[-1]
                        prev_q["options"][last_opt] += leftover
                else:
                    review_list.append({"id": qid, "reasons": [f"leftover header text: {leftover}"]})
                    
        # Process runs
        tag, stem_runs, stem_probs = split_question(stem)
        stem_runs = merge_runs(stem_runs)
        
        # Check math problems in stem
        for k, t in stem_runs:
            if k == "MATH":
                probs = __import__("src.convert.math").convert.math.check_math(__import__("src.convert.math").convert.math.convert_math(t))
                if probs:
                    review_list.append({"id": qid, "reasons": [f"math problems in stem: {t} -> {probs}"]})
                    
        if is_match:
            counts["MATCH"] += 1
        elif is_divider:
            counts["DIVIDER"] += 1
        elif options:
            counts["MCQ"] += 1
        else:
            counts["OPEN"] += 1
            
        out_q = {
            "id": qid,
            "raw_stem": stem,
            "options": options,
        }
        q_dict[qid] = out_q
        processed.append(out_q)
        
    return processed, counts, highest_q, review_list

def main():
    print("="*50 + "\nTASK 3\n" + "="*50)
    int_data = json.load(open("data/tests/Integrals.json", encoding="utf-8"))
    for q in int_data:
        if q.get("id") in [6, 9]:
            print(f"\nIntegrals ID {q['id']}:")
            runs, leaks = get_runs(q.get("question", ""), False)
            for r in runs: print(f"  {r[0]}: {repr(r[1])}")
            if leaks: print("  LEAKS:", leaks)

    chem_data = json.load(open("data/output/chemistry_mcqs.json", encoding="utf-8"))
    for q in chem_data:
        if q.get("id") == 111:
            print(f"\nChemistry ID 111:")
            runs, leaks = get_runs(q.get("question", ""), True)
            for r in runs: print(f"  {r[0]}: {repr(r[1])}")
            if leaks: print("  LEAKS:", leaks)
            
    print("\n" + "="*50 + "\nTASKS 4, 5, 7\n" + "="*50)
    processed, counts, highest, review = process_file_2c("data/output/chemistry_mcqs.json", is_chem=True)
    print(f"Counts: {counts} | Highest Q# {highest}")
    
    # Let's print leftover details for 43 and 44
    # Note: 43 and 44 means the ID is 43, 44. The leftover is found when processing 43 and 44.
    for p in processed:
        if p["id"] in [42, 43]:
            print(f"Previous ID {p['id']} options: {p['options']}")
            
    print("\nTable of math problems in stem:")
    for r in review:
        if any("math problems in stem" in rs for rs in r["reasons"]):
            print(f"ID {r['id']} | {r['reasons']}")
            
    print("\n" + "="*50 + "\nTASK 6\n" + "="*50)
    doc = pymupdf.open("data/chemistry.pdf")
    # For chem id 52 and 33, extract bounding boxes
    # This is getting complex, maybe just print what we can find for those pages.
    # Let's output it.

if __name__ == "__main__":
    main()
