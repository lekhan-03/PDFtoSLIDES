import json
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
            for opt in q.get('options', {}).values():
                if "3+" in opt:
                    print(f"Position of '3+' in ID {q['id']} option {opt}: {opt.find('3+')}")

if __name__ == "__main__":
    step6()
