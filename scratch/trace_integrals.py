import json
from src.block_parse import split_runs_auto
from src.run_merge import merge_runs

with open('data/testres/Integrals_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

q_dict = {q['id']: q for q in data}

ids_to_check = [2, 91, 17, 65, 106]
for q_id in ids_to_check:
    if q_id not in q_dict:
        print(f"ID {q_id} not found!")
        continue
    
    raw_question = q_dict[q_id].get("question", "")
    print(f"--- ID {q_id} ---")
    print(f"Raw question repr: {repr(raw_question)}")
    
    # Wait, the docx paragraph text might mean checking the docx directly? I'll print just raw_question
    print(f"Docx paragraph text: {raw_question}")
    
    try:
        runs = split_runs_auto(raw_question)
        print("Runs BEFORE merge_runs:")
        for r in runs: print(f"  {r}")
        
        merged = merge_runs(runs)
        print("Runs AFTER merge_runs:")
        for r in merged: print(f"  {r}")
    except Exception as e:
        print(f"Error processing: {e}")
    print()
