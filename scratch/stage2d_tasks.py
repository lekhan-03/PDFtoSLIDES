import json
import re
import os
import sys

from src.run_merge import merge_runs
from src.chem_extra import attached_subscripts
from src.chem_convert import convert_chem
from src.convert.math import split_question, convert_math, check_math
from src.block_parse import parse_block

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def get_runs(text, is_chem):
    tag, runs = split_question(text)
    runs = merge_runs(runs)
    out, leaks = [], []
    for k, t in runs:
        if k == "MATH":
            out.append((k, convert_math(t)))
        else:
            if any(0x1D400 <= ord(c) <= 0x1D7FF for c in t):
                leaks.append(t)
            if is_chem:
                t = attached_subscripts(t)
                t = convert_chem(t)
            out.append((k, t))
    return out, leaks

def process_file_2d(json_path, is_chem=False):
    data = json.load(open(json_path, encoding='utf-8'))
    processed = []
    review_list = []
    highest_q = 0
    counts = {"MCQ": 0, "OPEN": 0, "MATCH": 0, "DIVIDER": 0}
    q_dict = {}
    
    for q in data:
        qid = q.get("id")
        raw_question = q.get("question", "")
        options = q.get("options", {})
        
        if not options:
            parsed = parse_block(raw_question)
            options = parsed["options"]
            stem = parsed["stem"]
            leftovers = parsed.get("header_leftovers", [])
        else:
            stem = raw_question
            leftovers = []
            
        m = re.search(r'^\s*(\d+)\.\s', stem)
        if m: highest_q = max(highest_q, int(m.group(1)))
        
        is_match = bool(re.search(r"(Column I|List-I)", stem, re.IGNORECASE))
        word_count = len(stem.strip().split())
        is_divider = (not m) and (not options) and (word_count <= 4)
        
        if leftovers and (qid - 1) in q_dict:
            prev_q = q_dict[qid - 1]
            for leftover in leftovers:
                if qid in [42, 43, 44]:
                    print(f"Header for ID {qid} leftover: {repr(leftover)}")
                    print(f"Previous ID {qid-1} raw text: {repr(prev_q['raw'])}")
                    print(f"Previous ID {qid-1} options: {prev_q['options']}")
                
                if re.match(r'^\d+[+-]$', leftover):
                    if prev_q["options"]:
                        last_opt = list(prev_q["options"].keys())[-1]
                        prev_q["options"][last_opt] += leftover
                        if qid in [43, 44]:
                            print(f"Attached leftover '{leftover}' to option {last_opt}: {prev_q['options'][last_opt]}")
                else:
                    review_list.append({"id": qid, "reasons": [f"leftover header text: {leftover}"]})
                    
        tag, stem_runs = split_question(stem)
        stem_runs = merge_runs(stem_runs)
        for k, t in stem_runs:
            if k == "MATH":
                probs = check_math(convert_math(t))
                if probs:
                    review_list.append({"id": qid, "raw_math": t, "probs": probs, "reasons": [f"math problems in stem: {probs}"]})
                    
        if is_match: counts["MATCH"] += 1
        elif is_divider: counts["DIVIDER"] += 1
        elif options: counts["MCQ"] += 1
        else: counts["OPEN"] += 1
        
        q_dict[qid] = {"id": qid, "raw": raw_question, "options": options}
        processed.append(q_dict[qid])
        
    return processed, counts, highest_q, review_list

def run():
    print("--- TASK 2 ---")
    chem_path = "data/outputs/chemistry_2026_10_03_130427.json"
    print(f"File: {chem_path} | Items: {len(json.load(open(chem_path, encoding='utf-8')))} | MTime: {os.path.getmtime(chem_path)}")
    chem_data = json.load(open(chem_path, encoding='utf-8'))
    for q in chem_data:
        if q["id"] in [57, 66]:
            print(f"Raw JSON entry ID {q['id']}: {json.dumps(q, ensure_ascii=False)}")
            
    print("\nIDs whose type changed (OPEN to MCQ):")
    for q in chem_data:
        if not q.get("options"):
            parsed = parse_block(q.get("question", ""))
            if len(parsed["options"]) == 4:
                print(f"ID {q['id']}: {parsed['options']}")
                
    print("\n--- TASK 3 ---")
    int_path = "data/testres/Integrals.json"
    print(f"File: {int_path} | Items: {len(json.load(open(int_path, encoding='utf-8')))} | MTime: {os.path.getmtime(int_path)}")
    
    # Actually, we need to run process_file_2d on Integrals as well for math problems
    _, _, _, int_rev = process_file_2d(int_path, False)
    
    print("\nReview list reasons and counts:")
    rc = {}
    for r in int_rev:
        for rs in r["reasons"]:
            prefix = rs.split(":")[0]
            rc[prefix] = rc.get(prefix, 0) + 1
    for k, v in rc.items():
        print(f"  {k}: {v}")
        
    print("\nMath problems in stem entries:")
    for r in int_rev:
        if any("math problems in stem" in rs for rs in r["reasons"]):
            print(f"ID: {r['id']} | Raw MATH: {repr(r['raw_math'])} | Problem: {r['probs']}")

    print("\n--- TASK 6 ---")
    _, _, _, chem_rev = process_file_2d(chem_path, True)
    
if __name__ == "__main__":
    run()
