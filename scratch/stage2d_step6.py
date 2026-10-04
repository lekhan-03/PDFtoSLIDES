import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from src.chem_convert import is_formula

def step6():
    print("--- TASK 6 ---")
    d = json.load(open('data/outputs/chemistry_2026_10_03_130427.json', encoding='utf-8'))
    for q in d:
        if q['id'] in [42, 43, 44]:
            print(f"ID {q['id']} raw text: {repr(q['question'])}")
            print(f"ID {q['id']} options: {q.get('options')}")
            if "3+" in q['question']:
                print(f"Position of '3+' in ID {q['id']} raw text: {q['question'].find('3+')}")
                
            # print previous option and is_formula
            prev_q = next((p for p in d if p['id'] == q['id'] - 1), None)
            if prev_q and prev_q.get('options'):
                last_opt = list(prev_q['options'].values())[-1]
                print(f"Previous ID {prev_q['id']} last option: {repr(last_opt)} | is_formula: {is_formula(last_opt.split()[-1] if last_opt else '')}")

if __name__ == "__main__":
    step6()
