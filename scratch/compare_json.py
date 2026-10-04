import json
import time
import os

int_old = "data/testres/Integrals.json"
int_new = "data/testres/Integrals_v2.json"

print("Old Integrals:", time.ctime(os.path.getmtime(int_old)), "Items:", len(json.load(open(int_old, encoding='utf-8'))))
print("New Integrals:", time.ctime(os.path.getmtime(int_new)), "Items:", len(json.load(open(int_new, encoding='utf-8'))))

o_data = {q.get('id'): q for q in json.load(open(int_old, encoding='utf-8')) if q.get('id') is not None}
n_data = {q.get('id'): q for q in json.load(open(int_new, encoding='utf-8')) if q.get('id') is not None}

ids = [4, 5, 8, 9, 22, 24]
for idx in ids:
    print(f"\n--- Integrals ID {idx} ---")
    print("OLD:")
    print(json.dumps(o_data.get(idx), indent=2, ensure_ascii=False))
    print("NEW:")
    print(json.dumps(n_data.get(idx), indent=2, ensure_ascii=False))

chem_file = "data/outputs/chemistry_2026_10_03_130427.json"
chem_data = {q.get('id'): q for q in json.load(open(chem_file, encoding='utf-8')) if q.get('id') is not None}
print("\n--- Chemistry ID 8 ---")
print(json.dumps(chem_data.get(8), indent=2, ensure_ascii=False))
print("\n--- Chemistry ID 9 ---")
print(json.dumps(chem_data.get(9), indent=2, ensure_ascii=False))

print("\n--- Why same stems appear under different IDs (Old 8, 9, 65, 66) ---")
for idx in [8, 9, 65, 66]:
    print(f"OLD {idx}:")
    print(json.dumps(o_data.get(idx), indent=2, ensure_ascii=False))
