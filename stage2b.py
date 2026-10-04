import json
import re

from src.block_parse import parse_block
from src.chem_convert import convert_chem, conc_to_latex, suspect_options
from src.convert.math import split_question, convert_math, check_math

def is_math_without_dollars(text: str) -> bool:
    if "^{" in text or "_{" in text:
        return True
    if re.search(r"\\[A-Za-z]+", text): # LaTeX command
        return True
    return False

def process_text(text: str):
    # Check if the whole option/run is MATH implicitly
    if not "$" in text and is_math_without_dollars(text):
        tag, runs = None, [("MATH", text)]
    else:
        tag, runs = split_question(text)
        
    out_runs = []
    problems = []
    for kind, content in runs:
        if kind == "MATH":
            if "[" in content:
                content = conc_to_latex(content)
            converted = convert_math(content)
            probs = check_math(converted)
            problems.extend(probs)
            out_runs.append({"type": "MATH", "text": converted})
        else: # TEXT
            # Wait, check if a TEXT run is actually MATH without $
            if is_math_without_dollars(content):
                if "[" in content:
                    content = conc_to_latex(content)
                converted = convert_math(content)
                probs = check_math(converted)
                problems.extend(probs)
                out_runs.append({"type": "MATH", "text": converted})
            else:
                converted = convert_chem(content)
                out_runs.append({"type": "TEXT", "text": converted})
    return tag, out_runs, problems

def diagnose_133_135(q_raw, q_id):
    print(f"\n--- Diagnosing ID {q_id} ---")
    print(f"Raw string: {repr(q_raw)}")
    print(f"Count of '$' in raw string: {q_raw.count('$')}")
    tag, runs = split_question(q_raw)
    print(f"split_question returns:")
    for r in runs:
        print(f"  {r}")
    print("----------------------------\n")

def process_file(json_path, ids_to_print, is_integrals=False):
    data = json.load(open(json_path, encoding='utf-8'))
    review_list = []
    processed = []
    
    highest_q = 0
    counts = {"MCQ": 0, "OPEN": 0, "MATCH": 0, "DIVIDER": 0}
    leaks_found = []
    
    for q in data:
        qid = q.get("id")
        
        # If options are present, use them. If not, use parse_block to try to find them.
        raw_question = q.get("question", "")
        options = q.get("options", {})
        
        if not options:
            parsed = parse_block(raw_question)
            options = parsed["options"]
            stem = parsed["stem"]
            chapter = parsed["chapter"]
        else:
            from src.block_parse import strip_noise
            stem, chapter = strip_noise(raw_question)
            
        if qid in [133, 135]:
            diagnose_133_135(stem, qid)
            
        # Check match the column
        is_match = bool(re.search(r"(Column I|List-I)", stem, re.IGNORECASE))
        
        # update highest question number
        m = re.search(r'^\s*(\d+)\.\s', stem)
        if m:
            highest_q = max(highest_q, int(m.group(1)))
            
        # process stem
        tag, stem_runs, stem_probs = process_text(stem)
        
        # process options
        opt_runs = {}
        opt_probs = []
        for k, v in options.items():
            _, oruns, oprobs = process_text(v)
            opt_runs[k] = oruns
            opt_probs.extend(oprobs)
            
        mid_sentence = [k for k, v in options.items() if re.search(r'\b(and|or|with|of|the)\s*$', v.strip(), re.IGNORECASE)]
        suspects = suspect_options(options)
        
        reasons = []
        if is_match: reasons.append("match-the-column unsupported")
        if stem_probs: reasons.append(f"math problems in stem: {stem_probs}")
        if opt_probs: reasons.append(f"math problems in options: {opt_probs}")
        if mid_sentence: reasons.append(f"options ending mid-sentence: {mid_sentence}")
        if suspects: reasons.append(f"suspect options: {suspects}")
        if "Boar" in stem: reasons.append("stem contains 'Boar'")
        if re.search(r'(^|\s)✉(\s|$)', stem): reasons.append("stem contains lone ✉")
        
        # Leaks
        runs_to_check = [stem_runs] + list(opt_runs.values())
        for runlist in runs_to_check:
            for r in runlist:
                if r["type"] == "TEXT":
                    text = r["text"]
                    if "$" in text or "^{" in text or "\\" in text:
                        leaks_found.append({"id": qid, "type": "TEXT", "text": text})
                        reasons.append("leaked $ or ^{ or \\ in TEXT run")
                        
        if reasons:
            review_list.append({
                "id": qid,
                "reasons": reasons,
            })
            
        out_q = {
            "id": qid,
            "chapter": chapter,
            "tag": tag,
            "stem_runs": stem_runs,
            "options_runs": opt_runs,
            "raw_stem": stem,
        }
        processed.append(out_q)
        
        if is_match:
            counts["MATCH"] += 1
        elif options:
            counts["MCQ"] += 1
        else:
            counts["OPEN"] += 1
            
    print(f"\n--- {json_path} ---")
    print(f"Total questions: {len(data)} | Highest Q# in text: {highest_q}")
    print(f"Counts: {counts}")
    
    print("\nRequested JSON Dumps:")
    for p in processed:
        if p["id"] in ids_to_print:
            print(f"\nID {p['id']} RAW:")
            print(repr(p["raw_stem"]))
            print("RUNS:")
            print(json.dumps({"stem_runs": p["stem_runs"], "options_runs": p["options_runs"]}, indent=2, ensure_ascii=True))
            
    return processed, review_list, leaks_found, counts

def main():
    integrals = "data/tests/testres/Integrals.json"
    integrals_ids = [6, 9, 129, 133, 135]
    
    chem = "data/outputs/chemistry_2026_10_03_130427.json"
    chem_ids = [48, 54, 55, 111, 196] # 196 is the extra item
    
    print("="*50)
    _, rev_int, leaks_int, counts_int = process_file(integrals, integrals_ids, is_integrals=True)
    _, rev_chem, leaks_chem, counts_chem = process_file(chem, chem_ids)
    print("="*50)
    
    print("\nLEAKS FOUND:")
    for leak in leaks_int + leaks_chem:
        print(f"  ID {leak['id']} | {leak['type']} | {repr(leak['text'])}")
        
    print("\nREVIEW LIST REASON COUNTS:")
    reason_counts = {}
    for r in rev_int + rev_chem:
        for reason in r["reasons"]:
            # extract prefix if needed
            prefix = reason.split(":")[0] if ":" in reason else reason
            reason_counts[prefix] = reason_counts.get(prefix, 0) + 1
            
    for k, v in reason_counts.items():
        print(f"  {k}: {v}")
        
    print("\nReview List Total Items:", len(rev_int) + len(rev_chem))

if __name__ == "__main__":
    main()
