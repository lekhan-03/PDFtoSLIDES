import json
import re
from src.block_parse import parse_block
from src.chem_convert import convert_chem, conc_to_latex, suspect_options
from src.convert.math import split_question, convert_math, check_math

def process_text(text):
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
            converted = convert_chem(content)
            out_runs.append({"type": "TEXT", "text": converted})
    return tag, out_runs, problems

def count_leaks(runs_list):
    leaks = 0
    for runs in runs_list:
        for r in runs:
            if r["type"] == "TEXT":
                # TEXT shouldn't have $, ^{, or LaTeX backslashes except maybe if it was plain text.
                # The rule: leaked "$", "^{", or "\" in slide text.
                text = r["text"]
                if "$" in text or "^{" in text or "\\" in text:
                    leaks += text.count("$") + text.count("^{") + text.count("\\")
            elif r["type"] == "MATH":
                # MATH runs are wrapped in $ at render time, so they shouldn't contain literal $ unless escaped?
                # Actually, check_math handles math validation. We just check if the text itself has leaked $
                if "$" in r["text"]:
                    leaks += r["text"].count("$")
    return leaks

def process_file(json_path, ids_to_print):
    data = json.load(open(json_path, encoding='utf-8'))
    review_list = []
    processed = []
    
    highest_q = 0
    counts = {"MCQ": 0, "OPEN": 0, "DIVIDER": 0}
    leaked = 0
    
    prev_q = None
    
    for q in data:
        # Reconstruct raw string to handle options accidentally parsed or not parsed
        raw = q.get("question", "")
        for k, v in q.get("options", {}).items():
            raw += f"\n({k}) {v}"
            
        parsed = parse_block(raw)
        
        # update highest question number
        m = re.search(r'^\s*(\d+)\.\s', parsed["stem"])
        if m:
            highest_q = max(highest_q, int(m.group(1)))
            
        # spill handling
        if parsed["spill"]:
            if prev_q and not any(k in prev_q["options_runs"] for k in parsed["spill"]):
                # Attach to previous question (we actually just need to process it and add to runs)
                for k, v in parsed["spill"].items():
                    _, oruns, oprobs = process_text(v)
                    prev_q["options_runs"][k] = oruns
            else:
                review_list.append({"id": q.get("id"), "reason": "unresolved spill", "spill": parsed["spill"]})
                
        # process stem
        tag, stem_runs, stem_probs = process_text(parsed["stem"])
        
        # process options
        opt_runs = {}
        opt_probs = []
        for k, v in parsed["options"].items():
            _, oruns, oprobs = process_text(v)
            opt_runs[k] = oruns
            opt_probs.extend(oprobs)
            
        # validation for review_list
        mid_sentence = [k for k, v in parsed["options"].items() if re.search(r'\b(and|or|with|of|the)\s*$', v.strip(), re.IGNORECASE)]
        suspects = suspect_options(parsed["options"])
        
        reasons = []
        if stem_probs: reasons.append(f"math problems in stem: {stem_probs}")
        if opt_probs: reasons.append(f"math problems in options: {opt_probs}")
        if mid_sentence: reasons.append(f"options ending mid-sentence: {mid_sentence}")
        if suspects: reasons.append(f"suspect options: {suspects}")
        if "Boar" in parsed["stem"]: reasons.append("stem contains 'Boar'")
        if re.search(r'(^|\s)✉(\s|$)', parsed["stem"]): reasons.append("stem contains lone ✉")
        if "$" in parsed["stem"]: reasons.append("stem contains leaked $")
        
        if reasons:
            review_list.append({
                "id": q.get("id"),
                "reasons": reasons,
            })
            
        # count leaks
        runs_to_check = [stem_runs] + list(opt_runs.values())
        leaked += count_leaks(runs_to_check)
            
        out_q = {
            "id": q.get("id"),
            "chapter": parsed["chapter"],
            "tag": tag,
            "stem_runs": stem_runs,
            "options_runs": opt_runs
        }
        processed.append(out_q)
        prev_q = out_q
        
        if parsed["options"]:
            counts["MCQ"] += 1
        else:
            counts["OPEN"] += 1
            
    print(f"\n--- {json_path} ---")
    print(f"Total questions processed: {len(data)} | Highest Q# in text: {highest_q}")
    print(f"Counts: {counts}")
    print(f"Flagged for review: {len(review_list)}")
    for r in review_list:
        print(f"  ID {r['id']}: {r}")
    print(f"Leaked symbols ($, ^{{, \\): {leaked}")
    
    print("\nSample processed JSON:")
    sample = [p for p in processed if str(p["id"]) in ids_to_print]
    try:
        print(json.dumps(sample, indent=2, ensure_ascii=False))
    except UnicodeEncodeError:
        print(json.dumps(sample, indent=2, ensure_ascii=True))
    
    return review_list

def main():
    integrals = "data/tests/testres/Integrals.json"
    integrals_ids = [str(i) for i in range(128, 137)]
    
    chem = "data/outputs/chemistry_2026_10_03_130427.json"
    chem_ids = [str(i) for i in range(47, 68)]
    
    rev_int = process_file(integrals, integrals_ids)
    rev_chem = process_file(chem, chem_ids)
    
    with open("review_list.json", "w", encoding="utf-8") as f:
        json.dump(rev_int + rev_chem, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(rev_int) + len(rev_chem)} items to review_list.json")

if __name__ == "__main__":
    main()
