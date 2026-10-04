import json
import re
import pymupdf
import sys
import os

from src.run_merge import merge_runs
from src.chem_extra import attached_subscripts
from src.chem_convert import convert_chem
from src.convert.math import split_question, convert_math
from src.convert.math import check_math
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
            if is_chem:
                t = attached_subscripts(t)
                t = convert_chem(t)
            out.append((k, t))
    return out, leaks

def extract_pdf_option_bboxes(pdf_path, search_str):
    doc = pymupdf.open(pdf_path)
    res = []
    for p_num, page in enumerate(doc):
        # We just want to get raw text lines and bboxes around that area
        text_page = page.get_text("dict")
        for b in text_page.get("blocks", []):
            if b.get("type") != 0: continue
            for l in b.get("lines", []):
                line_str = " ".join([s["text"] for s in l.get("spans", [])])
                if search_str in line_str:
                    res.append(line_str)
    return res

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
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
    
    highest_q = 0
    counts = {"MCQ": 0, "OPEN": 0, "MATCH": 0, "DIVIDER": 0}
    q_dict = {}
    review_list = []
    
    for q in chem_data:
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
                if qid in [43, 44]:
                    print(f"\nLeftover for ID {qid}: {repr(leftover)}")
                    print(f"Previous ID {qid-1} raw text: {repr(prev_q['raw'])}")
                    print(f"Previous ID {qid-1} options: {prev_q['options']}")
                if re.match(r'^\d+[+-]$', leftover):
                    if prev_q["options"]:
                        last_opt = list(prev_q["options"].keys())[-1]
                        prev_q["options"][last_opt] += leftover
                        if qid in [43, 44]:
                            print(f"Attached to option {last_opt}: {prev_q['options'][last_opt]}")
                else:
                    review_list.append({"id": qid, "reasons": [f"leftover header text: {leftover}"]})
                    
        tag, stem_runs = split_question(stem)
        stem_runs = merge_runs(stem_runs)
        for k, t in stem_runs:
            if k == "MATH":
                probs = check_math(convert_math(t))
                if probs:
                    review_list.append({"id": qid, "reasons": [f"math problems in stem|{t}|{probs}"]})
                    
        if is_match: counts["MATCH"] += 1
        elif is_divider: counts["DIVIDER"] += 1
        elif options: counts["MCQ"] += 1
        else: counts["OPEN"] += 1
        
        q_dict[qid] = {"id": qid, "raw": raw_question, "options": options}
        
    print(f"\nCounts: {counts} | Highest Q# {highest_q}")
    
    print("\nTable of math problems in stem:")
    for r in review_list:
        for rs in r["reasons"]:
            if "math problems in stem" in rs:
                parts = rs.split("|")
                print(f"ID {r['id']} | RUN: {parts[1]} | PROB: {parts[2]}")
                
    # Also list the 5 chemistry questions that moved from OPEN to MCQ with their 4 options each.
    # To do this, we compare originally no options with now having 4 options.
    print("\nMoved from OPEN to MCQ:")
    for q in chem_data:
        if not q.get("options"):
            parsed = parse_block(q.get("question", ""))
            if len(parsed["options"]) == 4:
                print(f"ID {q['id']}: {parsed['options']}")
                
    print("\n" + "="*50 + "\nTASK 6: Wrapped Option Lines\n" + "="*50)
    print("Please inspect manually using PyMuPDF script.")

if __name__ == "__main__":
    main()
